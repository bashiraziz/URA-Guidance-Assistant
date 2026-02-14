from app.config import Settings
from app.retrieval.base import Retriever
from app.retrieval.fts import PostgresFTSRetriever
from app.retrieval.pgvector import PgVectorRetriever
from app.retrieval.qdrant import QdrantRetriever


def build_retriever(settings: Settings) -> Retriever:
    if settings.retriever_mode == "pgvector":
        return PgVectorRetriever()
    if settings.retriever_mode == "qdrant":
        return QdrantRetriever()
    return PostgresFTSRetriever()
