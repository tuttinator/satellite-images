"""Annual Landsat views of Indonesia's nickel parks → outputs/nickel/.

For each site and each year from 2013 to the last complete year:
  - <site>/<year>.jpg   true-colour median of Landsat 8 + 9 Collection 2 surface reflectance,
                        from scenes under 50% cloud, cloud- and shadow-masked from QA_PIXEL with a
                        60 m margin, plus a brightness test for thin cloud the QA band misses.
                        Gaps left by persistent cloud are filled from the clear scenes of the years
                        either side, then of the five years around. Pixels bright in one year but not in
                        the next three are cloud, and take the later composite.
  - cleared_km2         land in the box that is neither vegetated (NDVI < 0.3) nor water
                        (MNDWI < 0, SWIR1 > 0.1): pits, stockpiles, roads, smelter roofs, tailings, and also
                        towns and natural bare ground, which is why the 2013 value is a baseline,
                        not zero.
Plus <site>/cleared.png: the first year each 30 m pixel was cleared and stayed cleared the year
after (two in a row, so one cloudy composite cannot fake it), coloured by year, transparent where
the land was already cleared in 2013 or never was.

Landsat rather than Sentinel-2 because Sentinel-2 surface reflectance over eastern Indonesia only
becomes dependable in 2018–19, years after the 2014 ore-export ban that started the boom.

Run:  uv run python scripts/nickel_export.py [site ...]   (default: every site)
"""

from __future__ import annotations

import io
import json
import math
import struct
import sys
import time
import zlib
from datetime import date
from pathlib import Path

import ee
import httpx
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from satimg import layers  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "outputs" / "nickel"
FIRST_YEAR = 2013  # Landsat 8 goes operational in April 2013
LAST_YEAR = date.today().year - 1
YEARS = list(range(FIRST_YEAR, LAST_YEAR + 1))
SCALE = 30
THUMB_PX = 720
CLEARED_NDVI = 0.3
MAX_CLOUD = 50  # % scene cloud cover
CLOUD_BLUE = 0.16  # surface reflectance; clear land and water sit well below this
STEADY_BLUE = 0.12

# id → name, centre (lon, lat), box side in km. Boxes are sized to hold the park and its pits.
SITES = {
    "morowali": ("IMIP, Morowali", (122.165, -2.845), 18),
    "weda-bay": ("IWIP, Weda Bay", (127.95, 0.53), 20),
    "obi": ("Harita, Obi Island", (127.425, -1.555), 12),
    "konawe": ("VDNI and OSS, Konawe", (122.42, -3.855), 14),
    "pomalaa": ("Pomalaa, Kolaka", (121.64, -4.225), 18),
    "sorowako": ("Vale, Sorowako", (121.37, -2.55), 18),
}

# Colours for cleared.png, oldest to newest (2014 … LAST_YEAR).
YEAR_PALETTE = ["#fde725", "#b5de2b", "#6ece58", "#35b779", "#1f9e89", "#26828e",
                "#31688e", "#3e4989", "#482878", "#440154", "#7a0177", "#ae017e"]


def bounds(centre: tuple[float, float], km: float) -> tuple[float, float, float, float]:
    """West, south, east, north of a square km on a side."""
    lon, lat = centre
    dlat = km / 2 / 111.32
    dlon = km / 2 / (111.32 * math.cos(math.radians(lat)))
    return lon - dlon, lat - dlat, lon + dlon, lat + dlat


def box(centre: tuple[float, float], km: float) -> ee.Geometry:
    return ee.Geometry.Rectangle(list(bounds(centre, km)), geodesic=False)


def landsat(year: int, region: ee.Geometry, max_cloud: float = 100) -> ee.ImageCollection:
    def prep(img: ee.Image) -> ee.Image:
        qa = img.select("QA_PIXEL")
        # Bits: 1 dilated cloud, 2 cirrus, 3 cloud, 4 cloud shadow. Grown by 60 m, because the
        # QA band misses cloud edges and thin cloud around them.
        clear = qa.bitwiseAnd(0b11110).eq(0).focalMin(2, "square", "pixels")
        sr = img.select(["SR_B2", "SR_B3", "SR_B4", "SR_B5", "SR_B6"],
                        ["blue", "green", "red", "nir", "swir1"])
        return sr.multiply(0.0000275).add(-0.2).updateMask(clear)

    start, end = f"{year}-01-01", f"{year + 1}-01-01"
    col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(
        ee.ImageCollection("LANDSAT/LC09/C02/T1_L2"))
    col = col.filterBounds(region).filterDate(start, end).filter(ee.Filter.lte("CLOUD_COVER", max_cloud))
    col = col.map(prep)
    # Thin cloud the QA band misses in most scenes over Halmahera survives a median as white
    # blotches. It is bright in blue and comes and goes; roofs and tailings are bright all year.
    # So mask bright-blue pixels unless that pixel's 25th-percentile blue is already high.
    steady = col.select("blue").reduce(ee.Reducer.percentile([25])).gt(STEADY_BLUE)
    return col.map(lambda img: img.updateMask(img.select("blue").lt(CLOUD_BLUE).Or(steady)))


