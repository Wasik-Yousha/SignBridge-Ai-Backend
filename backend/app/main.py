"""
SignBridge AI — FastAPI Application Entry Point.

Configures CORS, mounts routers, sets up logging, and manages the
startup / shutdown lifecycle (Whisper model loading, Ollama check).
"""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import health, process_text, transcribe
from app.services.llm_service import llm_service
from app.services.whisper_service import whisper_service

# ─── Logging ──────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s │ %(levelname)-7s │ %(name)s │ %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("signbridge")


# ─── ASCII Banner ─────────────────────────────────────────────

BANNER = r"""
╔══════════════════════════════════════════════╗
║        🤟  SignBridge AI  Backend  🤟        ║
╠══════════════════════════════════════════════╣
║  ASL Avatar Translation Engine — v1.0        ║
╚══════════════════════════════════════════════╝
"""


# ─── Lifespan (startup / shutdown) ────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown."""
    # ── Startup ───────────────────────────────────────────────
    print(BANNER)

    # Load Whisper model
    logger.info("Loading Whisper model (%s on %s)…", settings.whisper_model_size, settings.whisper_device)
    whisper_service.load_model()
    whisper_status = "✓" if whisper_service.is_loaded else "✗"

    # Check Ollama
    ollama_ok = await llm_service.health_check()
    ollama_status = "✓" if ollama_ok else "✗"

    logger.info("─── Startup Summary ───")
    logger.info("  Whisper : %s  (model=%s, device=%s)", whisper_status, settings.whisper_model_size, settings.whisper_device)
    logger.info("  Ollama  : %s  (url=%s, model=%s)", ollama_status, settings.ollama_base_url, settings.ollama_model)
    logger.info("  CORS    : %s", settings.cors_origin_list)
    logger.info("  Server  : http://localhost:8000")
    logger.info("  Docs    : http://localhost:8000/docs")
    logger.info("───────────────────────")

    yield

    # ── Shutdown ──────────────────────────────────────────────
    logger.info("Shutting down…")
    whisper_service.cleanup()
    await llm_service.close()
    logger.info("Goodbye 👋")


# ─── App Instance ─────────────────────────────────────────────

app = FastAPI(
    title="SignBridge AI",
    description="Backend API for ASL avatar translation — text processing & video transcription.",
    version="1.0.0",
    lifespan=lifespan,
)


# ─── CORS Middleware ──────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Logging Middleware ───────────────────────────────


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request with method, path, and duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start
    logger.info(
        "%s %s → %d (%.2fs)",
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


# ─── Global Exception Handler ─────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch any unhandled exceptions — never expose internals to the client."""
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred. Please try again later."},
    )


# ─── Routers ──────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(transcribe.router)
app.include_router(process_text.router)


# ─── Root ─────────────────────────────────────────────────────


@app.get("/", tags=["root"])
async def root():
    """Simple root endpoint confirming the backend is alive."""
    return {"message": "SignBridge AI Backend", "version": "1.0.0"}
