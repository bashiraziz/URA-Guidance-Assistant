"""LLM provider abstraction for BYOK (Bring Your Own Key) support."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from cryptography.fernet import Fernet
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.retrieval.base import RetrievedChunk


# ---------------------------------------------------------------------------
# Shared constants (duplicated from llm.py to avoid circular import)
# ---------------------------------------------------------------------------

@dataclass
class LLMResult:
    answer_md: str
    estimated_input_tokens: int
    estimated_output_tokens: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


_TAX_KEYWORDS: set[str] = {
    "vat", "paye", "wht", "efris", "tax", "ura", "income", "withholding",
    "registration", "penalty", "penalties", "filing", "exemption", "exemptions",
    "deduction", "deductions", "assessment", "refund", "invoice", "tin",
    "excise", "customs", "stamp", "duty", "rental", "taxpayer", "revenue",
    "return", "returns", "compliance", "audit", "objection", "tribunal",
    "amendment", "act", "statute", "provision", "section", "schedule",
    "zero-rating", "zero", "rated", "supply", "taxable", "threshold",
    "capital gains", "gains", "allowance", "depreciation", "commissioner",
    "omusolo", "emisolo", "okufayilo", "ebitagobererwa", "ensasula",
    "obwannannyini",
}

_SYSTEM_PROMPT = """\
You are a Uganda tax law assistant. You MUST follow these rules strictly:

1. Answer PRIMARILY from the provided Evidence excerpts. Cite them by number [1], [2], etc.
2. If the evidence fully answers the question, use ONLY the evidence.
3. If the evidence partially answers it, present the evidence-based answer first, then clearly separate any supplementary knowledge with:
   "\u26a0 **Additional context (not from the indexed URA corpus):** ..."
4. If your general knowledge includes a MORE RECENT amendment or proclamation than what appears in the evidence, say so explicitly, e.g.:
   "\u26a0 **Note:** There may be a more recent amendment (e.g., [year] Act) not yet in the indexed corpus."
