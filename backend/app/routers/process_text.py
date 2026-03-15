"""
SignBridge AI — Text Processing Router.

POST /api/process-text — cleans, simplifies, and tokenises English text for
sign-language display.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field, field_validator

from app.services.llm_service import llm_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["text-processing"])


# ─── Request / Response Schemas ───────────────────────────────


class ProcessTextRequest(BaseModel):
    """Incoming text-processing request."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="English text to simplify for sign language (max 500 chars)",
    )

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Text must not be blank")
        return v.strip()


class TextChange(BaseModel):
    """One transformation that was applied."""

    from_word: str = Field(..., alias="from")
    to_word: str | None = Field(None, alias="to")
    reason: str

    model_config = {"populate_by_name": True}


class ProcessTextResponse(BaseModel):
    """Successful text-processing result."""

    original: str
    processed_words: list[str]
    removed: list[str]
    changes: list[TextChange]
    method: str  # "ollama" | "rule-based"


# ─── Endpoint ─────────────────────────────────────────────────


@router.post("/process-text", response_model=ProcessTextResponse)
async def process_text(request: ProcessTextRequest) -> ProcessTextResponse:
    """
    Clean and simplify English text for sign-language avatar display.

    Processing steps (via Ollama or rule-based fallback):
    - Remove articles, auxiliary verbs, and unnecessary prepositions.
    - Lemmatize verbs and nouns.
    - Expand contractions.
    - Lowercase everything.

    If Ollama is unreachable the endpoint silently falls back to a
    deterministic rule engine — the caller never receives an error.
    """
    result = await llm_service.process_text(request.text)

    return ProcessTextResponse(
        original=result.original,
        processed_words=result.processed_words,
        removed=result.removed,
        changes=[
            TextChange(
                **{"from": c.from_word, "to": c.to_word, "reason": c.reason}
            )
            for c in result.changes
        ],
        method=result.method,
    )
