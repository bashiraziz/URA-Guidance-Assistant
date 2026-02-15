from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Citation(BaseModel):
    source_id: str | None = None
    doc_path: str
    title: str
    section_ref: str | None = None
    page_ref: str | None = None
    snippet: str


class CalculationResult(BaseModel):
    type: str
    inputs: dict[str, Any]
    outputs: dict[str, Any]
    explanation: str


class UsageEnvelope(BaseModel):
    daily_requests_used: int
    daily_requests_remaining: int
    minute_requests_used: int
    minute_requests_remaining: int
    daily_output_tokens_used: int
    daily_output_tokens_remaining: int


class ChatRequest(BaseModel):
    conversation_id: str | None = None
    language_code: str = "en"
    question: str = Field(min_length=3, max_length=4000)


class ChatResponse(BaseModel):
    conversation_id: str
    answer_md: str
    citations: list[Citation]
    calculation: CalculationResult | None = None
    usage: UsageEnvelope


class ConversationSummary(BaseModel):
    id: str
    created_at: datetime
    updated_at: datetime
    latest_question: str | None = None


class MessageModel(BaseModel):
    id: str
    role: str
    content_md: str
    created_at: datetime


class DocsTreeNode(BaseModel):
    path: str
    title: str
    category: str = "General"


class DocsPageResponse(BaseModel):
    path: str
    title: str
    category: str = "General"
    content_md: str


class DocSectionNode(BaseModel):
    id: str
    slug: str
    full_path: str
    title: str
    level: int
    section_ref: str | None = None
    word_count: int = 0
    reading_time_minutes: int = 0
    is_placeholder: bool = False
    children: list["DocSectionNode"] = []


class BreadcrumbItem(BaseModel):
    title: str
    full_path: str


class PrevNextLink(BaseModel):
    title: str
    full_path: str


class DocSectionPage(BaseModel):
    id: str
    full_path: str
    title: str
    section_ref: str | None = None
    content_md: str
    level: int
    word_count: int = 0
    reading_time_minutes: int = 0
    is_placeholder: bool = False
    breadcrumbs: list[BreadcrumbItem] = []
    prev: PrevNextLink | None = None
    next: PrevNextLink | None = None
