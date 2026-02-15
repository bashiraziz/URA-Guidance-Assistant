from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import uuid
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import psycopg
import requests
import yaml
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCES_FILE = PROJECT_ROOT / "docs" / "sources.yaml"
DEFAULT_INGEST_DIR = PROJECT_ROOT / ".tmp" / "ingest"
MIGRATIONS_DIR = PROJECT_ROOT / "apps" / "api" / "migrations"
REQUIRED_CATEGORIES = ["VAT", "PAYE", "WHT", "EFRIS", "registration", "penalties"]


@dataclass
class SourceRecord:
    id: str
    title: str
    publisher: str
    category: str
    doc_type: str
    source_type: str
    url: str | None
    acquisition: str
    local_path: str | None
    effective_from: str | None
    effective_to: str | None
    notes: str | None
    language_code: str

    def source_uuid(self) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"source|{self.id}"))

    def canonical_doc_path(self) -> str:
        if self.url:
            return self.url
        if self.local_path:
            return self.local_path
        return f"source:{self.id}"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_text(payload: str) -> str:
    return sha256_bytes(payload.encode("utf-8"))


def ensure_ingest_dirs(ingest_dir: Path) -> None:
    (ingest_dir / "raw").mkdir(parents=True, exist_ok=True)
    (ingest_dir / "normalized").mkdir(parents=True, exist_ok=True)
    (ingest_dir / "reports").mkdir(parents=True, exist_ok=True)
    (ingest_dir / "state").mkdir(parents=True, exist_ok=True)


