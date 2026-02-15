from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import (
    BreadcrumbItem,
    DocSectionNode,
    DocSectionPage,
    DocsPageResponse,
    DocsTreeNode,
    PrevNextLink,
)


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


async def build_docs_tree(session: AsyncSession) -> list[DocsTreeNode]:
    try:
        rows = (
            await session.execute(
                text(
                    """
                    SELECT source_key AS path, title, COALESCE(category, 'General') AS category
                    FROM sources
                    ORDER BY source_key
                    """
                )
            )
        ).mappings().all()
        if rows:
            return [DocsTreeNode(path=str(row["path"]), title=str(row["title"]), category=str(row["category"])) for row in rows]
    except Exception:
        rows = []

    fallback = (
        await session.execute(
            text(
                """
                SELECT doc_path AS path, title, COALESCE(category, 'General') AS category
                FROM source_documents
                ORDER BY doc_path
                """
            )
        )
    ).mappings().all()
    return [DocsTreeNode(path=str(row["path"]), title=str(row["title"]), category=str(row["category"])) for row in fallback]


async def read_docs_page(session: AsyncSession, relative_path: str) -> DocsPageResponse:
    try:
        row = (
            await session.execute(
                text(
                    """
                    SELECT source_key AS path, title, COALESCE(category, 'General') AS category, content_md
                    FROM sources
                    WHERE source_key = :path OR doc_path = :path
                    LIMIT 1
                    """
                ),
                {"path": relative_path},
            )
        ).mappings().first()
    except Exception:
        row = None
    if not row:
        fallback = (
            await session.execute(
                text(
                    """
                    SELECT doc_path AS path, title, COALESCE(category, 'General') AS category, content_md
                    FROM source_documents
                    WHERE doc_path = :path
                    LIMIT 1
                    """
                ),
                {"path": relative_path},
            )
        ).mappings().first()
        row = fallback
    if not row:
        raise FileNotFoundError("Docs page not found")

    frontmatter, body = _parse_frontmatter(str(row["content_md"]))
    return DocsPageResponse(
        path=str(row["path"]),
        title=frontmatter.get("title", str(row["title"])),
        category=frontmatter.get("category", str(row["category"])),
        content_md=body,
    )


async def build_sections_tree(session: AsyncSession) -> list[DocSectionNode]:
    rows = (
        await session.execute(
            text(
                """
                SELECT id::text, parent_id::text, slug, full_path, title, level,
                       section_ref, word_count, reading_time_minutes, is_placeholder, sort_order
                FROM doc_sections
                ORDER BY level, sort_order, title
                """
            )
        )
    ).mappings().all()

    nodes_by_id: dict[str, DocSectionNode] = {}
    roots: list[DocSectionNode] = []

    for row in rows:
        node = DocSectionNode(
            id=str(row["id"]),
            slug=str(row["slug"]),
            full_path=str(row["full_path"]),
            title=str(row["title"]),
            level=int(row["level"]),
            section_ref=row["section_ref"],
            word_count=int(row["word_count"]),
            reading_time_minutes=int(row["reading_time_minutes"]),
            is_placeholder=bool(row["is_placeholder"]),
        )
        nodes_by_id[node.id] = node

    for row in rows:
        node = nodes_by_id[str(row["id"])]
        parent_id = row["parent_id"]
        if parent_id and str(parent_id) in nodes_by_id:
            nodes_by_id[str(parent_id)].children.append(node)
        else:
            roots.append(node)

    return roots


def _flatten_dfs(nodes: list[DocSectionNode]) -> list[DocSectionNode]:
    result: list[DocSectionNode] = []
    for node in nodes:
        result.append(node)
        result.extend(_flatten_dfs(node.children))
    return result


async def read_section_page(session: AsyncSession, full_path: str) -> DocSectionPage:
    row = (
        await session.execute(
            text(
                """
                SELECT id::text, full_path, title, section_ref, content_md, level,
                       word_count, reading_time_minutes, is_placeholder, parent_id::text
                FROM doc_sections
                WHERE full_path = :path
                LIMIT 1
                """
            ),
            {"path": full_path},
        )
    ).mappings().first()

    if not row:
        raise FileNotFoundError("Section not found")

    # Build breadcrumbs by walking parent chain
    breadcrumbs: list[BreadcrumbItem] = []
    current_parent = row["parent_id"]
    while current_parent:
        parent = (
            await session.execute(
                text(
                    "SELECT id::text, full_path, title, parent_id::text FROM doc_sections WHERE id = :id"
                ),
                {"id": current_parent},
            )
        ).mappings().first()
        if not parent:
            break
        breadcrumbs.insert(0, BreadcrumbItem(title=str(parent["title"]), full_path=str(parent["full_path"])))
        current_parent = parent["parent_id"]

    breadcrumbs.append(BreadcrumbItem(title=str(row["title"]), full_path=str(row["full_path"])))

    # Get prev/next from DFS order
    tree = await build_sections_tree(session)
    flat = _flatten_dfs(tree)
    current_idx = next((i for i, n in enumerate(flat) if n.full_path == full_path), -1)

    prev_link = None
    next_link = None
    if current_idx > 0:
        p = flat[current_idx - 1]
        prev_link = PrevNextLink(title=p.title, full_path=p.full_path)
    if current_idx >= 0 and current_idx < len(flat) - 1:
        n = flat[current_idx + 1]
        next_link = PrevNextLink(title=n.title, full_path=n.full_path)

    return DocSectionPage(
        id=str(row["id"]),
        full_path=str(row["full_path"]),
        title=str(row["title"]),
        section_ref=row["section_ref"],
        content_md=str(row["content_md"]),
        level=int(row["level"]),
        word_count=int(row["word_count"]),
        reading_time_minutes=int(row["reading_time_minutes"]),
        is_placeholder=bool(row["is_placeholder"]),
        breadcrumbs=breadcrumbs,
        prev=prev_link,
        next=next_link,
    )
