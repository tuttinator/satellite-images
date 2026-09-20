"""Daily smoke + fire grids for maritime Southeast Asia → outputs/sea_haze.json.

For each UTC day from START to the latest complete day:
  - pm25:  CAMS NRT surface PM2.5 (µg/m³), mean of the freshest forecast steps (< 12 h lead)
           on the native 0.4° grid. This is a *model* field (it assimilates satellite AOD), not
           a measurement; it is known to under-read extreme peat-smoke episodes near source.
  - aod:   CAMS NRT organic-matter aerosol optical depth at 550 nm — the smoke in the whole
           column, which is what travels; surface PM2.5 far downwind can stay low while this rises.
  - fires: FIRMS (MODIS 1 km) active-fire footprint in km² per 0.1° cell, stored sparse.
Plus the PM2.5 series at a handful of cities (nearest CAMS cell).

Run:  uv run python scripts/haze_export.py [YYYY-MM-DD start]   (default: 15 July this year)
"""

from __future__ import annotations

import base64
import io
import json
import math
import sys
from datetime import date, timedelta
from pathlib import Path

import ee
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from satimg import layers  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "outputs" / "sea_haze.json"
TODAY = date.today()
START = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date(TODAY.year, 7, 15)

# Aligned to the CAMS grid (origin -180.2, 90.2; 0.4° cells).
LON0, LAT0 = 93.0, 21.4  # top-left corner
PM_D, PM_W, PM_H = 0.4, 92, 75  # → 129.8°E, 8.6°S
FIRE_D, FIRE_W, FIRE_H = 0.1, 368, 300
PM_BAND = "particulate_matter_d_less_than_25_um_surface"
PM_Q = 6.0  # uint8 = round(sqrt(µg/m³) × PM_Q), saturates at ~1800
AOD_BAND = "organic_matter_aerosol_optical_depth_at_550nm_surface"
AOD_Q = 110.0  # uint8 = round(sqrt(AOD) × AOD_Q), saturates at ~5.4
CHUNK = 12  # days per computePixels request

CITIES = {
    "Pekanbaru": (101.45, 0.51),
    "Jambi": (103.61, -1.61),
    "Palembang": (104.75, -2.98),
    "Pontianak": (109.33, -0.03),
    "Palangka Raya": (113.92, -2.21),
    "Kuching": (110.35, 1.55),
    "Singapore": (103.82, 1.35),
    "Kuala Lumpur": (101.69, 3.14),
    "Bandar Seri Begawan": (114.94, 4.90),
    "Ho Chi Minh City": (106.63, 10.82),
    "Cebu": (123.89, 10.32),
    "Manila": (120.98, 14.60),
    "Jakarta": (106.85, -6.21),
}


def cams_day(d: date, band: str, mult: float) -> ee.Image:
    s = ee.Date(d.isoformat())
    col = (
        ee.ImageCollection("ECMWF/CAMS/NRT")
        .filterDate(s, s.advance(1, "day"))
        .filter(ee.Filter.lt("model_forecast_hour", 12))
        .select(band)
    )
    return col.mean().multiply(mult).rename(f"d{d:%Y%m%d}")


def fire_day(d: date) -> ee.Image:
    """Fraction of each 0.1° cell covered by FIRMS pixels with ≥1 detection that day."""
    s = ee.Date(d.isoformat())
    col = ee.ImageCollection("FIRMS").filterDate(s, s.advance(1, "day")).select("T21")
    proj = ee.ImageCollection("FIRMS").first().projection()
    present = col.count().gt(0).unmask(0).setDefaultProjection(proj)
    return present.reduceResolution(ee.Reducer.mean(), maxPixels=1024).rename(f"d{d:%Y%m%d}")


def fetch(img: ee.Image, scale: float, w: int, h: int) -> np.ndarray:
    """(bands, h, w) float array on the export grid."""
    raw = ee.data.computePixels(
        {
            "expression": img,
            "fileFormat": "NPY",
            "grid": {
                "dimensions": {"width": w, "height": h},
                "affineTransform": {
                    "scaleX": scale, "shearX": 0, "translateX": LON0,
                    "shearY": 0, "scaleY": -scale, "translateY": LAT0,
                },
                "crsCode": "EPSG:4326",
            },
        }
    )
    arr = np.load(io.BytesIO(raw))
    return np.stack([arr[n] for n in arr.dtype.names]).astype("float64")


