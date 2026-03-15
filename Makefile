SHELL := /bin/bash

BACKEND_DIR := backend
VENV_DIR := $(BACKEND_DIR)/.venv
PYTHON := python3
PIP := $(VENV_DIR)/bin/pip
UVICORN := $(VENV_DIR)/bin/uvicorn
OLLAMA_URL := http://localhost:11434/api/tags
PORT ?= 8000
HEALTH_URL := http://localhost:$(PORT)/api/health

.PHONY: help venv deps env ollama run

help:
	@echo "SignBridge backend commands:"
	@echo "  make run   - Create venv, install deps, ensure Ollama is up, run API"
	@echo "              If already running on :$(PORT), exits successfully"
	@echo "  make deps  - Install/update backend Python dependencies"
	@echo "  make venv  - Create backend virtual environment"

venv:
	@if [ ! -d "$(VENV_DIR)" ]; then \
		echo "Creating virtual environment at $(VENV_DIR)..."; \
		$(PYTHON) -m venv "$(VENV_DIR)"; \
	else \
		echo "Virtual environment already exists: $(VENV_DIR)"; \
	fi

deps: venv
	@echo "Installing backend dependencies..."
	@"$(PIP)" install -r "$(BACKEND_DIR)/requirements.txt"

env:
	@if [ ! -f "$(BACKEND_DIR)/.env" ] && [ -f "$(BACKEND_DIR)/.env.example" ]; then \
		echo "Creating $(BACKEND_DIR)/.env from .env.example"; \
		cp "$(BACKEND_DIR)/.env.example" "$(BACKEND_DIR)/.env"; \
	fi

ollama:
	@if ! command -v ollama >/dev/null 2>&1; then \
		echo "Warning: ollama is not installed. Skipping auto-start."; \
		echo "Install from https://ollama.ai and run: ollama serve"; \
	elif curl -fsS "$(OLLAMA_URL)" >/dev/null 2>&1; then \
		echo "Ollama is already running."; \
	else \
		echo "Starting Ollama in background..."; \
		nohup ollama serve >/tmp/signbridge-ollama.log 2>&1 & \
		sleep 2; \
		if curl -fsS "$(OLLAMA_URL)" >/dev/null 2>&1; then \
			echo "Ollama is up."; \
		else \
			echo "Warning: Ollama did not become ready. Check /tmp/signbridge-ollama.log"; \
		fi; \
	fi

run: deps env ollama
	@if curl -fsS "$(HEALTH_URL)" >/dev/null 2>&1; then \
		echo "Backend already running at http://localhost:$(PORT)"; \
	elif command -v lsof >/dev/null 2>&1 && lsof -ti:$(PORT) >/dev/null 2>&1; then \
		echo "Port $(PORT) is in use by another process."; \
		echo "Stop it first, or run with a different port: make run PORT=8001"; \
		exit 1; \
	else \
		echo "Starting backend at http://localhost:$(PORT) ..."; \
		cd "$(BACKEND_DIR)" && ./.venv/bin/uvicorn app.main:app --reload --port "$(PORT)"; \
	fi
