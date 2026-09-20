"""Island-wide fire analysis via Earth Engine → outputs/{borneo,sumatra}_fire.json.

Per region (island total + its admin-1 units) and per month 2001–present:
  - fire_km2:  area of 1 km FIRMS pixels with ≥1 MODIS active-fire detection that month
  - burned_km2: MODIS MCD64A1 burned area (500 m), lags ~2 months
Plus daily fire_km2 for the current dry season (from 1 June) for the narrative.

Run:  uv run python scripts/fire_analysis.py [borneo|sumatra]   (default: borneo)
"""

from __future__ import annotations

import json
import sys
from datetime import date, timedelta
from pathlib import Path

import ee

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from satimg import layers  # noqa: E402

OUT_DIR = Path(__file__).resolve().parents[1] / "outputs"
FIRST_YEAR = 2001
TODAY = date.today()

# GAUL 2015 predates the 2012 Kalimantan Utara split; it sits inside Kalimantan Timur here.
BORNEO = {
    "kalbar": ("Kalimantan Barat", ["Kalimantan Barat"]),
    "kalteng": ("Kalimantan Tengah", ["Kalimantan Tengah"]),
    "kalsel": ("Kalimantan Selatan", ["Kalimantan Selatan"]),
    "kaltim": ("Kalimantan Timur (+Utara)", ["Kalimantan Timur"]),
    "sabah": ("Sabah", ["Sabah", "Labuan"]),
    "sarawak": ("Sarawak", ["Sarawak"]),
    "brunei": ("Brunei", ["Belait", "Brunei and Muara", "Temburong", "Tutong"]),
}
SUMATRA = {
    "aceh": ("Aceh", ["Nangroe Aceh Darussalam"]),
    "sumut": ("Sumatera Utara", ["Sumatera Utara"]),
    "sumbar": ("Sumatera Barat", ["Sumatera Barat"]),
    "riau": ("Riau", ["Riau"]),
    "kepri": ("Kepulauan Riau", ["Kepulauan-riau"]),
    "jambi": ("Jambi", ["Jambi"]),
    "sumsel": ("Sumatera Selatan", ["Sumatera Selatan"]),
    "babel": ("Bangka Belitung", ["Bangka Belitung"]),
    "bengkulu": ("Bengkulu", ["Bengkulu"]),
    "lampung": ("Lampung", ["Lampung"]),
}
# island key → (label, bbox, regions)
ISLANDS = {
    "borneo": ("Borneo", [108.5, -4.5, 119.5, 7.5], BORNEO),
    "sumatra": ("Sumatra", [94.5, -6.5, 109.0, 6.5], SUMATRA),
}
ISLAND = sys.argv[1] if len(sys.argv) > 1 else "borneo"
ISLAND_LABEL, BBOX, REGIONS = ISLANDS[ISLAND]
OUT = OUT_DIR / f"{ISLAND}_fire.json"


def region_fc() -> ee.FeatureCollection:
    gaul = ee.FeatureCollection("FAO/GAUL/2015/level1").filterBounds(ee.Geometry.Rectangle(BBOX))
    feats = []
    for key, (label, names) in REGIONS.items():
        geom = gaul.filter(ee.Filter.inList("ADM1_NAME", names)).geometry()
        feats.append(ee.Feature(geom, {"key": key, "label": label}))
    fc = ee.FeatureCollection(feats)
    total = ee.Feature(fc.geometry().dissolve(1000), {"key": ISLAND, "label": ISLAND_LABEL})
    return fc.merge(ee.FeatureCollection([total]))


def footprint_km2(col: ee.ImageCollection, band: str, name: str) -> ee.Image:
    """km² per pixel where ≥1 image in `col` has data; zero everywhere if `col` is empty."""
    present = col.select(band).count().gt(0).unmask(0)
    img = ee.Image(ee.Algorithms.If(col.size().gt(0), present, ee.Image.constant(0)))
    return img.multiply(ee.Image.pixelArea()).divide(1e6).rename(name)


def monthly_bands(year: int, months: list[int]) -> tuple[ee.Image, ee.Image]:
    """Two multi-band images (one band per month): fire footprint and burned area, both in km²."""
    fire_bands, burn_bands = [], []
    for m in months:
        start = ee.Date.fromYMD(year, m, 1)
        end = start.advance(1, "month")
        firms = ee.ImageCollection("FIRMS").filterDate(start, end)
        fire_bands.append(footprint_km2(firms, "T21", f"fire_{m:02d}"))
        mcd = ee.ImageCollection("MODIS/061/MCD64A1").filterDate(start, end)
        burn_bands.append(footprint_km2(mcd, "BurnDate", f"burn_{m:02d}"))
    return ee.Image.cat(fire_bands), ee.Image.cat(burn_bands)


def reduce(img: ee.Image, fc: ee.FeatureCollection, scale: int) -> list[dict]:
    out = img.reduceRegions(collection=fc, reducer=ee.Reducer.sum(), scale=scale, tileScale=4)
    return [f["properties"] for f in out.getInfo()["features"]]


def main() -> None:
    layers.init_ee()
    fc = region_fc()
    rows: dict[str, dict] = {k: {"label": v[0], "monthly": {}} for k, v in REGIONS.items()}
    rows[ISLAND] = {"label": ISLAND_LABEL, "monthly": {}}

    for year in range(FIRST_YEAR, TODAY.year + 1):
        months = list(range(1, 13)) if year < TODAY.year else list(range(1, TODAY.month + 1))
        fire_img, burn_img = monthly_bands(year, months)
        fire = reduce(fire_img, fc, 1000)
        burn = reduce(burn_img, fc, 500)
        for f, b in zip(fire, burn, strict=True):
            for m in months:
                rows[f["key"]]["monthly"][f"{year}-{m:02d}"] = {
                    "fire_km2": round(f.get(f"fire_{m:02d}", 0) or 0, 1),
                    "burned_km2": round(b.get(f"burn_{m:02d}", 0) or 0, 1),
                }
        print(f"{year}: {ISLAND_LABEL} fire {sum(fire[-1].get(f'fire_{m:02d}',0) for m in months):.0f} km²", flush=True)

    # Daily footprint for the current dry season (FIRMS only; MCD64A1 is monthly).
    season_start = date(TODAY.year, 6, 1)
    days = [(season_start + timedelta(d)) for d in range((TODAY - season_start).days + 1)]
    daily_bands = []
    for d in days:
        s = ee.Date(d.isoformat())
        firms = ee.ImageCollection("FIRMS").filterDate(s, s.advance(1, "day"))
        daily_bands.append(footprint_km2(firms, "T21", f"d{d.isoformat()}"))
    daily = reduce(ee.Image.cat(daily_bands), fc, 1000)
    for r in daily:
        rows[r["key"]]["daily"] = {
            d.isoformat(): round(r.get(f"d{d.isoformat()}", 0) or 0, 1) for d in days
        }

    # Simplified region outlines for the map.
    outlines = fc.map(lambda f: f.simplify(2000)).getInfo()

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        json.dumps(
            {
                "generated": TODAY.isoformat(),
                "sources": {
                    "fire_km2": "FIRMS (MODIS active fire, 1 km) — area of pixels with ≥1 detection",
                    "burned_km2": "MODIS/061/MCD64A1 burned area (500 m)",
                    "regions": "FAO GAUL 2015 level 1",
                },
                "regions": rows,
                "outlines": outlines,
            }
        )
    )
    print("wrote", OUT)


if __name__ == "__main__":
    main()
