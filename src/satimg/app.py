"""FastAPI app: serves the static viewer plus a thin JSON API over layers.py."""

from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from satimg import layers

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / "static"
CONCESSIONS = json.loads((ROOT / "data" / "concessions.geojson").read_text())

TILE_TTL = 3 * 3600  # EE map ids expire after a few hours; refresh before that.
_cache: dict[str, tuple[float, Any]] = {}


def cached(key: str, ttl: float, fn):
    now = time.time()
    hit = _cache.get(key)
    if hit and now - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (now, val)
    return val


_ee_ready = False


def ee_call(fn):
    global _ee_ready
    try:
        if not _ee_ready:
            layers.init_ee()
            _ee_ready = True
        return fn()
    except Exception as exc:  # EE raises a grab-bag of exception types
        msg = str(exc)
        if any(k in msg.lower() for k in ("authorize", "reauthentication", "not initialized")):
            raise HTTPException(
                503,
                "Earth Engine auth failed. Run `gcloud auth application-default login` "
                "and restart the server.",
            ) from exc
        raise HTTPException(502, f"Earth Engine error: {msg}") from exc


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _ee_ready
    try:
        layers.init_ee()
        _ee_ready = True
    except Exception as exc:  # start anyway so the UI can show the error
        print(f"[satimg] Earth Engine init failed: {exc}")
    yield


app = FastAPI(title="Palangka Raya forest viewer", lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=10_000)


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/concessions")
def concessions():
    return CONCESSIONS


@app.get("/api/context")
def context():
    path = ROOT / "data" / "context.geojson"
    if not path.exists():
        raise HTTPException(404, "run `uv run python scripts/build_context.py` first")
    return FileResponse(path, media_type="application/geo+json")


@app.get("/api/layers")
def layer_list():
    return [{"id": k, "label": v} for k, v in layers.LAYER_LABELS.items()]


@app.get("/api/tiles")
def tiles(
    layer: str = Query("rgb"),
    start: str = Query(...),
    end: str = Query(...),
    before_start: str | None = None,
    before_end: str | None = None,
):
    if layer in ("change", "dnbr"):
        if not (before_start and before_end):
            raise HTTPException(400, f"{layer} layer needs before_start and before_end")
        fn = layers.change_tile_url if layer == "change" else layers.change_tile_url_nbr
        key = f"{layer}|{before_start}|{before_end}|{start}|{end}"
        url = cached(
            key, TILE_TTL, lambda: ee_call(lambda: fn((before_start, before_end), (start, end)))
        )
    elif layer == "fire":
        key = f"fire|{start}|{end}"
        url = cached(key, TILE_TTL, lambda: ee_call(lambda: layers.fire_tile_url(start, end)))
    else:
        key = f"{layer}|{start}|{end}"
        url = cached(key, TILE_TTL, lambda: ee_call(lambda: layers.tile_url(layer, start, end)))
    return {"url": url, "layer": layer, "start": start, "end": end}


@app.get("/api/timeseries")
def timeseries(
    id: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
    index: str = Query("NDVI", pattern="^(NDVI|NBR|NDMI)$"),
):
    feat = next((f for f in CONCESSIONS["features"] if f["id"] == id), None)
    if feat is None:
        raise HTTPException(404, f"unknown concession {id!r}")
    key = f"ts|{id}|{index}|{start}|{end}"
    rows = cached(
        key,
        24 * 3600,
        lambda: ee_call(lambda: layers.monthly_timeseries(feat["geometry"], start, end, index)),
    )
    return {"id": id, "index": index, "rows": rows}


def _feature(id: str) -> dict:
    feat = next((f for f in CONCESSIONS["features"] if f["id"] == id), None)
    if feat is None:
        raise HTTPException(404, f"unknown concession {id!r}")
    return feat


@app.get("/api/fire/weekly")
def fire_weekly(id: str = Query(...), years: str = Query("2015,2019,2023,2025,2026")):
    feat = _feature(id)
    ys = sorted({int(y) for y in years.split(",")})
    key = f"fw|{id}|{ys}"
    data = cached(
        key, 24 * 3600, lambda: ee_call(lambda: layers.weekly_fire(feat["geometry"], ys))
    )
    return {"id": id, "years": data}


@app.get("/api/fire/burned")
def fire_burned(
    id: str = Query(...),
    before_start: str = Query(...),
    before_end: str = Query(...),
    start: str = Query(...),
    end: str = Query(...),
):
    feat = _feature(id)
    key = f"burn|{id}|{before_start}|{before_end}|{start}|{end}"
    data = cached(
        key,
        24 * 3600,
        lambda: ee_call(
            lambda: layers.burned_area_ha(feat["geometry"], (before_start, before_end), (start, end))
        ),
    )
    return {"id": id, **data}


@app.get("/story")
def story():
    return FileResponse(STATIC / "story.html")


@app.get("/api/fire/{island}")
def island_fire(island: str):
    if island not in ("borneo", "sumatra"):
        raise HTTPException(404, "unknown island")
    path = ROOT / "outputs" / f"{island}_fire.json"
    if not path.exists():
        raise HTTPException(404, f"run `uv run python scripts/fire_analysis.py {island}` first")
    return FileResponse(path)


app.mount("/static", StaticFiles(directory=STATIC), name="static")