def load_sources(sources_file: Path) -> list[SourceRecord]:
    if not sources_file.exists():
        raise FileNotFoundError(f"Missing sources registry: {sources_file}")
    raw = yaml.safe_load(sources_file.read_text(encoding="utf-8")) or {}
    items = raw.get("sources", [])
    if not isinstance(items, list):
        raise ValueError("sources file must contain top-level `sources` list")

    sources: list[SourceRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        source = SourceRecord(
            id=str(item.get("id", "")).strip(),
            title=str(item.get("title", "")).strip(),
            publisher=str(item.get("publisher", "")).strip(),
            category=str(item.get("category", "")).strip(),
            doc_type=str(item.get("doc_type", "")).strip(),
            source_type=str(item.get("source_type", "")).strip().lower(),
            url=(str(item.get("url")).strip() if item.get("url") else None),
            acquisition=str(item.get("acquisition", "")).strip(),
            local_path=(str(item.get("local_path")).strip() if item.get("local_path") else None),
            effective_from=(str(item.get("effective_from")).strip() if item.get("effective_from") else None),
            effective_to=(str(item.get("effective_to")).strip() if item.get("effective_to") else None),
            notes=(str(item.get("notes")).strip() if item.get("notes") else None),
            language_code=str(item.get("language_code", "en-UG")).strip() or "en-UG",
        )
        if not source.id:
            raise ValueError("Each source must include id")
        if source.source_type not in {"html", "pdf"}:
            raise ValueError(f"Invalid source_type for {source.id}: {source.source_type}")
        if source.acquisition not in {"fetch", "manual_download"}:
            raise ValueError(f"Invalid acquisition for {source.id}: {source.acquisition}")
        sources.append(source)
    return sources


def fetch_output_filename(source: SourceRecord) -> str:
    if source.source_type == "html":
        return "source.html"
    if not source.url:
        return "downloaded.pdf"
    name = Path(urlparse(source.url).path).name
    if name and name.lower().endswith(".pdf"):
        return name
    return "downloaded.pdf"


def source_raw_dir(source: SourceRecord, ingest_dir: Path) -> Path:
    return ingest_dir / "raw" / source.id


def find_raw_input(source: SourceRecord, ingest_dir: Path) -> Path | None:
    if source.acquisition == "manual_download":
        if not source.local_path:
            return None
        path = PROJECT_ROOT / source.local_path
        return path if path.exists() else None

    raw_dir = source_raw_dir(source, ingest_dir)
    if not raw_dir.exists():
        return None
    preferred = raw_dir / fetch_output_filename(source)
    if preferred.exists():
        return preferred
    pattern = "*.html" if source.source_type == "html" else "*.pdf"
    matches = sorted(raw_dir.glob(pattern))
    return matches[0] if matches else None


def fetch_sources(sources: list[SourceRecord], ingest_dir: Path, only_missing: bool = False) -> list[dict]:
    ensure_ingest_dirs(ingest_dir)
    rows: list[dict] = []
    for source in sources:
        if source.acquisition != "fetch":
            rows.append({"source_id": source.id, "stage": "fetch", "status": "PENDING", "message": f"manual_download expects {source.local_path}"})
            continue

        raw_dir = source_raw_dir(source, ingest_dir)
        raw_dir.mkdir(parents=True, exist_ok=True)
        output = raw_dir / fetch_output_filename(source)
        hash_file = raw_dir / "_hash.txt"

        if only_missing and output.exists():
            rows.append({"source_id": source.id, "stage": "fetch", "status": "SKIPPED", "raw_path": str(output), "message": "raw exists"})
            continue

        if output.exists() and hash_file.exists():
            current = sha256_bytes(output.read_bytes())
            stored = hash_file.read_text(encoding="utf-8").strip()
            if current == stored:
                rows.append({"source_id": source.id, "stage": "fetch", "status": "SKIPPED", "raw_path": str(output), "content_hash": current, "message": "hash match"})
                continue

        if not source.url:
            rows.append({"source_id": source.id, "stage": "fetch", "status": "FAILED", "message": "missing URL"})
            continue

        try:
            response = requests.get(source.url, timeout=90)
            response.raise_for_status()
            output.write_bytes(response.content)
            digest = sha256_bytes(response.content)
            hash_file.write_text(digest, encoding="utf-8")
            rows.append({"source_id": source.id, "stage": "fetch", "status": "FETCHED", "raw_path": str(output), "content_hash": digest})
        except Exception as exc:
            rows.append({"source_id": source.id, "stage": "fetch", "status": "FAILED", "message": str(exc)})
    return rows


def parse_html(content: str) -> str:
    soup = BeautifulSoup(content, "html.parser")

    # Prefer Akoma Ntoso structured legal content (ULII uses this)
    akn = soup.find(class_="akn-akomaNtoso") or soup.find(class_="akn-act") or soup.find(class_="akn-body")
    if akn:
        return _parse_akn(akn)

    container = soup.find("article") or soup.find(id="main-content") or soup.body
    if container is None:
        return ""
    lines: list[str] = []
    for node in container.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"], recursive=True):
        text = node.get_text(" ", strip=True)
        if not text:
            continue
        if node.name and node.name.startswith("h"):
            level = max(1, min(6, int(node.name[1])))
            lines += [f"{'#' * level} {text}", ""]
        elif node.name == "li":
            lines.append(f"- {text}")
        else:
            lines += [text, ""]
    return "\n".join(lines).strip()


def _parse_akn(container) -> str:
    """Parse Akoma Ntoso structured legal HTML into markdown."""
    lines: list[str] = []
    emitted_ids: set[int] = set()

    # Walk the AKN tree: sections have headings (h2/h3/h4), paragraphs have akn-num + akn-content
    for node in container.descendants:
        if not hasattr(node, "name") or node.name is None:
            continue
        if id(node) in emitted_ids:
            continue

        classes = node.get("class", [])

        # Headings
        if node.name in ("h1", "h2", "h3", "h4", "h5", "h6"):
            text = node.get_text(" ", strip=True)
            if text:
                level = max(1, min(6, int(node.name[1])))
                lines += ["", f"{'#' * level} {text}", ""]

        # Numbered paragraphs: (a), (b), etc. — emit as single line with number prefix
        elif "akn-paragraph" in classes or "akn-subsection" in classes:
            num_el = node.find(class_="akn-num", recursive=False)
            content_el = node.find(class_="akn-content", recursive=False) or node.find(class_="akn-intro", recursive=False)
            if num_el and content_el:
                num = num_el.get_text(strip=True)
                text = content_el.get_text(" ", strip=True)
                if text:
                    lines.append(f"{num} {text}")
                    lines.append("")
            # Mark all descendants as emitted to avoid duplicate output
            for child in node.descendants:
                emitted_ids.add(id(child))

        # Intro text (section-level intro before numbered paragraphs)
        elif "akn-intro" in classes:
            text = node.get_text(" ", strip=True)
            if text:
                lines.append(text)
                lines.append("")
            for child in node.descendants:
                emitted_ids.add(id(child))

        # Akoma Ntoso standalone paragraph text (not inside numbered items)
        elif "akn-p" in classes:
            nested = node.find(class_="akn-p")
            if not nested:
                text = node.get_text(" ", strip=True)
                if text:
                    lines.append(text)
                    lines.append("")

        # Preface long title
        elif "akn-longTitle" in classes:
            text = node.get_text(" ", strip=True)
            if text:
                lines.append(f"*{text}*")
                lines.append("")
            for child in node.descendants:
                emitted_ids.add(id(child))

    # Deduplicate: the nested walk can produce duplicates; remove consecutive identical lines
    deduped: list[str] = []
    for line in lines:
        if not deduped or line != deduped[-1] or line == "":
            deduped.append(line)

    return "\n".join(deduped).strip()


def parse_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except Exception as exc:
        raise RuntimeError("pypdf is required to parse PDF files") from exc

    reader = PdfReader(str(path))
    lines: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        cleaned = "\n".join([line.strip() for line in text.splitlines() if line.strip()])
        if not cleaned:
            continue
        lines += [f"## Page {index}", "", cleaned, ""]
    return "\n".join(lines).strip()

def normalize_sources(sources: list[SourceRecord], ingest_dir: Path) -> tuple[list[dict], list[dict]]:
    normalized: list[dict] = []
    statuses: list[dict] = []
    for source in sources:
        input_path = find_raw_input(source, ingest_dir)
        output_path = ingest_dir / "normalized" / f"{source.id}.md"
        if input_path is None:
            if source.acquisition == "manual_download":
                statuses.append({"source_id": source.id, "stage": "ingest", "status": "PENDING", "message": f"manual file missing at {source.local_path}"})
            else:
                statuses.append({"source_id": source.id, "stage": "ingest", "status": "MISSING_RAW", "message": "fetch source missing raw file in .tmp/ingest/raw"})
            continue

        try:
            body = parse_html(input_path.read_text(encoding="utf-8", errors="ignore")) if source.source_type == "html" else parse_pdf(input_path)
            content_md = "\n".join([
                "---",
                f'title: "{source.title}"',
                f'category: "{source.category}"',
                f'doc_type: "{source.doc_type}"',
                f'language_code: "{source.language_code}"',
                f'source_id: "{source.id}"',
                "---",
                "",
                body,
                "",
            ])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(content_md, encoding="utf-8")
            normalized.append({"source": source, "content_md": content_md, "normalized_path": str(output_path)})
            statuses.append({"source_id": source.id, "stage": "ingest", "status": "PARSED", "normalized_path": str(output_path)})
        except Exception as exc:
            statuses.append({"source_id": source.id, "stage": "ingest", "status": "FAILED", "message": str(exc)})
    return normalized, statuses


def chunk_markdown(source: SourceRecord, content_md: str, max_chars: int = 1000) -> list[dict]:
    heading_title: str | None = None
    section_ref: str | None = None
    page_ref: str | None = None
    buffer: list[str] = []
    chunks: list[dict] = []

    def flush() -> None:
        nonlocal buffer
        text = re.sub(r"\s+", " ", " ".join(buffer)).strip()
        if len(text) < 60:
            buffer = []
            return
        chunk_hash = sha256_text(f"{source.id}|{section_ref or ''}|{text}")
        chunks.append(
            {
                "id": str(uuid.uuid5(uuid.NAMESPACE_OID, chunk_hash)),
                "source_id": source.source_uuid(),
                "doc_path": source.canonical_doc_path(),
                "title": source.title,
                "section_ref": section_ref,
                "page_ref": page_ref,
                "chunk_text": text,
                "chunk_hash": chunk_hash,
                "scope": "global",
                "category": source.category,
                "doc_type": source.doc_type,
                "heading_title": heading_title,
                "effective_from": source.effective_from,
                "effective_to": source.effective_to,
                "chunk_language_code": source.language_code,
            }
        )
        buffer = []

    in_frontmatter = False
    for line in content_md.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter or not stripped:
            continue
        if stripped.startswith("#"):
            if buffer:
                flush()
            heading_title = stripped.lstrip("#").strip()
            if re.match(r"^(section|part|article|schedule)\b", heading_title, re.IGNORECASE):
                section_ref = heading_title
            page_match = re.match(r"^page\s+(\d+)$", heading_title, re.IGNORECASE)
            if page_match:
                page_ref = page_match.group(1)
            continue
        buffer.append(stripped)
        if sum(len(item) for item in buffer) >= max_chars:
            flush()
    if buffer:
        flush()
    return chunks


def slugify(text: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    return re.sub(r"-+", "-", slug).strip("-")[:80]


def compute_reading_time(text: str) -> tuple[int, int]:
    words = len(text.split())
    minutes = max(1, round(words / 200))
    return words, minutes


def generate_category_nodes(sources: list[SourceRecord]) -> list[dict]:
    seen: dict[str, int] = {}
    nodes: list[dict] = []
    for source in sources:
        cat = source.category
        if cat not in seen:
            seen[cat] = len(seen)
            nodes.append({
                "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"category|{cat}")),
                "source_id": None,
                "parent_id": None,
                "slug": slugify(cat),
                "full_path": slugify(cat),
                "section_ref": None,
                "title": cat,
                "content_md": "",
                "sort_order": seen[cat],
                "level": 0,
                "word_count": 0,
                "reading_time_minutes": 0,
                "is_placeholder": False,
            })
    return nodes


def generate_doc_sections(source: SourceRecord, content_md: str, category_slug: str, category_id: str) -> list[dict]:
    doc_slug = slugify(source.id)
    doc_path = f"{category_slug}/{doc_slug}"

    in_frontmatter = False
    body_lines: list[str] = []
    for line in content_md.splitlines():
        stripped = line.strip()
        if stripped == "---":
            in_frontmatter = not in_frontmatter
            continue
        if in_frontmatter:
            continue
        body_lines.append(line)
    body = "\n".join(body_lines).strip()

    doc_words, doc_reading = compute_reading_time(body)
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"doc|{source.id}"))

    sections: list[dict] = []
    sections.append({
        "id": doc_id,
        "source_id": source.source_uuid(),
        "parent_id": category_id,
        "slug": doc_slug,
        "full_path": doc_path,
        "section_ref": None,
        "title": source.title,
        "content_md": "",
        "sort_order": 0,
        "level": 1,
        "word_count": doc_words,
        "reading_time_minutes": doc_reading,
        "is_placeholder": False,
    })

    # Detect if this is a page-number-only PDF (all headings are "Page N")
    headings = [line.lstrip("#").strip() for line in body_lines if line.strip().startswith("#")]
    all_page_headings = headings and all(re.match(r"^page\s+\d+$", h, re.IGNORECASE) for h in headings)

    if all_page_headings:
        # Collapse page-based PDF into single document — strip page headings from body
        collapsed = "\n".join(line for line in body_lines if not re.match(r"^\s*#+\s*page\s+\d+\s*$", line, re.IGNORECASE)).strip()
        sections[0]["content_md"] = collapsed
        words, reading = compute_reading_time(collapsed) if collapsed else (0, 0)
        sections[0]["word_count"] = words
        sections[0]["reading_time_minutes"] = reading
    else:
        current_heading: str | None = None
        current_ref: str | None = None
        current_lines: list[str] = []
        child_order = 0

        def flush_section() -> None:
            nonlocal current_lines, child_order
            text = "\n".join(current_lines).strip()
            if not text and not current_heading:
                current_lines = []
                return
            heading = current_heading or "Introduction"
            sec_slug = slugify(heading)
            sec_path = f"{doc_path}/{sec_slug}"
            sec_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"section|{source.id}|{child_order}|{heading}"))
            words, reading = compute_reading_time(text) if text else (0, 0)
            sections.append({
                "id": sec_id,
                "source_id": source.source_uuid(),
                "parent_id": doc_id,
                "slug": sec_slug,
                "full_path": sec_path,
                "section_ref": current_ref,
                "title": heading,
                "content_md": text,
                "sort_order": child_order,
                "level": 2,
                "word_count": words,
                "reading_time_minutes": reading,
                "is_placeholder": False,
            })
            child_order += 1
            current_lines = []

        for line in body_lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                flush_section()
                current_heading = stripped.lstrip("#").strip()
                ref_match = re.match(r"^(section|part|article|schedule)\b", current_heading, re.IGNORECASE)
                current_ref = current_heading if ref_match else None
            else:
                current_lines.append(line)

        flush_section()

        if len(sections) == 1:
            sections[0]["content_md"] = body

    return sections


