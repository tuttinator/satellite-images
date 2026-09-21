.PHONY: help dev test lint fire haze blog screenshot

help:
	@echo "  dev         run the viewer at http://127.0.0.1:8000 (needs Earth Engine auth + .env)"
	@echo "  test        pytest"
	@echo "  lint        ruff check"
	@echo "  fire        island fire seasons → outputs/{borneo,sumatra}_fire.json (~8 min each, run in parallel)"
	@echo "  haze        daily smoke + fire grids → outputs/sea_haze.json (~2 min)"
	@echo "  blog        copy outputs into a site's static data dir (DEST=path, default ../caleb-tutty.com/...)"
	@echo "  screenshot  headless-Chrome PNG of the running viewer → shot.png"

dev:
	uv run uvicorn satimg.app:app --reload --app-dir src

test:
	uv run pytest tests/ -v

lint:
	uv run ruff check .

fire:
	uv run python scripts/fire_analysis.py borneo & \
	uv run python scripts/fire_analysis.py sumatra & \
	wait

haze:
	uv run python scripts/haze_export.py

blog:
	uv run python scripts/export_blog.py $(if $(DEST),--dest $(DEST),)

screenshot:
	uv run python scripts/screenshot.py http://127.0.0.1:8000/ shot.png
