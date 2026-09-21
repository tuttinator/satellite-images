# Southeast Asia haze: method and data format

How the daily smoke and fire grids behind the 2026 haze post are produced, what the numbers mean,
and the shape of the JSON files a front end consumes. Scripts: `scripts/haze_export.py`,
`scripts/fire_analysis.py`, `scripts/export_blog.py`. All processing happens in Google Earth
Engine; see the README for authentication.

## Summary

| Layer | Source | Resolution | What was done |
| --- | --- | --- | --- |
| Active fires | NASA FIRMS, MODIS Collection 6.1 NRT (`FIRMS`) | 1 km, aggregated to 0.1° | Daily presence of at least one detection per 1 km pixel, averaged to the fraction of each 0.1° cell, multiplied by cell area (km²) |
| Smoke aloft | ECMWF CAMS NRT (`ECMWF/CAMS/NRT`), organic-matter AOD at 550 nm | 0.4° | Mean of the forecast steps with under 12 hours' lead, per UTC day |
| Surface PM2.5 | ECMWF CAMS NRT, `particulate_matter_d_less_than_25_um_surface` | 0.4° | Same averaging, converted from kg/m³ to µg/m³; nearest cell for the city series |
| Fire seasons | FIRMS monthly footprint, 2001 to now | 1 km | Summed over FAO GAUL 2015 provinces; island totals are the dissolved union |
| Burned area | MODIS MCD64A1 (`MODIS/061/MCD64A1`) | 500 m | Monthly, per province; lags about two months |

## Daily grids (`haze_export.py`)

**Extent.** One grid, top-left corner 93.0°E 21.4°N, aligned to the CAMS cell edges (CAMS's origin
is -180.2, 90.2 with 0.4° cells). The CAMS fields are 92 × 75 cells at 0.4°, reaching 129.8°E and
8.6°S. The fire grid covers the same box at 0.1°, 368 × 300 cells. Change `LON0`, `LAT0` and the
`*_W`, `*_H` constants to move the box; keep the corner on a CAMS cell edge or the PM2.5 and AOD
fields will be resampled.

**Days.** From `START` (default 15 July of the current year, or the first CLI argument as
`YYYY-MM-DD`) to the earlier of yesterday and the last day FIRMS has any data for. Everything is
in UTC days, which matters for a region that spans UTC+7 to UTC+8: a fire detected at 02:00 local
on the 18th is counted on the 17th.

**CAMS.** For each day, the collection is filtered to that date and to `model_forecast_hour < 12`,
then averaged. CAMS NRT issues two forecasts a day (00 and 12 UTC) at 3-hourly steps, so this
averages the freshest steps only rather than blending long-lead forecasts. The two bands used are
`organic_matter_aerosol_optical_depth_at_550nm_surface` (dimensionless) and
`particulate_matter_d_less_than_25_um_surface` (kg/m³, multiplied by 10⁹ to give µg/m³).

**FIRMS.** For each day, `count().gt(0)` over the `T21` band gives a 1 km mask of pixels with at
least one detection. `reduceResolution(mean)` onto the 0.1° grid gives the covered fraction, and
multiplying by the cell's area (111.32 km × 0.1° squared × cos latitude) gives km². Cells under
0.5 km² are dropped from the sparse list. This is a *footprint*: the area of 1 km pixels that had a
detection, not the area that burned. It is comparable across years but overstates burned area by
roughly an order of magnitude in peatland, where fires smoulder under smoke and are often missed.

**Fetching.** Bands for twelve days are concatenated into one image and pulled with
`ee.data.computePixels` as an NPY array on an explicit affine grid. This is faster and more
predictable than an export task and needs no Cloud Storage bucket. Sixty-five days of all three
fields takes about two minutes.

**Encoding.** The PM2.5 and AOD fields are stored as one base64 uint8 frame per day, row-major
from the top-left corner. Values are square-root quantised so the low end keeps precision:

```
byte = round(sqrt(value) × q)         value = (byte / q)²
PM2.5: q = 6    → saturates at ≈1800 µg/m³, step ≈0.03 at 1 µg/m³, ≈3 at 100 µg/m³
AOD:   q = 110  → saturates at ≈5.4,        step ≈0.002 at 0.1, ≈0.02 at 1.0
```

## Fire seasons (`fire_analysis.py`)

For one island per run, the script builds a FeatureCollection of provinces from FAO GAUL 2015
level 1 (the name lists in `BORNEO` and `SUMATRA` map GAUL names to display labels; Kalimantan
Utara did not exist in GAUL 2015 and is counted inside Kalimantan Timur) plus a dissolved island
total. Then, for every month since January 2001:

- `fire_km2`: sum over the region of the FIRMS footprint image described above, at 1 km.
- `burned_km2`: the same construction on MCD64A1's `BurnDate` band, at 500 m.

