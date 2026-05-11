.PHONY: help install local dev up down migrate seed test lint format scan-demo

help:
	@echo "Targets:"
	@echo "  install       Install Python deps in the current venv"
	@echo "  local         Run the API locally with SQLite (no Docker needed)"
	@echo "  up            Start Postgres + API via docker-compose"
	@echo "  down          Stop docker-compose stack"
	@echo "  dev           Run the API with hot reload (requires Postgres)"
	@echo "  migrate       Apply Alembic migrations"
	@echo "  seed          Load the bundled CVE seed data"
	@echo "  test          Run the test suite"
	@echo "  lint          Run ruff"
	@echo "  format        Auto-fix formatting with ruff"
	@echo "  scan-demo     POST examples/scan_request.json to a running API"

install:
	pip install -r requirements.txt

local:
	python scripts/run_local.py

up:
	docker compose up --build -d

down:
	docker compose down

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	alembic upgrade head

seed:
	python -m app.rag.cve_loader --seed

test:
	pytest -q

lint:
	ruff check .

format:
	ruff check . --fix
	ruff format .

scan-demo:
	curl -sS -X POST http://localhost:8000/scans \
		-H "Content-Type: application/json" \
		-d @examples/scan_request.json | python -m json.tool
