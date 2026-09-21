"""Sentinel-2 composites and forest-health indices via Earth Engine.

Imagery: COPERNICUS/S2_SR_HARMONIZED (surface reflectance, scaled 0–10000),
cloud-masked with Cloud Score+ (cs_cdf band). Everything here returns either
an ee.Image or plain JSON-able data; the FastAPI layer does the caching.
"""

from __future__ import annotations

import os
from datetime import date

import ee
from dotenv import load_dotenv

S2 = "COPERNICUS/S2_SR_HARMONIZED"
CLOUD_SCORE = "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
CLEAR_THRESHOLD = 0.6  # cs_cdf >= this counts as clear (Google's recommended 0.5–0.65)

def init_ee(project: str | None = None) -> None:
    """Authenticate with Earth Engine: stored credentials or gcloud ADC, plus EE_PROJECT_ID (see README)."""
    load_dotenv()
    project = project or os.environ.get("EE_PROJECT_ID")
    if not project:
        raise RuntimeError("EE_PROJECT_ID is unset. Copy .env.example to .env and set it.")
    ee.Initialize(project=project)


def masked_collection(start: str, end: str, region: ee.Geometry | None = None) -> ee.ImageCollection:
    col = ee.ImageCollection(S2).filterDate(start, end)
    cs = ee.ImageCollection(CLOUD_SCORE).filterDate(start, end)
    if region is not None:
        col = col.filterBounds(region)
        cs = cs.filterBounds(region)

    def mask(img: ee.Image) -> ee.Image:
        return img.updateMask(img.select("cs_cdf").gte(CLEAR_THRESHOLD))

    return col.linkCollection(cs, ["cs_cdf"]).map(mask)


def composite(start: str, end: str) -> ee.Image:
    """Median cloud-free composite over [start, end)."""
    return masked_collection(start, end).median()


def add_indices(img: ee.Image) -> ee.Image:
    ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
    nbr = img.normalizedDifference(["B8", "B12"]).rename("NBR")
    ndmi = img.normalizedDifference(["B8", "B11"]).rename("NDMI")
    return img.addBands([ndvi, nbr, ndmi])


# Visualisation presets. Keys are what the frontend sends as ?layer=.
VIS = {
    "rgb": {"bands": ["B4", "B3", "B2"], "min": 0, "max": 3000, "gamma": 1.3},
    "false": {"bands": ["B8", "B4", "B3"], "min": 0, "max": 4000, "gamma": 1.2},
    "swir": {"bands": ["B12", "B8", "B4"], "min": 0, "max": 4000, "gamma": 1.2},
    "ndvi": {
        "bands": ["NDVI"],
        "min": 0.0,
        "max": 0.9,
        "palette": ["a50026", "f46d43", "fee08b", "d9ef8b", "66bd63", "006837"],
    },
    "nbr": {
        "bands": ["NBR"],
        "min": -0.2,
        "max": 0.8,
        "palette": ["7f3b08", "fdb863", "f7f7f7", "b2abd2", "542788"],
    },
    "ndmi": {
        "bands": ["NDMI"],
        "min": -0.2,
        "max": 0.6,
        "palette": ["8c510a", "f6e8c3", "c7eae5", "01665e"],
    },
}

CHANGE_VIS = {
    "bands": ["dNDVI"],
    "min": -0.4,
    "max": 0.4,
    # loss = red, no change = transparent-ish grey, gain = blue
    "palette": ["b2182b", "ef8a62", "fddbc7", "f7f7f7", "d1e5f0", "67a9cf", "2166ac"],
}

LAYER_LABELS = {
    "rgb": "True colour",
    "false": "False colour (NIR)",
    "swir": "SWIR (burn / moisture)",
    "ndvi": "NDVI (greenness)",
    "nbr": "NBR (burn ratio)",
    "ndmi": "NDMI (canopy moisture)",
    "change": "NDVI change (before → after)",
    "dnbr": "Burn scars — dNBR (before → after)",
    "fire": "Active fires — FIRMS hotspots",
}


def tile_url(layer: str, start: str, end: str) -> str:
    if layer not in VIS:
        raise ValueError(f"unknown layer {layer!r}; choose from {sorted(VIS)}")
    img = add_indices(composite(start, end))
    return img.getMapId(VIS[layer])["tile_fetcher"].url_format


def change_tile_url(before: tuple[str, str], after: tuple[str, str]) -> str:
    """dNDVI = NDVI(after) − NDVI(before). Strong negatives = canopy loss."""
    a = add_indices(composite(*after)).select("NDVI")
    b = add_indices(composite(*before)).select("NDVI")
    d = a.subtract(b).rename("dNDVI")
    # Hide near-zero change so the basemap shows through.
    d = d.updateMask(d.abs().gt(0.08))
    return d.getMapId(CHANGE_VIS)["tile_fetcher"].url_format


