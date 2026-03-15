"""
SignBridge AI — Whisper Transcription Service.

Singleton wrapper around faster-whisper that loads the model once at startup
and exposes a thread-safe ``transcribe()`` method.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from app.config import settings

logger = logging.getLogger(__name__)


# ─── Data Models ──────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class WordTimestamp:
    """Single word with its time boundaries in the audio."""

    word: str
    start: float
    end: float


@dataclass(frozen=True, slots=True)
class TranscriptResult:
    """Complete transcription result returned by the service."""

    text: str
    words: list[WordTimestamp] = field(default_factory=list)
    duration: float = 0.0
    language: str = "en"


# ─── Service ──────────────────────────────────────────────────


class WhisperService:
    """Singleton service that manages the faster-whisper model lifecycle."""

    _instance: WhisperService | None = None

    def __new__(cls) -> WhisperService:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None  # type: ignore[attr-defined]
            cls._instance._is_loaded = False  # type: ignore[attr-defined]
        return cls._instance

    # ── Model Lifecycle ───────────────────────────────────────

    def load_model(self) -> None:
        """Load the Whisper model into memory (GPU or CPU)."""
        if self._is_loaded:
            logger.info("Whisper model already loaded — skipping.")
            return

        try:
            from faster_whisper import WhisperModel

            start = time.perf_counter()
            self._model = WhisperModel(
                model_size_or_path=settings.whisper_model_size,
                device=settings.whisper_device,
                compute_type=settings.whisper_compute_type,
            )
            elapsed = time.perf_counter() - start
            self._is_loaded = True
            logger.info(
                "Whisper model '%s' loaded on %s in %.2fs",
                settings.whisper_model_size,
                settings.whisper_device,
                elapsed,
            )
        except Exception as exc:
            logger.error("Failed to load Whisper on %s: %s", settings.whisper_device, exc)
            # Attempt CPU fallback
            if settings.whisper_device != "cpu":
                logger.info("Attempting CPU fallback for Whisper model…")
                try:
                    from faster_whisper import WhisperModel

                    self._model = WhisperModel(
                        model_size_or_path=settings.whisper_model_size,
                        device="cpu",
                        compute_type="int8",
                    )
                    self._is_loaded = True
                    logger.info("Whisper model loaded on CPU (fallback).")
                except Exception as fallback_exc:
                    logger.error("CPU fallback also failed: %s", fallback_exc)
                    self._is_loaded = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    # ── Transcription ─────────────────────────────────────────

    def transcribe(self, audio_path: str) -> TranscriptResult:
        """
        Transcribe an audio file and return structured results with word-level
        timestamps.

        Args:
            audio_path: Absolute or relative path to a 16 kHz mono WAV file.

        Returns:
            A ``TranscriptResult`` with full text, per-word timestamps, duration,
            and detected language.

        Raises:
            RuntimeError: If the model is not loaded.
            FileNotFoundError: If the audio file does not exist.
        """
        if not self._is_loaded or self._model is None:
            raise RuntimeError("Whisper model is not loaded. Call load_model() first.")

        from pathlib import Path

        if not Path(audio_path).exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        logger.info("Transcribing: %s", audio_path)
        start = time.perf_counter()

        segments, info = self._model.transcribe(
            audio_path,
            language="en",
            beam_size=1,
            word_timestamps=True,
            vad_filter=True,
            condition_on_previous_text=False,
        )

        # Collect words from all segments
        words: list[WordTimestamp] = []
        full_text_parts: list[str] = []

        for segment in segments:
            full_text_parts.append(segment.text.strip())
            if segment.words:
                for w in segment.words:
                    words.append(
                        WordTimestamp(
                            word=w.word.strip(),
                            start=round(w.start, 3),
                            end=round(w.end, 3),
                        )
                    )

        full_text = " ".join(full_text_parts)
        elapsed = time.perf_counter() - start
        logger.info("Transcription completed in %.2fs — %d words", elapsed, len(words))

        return TranscriptResult(
            text=full_text,
            words=words,
            duration=round(info.duration, 2),
            language=info.language or "en",
        )

    # ── Cleanup ───────────────────────────────────────────────

    def cleanup(self) -> None:
        """Release the model from memory."""
        self._model = None
        self._is_loaded = False
        logger.info("Whisper model released from memory.")


# ─── Module-level singleton ──────────────────────────────────
whisper_service = WhisperService()
