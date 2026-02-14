from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.base import RetrievedChunk, Retriever


class QdrantRetriever(Retriever):
    async def retrieve(self, session: AsyncSession, query: str, top_k: int, scope: str = "global") -> list[RetrievedChunk]:
        raise NotImplementedError("QdrantRetriever is a Phase 3 adapter stub and is disabled by default.")
