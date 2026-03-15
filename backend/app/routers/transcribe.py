"""
SignBridge AI — Video Transcription Router.

POST /api/transcribe — accepts a media URL, extracts audio, and returns a
word-level transcript via faster-whisper.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.audio_service import cleanup_audio, extract_audio, validate_and_get_duration
from app.services.whisper_service import whisper_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["transcription"])


# ─── Request / Response Schemas ───────────────────────────────


class TranscribeRequest(BaseModel):
    """Incoming transcription request."""

    url: str = Field(..., description="YouTube URL or direct video/audio link")
    max_duration: int = Field(
        default=3600,
        ge=1,
        le=3600,
        description="Maximum seconds to transcribe",
    )

    @field_validator("url")
    @classmethod
    def url_must_be_http(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v.strip()


class WordTimestamp(BaseModel):
    """A single word with start/end times."""

    word: str
    start: float
    end: float


class TranscribeResponse(BaseModel):
    """Successful transcription result."""

    text: str
    words: list[WordTimestamp]
    duration: float
    language: str


# ─── Endpoint ─────────────────────────────────────────────────


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe(request: TranscribeRequest) -> TranscribeResponse:
    """
    Transcribe a video/audio URL to English text with word-level timestamps.

    **Pipeline:**
    1. Validate URL & check duration via yt-dlp (single metadata call).
    2. Download & convert audio to 16 kHz mono WAV.
    3. Run faster-whisper transcription.
    4. Clean up the temporary audio file.

    **Error codes:**
    - *422* — invalid URL format.
    - *400* — video too long or URL inaccessible.
    - *500* — transcription engine failure.
    """
    # 1. Validate URL & check duration in a single extract_info call
    try:
        duration = await asyncio.to_thread(validate_and_get_duration, request.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if duration > request.max_duration:
        raise HTTPException(
            status_code=400,
            detail=f"Video is {duration:.0f}s — exceeds the {request.max_duration}s limit. Please use a shorter clip.",
        )

    # 2. Extract audio
    audio_path: str | None = None
    try:
        audio_path = await asyncio.to_thread(extract_audio, request.url)

        # 3. Transcribe
        if not whisper_service.is_loaded:
            raise HTTPException(status_code=503, detail="Whisper model is not loaded. Please try again later.")

        result = await asyncio.to_thread(whisper_service.transcribe, audio_path)

        return TranscribeResponse(
            text=result.text,
            words=[
                WordTimestamp(word=w.word, start=w.start, end=w.end)
                for w in result.words
            ],
            duration=result.duration,
            language=result.language,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Transcription pipeline failed")
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}")
    finally:
        # 4. Always clean up
        if audio_path:
            cleanup_audio(audio_path)
