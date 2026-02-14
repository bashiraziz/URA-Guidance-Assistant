from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.retrieval.base import RetrievedChunk


@dataclass
class LLMResult:
    answer_md: str
    estimated_input_tokens: int
    estimated_output_tokens: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


async def generate_answer(
    settings: Settings,
    question: str,
    chunks: list[RetrievedChunk],
) -> LLMResult:
    if not chunks:
        fallback = (
            "I could not find enough evidence in the current corpus for that question.\n\n"
            "Please clarify the tax type, period, and exact transaction details."
        )
        return LLMResult(answer_md=fallback, estimated_input_tokens=_estimate_tokens(question), estimated_output_tokens=40)

    if settings.gemini_enabled:
        try:
            import google.generativeai as genai  # type: ignore
        except Exception as exc:
            raise RuntimeError("Gemini is enabled but google-generativeai is not installed.") from exc
        if not settings.gemini_api_key:
            raise RuntimeError("Gemini is enabled but GEMINI_API_KEY is not configured.")

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(settings.gemini_model)
        context = "\n\n".join([f"[{idx+1}] {chunk.title} - {chunk.chunk_text}" for idx, chunk in enumerate(chunks)])
        prompt = (
            "Answer the user using only the provided Uganda tax evidence. "
            "When uncertain, say so. Return concise markdown.\n\n"
            f"Question:\n{question}\n\nEvidence:\n{context}"
        )
        completion = model.generate_content(prompt)
        text = (completion.text or "").strip() or "No answer generated."
        return LLMResult(
            answer_md=text,
            estimated_input_tokens=_estimate_tokens(prompt),
            estimated_output_tokens=_estimate_tokens(text),
        )

    # Deterministic mock mode to support free-tier / offline development.
    top = chunks[:3]
    bullets = "\n".join([f"- {chunk.title}: {chunk.chunk_text[:260].strip()}..." for chunk in top])
    answer = (
        "Based on URA guidance in the indexed corpus:\n\n"
        f"{bullets}\n\n"
        "If you need a strict legal interpretation, specify the tax head, period, and transaction facts."
    )
    return LLMResult(
        answer_md=answer,
        estimated_input_tokens=_estimate_tokens(question),
        estimated_output_tokens=_estimate_tokens(answer),
    )
