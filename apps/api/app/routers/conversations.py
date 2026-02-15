from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_token_payload
from app.db import get_session
from app.schemas import ConversationSummary, MessageModel

router = APIRouter(prefix="/v1", tags=["conversations"])


@router.get("/conversations", response_model=list[ConversationSummary])
async def list_conversations(
    payload: dict = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> list[ConversationSummary]:
    user_id = str(payload["sub"])
    if user_id.startswith("guest:"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conversation history is only available for signed-in users.",
        )
    rows = (
        await session.execute(
            text(
                """
                SELECT c.id, c.created_at, c.updated_at,
                       (
                         SELECT m.content_md
                         FROM messages m
                         WHERE m.conversation_id = c.id AND m.role = 'user'
                         ORDER BY m.created_at DESC
                         LIMIT 1
                       ) AS latest_question
                FROM conversations c
                WHERE c.user_id = :user_id
                ORDER BY c.updated_at DESC
                """
            ),
            {"user_id": user_id},
        )
    ).mappings().all()
    return [ConversationSummary.model_validate(dict(row)) for row in rows]


@router.get("/conversations/{conversation_id}", response_model=list[MessageModel])
async def get_conversation_messages(
    conversation_id: str,
    payload: dict = Depends(get_token_payload),
    session: AsyncSession = Depends(get_session),
) -> list[MessageModel]:
    user_id = str(payload["sub"])
    if user_id.startswith("guest:"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conversation history is only available for signed-in users.",
        )

    owner = (
        await session.execute(
            text("SELECT 1 FROM conversations WHERE id = :id AND user_id = :user_id"),
            {"id": conversation_id, "user_id": user_id},
        )
    ).first()
    if not owner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    rows = (
        await session.execute(
            text(
                """
                SELECT id, role, content_md, created_at
                FROM messages
                WHERE conversation_id = :conversation_id
                ORDER BY created_at ASC
                """
            ),
            {"conversation_id": conversation_id},
        )
    ).mappings().all()
    return [MessageModel.model_validate(dict(row)) for row in rows]
