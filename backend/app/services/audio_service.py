"""
SignBridge AI — Audio Extraction Service.

Uses yt-dlp to download audio from YouTube / direct video links and convert
it to 16 kHz mono WAV for Whisper consumption.
"""

from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from app.config import settings

logger = logging.getLogger(__name__)

# ─── Common yt-dlp options ─────────────────────────────────────

_YDL_BASE_OPTS: dict = {
    "quiet": True,
    "no_warnings": True,
    "js_runtimes": {"node": {}},
    "remote_components": {"ejs:github"},
}


# ─── URL Validation ───────────────────────────────────────────


def validate_url(url: str) -> bool:
    """
    Check that *url* is a valid, downloadable media URL.

    Uses yt-dlp's ``extract_info(download=False)`` so we don't fetch any bytes.
    Returns ``True`` when valid, ``False`` otherwise.
    """
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL(_YDL_BASE_OPTS) as ydl:
            ydl.extract_info(url, download=False)
        return True
    except Exception:
        return False


def get_duration(url: str) -> float:
    """
    Return the duration of the media at *url* in seconds (without downloading).

    Raises ``ValueError`` if the duration cannot be determined.
    """
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL(_YDL_BASE_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration")  # type: ignore[union-attr]
            if duration is None:
                raise ValueError("Could not determine video duration")
            return float(duration)
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(f"Cannot access URL: {exc}") from exc


def validate_and_get_duration(url: str) -> float:
    """
    Validate the URL and return its duration in a single ``extract_info`` call.

    Raises ``ValueError`` if the URL is invalid or the duration is unavailable.
    """
    import yt_dlp

    try:
        with yt_dlp.YoutubeDL(_YDL_BASE_OPTS) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get("duration")  # type: ignore[union-attr]
            if duration is None:
                raise ValueError("Could not determine video duration")
            return float(duration)
    except yt_dlp.utils.DownloadError as exc:
        raise ValueError(f"Cannot access URL: {exc}") from exc


# ─── Audio Extraction ─────────────────────────────────────────


def extract_audio(url: str, output_dir: str | Path | None = None) -> str:
    """
    Download audio from *url* and convert to 16 kHz mono WAV.

    Args:
        url: YouTube URL or direct video/audio link.
        output_dir: Directory for the temp file (defaults to ``settings.temp_path``).

    Returns:
        Absolute path to the extracted WAV file.

    Raises:
        RuntimeError: If yt-dlp fails to download or convert.
    """
    import yt_dlp

    out_dir = Path(output_dir) if output_dir else settings.temp_path
    out_dir.mkdir(parents=True, exist_ok=True)

    file_stem = str(uuid4())
    output_template = str(out_dir / file_stem)

    ydl_opts: dict = {
        **_YDL_BASE_OPTS,
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
            }
        ],
        "postprocessor_args": {"FFmpegExtractAudio": [
            "-ar", "16000",   # 16 kHz sample rate
            "-ac", "1",       # mono
        ]},
        "outtmpl": output_template,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
    except yt_dlp.utils.DownloadError as exc:
        raise RuntimeError(f"Audio extraction failed: {exc}") from exc

    # yt-dlp adds the codec extension after our template
    wav_path = out_dir / f"{file_stem}.wav"
    if not wav_path.exists():
        # Some versions keep the original extension — try to find the file
        candidates = list(out_dir.glob(f"{file_stem}.*"))
        if candidates:
            wav_path = candidates[0]
        else:
            raise RuntimeError("Audio extraction produced no output file.")

    logger.info("Audio extracted → %s", wav_path)
    return str(wav_path)


# ─── Cleanup ──────────────────────────────────────────────────


def cleanup_audio(file_path: str) -> None:
    """Delete a temporary audio file if it exists."""
    path = Path(file_path)
    if path.exists():
        path.unlink()
        logger.info("Cleaned up temp audio: %s", path.name)
