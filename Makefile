.PHONY: setup start-backend start-frontend channels test lint build index-project reindex-project clean

setup:
	@bash scripts/setup.sh

start-backend:
	@.venv/bin/python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000

start-frontend:
	@cd frontend && npm run dev

channels:
	@.venv/bin/python3 -m backend.support.channel_manager

index-project:
	@.venv/bin/python3 -m project_init index $(or $(PROJECT),fixdesk)

reindex-project:
	@.venv/bin/python3 -m project_init reindex $(or $(PROJECT),fixdesk)

test:
	@.venv/bin/pytest tests/ -v

lint:
	@cd frontend && npm run lint

build:
	@cd frontend && npm run build
