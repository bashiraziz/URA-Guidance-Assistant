from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession


@dataclass
class RetrievedChunk:
    id: str
    source_id: str | None
    doc_path: str
    title: str
    section_ref: str | None
    page_ref: str | None
    chunk_text: str
    rank: float


class Retriever(ABC):
    @abstractmethod
    async def retrieve(self, session: AsyncSession, query: str, top_k: int, scope: str = "global") -> list[RetrievedChunk]:
        raise NotImplementedError
