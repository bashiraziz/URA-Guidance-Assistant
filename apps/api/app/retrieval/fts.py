from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.base import RetrievedChunk, Retriever


class PostgresFTSRetriever(Retriever):
    async def retrieve(self, session: AsyncSession, query: str, top_k: int, scope: str = "global") -> list[RetrievedChunk]:
        sql = text(
            """
            SELECT
              id::text,
              source_id::text,
              doc_path,
              title,
              section_ref,
              page_ref,
              chunk_text,
              ts_rank_cd(chunk_tsvector, plainto_tsquery('english', :query)) AS rank
            FROM source_chunks
            WHERE scope = :scope
              AND chunk_tsvector @@ plainto_tsquery('english', :query)
            ORDER BY rank DESC, created_at DESC
            LIMIT :top_k
            """
        )
        rows = (await session.execute(sql, {"query": query, "top_k": top_k, "scope": scope})).mappings().all()
        if not rows:
            fallback = text(
                """
                SELECT
                  id::text,
                  source_id::text,
                  doc_path,
                  title,
                  section_ref,
                  page_ref,
                  chunk_text,
                  0.01 AS rank
                FROM source_chunks
                WHERE scope = :scope
                  AND chunk_text ILIKE :pattern
                ORDER BY created_at DESC
                LIMIT :top_k
                """
            )
            rows = (
                await session.execute(
                    fallback,
                    {"pattern": f"%{query.strip()}%", "top_k": top_k, "scope": scope},
                )
            ).mappings().all()

        return [
            RetrievedChunk(
                id=row["id"],
                source_id=row["source_id"],
                doc_path=row["doc_path"],
                title=row["title"],
                section_ref=row["section_ref"],
                page_ref=row["page_ref"],
                chunk_text=row["chunk_text"],
                rank=float(row["rank"]),
            )
            for row in rows
        ]
