from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.base import RetrievedChunk, Retriever


class PgVectorRetriever(Retriever):
    async def retrieve(self, session: AsyncSession, query: str, top_k: int, scope: str = "global") -> list[RetrievedChunk]:
        raise NotImplementedError("PgVectorRetriever is a Phase 2 adapter stub and is disabled by default.")
