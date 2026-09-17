.PHONY: help dev test

help:
	@echo "  dev   — run the app at http://127.0.0.1:8000 (needs gcloud ADC + .env)"
	@echo "  test  — pytest"

dev:
	uv run uvicorn satimg.app:app --reload --app-dir src

test:
	uv run pytest tests/ -v

screenshot:
	uv run python scripts/screenshot.py http://127.0.0.1:8000/ shot.png
