"""
SignBridge AI — Health Check Router.

GET /api/health — reports the status of Whisper and Ollama services.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm_service import llm_service
from app.services.whisper_service import whisper_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["health"])


# ─── Response Schema ──────────────────────────────────────────


class HealthResponse(BaseModel):
    """Health check result."""

    status: str
    whisper_loaded: bool
    ollama_available: bool


# ─── Endpoint ─────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Return the operational status of all backend services.

    - **whisper_loaded** — ``True`` when the Whisper model is in memory.
    - **ollama_available** — ``True`` when Ollama responds on its default port.
    """
    ollama_ok = await llm_service.health_check()

    status = "ok" if whisper_service.is_loaded and ollama_ok else "degraded"

    return HealthResponse(
        status=status,
        whisper_loaded=whisper_service.is_loaded,
        ollama_available=ollama_ok,
    )
