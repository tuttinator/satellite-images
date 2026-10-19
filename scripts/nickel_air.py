"""Nitrogen dioxide and night lights over the nickel parks → outputs/nickel/air.json.

  - no2.grids   annual mean TROPOMI tropospheric NO2 column (Sentinel-5P OFFL L3) on a 0.05° grid
                over Sulawesi and Halmahera, one per year from 2019 (the first full year) to the
                last complete year. Stored as uint8 µmol/m², rounded, saturating at 255. The
                column over clean ocean here is ~10–20 µmol/m², so a park's plume shows as the
                excess over that.
  - sites       per site, the same annual NO2 mean inside the site's box and a background ring
                30–60 km out, plus VIIRS night-light radiance (NOAA's annual VNL composites,
                median_masked: the median of cloud-free nights with fires, flares and other
                short-lived light removed, nW/cm²/sr) summed over the box.
                Boxes come from nickel_export.SITES, so run that first or at least import it.

Run:  uv run python scripts/nickel_air.py
"""

from __future__ import annotations

import base64
import io
import json
import sys
from datetime import date
from pathlib import Path

import ee
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from nickel_export import SITES, box  # noqa: E402

from satimg import layers  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "outputs" / "nickel" / "air.json"
NO2 = "COPERNICUS/S5P/OFFL/L3_NO2"
NO2_BAND = "tropospheric_NO2_column_number_density"
LIGHTS = ("NOAA/VIIRS/DNB/ANNUAL_V21", "NOAA/VIIRS/DNB/ANNUAL_V22")  # 2013–2021, 2022 on
LAST_YEAR = date.today().year - 1
NO2_YEARS = list(range(2019, LAST_YEAR + 1))
LIGHT_YEARS = list(range(2013, LAST_YEAR + 1))

LON0, LAT0 = 118.5, 2.5  # top-left corner
D, W, H = 0.05, 220, 150  # → 129.5°E, 5.0°S


def no2_year(year: int) -> ee.Image:
    col = ee.ImageCollection(NO2).filterDate(f"{year}-01-01", f"{year + 1}-01-01").select(NO2_BAND)
    # Retrievals over a cloudy pixel come back with large errors; the L3 product already drops
    # qa_value < 0.75, so a plain mean of what is left is the standard annual average.
    return col.mean().multiply(1e6).rename("no2")  # mol/m² → µmol/m²


def fetch_grid(img: ee.Image) -> np.ndarray:
    raw = ee.data.computePixels({
        "expression": img.unmask(0),
        "fileFormat": "NPY",
        "grid": {
            "dimensions": {"width": W, "height": H},
            "affineTransform": {"scaleX": D, "shearX": 0, "translateX": LON0,
                                "shearY": 0, "scaleY": -D, "translateY": LAT0},
            "crsCode": "EPSG:4326",
        },
    })
    arr = np.load(io.BytesIO(raw))
    return np.asarray(arr["no2"], dtype=np.float64)


def ring(centre: tuple[float, float], inner_km: float, outer_km: float) -> ee.Geometry:
    pt = ee.Geometry.Point(list(centre))
    return pt.buffer(outer_km * 1000).difference(pt.buffer(inner_km * 1000), 100)


def main() -> None:
    layers.init_ee()
    grids = {}
    for year in NO2_YEARS:
        g = fetch_grid(no2_year(year))
        q = np.clip(np.round(g), 0, 255).astype(np.uint8)
        grids[str(year)] = base64.b64encode(q.tobytes()).decode()
        print(f"no2 {year}: max {g.max():.0f} µmol/m²", flush=True)

    annual = ee.ImageCollection(LIGHTS[0]).merge(ee.ImageCollection(LIGHTS[1]))
    light_years = [y for y in LIGHT_YEARS
                   if annual.filterDate(f"{y}-01-01", f"{y + 1}-01-01").size().getInfo()]
    sites = {}
    for sid, (_name, centre, km) in SITES.items():
        region = box(centre, km)
        bg = ring(centre, 30, 60)

        def no2_at(year: int, region: ee.Geometry = region, bg: ee.Geometry = bg) -> ee.List:
            img = no2_year(year)
            return ee.List([
                img.reduceRegion(ee.Reducer.mean(), region, 1113).get("no2"),
                img.reduceRegion(ee.Reducer.mean(), bg, 1113).get("no2"),
            ])

        def light_at(year: int, region: ee.Geometry = region) -> ee.ComputedObject:
            img = annual.filterDate(f"{year}-01-01", f"{year + 1}-01-01").first()
            return (img.select("median_masked")
                    .reduceRegion(ee.Reducer.sum(), region, 463.83, maxPixels=1e8)
                    .get("median_masked"))

        # One request per site: separate getInfo calls per year were slow and occasionally hung.
        got = ee.List([ee.List([no2_at(y) for y in NO2_YEARS]),
                       ee.List([light_at(y) for y in light_years])]).getInfo()
        no2 = [{"year": y, "site": round(v[0], 1), "background": round(v[1], 1)}
               for y, v in zip(NO2_YEARS, got[0], strict=True)]
        lights = [{"year": y, "radiance": round(v or 0, 1)} for y, v in zip(light_years, got[1], strict=True)]
        sites[sid] = {"no2": no2, "lights": lights}
        print(sid, no2[0]["site"], "→", no2[-1]["site"], "µmol/m²;",
              lights[0]["radiance"], "→", lights[-1]["radiance"], "radiance", flush=True)

    OUT.write_text(json.dumps({
        "generated": date.today().isoformat(),
        "no2": {"years": NO2_YEARS, "lon0": LON0, "lat0": LAT0, "d": D, "w": W, "h": H,
                "units": "µmol/m²", "grids": grids},
        "light_years": light_years,
        "sites": sites,
    }))


if __name__ == "__main__":
    main()
