"""
SignBridge AI — Application Configuration.

Loads settings from environment variables / .env file using Pydantic Settings.
All configuration is centralized here with sensible defaults.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ─── Whisper ───────────────────────────────────────────────
    whisper_model_size: str = "base"
    whisper_device: str = "cuda"
    whisper_compute_type: str = "float16"

    # ─── Ollama / LLM ─────────────────────────────────────────
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "mistral:latest"

    # ─── CORS ─────────────────────────────────────────────────
    cors_origins: str = "http://localhost:5173,http://localhost:5177"

    # ─── File Storage ─────────────────────────────────────────
    temp_dir: str = "./temp"

    # ─── Limits ───────────────────────────────────────────────
    max_video_duration: int = 3600  # seconds (60 minutes)
    max_text_length: int = 500    # characters

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def temp_path(self) -> Path:
        """Return the temp directory as a resolved Path, creating it if needed."""
        path = Path(self.temp_dir)
        path.mkdir(parents=True, exist_ok=True)
        return path


# ─── Singleton instance ──────────────────────────────────────
settings = Settings()
