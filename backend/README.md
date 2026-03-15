# SignBridge AI — Backend

Python FastAPI backend that powers the SignBridge AI sign-language avatar.

## Features

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/` | GET | Root — confirms backend is alive |
| `/api/health` | GET | Service health (Whisper + Ollama status) |
| `/api/transcribe` | POST | Video/audio URL → word-level transcript |
| `/api/process-text` | POST | English text → simplified word list for signing |
| `/docs` | GET | Interactive Swagger UI |

---

## Prerequisites

| Dependency | Install |
|-----------|---------|
| Python 3.11+ | `python3 --version` |
| pip | `pip --version` |
| ffmpeg | `sudo apt install ffmpeg` |
| NVIDIA GPU + CUDA 12.x | `nvcc --version` (optional — falls back to CPU) |
| Ollama | [https://ollama.ai](https://ollama.ai) |
| Llama 3.1 8B | `ollama pull llama3.1:8b` |

---

## Quick Start

```bash
# 1. Navigate to backend
cd backend

# 2. Create & activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy environment config
cp .env.example .env      # edit .env if needed

# 5. Start Ollama (separate terminal)
ollama serve

# 6. Start the backend server
uvicorn app.main:app --reload --port 8000
```

The server is now running at **http://localhost:8000**.  
API docs are at **http://localhost:8000/docs**.

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WHISPER_MODEL_SIZE` | `base` | Whisper model: tiny, base, small, medium, large-v3 |
| `WHISPER_DEVICE` | `cuda` | `cuda` for GPU, `cpu` for CPU |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` (GPU), `int8` (CPU) |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama API address |
| `OLLAMA_MODEL` | `llama3.1:8b` | LLM model for text processing |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |
| `TEMP_DIR` | `./temp` | Temporary audio file directory |
| `MAX_VIDEO_DURATION` | `300` | Maximum video length in seconds |
| `MAX_TEXT_LENGTH` | `500` | Maximum input text characters |

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py              # Package marker
│   ├── main.py                  # FastAPI app, CORS, lifespan, routers
│   ├── config.py                # Pydantic Settings (env loading)
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py            # GET  /api/health
│   │   ├── transcribe.py        # POST /api/transcribe
│   │   └── process_text.py      # POST /api/process-text
│   └── services/
│       ├── __init__.py
│       ├── whisper_service.py   # faster-whisper singleton
│       ├── audio_service.py     # yt-dlp audio extraction
│       └── llm_service.py       # Ollama client + rule-based fallback
├── temp/                        # Temporary audio files (gitignored)
│   └── .gitkeep
├── .env                         # Local config (gitignored)
├── .env.example                 # Config template
├── requirements.txt             # Pinned Python dependencies
└── README.md                    # This file
```

---

## API Examples

### Health Check

```bash
curl http://localhost:8000/api/health
```

```json
{ "status": "ok", "whisper_loaded": true, "ollama_available": true }
```

### Process Text

```bash
curl -X POST http://localhost:8000/api/process-text \
  -H "Content-Type: application/json" \
  -d '{"text": "I am going to the store to buy some groceries"}'
```

```json
{
  "original": "I am going to the store to buy some groceries",
  "processed_words": ["i", "go", "store", "buy", "grocery"],
  "removed": ["am", "to", "the", "some"],
  "changes": [...],
  "method": "ollama"
}
```

### Transcribe Video

```bash
curl -X POST http://localhost:8000/api/transcribe \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"}'
```

```json
{
  "text": "Never gonna give you up...",
  "words": [{"word": "never", "start": 0.0, "end": 0.4}, ...],
  "duration": 212.0,
  "language": "en"
}
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `CUDA out of memory` | Set `WHISPER_DEVICE=cpu` and `WHISPER_COMPUTE_TYPE=int8` in `.env` |
| `Ollama connection refused` | Run `ollama serve` in a separate terminal |
| `ffmpeg not found` | Install: `sudo apt install ffmpeg` |
| `ModuleNotFoundError` | Activate venv: `source venv/bin/activate` |
| Text processing returns `rule-based` | Ollama is down — start it with `ollama serve` |