def main() -> None:
    layers.init_ee()
    firms_last = ee.Date(
        ee.ImageCollection("FIRMS").filterDate(START.isoformat(), "2100-01-01")
        .aggregate_max("system:time_start")
    ).format("YYYY-MM-dd").getInfo()
    end = min(date.fromisoformat(firms_last), TODAY - timedelta(1))
    days = [START + timedelta(n) for n in range((end - START).days + 1)]

    pm, aod, fire = [], [], []
    for i in range(0, len(days), CHUNK):
        chunk = days[i : i + CHUNK]
        pm.append(fetch(ee.Image.cat([cams_day(d, PM_BAND, 1e9) for d in chunk]), PM_D, PM_W, PM_H))
        aod.append(fetch(ee.Image.cat([cams_day(d, AOD_BAND, 1) for d in chunk]), PM_D, PM_W, PM_H))
        fire.append(fetch(ee.Image.cat([fire_day(d) for d in chunk]), FIRE_D, FIRE_W, FIRE_H))
        print(f"{chunk[0]} … {chunk[-1]}", flush=True)
    pm = np.nan_to_num(np.concatenate(pm))
    aod = np.nan_to_num(np.concatenate(aod))
    fire = np.nan_to_num(np.concatenate(fire))

    # km² per 0.1° cell, by row
    lat = LAT0 - FIRE_D * (np.arange(FIRE_H) + 0.5)
    cell_km2 = (111.32 * FIRE_D) ** 2 * np.cos(np.radians(lat))
    fire_km2 = fire * cell_km2[None, :, None]

    fires = []
    for f in fire_km2:
        ys, xs = np.nonzero(f >= 0.5)
        fires.append([[int(x), int(y), round(float(f[y, x]), 1)] for y, x in zip(ys, xs, strict=True)])

    q = np.clip(np.rint(np.sqrt(pm) * PM_Q), 0, 255).astype("uint8")
    qa = np.clip(np.rint(np.sqrt(aod) * AOD_Q), 0, 255).astype("uint8")
    cities = {}
    for name, (lon, la) in CITIES.items():
        x, y = math.floor((lon - LON0) / PM_D), math.floor((LAT0 - la) / PM_D)
        cities[name] = {
            "lon": lon, "lat": la,
            "pm25": [round(float(v), 1) for v in pm[:, y, x]],
            "aod": [round(float(v), 2) for v in aod[:, y, x]],
        }

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "generated": TODAY.isoformat(),
                "sources": {
                    "aod": "ECMWF/CAMS/NRT organic-matter AOD at 550 nm, same averaging as pm25",
                    "pm25": "ECMWF/CAMS/NRT surface PM2.5, daily mean of forecast steps < 12 h (UTC day)",
                    "fires": "FIRMS (MODIS active fire, 1 km) — km² of pixels with ≥1 detection per 0.1° cell",
                },
                "days": [d.isoformat() for d in days],
                "pm25": {
                    "lon0": LON0, "lat0": LAT0, "d": PM_D, "w": PM_W, "h": PM_H, "q": PM_Q,
                    "encoding": "base64 uint8 per day, row-major from top-left; µg/m³ = (v / q)²",
                    "frames": [base64.b64encode(f.tobytes()).decode() for f in q],
                },
                "aod": {
                    "lon0": LON0, "lat0": LAT0, "d": PM_D, "w": PM_W, "h": PM_H, "q": AOD_Q,
                    "encoding": "base64 uint8 per day, row-major from top-left; AOD = (v / q)²",
                    "frames": [base64.b64encode(f.tobytes()).decode() for f in qa],
                },
                "fires": {"lon0": LON0, "lat0": LAT0, "d": FIRE_D, "cells": fires},
                "fire_km2_total": [round(float(f.sum()), 1) for f in fire_km2],
                "cities": cities,
            },
            separators=(",", ":"),
        )
    )
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.2f} MB, {len(days)} days to {end}")


if __name__ == "__main__":
    main()