5. Never fabricate legal provisions. If uncertain, say so.
6. Keep answers concise. Use markdown formatting.
"""

_LUGANDA_RULE = (
    "7. Respond ENTIRELY in Luganda (Ganda language). "
    "Translate legal terms but keep Act names and section numbers in English for precision."
)

_NO_CHUNKS_FALLBACKS: dict[str, str] = {
    "en": (
        "I could not find enough evidence in the current corpus for that question.\n\n"
        "Please clarify the tax type, period, and exact transaction details."
    ),
    "lg": (
        "Sisobodde kuzuula bujjulizi bumala mu ky'obuuzizza.\n\n"
        "Nsaba onnyonyole ekika ky'omusolo, ekiseera, n'ebikwata ku mulimu gwo."
    ),
}


def _keyword_on_topic(question: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", question.lower()))
    return bool(words & _TAX_KEYWORDS)


# ---------------------------------------------------------------------------
# Encryption helpers
# ---------------------------------------------------------------------------

def _get_fernet(settings: Settings) -> Fernet:
    """Derive a Fernet key from the provider_key_secret setting."""
    secret = settings.provider_key_secret.encode()
    # Fernet requires a 32-byte url-safe base64 key. We derive one from the secret.
    key = base64.urlsafe_b64encode(secret.ljust(32, b"\0")[:32])
    return Fernet(key)


def encrypt_api_key(settings: Settings, plaintext: str) -> str:
    return _get_fernet(settings).encrypt(plaintext.encode()).decode()


def decrypt_api_key(settings: Settings, ciphertext: str) -> str:
    return _get_fernet(settings).decrypt(ciphertext.encode()).decode()


# ---------------------------------------------------------------------------
# Provider protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class LLMProvider(Protocol):
    async def is_on_topic(self, question: str, model: str | None = None) -> bool: ...
    async def generate_answer(self, question: str, chunks: list[RetrievedChunk], language_code: str, model: str | None = None) -> LLMResult: ...
    async def rewrite_query(self, question: str, model: str | None = None) -> str: ...


# ---------------------------------------------------------------------------
# Gemini provider
# ---------------------------------------------------------------------------

_TOPIC_PROMPT = (
    "Is the following question about Uganda tax law, URA, VAT, PAYE, "
    "WHT, EFRIS, income tax, registration, penalties, or tax procedures? "
    "Reply with exactly YES or NO.\n\n"
    "Question: {question}"
)

_REWRITE_PROMPT = (
    "Rewrite this tax question into a compact keyword query for Postgres full-text search.\n"
    "Return only keywords in one line.\n\n"
    "{question}"
)


def _rewrite_fallback(question: str) -> str:
    _STOPWORDS = {"the", "is", "a", "an", "for", "and", "or", "to", "of", "in", "on", "with", "uganda", "ura", "tax"}
    words = re.findall(r"[a-zA-Z0-9]+", question.lower())
    keywords = [w for w in words if len(w) > 2 and w not in _STOPWORDS]
    return " ".join(keywords[:12]) or question


def _build_answer_prompt(question: str, chunks: list[RetrievedChunk], language_code: str) -> str:
    is_luganda = language_code.startswith("lg")
    context = "\n\n".join([f"[{idx+1}] {chunk.title} - {chunk.chunk_text}" for idx, chunk in enumerate(chunks)])
    system_prompt = _SYSTEM_PROMPT
    if is_luganda:
        system_prompt += _LUGANDA_RULE + "\n"
    return f"{system_prompt}\nQuestion:\n{question}\n\nEvidence:\n{context}"


class GeminiProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def is_on_topic(self, question: str, model: str | None = None) -> bool:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            m = genai.GenerativeModel(model or "gemini-1.5-flash")
            completion = m.generate_content(_TOPIC_PROMPT.format(question=question))
            reply = (completion.text or "").strip().upper()
            return reply.startswith("YES")
        except Exception:
            return _keyword_on_topic(question)

    async def generate_answer(self, question: str, chunks: list[RetrievedChunk], language_code: str, model: str | None = None) -> LLMResult:
        is_luganda = language_code.startswith("lg")
        fallback_key = "lg" if is_luganda else "en"
        if not chunks:
            fallback = _NO_CHUNKS_FALLBACKS[fallback_key]
            return LLMResult(answer_md=fallback, estimated_input_tokens=_estimate_tokens(question), estimated_output_tokens=40)

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        m = genai.GenerativeModel(model or "gemini-1.5-flash")
        prompt = _build_answer_prompt(question, chunks, language_code)
        completion = m.generate_content(prompt)
        answer_text = (completion.text or "").strip() or "No answer generated."
        return LLMResult(
            answer_md=answer_text,
            estimated_input_tokens=_estimate_tokens(prompt),
            estimated_output_tokens=_estimate_tokens(answer_text),
        )

    async def rewrite_query(self, question: str, model: str | None = None) -> str:
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            m = genai.GenerativeModel(model or "gemini-1.5-flash")
            completion = m.generate_content(_REWRITE_PROMPT.format(question=question))
            text = (completion.text or "").strip()
            return text if text else _rewrite_fallback(question)
        except Exception:
            return _rewrite_fallback(question)


# ---------------------------------------------------------------------------
# Anthropic provider
# ---------------------------------------------------------------------------

class AnthropicProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def is_on_topic(self, question: str, model: str | None = None) -> bool:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            resp = await client.messages.create(
                model=model or "claude-sonnet-4-5-20250929",
                max_tokens=10,
                messages=[{"role": "user", "content": _TOPIC_PROMPT.format(question=question)}],
            )
            reply = resp.content[0].text.strip().upper() if resp.content else ""
            return reply.startswith("YES")
        except Exception:
            return _keyword_on_topic(question)

    async def generate_answer(self, question: str, chunks: list[RetrievedChunk], language_code: str, model: str | None = None) -> LLMResult:
        is_luganda = language_code.startswith("lg")
        fallback_key = "lg" if is_luganda else "en"
        if not chunks:
            fallback = _NO_CHUNKS_FALLBACKS[fallback_key]
            return LLMResult(answer_md=fallback, estimated_input_tokens=_estimate_tokens(question), estimated_output_tokens=40)

        from anthropic import AsyncAnthropic
        client = AsyncAnthropic(api_key=self.api_key)
        system_prompt = _SYSTEM_PROMPT
        if is_luganda:
            system_prompt += _LUGANDA_RULE + "\n"
        context = "\n\n".join([f"[{idx+1}] {chunk.title} - {chunk.chunk_text}" for idx, chunk in enumerate(chunks)])
        user_msg = f"Question:\n{question}\n\nEvidence:\n{context}"

        resp = await client.messages.create(
            model=model or "claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        answer_text = resp.content[0].text.strip() if resp.content else "No answer generated."
        return LLMResult(
            answer_md=answer_text,
            estimated_input_tokens=_estimate_tokens(system_prompt + user_msg),
            estimated_output_tokens=_estimate_tokens(answer_text),
        )

    async def rewrite_query(self, question: str, model: str | None = None) -> str:
        try:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=self.api_key)
            resp = await client.messages.create(
                model=model or "claude-sonnet-4-5-20250929",
                max_tokens=100,
                messages=[{"role": "user", "content": _REWRITE_PROMPT.format(question=question)}],
            )
            text = resp.content[0].text.strip() if resp.content else ""
            return text if text else _rewrite_fallback(question)
        except Exception:
            return _rewrite_fallback(question)


# ---------------------------------------------------------------------------
# OpenAI provider
# ---------------------------------------------------------------------------

class OpenAIProvider:
    def __init__(self, api_key: str):
        self.api_key = api_key

    async def is_on_topic(self, question: str, model: str | None = None) -> bool:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            resp = await client.chat.completions.create(
                model=model or "gpt-4o-mini",
                max_tokens=10,
                messages=[{"role": "user", "content": _TOPIC_PROMPT.format(question=question)}],
            )
            reply = (resp.choices[0].message.content or "").strip().upper()
            return reply.startswith("YES")
        except Exception:
            return _keyword_on_topic(question)

    async def generate_answer(self, question: str, chunks: list[RetrievedChunk], language_code: str, model: str | None = None) -> LLMResult:
        is_luganda = language_code.startswith("lg")
        fallback_key = "lg" if is_luganda else "en"
        if not chunks:
            fallback = _NO_CHUNKS_FALLBACKS[fallback_key]
            return LLMResult(answer_md=fallback, estimated_input_tokens=_estimate_tokens(question), estimated_output_tokens=40)

        from openai import AsyncOpenAI
        client = AsyncOpenAI(api_key=self.api_key)
        system_prompt = _SYSTEM_PROMPT
        if is_luganda:
            system_prompt += _LUGANDA_RULE + "\n"
        context = "\n\n".join([f"[{idx+1}] {chunk.title} - {chunk.chunk_text}" for idx, chunk in enumerate(chunks)])
        user_msg = f"Question:\n{question}\n\nEvidence:\n{context}"

        resp = await client.chat.completions.create(
            model=model or "gpt-4o-mini",
            max_tokens=2048,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        answer_text = (resp.choices[0].message.content or "").strip() or "No answer generated."
        return LLMResult(
            answer_md=answer_text,
            estimated_input_tokens=_estimate_tokens(system_prompt + user_msg),
            estimated_output_tokens=_estimate_tokens(answer_text),
        )

    async def rewrite_query(self, question: str, model: str | None = None) -> str:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=self.api_key)
            resp = await client.chat.completions.create(
                model=model or "gpt-4o-mini",
                max_tokens=100,
                messages=[{"role": "user", "content": _REWRITE_PROMPT.format(question=question)}],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text if text else _rewrite_fallback(question)
        except Exception:
            return _rewrite_fallback(question)


# ---------------------------------------------------------------------------
# Mock provider (no LLM key available)
# ---------------------------------------------------------------------------

class MockProvider:
    async def is_on_topic(self, question: str, model: str | None = None) -> bool:
        return _keyword_on_topic(question)

    async def generate_answer(self, question: str, chunks: list[RetrievedChunk], language_code: str, model: str | None = None) -> LLMResult:
        is_luganda = language_code.startswith("lg")
        fallback_key = "lg" if is_luganda else "en"
        if not chunks:
            fallback = _NO_CHUNKS_FALLBACKS[fallback_key]
            return LLMResult(answer_md=fallback, estimated_input_tokens=_estimate_tokens(question), estimated_output_tokens=40)
        top = chunks[:3]
        bullets = "\n".join([f"- **[{idx+1}]** {chunk.title}: {chunk.chunk_text[:260].strip()}..." for idx, chunk in enumerate(top)])
        prefix = "[Luganda mode \u2014 requires LLM provider]\n\n" if is_luganda else ""
        answer = f"{prefix}Based on the indexed URA corpus:\n\n{bullets}"
        return LLMResult(
            answer_md=answer,
            estimated_input_tokens=_estimate_tokens(question),
            estimated_output_tokens=_estimate_tokens(answer),
        )

    async def rewrite_query(self, question: str, model: str | None = None) -> str:
        return _rewrite_fallback(question)


# ---------------------------------------------------------------------------
# Provider resolution
# ---------------------------------------------------------------------------

_PROVIDER_CLASSES: dict[str, type] = {
    "gemini": GeminiProvider,
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
}


@dataclass
class ResolvedProvider:
    provider: LLMProvider
    is_byok: bool


async def resolve_provider(settings: Settings, session: AsyncSession, user_id: str) -> ResolvedProvider:
    """Resolve the LLM provider for a user. BYOK takes priority, then server Gemini, then mock."""
    if not user_id.startswith("guest:"):
        try:
            row = (
                await session.execute(
                    text("SELECT provider, api_key_encrypted, model_name FROM user_providers WHERE user_id = :user_id ORDER BY updated_at DESC LIMIT 1"),
                    {"user_id": user_id},
                )
            ).mappings().first()
            if row:
                api_key = decrypt_api_key(settings, row["api_key_encrypted"])
                provider_cls = _PROVIDER_CLASSES.get(row["provider"])
                if provider_cls:
                    instance = provider_cls(api_key=api_key)
                    # Attach custom model_name if specified
                    instance._custom_model = row["model_name"]  # type: ignore[attr-defined]
                    return ResolvedProvider(provider=instance, is_byok=True)
        except Exception:
            pass  # Fall through to server defaults

    # Server-side Gemini
    if settings.gemini_enabled and settings.gemini_api_key:
        return ResolvedProvider(provider=GeminiProvider(api_key=settings.gemini_api_key), is_byok=False)

    return ResolvedProvider(provider=MockProvider(), is_byok=False)


async def has_byok_provider(session: AsyncSession, user_id: str) -> bool:
    """Check if user has any BYOK provider configured."""
    if user_id.startswith("guest:"):
        return False
    try:
        row = (
            await session.execute(
                text("SELECT 1 FROM user_providers WHERE user_id = :user_id LIMIT 1"),
                {"user_id": user_id},
            )
        ).first()
        return row is not None
    except Exception:
        return False