def change_tile_url_nbr(before: tuple[str, str], after: tuple[str, str]) -> str:
    """dNBR = NBR(before) − NBR(after). USGS classes: >0.27 moderate burn, >0.66 high severity."""
    b = add_indices(composite(*before)).select("NBR")
    a = add_indices(composite(*after)).select("NBR")
    d = b.subtract(a).rename("dNBR").updateMask(b.subtract(a).gt(0.1))
    return d.getMapId(DNBR_VIS)["tile_fetcher"].url_format


DNBR_VIS = {
    "bands": ["dNBR"],
    "min": 0.1,
    "max": 0.8,
    "palette": ["fff7bc", "fec44f", "fe9929", "d95f0e", "993404", "4d004b"],
}

FIRE_VIS = {
    "bands": ["age"],
    "min": 0,
    "max": 1,
    # old detections = dark red, newest = bright yellow
    "palette": ["67000d", "cb181d", "fb6a4a", "fd8d3c", "feb24c", "ffff33"],
}


def fire_tile_url(start: str, end: str) -> str:
    """FIRMS active-fire pixels in [start, end), coloured by how recent the latest detection is."""
    s, e = ee.Date(start), ee.Date(end)
    span = e.difference(s, "day")

    def stamp(img: ee.Image) -> ee.Image:
        age = ee.Image.constant(img.date().difference(s, "day")).divide(span).toFloat()
        return age.updateMask(img.select("T21").mask()).rename("age")

    img = ee.ImageCollection("FIRMS").filterDate(s, e).map(stamp).max()
    return img.getMapId(FIRE_VIS)["tile_fetcher"].url_format


def _footprint_km2(col: ee.ImageCollection, band: str, name: str) -> ee.Image:
    present = col.select(band).count().gt(0).unmask(0)
    img = ee.Image(ee.Algorithms.If(col.size().gt(0), present, ee.Image.constant(0)))
    return img.multiply(ee.Image.pixelArea()).divide(1e6).rename(name)


def weekly_fire(geometry: dict, years: list[int], end_week: int = 52) -> dict[int, list[float]]:
    """Per year: km² of FIRMS pixels with ≥1 detection in each ISO-ish 7-day week (Jan 1 + 7n)."""
    region = ee.Geometry(geometry)
    out: dict[int, list[float]] = {}
    for y in years:
        bands = []
        for w in range(end_week):
            s = ee.Date.fromYMD(y, 1, 1).advance(7 * w, "day")
            col = ee.ImageCollection("FIRMS").filterDate(s, s.advance(7, "day"))
            bands.append(_footprint_km2(col, "T21", f"w{w:02d}"))
        vals = ee.Image.cat(bands).reduceRegion(
            ee.Reducer.sum(), region, scale=1000, maxPixels=1e9, tileScale=4
        ).getInfo()
        out[y] = [round(vals.get(f"w{w:02d}", 0) or 0, 1) for w in range(end_week)]
    return out


def burned_area_ha(geometry: dict, before: tuple[str, str], after: tuple[str, str]) -> dict:
    """Hectares inside the polygon with dNBR > 0.27 (moderate+) and > 0.66 (high severity)."""
    region = ee.Geometry(geometry)
    b = add_indices(composite(*before)).select("NBR")
    a = add_indices(composite(*after)).select("NBR")
    d = b.subtract(a)
    img = ee.Image.cat(
        d.gt(0.27).rename("moderate"), d.gt(0.66).rename("high"), d.mask().rename("valid")
    ).multiply(ee.Image.pixelArea()).divide(1e4)
    vals = img.reduceRegion(ee.Reducer.sum(), region, scale=20, maxPixels=1e10, bestEffort=True).getInfo()
    return {k: round(vals.get(k) or 0) for k in ("moderate", "high", "valid")}


def monthly_timeseries(geometry: dict, start: str, end: str, index: str = "NDVI") -> list[dict]:
    """Monthly median of `index` over the polygon. Returns [{month, value, n_scenes}]."""
    region = ee.Geometry(geometry)
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    months = []
    y, m = s.year, s.month
    while date(y, m, 1) < e:
        months.append(f"{y:04d}-{m:02d}-01")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)

    def per_month(m0: ee.String) -> ee.Feature:
        m0 = ee.Date(m0)
        m1 = m0.advance(1, "month")
        col = masked_collection(m0, m1, region)
        n = col.size()
        img = add_indices(col.median()).select(index)
        val = img.reduceRegion(
            reducer=ee.Reducer.median(),
            geometry=region,
            scale=100,
            maxPixels=1e9,
            bestEffort=True,
        ).get(index)
        return ee.Feature(None, {"month": m0.format("YYYY-MM"), "value": val, "n_scenes": n})

    fc = ee.FeatureCollection(ee.List(months).map(per_month))
    rows = fc.getInfo()["features"]
    return [
        {
            "month": r["properties"]["month"],
            "value": r["properties"].get("value"),
            "n_scenes": r["properties"].get("n_scenes", 0),
        }
        for r in rows
    ]
