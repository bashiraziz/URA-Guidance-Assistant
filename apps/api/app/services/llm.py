from __future__ import annotations

import re
from dataclasses import dataclass

from app.config import Settings
from app.retrieval.base import RetrievedChunk

# ---------------------------------------------------------------------------
# Topic-gating keywords used when Gemini is unavailable
# ---------------------------------------------------------------------------
_TAX_KEYWORDS: set[str] = {
    "vat", "paye", "wht", "efris", "tax", "ura", "income", "withholding",
    "registration", "penalty", "penalties", "filing", "exemption", "exemptions",
    "deduction", "deductions", "assessment", "refund", "invoice", "tin",
    "excise", "customs", "stamp", "duty", "rental", "taxpayer", "revenue",
    "return", "returns", "compliance", "audit", "objection", "tribunal",
    "amendment", "act", "statute", "provision", "section", "schedule",
    "zero-rating", "zero", "rated", "supply", "taxable", "threshold",
    "capital gains", "gains", "allowance", "depreciation", "commissioner",
    # Luganda tax keywords
    "omusolo", "emisolo", "okufayilo", "ebitagobererwa", "ensasula",
    "obwannannyini",
}

_OFF_TOPIC_REPLIES: dict[str, str] = {
    "en": (
        "I can only assist with Uganda tax law and URA-related topics — "
        "VAT, PAYE, WHT, EFRIS, registration, penalties, and related matters. "
        "Please rephrase your question about a tax topic."
    ),
    "lg": (
        "Nsobola okuyamba ku mateeka g'omusolo mu Uganda ne URA byokka — "
        "VAT, PAYE, WHT, EFRIS, okwewandiisa, ebibonoobono, n'ebirala ebikwatagana. "
        "Nsaba oddemu okubuuza ekibuuzo ku musolo."
    ),
}

OFF_TOPIC_REPLY = _OFF_TOPIC_REPLIES["en"]


def get_off_topic_reply(language_code: str) -> str:
    key = "lg" if language_code.startswith("lg") else "en"
    return _OFF_TOPIC_REPLIES[key]


async def is_on_topic(question: str, settings: Settings) -> bool:
    """Return True if *question* is about Uganda tax / URA topics."""

    if settings.gemini_enabled:
        try:
            import google.generativeai as genai  # type: ignore

            if not settings.gemini_api_key:
                return _keyword_on_topic(question)
            genai.configure(api_key=settings.gemini_api_key)
            model = genai.GenerativeModel(settings.gemini_model)
            prompt = (
                "Is the following question about Uganda tax law, URA, VAT, PAYE, "
                "WHT, EFRIS, income tax, registration, penalties, or tax procedures? "
                "Reply with exactly YES or NO.\n\n"
                f"Question: {question}"
            )
            completion = model.generate_content(prompt)
            reply = (completion.text or "").strip().upper()
            return reply.startswith("YES")
        except Exception:
            return _keyword_on_topic(question)

    return _keyword_on_topic(question)


def _keyword_on_topic(question: str) -> bool:
    words = set(re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", question.lower()))
    return bool(words & _TAX_KEYWORDS)


# ---------------------------------------------------------------------------
# LLM answer generation
# ---------------------------------------------------------------------------

@dataclass
class LLMResult:
    answer_md: str
    estimated_input_tokens: int
    estimated_output_tokens: int


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


_GEMINI_SYSTEM_PROMPT = """\
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

_LUGANDA_RULE = (
    "7. Respond ENTIRELY in Luganda (Ganda language). "
    "Translate legal terms but keep Act names and section numbers in English for precision."
)


async def generate_answer(
    settings: Settings,
    question: str,
    chunks: list[RetrievedChunk],
    language_code: str = "en",
) -> LLMResult:
    is_luganda = language_code.startswith("lg")
    fallback_key = "lg" if is_luganda else "en"

    if not chunks:
        fallback = _NO_CHUNKS_FALLBACKS[fallback_key]
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
        system_prompt = _GEMINI_SYSTEM_PROMPT
        if is_luganda:
            system_prompt += _LUGANDA_RULE + "\n"
        prompt = (
            f"{system_prompt}\n"
            f"Question:\n{question}\n\nEvidence:\n{context}"
        )
        completion = model.generate_content(prompt)
        text = (completion.text or "").strip() or "No answer generated."
        return LLMResult(
            answer_md=text,
            estimated_input_tokens=_estimate_tokens(prompt),
            estimated_output_tokens=_estimate_tokens(text),
        )

    # Deterministic mock mode — show evidence snippets only.
    top = chunks[:3]
    bullets = "\n".join([f"- **[{idx+1}]** {chunk.title}: {chunk.chunk_text[:260].strip()}..." for idx, chunk in enumerate(top)])
    prefix = "[Luganda mode — requires Gemini]\n\n" if is_luganda else ""
    answer = (
        f"{prefix}Based on the indexed URA corpus:\n\n"
        f"{bullets}"
    )
    return LLMResult(
        answer_md=answer,
        estimated_input_tokens=_estimate_tokens(question),
        estimated_output_tokens=_estimate_tokens(answer),
    )
