from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.retrieval.base import Retriever
from app.schemas import ChatRequest, ChatResponse, Citation
from app.services.cache import get_cached_answer, set_cached_answer
from app.services.calculators import calculate_paye, calculate_vat, should_run_paye, should_run_vat
from app.services.llm import generate_answer
from app.services.quota import QuotaService

_STOPWORDS = {
    "the",
    "is",
    "a",
    "an",
    "for",
    "and",
    "or",
    "to",
    "of",
    "in",
    "on",
    "with",
    "uganda",
    "ura",
    "tax",
}


def rewrite_query_fallback(question: str) -> str:
    words = re.findall(r"[a-zA-Z0-9]+", question.lower())
    keywords = [w for w in words if len(w) > 2 and w not in _STOPWORDS]
    return " ".join(keywords[:12]) or question


async def rewrite_query(question: str, settings: Settings) -> str:
    if not settings.gemini_enabled:
        return rewrite_query_fallback(question)
    try:
        import google.generativeai as genai  # type: ignore

        if not settings.gemini_api_key:
            return rewrite_query_fallback(question)
        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        prompt = (
            "Rewrite this tax question into a compact keyword query for Postgres full-text search.\n"
            "Return only keywords in one line.\n\n"
            f"{question}"
        )
        completion = model.generate_content(prompt)
        text = (completion.text or "").strip()
        return text if text else rewrite_query_fallback(question)
    except Exception:
        return rewrite_query_fallback(question)


def build_citations(chunks) -> list[Citation]:
    citations: list[Citation] = []
    for chunk in chunks:
        citations.append(
            Citation(
                source_id=chunk.source_id,
                doc_path=chunk.doc_path,
                title=chunk.title,
                section_ref=chunk.section_ref,
                page_ref=chunk.page_ref,
                snippet=chunk.chunk_text[:320],
            )
        )
    return citations


class ChatService:
    def __init__(self, settings: Settings, retriever: Retriever):
        self.settings = settings
        self.retriever = retriever
        self.quota = QuotaService(settings)

    async def handle_chat(self, session: AsyncSession, user_id: str, request: ChatRequest) -> ChatResponse:
        lease, _ = await self.quota.reserve(session, user_id)
        token_in = 0
        token_out = 0
        conversation_id = request.conversation_id
        try:
            conversation_id = await self._ensure_conversation(session, user_id, request.conversation_id)

            cached = await get_cached_answer(session, request.question, request.language_code)
            if cached:
                answer_md, citations = cached
                await self._save_turn(session, conversation_id, request.question, answer_md, None)
                token_in = max(1, len(request.question.split()))
                token_out = max(1, len(answer_md.split()))
                usage = await self.quota.finalize(session, lease, token_in=token_in, token_out=token_out)
                await session.commit()
                return ChatResponse(
                    conversation_id=conversation_id,
                    answer_md=answer_md,
                    citations=citations,
                    calculation=None,
                    usage=usage,
                )

            rewritten_query = await rewrite_query(request.question, self.settings)
            async with session.begin():
                chunks = await self.retriever.retrieve(
                    session=session,
                    query=rewritten_query,
                    top_k=self.settings.retriever_top_k,
                    scope="global",
                )
            citations = build_citations(chunks)

            calc = None
            if should_run_vat(request.question):
                calc = calculate_vat(request.question)
            elif should_run_paye(request.question):
                calc = calculate_paye(request.question)

            llm_result = await generate_answer(settings=self.settings, question=request.question, chunks=chunks)
            answer_md = llm_result.answer_md
            token_in = llm_result.estimated_input_tokens
            token_out = llm_result.estimated_output_tokens

            if citations:
                source_lines = "\n".join(
                    [
                        f"- {idx+1}. {c.title} ({c.section_ref or 'section n/a'}) `{c.doc_path}`"
                        for idx, c in enumerate(citations)
                    ]
                )
                answer_md += f"\n\n### Sources\n{source_lines}"

            await self._save_turn(session, conversation_id, request.question, answer_md, calc.type if calc else None)
            await set_cached_answer(session, request.question, request.language_code, answer_md, citations)
            usage = await self.quota.finalize(session, lease, token_in=token_in, token_out=token_out)
            await session.commit()

            return ChatResponse(
                conversation_id=conversation_id,
                answer_md=answer_md,
                citations=citations,
                calculation=calc.__dict__ if calc else None,
                usage=usage,
            )
        except HTTPException:
            await self.quota.release(session, user_id)
            await session.commit()
            raise
        except Exception as exc:
            await session.rollback()
            await self.quota.release(session, user_id)
            await session.commit()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    async def _ensure_conversation(self, session: AsyncSession, user_id: str, requested_id: str | None) -> str:
        if requested_id:
            async with session.begin():
                row = (
                    await session.execute(
                        text("SELECT id FROM conversations WHERE id = :id AND user_id = :user_id"),
                        {"id": requested_id, "user_id": user_id},
                    )
                ).first()
            if not row:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
            return requested_id

        conversation_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO conversations (id, user_id, created_at, updated_at)
                    VALUES (:id, :user_id, :created_at, :updated_at)
                    """
                ),
                {"id": conversation_id, "user_id": user_id, "created_at": now, "updated_at": now},
            )
        return conversation_id

    async def _save_turn(
        self,
        session: AsyncSession,
        conversation_id: str,
        question: str,
        answer_md: str,
        tool_name: str | None,
    ) -> None:
        now = datetime.now(UTC)
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO messages (id, conversation_id, role, content_md, created_at)
                    VALUES (:id, :conversation_id, 'user', :content_md, :created_at)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "conversation_id": conversation_id,
                    "content_md": question,
                    "created_at": now,
                },
            )
            await session.execute(
                text(
                    """
                    INSERT INTO messages (id, conversation_id, role, content_md, created_at)
                    VALUES (:id, :conversation_id, 'assistant', :content_md, :created_at)
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "conversation_id": conversation_id,
                    "content_md": answer_md,
                    "created_at": now,
                },
            )
            if tool_name:
                await session.execute(
                    text(
                        """
                        INSERT INTO tool_calls (id, conversation_id, tool_name, payload_json, created_at)
                        VALUES (:id, :conversation_id, :tool_name, '{}'::jsonb, :created_at)
                        """
                    ),
                    {
                        "id": str(uuid.uuid4()),
                        "conversation_id": conversation_id,
                        "tool_name": tool_name,
                        "created_at": now,
                    },
                )
            await session.execute(
                text("UPDATE conversations SET updated_at = :updated_at WHERE id = :id"),
                {"updated_at": now, "id": conversation_id},
            )