def cleared(img: ee.Image) -> ee.Image:
    ndvi = img.normalizedDifference(["nir", "red"])
    mndwi = img.normalizedDifference(["green", "swir1"])
    # Hazy or turbid sea can pass the NDVI and MNDWI tests; water still absorbs SWIR, haze barely
    # touches it, so a SWIR floor keeps the sea out.
    land = img.select("swir1").gt(0.1)
    return ndvi.lt(CLEARED_NDVI).And(mndwi.lt(0)).And(land).rename("cleared")


def download(thumb: ee.Image, params: dict, path: Path, tries: int = 5) -> None:
    for attempt in range(tries):
        try:
            # A fresh URL each try: thumbnail URLs can expire while a retry waits.
            r = httpx.get(thumb.getThumbURL(params), timeout=600, follow_redirects=True)
            r.raise_for_status()
            path.write_bytes(r.content)
            return
        except (httpx.TimeoutException, httpx.HTTPStatusError, httpx.ConnectError,
                ee.EEException) as e:
            if attempt == tries - 1:
                raise
            print(f"  retrying {path.name}: {e!r}"[:200], flush=True)
            time.sleep(30 * (attempt + 1))  # 429s clear after a minute or two


def with_retry(call, what: str, tries: int = 4):
    """Earth Engine requests near the memory limit (Weda Bay) fail or succeed with load."""
    for attempt in range(tries):
        try:
            return call()
        except Exception as e:  # EEException and googleapiclient HttpError both land here
            if attempt == tries - 1:
                raise
            print(f"  retrying {what}: {e!r}"[:200], flush=True)
            time.sleep(60 * (attempt + 1))


def fetch_mask(img: ee.Image, w: float, n: float, e: float, s: float, what: str) -> np.ndarray:
    """THUMB_PX square 0/1 grid over the box, in 2×2 tiles: one request for the whole of Weda
    Bay's frame runs Earth Engine out of memory."""
    half = THUMB_PX // 2
    dx, dy = (e - w) / THUMB_PX, (n - s) / THUMB_PX
    out = np.zeros((THUMB_PX, THUMB_PX), dtype=bool)
    for row in (0, 1):
        for col in (0, 1):
            request = {
                "expression": img,
                "fileFormat": "NPY",
                "grid": {
                    "dimensions": {"width": half, "height": half},
                    "affineTransform": {"scaleX": dx, "shearX": 0, "translateX": w + col * half * dx,
                                        "shearY": 0, "scaleY": -dy, "translateY": n - row * half * dy},
                    "crsCode": "EPSG:4326",
                },
            }
            raw = with_retry(lambda r=request: ee.data.computePixels(r), what)
            tile = np.load(io.BytesIO(raw))["cleared"].astype(bool)
            out[row * half:(row + 1) * half, col * half:(col + 1) * half] = tile
    return out


def write_png(path: Path, rgba: np.ndarray) -> None:
    """Minimal RGBA PNG writer, so the script needs no imaging library."""
    h, w, _ = rgba.shape
    raw = b"".join(b"\x00" + rgba[y].tobytes() for y in range(h))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    path.write_bytes(b"\x89PNG\r\n\x1a\n"
                     + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
                     + chunk(b"IDAT", zlib.compress(raw, 9))
                     + chunk(b"IEND", b""))


