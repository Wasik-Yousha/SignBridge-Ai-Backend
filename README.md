<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" alt="FastAPI" />
  <img src="https://img.shields.io/badge/faster--whisper-1.1.0-FF6F00&logoColor=white" alt="faster-whisper" />
  <img src="https://img.shields.io/badge/Ollama-LLM-000000?logo=ollama&logoColor=white" alt="Ollama" />
  <img src="https://img.shields.io/badge/License-MIT-green" alt="License" />
</p>

# SignBridge AI — Backend

Python FastAPI backend for the SignBridge AI project. Accepts English text or a video/audio URL, and returns a simplified word sequence suitable for driving an ASL avatar on the frontend.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Development](#development)
- [License](#license)

---

## Overview

The backend exposes three HTTP endpoints:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/health` | GET | Reports Whisper and Ollama service status |
| `/api/transcribe` | POST | Downloads audio from a URL, transcribes it to text with word timestamps |
| `/api/process-text` | POST | Simplifies English text into a sign-ready word list |

Audio transcription is handled by [faster-whisper](https://github.com/SYSTRAN/faster-whisper). Text simplification is handled by a locally running [Ollama](https://ollama.ai) model (default: `mistral:latest`), with a deterministic rule-based fallback when Ollama is unavailable.

---

## Architecture

```
Client (React Frontend)
        │
        ▼
  FastAPI Application
        │
        ├── POST /api/transcribe
        │         │
        │         ├── yt-dlp  ──── Download audio from URL
        │         ├── ffmpeg  ──── Convert to 16 kHz mono WAV
        │         └── faster-whisper ── Transcribe → word timestamps
        │
        └── POST /api/process-text
                  │
                  ├── Ollama (mistral:latest) ── LLM simplification
                  └── Rule-based engine ─────── Fallback (no Ollama needed)
```

Both services are initialized once at startup and held in memory for the lifetime of the process.

---

## Prerequisites

| Dependency | Version | Notes |
|---|---|---|
| Python | 3.11+ | |
| ffmpeg | any recent | Must be on `PATH` |
| Ollama | [latest](https://ollama.ai) | Optional — fallback runs without it |
| CUDA toolkit | 11.x / 12.x | Optional — CPU works without it |

Install ffmpeg on Debian/Ubuntu:

```bash
sudo apt install ffmpeg
```

Install and pull the default model for Ollama:

```bash
curl -fsSL https://ollama.ai/install.sh | sh
ollama pull mistral
```

---

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/Wasik-Yousha/SignBridge-Ai-Backend.git
cd SignBridge-Ai-Backend
```

### 2. Start the server

The `Makefile` handles virtual environment creation, dependency installation, and server startup in a single command:

```bash
make run
```

The server starts at `http://localhost:8000`.  
Interactive API docs are available at `http://localhost:8000/docs`.

To use a different port:

```bash
make run PORT=8001
```

### 3. (Optional) Configure the environment

Copy the example file and edit as needed:

```bash
cp backend/.env.example backend/.env
```

See [Configuration](#configuration) for all available options.

---

## Configuration

All settings are read from environment variables or `backend/.env`. The file is not committed to version control.

| Variable | Default | Description |
|---|---|---|
| `WHISPER_MODEL_SIZE` | `base` | Model size: `tiny`, `base`, `small`, `medium`, `large-v3` |
| `WHISPER_DEVICE` | `cuda` | `cuda` or `cpu`. Falls back to `cpu` automatically if CUDA is unavailable |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` (GPU), `int8` (CPU) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `mistral:latest` | Any model tag available in your Ollama instance |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:5177` | Comma-separated list of allowed frontend origins |
| `TEMP_DIR` | `./temp` | Directory for temporary audio files |
| `MAX_VIDEO_DURATION` | `3600` | Maximum video length in seconds |
| `MAX_TEXT_LENGTH` | `500` | Maximum characters accepted by `/api/process-text` |

---

## API Reference

Full interactive documentation is available at `/docs` (Swagger UI) or `/redoc` when the server is running.

### `GET /api/health`

Returns the operational status of Whisper and Ollama.

**Response**

```json
{
  "status": "ok",
  "whisper_loaded": true,
  "ollama_available": true
}
```

`status` is `"ok"` when both services are up, `"degraded"` otherwise.

---

### `POST /api/transcribe`

Downloads audio from a URL and returns a transcript with word-level timestamps.

**Request body**

```json
{
  "url": "https://www.youtube.com/watch?v=...",
  "max_duration": 3600
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `url` | string | yes | Any URL supported by yt-dlp, or a direct audio/video file link |
| `max_duration` | integer | no | Cap in seconds (1–3600, default 3600) |

**Response**

```json
{
  "text": "hello my name is john",
  "words": [
    { "word": "hello", "start": 0.0,  "end": 0.48 },
    { "word": "my",    "start": 0.52, "end": 0.72 }
  ],
  "duration": 4.5,
  "language": "en"
}
```

**Error codes**

| Code | Cause |
|---|---|
| 422 | URL does not start with `http://` or `https://` |
| 400 | Video exceeds `max_duration`, or URL is inaccessible |
| 500 | Whisper transcription failure |

---

### `POST /api/process-text`

Simplifies English text into a word list for sign-language display.

**Request body**

```json
{
  "text": "I am going to the store to buy some groceries"
}
```

**Response**

```json
{
  "original": "I am going to the store to buy some groceries",
  "processed_words": ["going", "store", "buy", "groceries"],
  "removed": ["I", "am", "to", "the", "to", "some"],
  "changes": [
    { "from": "am",  "to": null, "reason": "auxiliary verb removed" },
    { "from": "the", "to": null, "reason": "article removed" }
  ],
  "method": "ollama"
}
```

`method` is `"ollama"` when the LLM was used, `"rule-based"` when the fallback ran.

---

## Project Structure

```
SignBridge-Ai-Backend/
├── Makefile                    # dev commands: make run, make deps, make venv
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── .gitignore
│   └── app/
│       ├── main.py             # FastAPI app, lifespan, CORS
│       ├── config.py           # Pydantic settings (env vars)
│       ├── routers/
│       │   ├── health.py       # GET /api/health
│       │   ├── transcribe.py   # POST /api/transcribe
│       │   └── process_text.py # POST /api/process-text
│       └── services/
│           ├── whisper_service.py  # faster-whisper singleton
│           ├── llm_service.py      # Ollama client + rule-based fallback
│           └── audio_service.py    # yt-dlp + ffmpeg audio extraction
```

---

## Development

### Available `make` targets

| Command | Description |
|---|---|
| `make run` | Create venv, install deps, start Ollama if needed, run the server |
| `make deps` | Install or update Python dependencies only |
| `make venv` | Create the virtual environment only |

### Running manually (without Make)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit as needed
uvicorn app.main:app --reload --port 8000
```

---

## License

[MIT](https://opensource.org/licenses/MIT)
