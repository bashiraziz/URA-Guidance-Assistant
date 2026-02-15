from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.base import RetrievedChunk, Retriever


class PostgresFTSRetriever(Retriever):
    @staticmethod
    def _build_or_tsquery(query: str) -> str:
        """Convert a keyword string into an OR-based tsquery expression.

        plainto_tsquery uses AND which is too strict for legal text where
        heading terms and body terms live in different chunks.  We use OR
        so that any matching keyword contributes to ranking, while ts_rank_cd
        still ranks chunks with more matching terms higher.
        """
        import re

        words = re.findall(r"[a-zA-Z0-9]+", query)
        if not words:
            return query
        return " | ".join(words)

    async def retrieve(self, session: AsyncSession, query: str, top_k: int, scope: str = "global") -> list[RetrievedChunk]:
        or_expr = self._build_or_tsquery(query)
        # Try OR-based query first for better recall
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
              ts_rank_cd(chunk_tsvector, to_tsquery('english', :or_query)) AS rank
            FROM source_chunks
            WHERE scope = :scope
              AND chunk_tsvector @@ to_tsquery('english', :or_query)
            ORDER BY rank DESC, created_at DESC
            LIMIT :top_k
            """
        )
        rows = (await session.execute(sql, {"or_query": or_expr, "top_k": top_k, "scope": scope})).mappings().all()
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