def export_site(site: str) -> dict:
    name, centre, km = SITES[site]
    region = box(centre, km)
    out = OUT / site
    out.mkdir(parents=True, exist_ok=True)
    w, s, e, n = bounds(centre, km)
    # Frames and masks share one EPSG:4326 grid over the box (see fetch_mask), so the overlay
    # lines up with the picture.

    # Each year's clear-scene median is built once and reused below; rebuilding it for every
    # gap-fill and check ran Earth Engine out of memory.
    strict = {y: landsat(y, region, MAX_CLOUD).median() for y in YEARS}

    years = []
    masks: dict[int, np.ndarray] = {}
    for year in YEARS:
        # Scenes over half cloud are where the QA band misses most, so only clearer scenes go
        # into the composite. Gaps are filled from the clear scenes of the years either side, then
        # of the five years around it. (Filling from the previous year's filled composite chains
        # all the years into one graph that Earth Engine times out on; a further fill from every
        # scene of the year brought cloud back and ran Weda Bay out of memory.)
        median = strict[year]
        either_side = ee.ImageCollection(
            [strict[y] for y in (year - 1, year + 1) if y in strict]).mosaic()
        window = ee.ImageCollection(
            [strict[y] for y in range(year - 2, year + 3) if y in strict]).median()
        filled = median.unmask(either_side).unmask(window)

        # Where a path edge saw only cloudy scenes all year (Weda Bay in 2013–14), the composite
        # is cloud. A roof stays bright in later years and a cloud does not, so a pixel bright
        # this year but not in the next three years' clear-scene medians takes their median
        # instead. The last year has nothing after it to check and is left as it is.
        later = [strict[y] for y in range(year + 1, year + 4) if y in strict]
        if later:
            after = ee.ImageCollection(later).median()
            transient = filled.select("blue").gt(CLOUD_BLUE).And(after.select("blue").lt(STEADY_BLUE))
            filled = filled.where(transient, after)

        rgb = filled.select(["red", "green", "blue"]).visualize(min=0, max=0.22, gamma=1.3)
        download(rgb, {"region": region, "crs": "EPSG:4326",
                       "dimensions": f"{THUMB_PX}x{THUMB_PX}", "format": "jpg"}, out / f"{year}.jpg")

        masks[year] = fetch_mask(cleared(filled).unmask(0).toUint8(), w, n, e, s, f"{year} mask")

        px_area = ee.Image.pixelArea().divide(1e6)
        # tileScale splits the reduction into smaller tiles: same sums, less memory per tile,
        # which Weda Bay needs.
        sums = ee.Image.cat(
            cleared(filled).multiply(px_area).rename("cleared"),
            median.select("red").mask().multiply(px_area).rename("observed"),
        ).reduceRegion(ee.Reducer.sum(), region, SCALE, maxPixels=1e9, tileScale=4)
        stats = with_retry(lambda d=sums: d.getInfo(), f"{year} stats")
        total = region.area(1).divide(1e6).getInfo()
        years.append({
            "year": year,
            "cleared_km2": round(stats["cleared"], 2),
            "observed": round(stats["observed"] / total, 3),
        })
        print(f"  {site} {year}: {years[-1]['cleared_km2']} km² cleared, "
              f"{years[-1]['observed']:.0%} seen this year", flush=True)

    # First year a pixel was cleared and still cleared the year after (the last year can only be
    # confirmed by itself), leaving out land already cleared in the first year. Built here from
    # the yearly masks rather than in Earth Engine, where all thirteen composites in one request
    # run out of memory.
    first = np.zeros((THUMB_PX, THUMB_PX), dtype=np.int16)
    base = masks[FIRST_YEAR]
    for y in reversed(YEARS[1:]):
        nxt = masks.get(y + 1, masks[y])
        first[masks[y] & nxt & ~base] = y
    palette = YEAR_PALETTE[: len(YEARS) - 1]
    rgba = np.zeros((THUMB_PX, THUMB_PX, 4), dtype=np.uint8)
    for k, colour in enumerate(palette):
        hit = first == YEARS[1] + k
        rgba[hit] = [int(colour[i:i + 2], 16) for i in (1, 3, 5)] + [255]
    write_png(out / "cleared.png", rgba)

    return {"id": site, "name": name, "centre": centre, "km": km,
            "bounds": [round(v, 5) for v in (w, s, e, n)], "years": years}


def main() -> None:
    layers.init_ee()
    # A getInfo or thumbnail request over Halmahera occasionally never returns; fail it instead.
    ee.data.setDeadline(600_000)
    OUT.mkdir(parents=True, exist_ok=True)
    for site in sys.argv[1:] or SITES:
        print(site, flush=True)
        (OUT / site / "site.json").write_text(json.dumps(export_site(site), indent=1))

    # Every finished site, in SITES order; sites run in parallel each write only their own file.
    done = [json.loads((OUT / s / "site.json").read_text())
            for s in SITES if (OUT / s / "site.json").exists()]
    (OUT / "sites.json").write_text(json.dumps({
        "generated": date.today().isoformat(), "years": YEARS,
        "palette": YEAR_PALETTE[: len(YEARS) - 1], "cleared_ndvi": CLEARED_NDVI, "sites": done,
    }, indent=1))


if __name__ == "__main__":
    main()
