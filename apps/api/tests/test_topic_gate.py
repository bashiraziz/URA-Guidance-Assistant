"""Tests for the topic-gating guardrail in llm.py."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services.llm import OFF_TOPIC_REPLY, _keyword_on_topic, get_off_topic_reply, is_on_topic


# ---------------------------------------------------------------------------
# _keyword_on_topic (synchronous, no Gemini)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "question",
    [
        "What is the VAT rate in Uganda?",
        "How do I register for a TIN?",
        "PAYE calculation for monthly salary",
        "What are the penalties for late filing?",
        "Is rental income taxable?",
        "EFRIS invoicing requirements",
        "Withholding tax on services",
        "Excise duty on beer",
        "What does the Income Tax Act say about deductions?",
        "stamp duty on property transfers",
    ],
)
def test_keyword_on_topic_accepts_tax_questions(question: str):
    assert _keyword_on_topic(question) is True


@pytest.mark.parametrize(
    "question",
    [
        "What is the weather today?",
        "Who won the football match?",
        "Tell me a joke",
        "How do I bake a cake?",
        "What is the capital of France?",
        "latest stock prices",
    ],
)
def test_keyword_on_topic_rejects_off_topic(question: str):
    assert _keyword_on_topic(question) is False


# ---------------------------------------------------------------------------
# is_on_topic (async, Gemini disabled → falls back to keyword check)
# ---------------------------------------------------------------------------

@pytest.fixture
def settings_no_gemini() -> Settings:
    """Settings with Gemini disabled (offline / keyword mode)."""
    return Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        gemini_enabled=False,
    )


async def test_is_on_topic_offline_accepts(settings_no_gemini: Settings):
    assert await is_on_topic("What is the VAT rate?", settings_no_gemini) is True


async def test_is_on_topic_offline_rejects(settings_no_gemini: Settings):
    assert await is_on_topic("What is the weather?", settings_no_gemini) is False


# ---------------------------------------------------------------------------
# OFF_TOPIC_REPLY sanity
# ---------------------------------------------------------------------------

def test_off_topic_reply_mentions_tax():
    assert "tax" in OFF_TOPIC_REPLY.lower()
    assert "Uganda" in OFF_TOPIC_REPLY


# ---------------------------------------------------------------------------
# Luganda language support
# ---------------------------------------------------------------------------

def test_get_off_topic_reply_en():
    reply = get_off_topic_reply("en")
    assert "tax" in reply.lower()
    assert "Uganda" in reply


def test_get_off_topic_reply_lg():
    reply = get_off_topic_reply("lg")
    assert "mateeka" in reply.lower()


def test_get_off_topic_reply_lg_ug_prefix():
    reply = get_off_topic_reply("lg-UG")
    assert "mateeka" in reply.lower()


def test_luganda_keyword_omusolo_passes_topic_gate():
    assert _keyword_on_topic("omusolo gwa VAT") is True


def test_luganda_keyword_okufayilo_passes_topic_gate():
    assert _keyword_on_topic("okufayilo kw'emisolo") is True