def generate_placeholder_sections(source: SourceRecord, category_slug: str, category_id: str) -> list[dict]:
    doc_slug = slugify(source.id)
    doc_path = f"{category_slug}/{doc_slug}"
    doc_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"doc|{source.id}"))
    return [{
        "id": doc_id,
        "source_id": None,
        "parent_id": category_id,
        "slug": doc_slug,
        "full_path": doc_path,
        "section_ref": None,
        "title": source.title,
        "content_md": "",
        "sort_order": 0,
        "level": 1,
        "word_count": 0,
        "reading_time_minutes": 0,
        "is_placeholder": True,
    }]


def run_migrations(database_url: str) -> None:
    files = sorted([p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file()])
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version TEXT PRIMARY KEY,
                  applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
            """)
            for file in files:
                version = file.name
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    continue
                sql = file.read_text(encoding="utf-8")
                for statement in [s.strip() for s in sql.split(";") if s.strip()]:
                    cur.execute(statement)
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        conn.commit()


def load_to_postgres(database_url: str, normalized: list[dict], all_sources: list[SourceRecord] | None = None) -> dict:
    source_rows: list[dict] = []
    chunk_rows: list[dict] = []
    ingested_sources: list[SourceRecord] = []
    for row in normalized:
        source: SourceRecord = row["source"]
        content_md: str = row["content_md"]
        ingested_sources.append(source)
        source_rows.append(
            {
                "id": source.source_uuid(),
                "source_key": source.id,
                "doc_path": source.canonical_doc_path(),
                "title": source.title,
                "publisher": source.publisher,
                "category": source.category,
                "doc_type": source.doc_type,
                "source_type": source.source_type,
                "source_url": source.url,
                "acquisition": source.acquisition,
                "local_path": source.local_path,
                "effective_from": source.effective_from,
                "effective_to": source.effective_to,
                "notes": source.notes,
                "language_code": source.language_code,
                "content_hash": sha256_text(content_md),
                "content_md": content_md,
            }
        )
        chunk_rows.extend(chunk_markdown(source, content_md))

    if not source_rows:
        return {"sources_upserted": 0, "chunks_upserted": 0, "chunks_by_category": {}, "chunks_by_language": {}, "sections_upserted": 0}

    all_sources = all_sources or ingested_sources
    category_nodes = generate_category_nodes(all_sources)
    cat_lookup: dict[str, tuple[str, str]] = {}
    for node in category_nodes:
        cat_lookup[node["title"]] = (node["full_path"], node["id"])

    section_rows: list[dict] = []
    for row in normalized:
        source = row["source"]
        content_md = row["content_md"]
        cat_slug, cat_id = cat_lookup.get(source.category, ("general", str(uuid.uuid4())))
        section_rows.extend(generate_doc_sections(source, content_md, cat_slug, cat_id))

    ingested_ids = {s.id for s in ingested_sources}
    for source in all_sources:
        if source.id in ingested_ids:
            continue
        if source.acquisition == "manual_download":
            cat_slug, cat_id = cat_lookup.get(source.category, ("general", str(uuid.uuid4())))
            section_rows.extend(generate_placeholder_sections(source, cat_slug, cat_id))

    run_migrations(database_url)
    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            for source in source_rows:
                cur.execute(
                    """
                    INSERT INTO source_documents (id, doc_path, title, category, content_md)
                    VALUES (%(id)s, %(doc_path)s, %(title)s, %(category)s, %(content_md)s)
                    ON CONFLICT (doc_path) DO UPDATE SET
                      title = EXCLUDED.title,
                      category = EXCLUDED.category,
                      content_md = EXCLUDED.content_md
                    """,
                    source,
                )
                cur.execute(
                    """
                    INSERT INTO sources (
                      id, source_key, doc_path, title, publisher, category, doc_type, source_type, source_url,
                      acquisition, local_path, effective_from, effective_to, notes, language_code, content_hash, content_md, updated_at
                    ) VALUES (
                      %(id)s, %(source_key)s, %(doc_path)s, %(title)s, %(publisher)s, %(category)s, %(doc_type)s, %(source_type)s, %(source_url)s,
                      %(acquisition)s, %(local_path)s, %(effective_from)s, %(effective_to)s, %(notes)s, %(language_code)s, %(content_hash)s, %(content_md)s, NOW()
                    ) ON CONFLICT (source_key) DO UPDATE SET
                      doc_path = EXCLUDED.doc_path,
                      title = EXCLUDED.title,
                      publisher = EXCLUDED.publisher,
                      category = EXCLUDED.category,
                      doc_type = EXCLUDED.doc_type,
                      source_type = EXCLUDED.source_type,
                      source_url = EXCLUDED.source_url,
                      acquisition = EXCLUDED.acquisition,
                      local_path = EXCLUDED.local_path,
                      effective_from = EXCLUDED.effective_from,
                      effective_to = EXCLUDED.effective_to,
                      notes = EXCLUDED.notes,
                      language_code = EXCLUDED.language_code,
                      content_hash = EXCLUDED.content_hash,
                      content_md = EXCLUDED.content_md,
                      updated_at = NOW()
                    """,
                    source,
                )
            for chunk in chunk_rows:
                cur.execute(
                    """
                    INSERT INTO source_chunks (
                      id, source_id, doc_path, title, section_ref, page_ref, chunk_text, chunk_hash, scope,
                      category, doc_type, heading_title, effective_from, effective_to, chunk_language_code
                    ) VALUES (
                      %(id)s, %(source_id)s, %(doc_path)s, %(title)s, %(section_ref)s, %(page_ref)s, %(chunk_text)s, %(chunk_hash)s, %(scope)s,
                      %(category)s, %(doc_type)s, %(heading_title)s, %(effective_from)s, %(effective_to)s, %(chunk_language_code)s
                    ) ON CONFLICT (chunk_hash) DO UPDATE SET
                      source_id = EXCLUDED.source_id,
                      doc_path = EXCLUDED.doc_path,
                      title = EXCLUDED.title,
                      section_ref = EXCLUDED.section_ref,
                      page_ref = EXCLUDED.page_ref,
                      chunk_text = EXCLUDED.chunk_text,
                      scope = EXCLUDED.scope,
                      category = EXCLUDED.category,
                      doc_type = EXCLUDED.doc_type,
                      heading_title = EXCLUDED.heading_title,
                      effective_from = EXCLUDED.effective_from,
                      effective_to = EXCLUDED.effective_to,
                      chunk_language_code = EXCLUDED.chunk_language_code
                    """,
                    chunk,
                )
            # Upsert doc_sections: category nodes + doc/section nodes.
            # We upsert (not delete-then-insert) so a partial re-run never
            # wipes sections that weren't re-generated this time.
            _SECTION_UPSERT = """
                    INSERT INTO doc_sections (id, source_id, parent_id, slug, full_path, section_ref, title, content_md, sort_order, level, word_count, reading_time_minutes, is_placeholder)
                    VALUES (%(id)s, %(source_id)s, %(parent_id)s, %(slug)s, %(full_path)s, %(section_ref)s, %(title)s, %(content_md)s, %(sort_order)s, %(level)s, %(word_count)s, %(reading_time_minutes)s, %(is_placeholder)s)
                    ON CONFLICT (full_path) DO UPDATE SET
                      source_id = EXCLUDED.source_id,
                      parent_id = EXCLUDED.parent_id,
                      slug = EXCLUDED.slug,
                      section_ref = EXCLUDED.section_ref,
                      title = EXCLUDED.title,
                      content_md = EXCLUDED.content_md,
                      sort_order = EXCLUDED.sort_order,
                      level = EXCLUDED.level,
                      word_count = EXCLUDED.word_count,
                      reading_time_minutes = EXCLUDED.reading_time_minutes,
                      is_placeholder = EXCLUDED.is_placeholder,
                      updated_at = NOW()
            """
            upserted_paths: list[str] = []
            for node in category_nodes:
                cur.execute(_SECTION_UPSERT, node)
                upserted_paths.append(node["full_path"])
            for sec in section_rows:
                cur.execute(_SECTION_UPSERT, sec)
                upserted_paths.append(sec["full_path"])

            # Remove stale sections that no longer appear in the current run.
            if upserted_paths:
                cur.execute(
                    "DELETE FROM doc_sections WHERE full_path != ALL(%s)",
                    (upserted_paths,),
                )
        conn.commit()

    return {
        "sources_upserted": len(source_rows),
        "chunks_upserted": len(chunk_rows),
        "chunks_by_category": dict(Counter([chunk["category"] for chunk in chunk_rows])),
        "chunks_by_language": dict(Counter([chunk["chunk_language_code"] for chunk in chunk_rows])),
        "sections_upserted": len(category_nodes) + len(section_rows),
    }

def write_report(ingest_dir: Path, fetch_statuses: list[dict] | None, ingest_statuses: list[dict] | None, load_summary: dict | None) -> Path:
    ensure_ingest_dirs(ingest_dir)
    report_path = ingest_dir / "reports" / f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}.md"
    fetch_statuses = fetch_statuses or []
    ingest_statuses = ingest_statuses or []
    load_summary = load_summary or {"sources_upserted": 0, "chunks_upserted": 0}

    lines = [
        "# Ingest Report",
        "",
        f"Generated: {datetime.now(UTC).isoformat()}",
        "",
        "## Fetch",
        "",
    ]
    lines.extend([f"- {row.get('source_id')}: {row.get('status')} {row.get('message') or row.get('raw_path') or ''}".strip() for row in fetch_statuses] or ["- not run"])
    lines += ["", "## Ingest", ""]
    lines.extend([f"- {row.get('source_id')}: {row.get('status')} {row.get('message') or row.get('normalized_path') or ''}".strip() for row in ingest_statuses] or ["- not run"])
    lines += [
        "",
        "## Load Summary",
        "",
        f"- sources_upserted: {load_summary.get('sources_upserted', 0)}",
        f"- chunks_upserted: {load_summary.get('chunks_upserted', 0)}",
        f"- chunks_by_category: {load_summary.get('chunks_by_category', {})}",
        f"- chunks_by_language: {load_summary.get('chunks_by_language', {})}",
        "",
        "## Notes",
        "",
        "- PENDING manual_download sources do not block seeding.",
        "- FAILED fetch sources do not block other sources.",
        "",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def verify_seed(database_url: str, sources: list[SourceRecord], ingest_dir: Path, require_manual_sources: bool = False) -> int:
    run_migrations(database_url)
    with psycopg.connect(database_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM sources")
            sources_count = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*) FROM source_chunks")
            chunks_count = int(cur.fetchone()[0])
            cur.execute("SELECT category, COUNT(*)::bigint FROM sources GROUP BY category")
            category_counts = {str(k): int(v) for k, v in cur.fetchall()}
            cur.execute("""
                SELECT COUNT(*)
                FROM source_chunks c
                JOIN sources s ON s.id = c.source_id
                WHERE s.acquisition = 'fetch'
            """)
            fetch_chunks_count = int(cur.fetchone()[0])

    fetch_sources_list = [s for s in sources if s.acquisition == "fetch"]
    manual_sources = [s for s in sources if s.acquisition == "manual_download"]
    fetch_raw_present = sum(1 for s in fetch_sources_list if find_raw_input(s, ingest_dir) is not None)
    missing_manual = [s for s in manual_sources if find_raw_input(s, ingest_dir) is None]

    print(f"sources={sources_count}")
    print(f"source_chunks={chunks_count}")
    print("category_counts:")
    for category in REQUIRED_CATEGORIES:
        print(f"  {category}: {category_counts.get(category, 0)}")
    print(f"fetch_chunks={fetch_chunks_count}")
    print(f"fetch_raw_present={fetch_raw_present}/{len(fetch_sources_list)}")
    print(f"manual_pending={len(missing_manual)}")

    if chunks_count == 0:
        print("verify_failed: source_chunks == 0", file=sys.stderr)
        return 1
    if fetch_sources_list and fetch_raw_present == 0 and fetch_chunks_count == 0:
        print("verify_failed: all fetch sources missing raw files; fetch stage appears broken", file=sys.stderr)
        return 1
    if require_manual_sources and missing_manual:
        print("verify_failed: manual sources required but missing local files", file=sys.stderr)
        return 1
    return 0


def run_ingest_pipeline(sources: list[SourceRecord], ingest_dir: Path, database_url: str | None, fetch_if_missing: bool) -> tuple[list[dict], dict]:
    fetch_rows: list[dict] = []
    if fetch_if_missing:
        missing_fetch = [s for s in sources if s.acquisition == "fetch" and find_raw_input(s, ingest_dir) is None]
        if missing_fetch:
            fetch_rows = fetch_sources(missing_fetch, ingest_dir, only_missing=True)

    normalized, ingest_statuses = normalize_sources(sources, ingest_dir)
    missing_fetch_rows = [row for row in ingest_statuses if row.get("status") == "MISSING_RAW"]
    parsed_rows = [row for row in ingest_statuses if row.get("status") == "PARSED"]
    if missing_fetch_rows and not parsed_rows and not fetch_if_missing:
        print("raw files missing; run seed or fetch")

    if not normalized:
        return ingest_statuses + fetch_rows, {"sources_upserted": 0, "chunks_upserted": 0, "chunks_by_category": {}, "chunks_by_language": {}, "sections_upserted": 0}

    if not database_url:
        raise RuntimeError("--database-url (or DATABASE_URL env) is required to load parsed sources")
    return ingest_statuses + fetch_rows, load_to_postgres(database_url, normalized, all_sources=sources)


def command_fetch(args: argparse.Namespace) -> int:
    sources = load_sources(args.sources_file)
    rows = fetch_sources(sources, args.ingest_dir)
    for row in rows:
        print(json.dumps(row, ensure_ascii=True))
    report = write_report(args.ingest_dir, rows, [], None)
    print(f"report={report}")
    return 0


def command_ingest(args: argparse.Namespace) -> int:
    sources = load_sources(args.sources_file)
    statuses, summary = run_ingest_pipeline(sources, args.ingest_dir, args.database_url, args.fetch_if_missing)
    for row in statuses:
        print(json.dumps(row, ensure_ascii=True))
    print(json.dumps(summary, ensure_ascii=True))
    report = write_report(args.ingest_dir, [], statuses, summary)
    print(f"report={report}")
    return 0


def command_verify(args: argparse.Namespace) -> int:
    if not args.database_url:
        raise RuntimeError("--database-url (or DATABASE_URL env) is required for verify")
    sources = load_sources(args.sources_file)
    return verify_seed(args.database_url, sources, args.ingest_dir, args.require_manual_sources)


def command_seed(args: argparse.Namespace) -> int:
    if not args.database_url:
        raise RuntimeError("--database-url (or DATABASE_URL env) is required for seed")
    sources = load_sources(args.sources_file)
    fetch_rows = fetch_sources(sources, args.ingest_dir)
    statuses, summary = run_ingest_pipeline(sources, args.ingest_dir, args.database_url, fetch_if_missing=False)

    for row in fetch_rows:
        print(json.dumps(row, ensure_ascii=True))
    for row in statuses:
        print(json.dumps(row, ensure_ascii=True))
    print(json.dumps(summary, ensure_ascii=True))

    report = write_report(args.ingest_dir, fetch_rows, statuses, summary)
    print(f"report={report}")
    return verify_seed(args.database_url, sources, args.ingest_dir, args.require_manual_sources)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Seed and verify Uganda Tax Assistant corpus in Postgres")
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common(cmd: argparse.ArgumentParser, include_db: bool) -> None:
        cmd.add_argument("--sources-file", type=Path, default=DEFAULT_SOURCES_FILE)
        cmd.add_argument("--ingest-dir", type=Path, default=DEFAULT_INGEST_DIR)
        if include_db:
            cmd.add_argument("--database-url", default=None)

    fetch_cmd = subparsers.add_parser("fetch", help="downloads fetch sources")
    add_common(fetch_cmd, include_db=False)

    ingest_cmd = subparsers.add_parser("ingest", help="parse/chunk/load")
    add_common(ingest_cmd, include_db=True)
    ingest_cmd.add_argument("--fetch-if-missing", action="store_true", help="fetch missing acquisition=fetch raw files before ingest")

    verify_cmd = subparsers.add_parser("verify", help="verify seeded db")
    add_common(verify_cmd, include_db=True)
    verify_cmd.add_argument("--require-manual-sources", action="store_true", help="fail when manual sources are missing")

    seed_cmd = subparsers.add_parser("seed", help="fetch + ingest + report + verify")
    add_common(seed_cmd, include_db=True)
    seed_cmd.add_argument("--require-manual-sources", action="store_true", help="fail when manual sources are missing")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    args.sources_file = args.sources_file.resolve()
    args.ingest_dir = args.ingest_dir.resolve()
    ensure_ingest_dirs(args.ingest_dir)
    if hasattr(args, "database_url"):
        args.database_url = args.database_url or os.environ.get("DATABASE_URL")

    if args.command == "fetch":
        return command_fetch(args)
    if args.command == "ingest":
        return command_ingest(args)
    if args.command == "verify":
        return command_verify(args)
    if args.command == "seed":
        return command_seed(args)
    parser.error(f"Unknown command {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
