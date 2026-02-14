from __future__ import annotations

from pathlib import Path

from app.schemas import DocsPageResponse, DocsTreeNode


def _parse_frontmatter(content: str) -> tuple[dict[str, str], str]:
    if not content.startswith("---\n"):
        return {}, content
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return {}, content

    raw = parts[1]
    body = parts[2]
    metadata: dict[str, str] = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        metadata[k.strip().lower()] = v.strip().strip('"').strip("'")
    return metadata, body.lstrip("\n")


def build_docs_tree(docs_root: Path) -> list[DocsTreeNode]:
    nodes: list[DocsTreeNode] = []
    for path in sorted(docs_root.rglob("*.md")):
        relative = path.relative_to(docs_root).as_posix()
        content = path.read_text(encoding="utf-8")
        frontmatter, _ = _parse_frontmatter(content)
        title = frontmatter.get("title", path.stem.replace("-", " ").title())
        category = frontmatter.get("category", "General")
        nodes.append(DocsTreeNode(path=relative, title=title, category=category))
    return nodes


def read_docs_page(docs_root: Path, relative_path: str) -> DocsPageResponse:
    safe_path = (docs_root / relative_path).resolve()
    if docs_root.resolve() not in safe_path.parents and safe_path != docs_root.resolve():
        raise FileNotFoundError("Invalid docs path")
    if not safe_path.exists() or safe_path.suffix.lower() != ".md":
        raise FileNotFoundError("Docs page not found")

    content = safe_path.read_text(encoding="utf-8")
    frontmatter, body = _parse_frontmatter(content)
    return DocsPageResponse(
        path=relative_path,
        title=frontmatter.get("title", safe_path.stem.replace("-", " ").title()),
        category=frontmatter.get("category", "General"),
        content_md=body,
    )
