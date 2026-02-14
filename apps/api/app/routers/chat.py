from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.config import get_settings
from app.db import get_session
from app.retrieval.factory import build_retriever
from app.schemas import ChatRequest, ChatResponse
from app.services.chat import ChatService

router = APIRouter(prefix="/v1", tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
) -> ChatResponse:
    settings = get_settings()
    service = ChatService(settings=settings, retriever=build_retriever(settings))
    return await service.handle_chat(session=session, user_id=user_id, request=request)
