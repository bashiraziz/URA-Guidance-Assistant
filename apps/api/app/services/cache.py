from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import Citation


def normalize_question(question: str) -> str:
    return re.sub(r"\s+", " ", question.strip().lower())


def question_hash(question: str) -> str:
    return hashlib.sha256(normalize_question(question).encode("utf-8")).hexdigest()


async def get_cached_answer(session: AsyncSession, question: str, language_code: str) -> tuple[str, list[Citation]] | None:
    q_hash = question_hash(question)
    async with session.begin():
        row = (
            await session.execute(
                text(
                    """
                    SELECT answer_md, citations_json
                    FROM qa_cache
                    WHERE question_hash = :question_hash
                      AND language_code = :language_code
                    """
                ),
                {"question_hash": q_hash, "language_code": language_code},
            )
        ).mappings().first()
        if row:
            await session.execute(
                text(
                    """
                    UPDATE qa_cache
                    SET hits = hits + 1
                    WHERE question_hash = :question_hash
                      AND language_code = :language_code
                    """
                ),
                {"question_hash": q_hash, "language_code": language_code},
            )

    if not row:
        return None
    return row["answer_md"], [Citation.model_validate(item) for item in row["citations_json"]]


async def set_cached_answer(
    session: AsyncSession,
    question: str,
    language_code: str,
    answer_md: str,
    citations: list[Citation],
) -> None:
    if not citations:
        return
    q_hash = question_hash(question)
    payload = [c.model_dump() for c in citations]
    async with session.begin():
        await session.execute(
            text(
                """
                INSERT INTO qa_cache (question_hash, language_code, answer_md, citations_json, created_at, hits)
                VALUES (:question_hash, :language_code, :answer_md, CAST(:citations_json AS JSONB), :created_at, 0)
                ON CONFLICT (question_hash, language_code)
                DO UPDATE SET
                  answer_md = EXCLUDED.answer_md,
                  citations_json = EXCLUDED.citations_json,
                  created_at = EXCLUDED.created_at
                """
            ),
            {
                "question_hash": q_hash,
                "language_code": language_code,
                "answer_md": answer_md,
                "citations_json": json.dumps(payload),
                "created_at": datetime.now(UTC),
            },
        )