A year's twelve months go into one multi-band image and a single `reduceRegions`, so the whole
record is 26 × 2 server calls per island. The current dry season also gets a daily FIRMS footprint
from 1 June. Province outlines are simplified to 2 km for the map. Expect about eight minutes per
island; the two islands can run in parallel.

## Interpretation notes

- MODIS passes about four times a day (Terra and Aqua). It cannot see fire through thick cloud or
  dense smoke, so the worst haze days can show *fewer* detections. Daily values are noisy; weekly
  or monthly sums are more robust.
- Only Terra was operating before mid-2002, so 2001 and early 2002 have roughly half the sampling.
- FIRMS NRT data lands a day or so late and the last two or three days are provisional and can
  be revised.
- CAMS is a model that assimilates satellite AOD and uses a fire-emissions inventory (GFAS). Its
  surface PM2.5 is an estimate and is known to under-read extreme peat-smoke episodes near source.
  AOD is better constrained by observation and is the right field for "where is the smoke going".
- Footprint is not burned area. In 2026 YKAN estimated around 6,000 km² actually burned in Borneo
  in August against a detection footprint roughly ten times that.

## JSON formats

### `outputs/sea_haze.json` (copied to `haze.json`)

```jsonc
{
  "generated": "2026-09-18",
  "sources": { "aod": "...", "pm25": "...", "fires": "..." },
  "days": ["2026-07-15", "..."],               // UTC days, index shared by every series below
  "pm25": {
    "lon0": 93.0, "lat0": 21.4, "d": 0.4,      // top-left corner and cell size, degrees
    "w": 92, "h": 75, "q": 6.0,
    "encoding": "base64 uint8 per day, row-major from top-left; µg/m³ = (v / q)²",
    "frames": ["<base64>", "..."]              // one per day
  },
  "aod": { /* same shape, q = 110; AOD = (v / q)² */ },
  "fires": {
    "lon0": 93.0, "lat0": 21.4, "d": 0.1,
    "cells": [ [[col, row, km2], ...], ... ]   // per day: sparse list of cells with ≥ 0.5 km²
  },
  "fire_km2_total": [1234.5, "..."],           // per day, whole grid
  "cities": {
    "Singapore": { "lon": 103.82, "lat": 1.35, "pm25": [/* per day */], "aod": [/* per day */] }
  }
}
```

Decoding a frame in JavaScript:

```js
const bytes = Uint8Array.from(atob(field.frames[i]), c => c.charCodeAt(0));
const value = (col, row) => (bytes[row * field.w + col] / field.q) ** 2;
const lon = col => field.lon0 + (col + 0.5) * field.d;
const lat = row => field.lat0 - (row + 0.5) * field.d;
```

### `outputs/<island>_fire.json`

```jsonc
{
  "generated": "2026-09-18",
  "sources": { "fire_km2": "...", "burned_km2": "...", "regions": "FAO GAUL 2015 level 1" },
  "regions": {
    "borneo": {                                // island total, key = island name
      "label": "Borneo",
      "monthly": { "2001-01": { "fire_km2": 12.0, "burned_km2": 0.0 }, "...": {} },
      "daily":   { "2026-06-01": 3.0, "...": 0 }    // current dry season, FIRMS only
    },
    "kalteng": { "label": "Kalimantan Tengah", "monthly": {}, "daily": {} }
    // ... one entry per province
  },
  "outlines": { /* GeoJSON FeatureCollection of the regions, simplified to 2 km */ }
}
```

### `seasons.json` (derived by `export_blog.py`)

```jsonc
{
  "generated": "2026-09-18",
  "through": "2026-09-17",                    // last day with any detection, min over islands
  "islands": {
    "borneo": {
      "label": "Borneo",
      "years": { "2001": [/* 12 monthly fire_km2, null if not yet reached */], "...": [] },
      "provinces": [ { "label": "Kalimantan Tengah", "months": { "01": 5.0, "...": 0 } } ]
    },
    "sumatra": { /* same */ }
  }
}
```

TypeScript interfaces for these shapes are in the blog repo at
`src/lib/vis/sea-haze/types.ts`.

## Adapting to another region

1. In `haze_export.py`, set `LON0`, `LAT0` to a CAMS cell edge and pick `PM_W`, `PM_H` (0.4° cells)
   and `FIRE_W`, `FIRE_H` (four times as many cells each way). Replace `CITIES`.
2. In `fire_analysis.py`, add an entry to `ISLANDS` with a bounding box and a mapping of region
   keys to GAUL `ADM1_NAME` values. Check names in the Earth Engine data catalog; GAUL spellings are
   sometimes archaic (`Nangroe Aceh Darussalam`, `Kepulauan-riau`).
3. Both scripts print progress per chunk or year. If `computePixels` times out, lower `CHUNK`.
