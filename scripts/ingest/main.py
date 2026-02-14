from __future__ import annotations

import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import psycopg

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCS_ROOT = PROJECT_ROOT / "docs"


@dataclass
class SourceDoc:
    path: str
    title: str
    category: str
    body: str


@dataclass
class Chunk:
    section_ref: str
    text: str
    chunk_hash: str


def parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}, content
    metadata: dict[str, str] = {}
    for line in parts[1].splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip().lower()] = value.strip().strip('"').strip("'")
    return metadata, parts[2].lstrip("\n")


def load_docs(root: Path) -> list[SourceDoc]:
    docs: list[SourceDoc] = []
    for file_path in sorted(root.rglob("*.md")):
        relative = file_path.relative_to(root).as_posix()
        content = file_path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(content)
        docs.append(
            SourceDoc(
                path=relative,
                title=frontmatter.get("title", file_path.stem.replace("-", " ").title()),
                category=frontmatter.get("category", "General"),
                body=body,
            )
        )
    return docs


def split_heading_aware(text: str, max_chars: int = 1400) -> Iterable[tuple[str, str]]:
    heading = "Introduction"
    buf: list[str] = []
    for line in text.splitlines():
        if line.startswith("#"):
            if buf:
                yield heading, "\n".join(buf).strip()
                buf = []
            heading = line.lstrip("#").strip() or heading
            continue
        buf.append(line)
        if sum(len(item) for item in buf) >= max_chars:
            yield heading, "\n".join(buf).strip()
            buf = []
    if buf:
        yield heading, "\n".join(buf).strip()


def build_chunks(doc: SourceDoc) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section_ref, text in split_heading_aware(doc.body):
        clean = re.sub(r"\s+", " ", text).strip()
        if len(clean) < 40:
            continue
        chunk_hash = hashlib.sha256(f"{doc.path}|{section_ref}|{clean}".encode("utf-8")).hexdigest()
        chunks.append(Chunk(section_ref=section_ref, text=clean, chunk_hash=chunk_hash))
    return chunks


def ingest(database_url: str) -> None:
    docs = load_docs(DOCS_ROOT)
    if not docs:
        print("No docs found under /docs; nothing to ingest.")
        return

    with psycopg.connect(database_url, autocommit=False) as conn:
        with conn.cursor() as cur:
            for doc in docs:
                source_id = uuid.uuid5(uuid.NAMESPACE_URL, doc.path)
                cur.execute(
                    """
                    INSERT INTO source_documents (id, doc_path, title, category, content_md)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (doc_path)
                    DO UPDATE SET title = EXCLUDED.title, category = EXCLUDED.category, content_md = EXCLUDED.content_md
                    RETURNING id
                    """,
                    (str(source_id), doc.path, doc.title, doc.category, doc.body),
                )
                saved_source_id = cur.fetchone()[0]
                chunks = build_chunks(doc)
                for chunk in chunks:
                    chunk_id = str(uuid.uuid5(uuid.NAMESPACE_OID, chunk.chunk_hash))
                    cur.execute(
                        """
                        INSERT INTO source_chunks (
                          id, source_id, doc_path, title, section_ref, page_ref, chunk_text, chunk_hash, scope
                        )
                        VALUES (%s, %s, %s, %s, %s, NULL, %s, %s, 'global')
                        ON CONFLICT (chunk_hash)
                        DO UPDATE SET
                          title = EXCLUDED.title,
                          section_ref = EXCLUDED.section_ref,
                          chunk_text = EXCLUDED.chunk_text,
                          doc_path = EXCLUDED.doc_path
                        """,
                        (
                            chunk_id,
                            str(saved_source_id),
                            doc.path,
                            doc.title,
                            chunk.section_ref,
                            chunk.text,
                            chunk.chunk_hash,
                        ),
                    )
        conn.commit()
    print(f"Ingested {len(docs)} source documents from {DOCS_ROOT}.")


def main() -> None:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required.")
    ingest(database_url)


if __name__ == "__main__":
    main()
