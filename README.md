# satellite-images

Small web viewer for Sentinel-2 imagery around Palangka Raya (Central Kalimantan), focused on the
REDD+ / ecosystem-restoration concessions — Katingan Mentaya and Rimba Raya — with Sebangau
National Park as a reference peat-swamp forest.

Composites are built on the fly by Google Earth Engine (same auth setup as
[`../deforestation-vis`](../deforestation-vis)), served as XYZ tiles into a MapLibre map.

## Quick start

```bash
mise install
uv sync
cp .env.example .env          # set EE_PROJECT_ID (same as deforestation-vis)
gcloud auth application-default login   # if the ADC token has expired
make dev                      # http://127.0.0.1:8000
```

## What it does

- **Layers**: true colour, false colour (NIR), SWIR, NDVI, NBR (burn), NDMI (canopy moisture),
  and an **NDVI change** layer (after − before; red = canopy loss, blue = regrowth).
- **Date windows**: any range; cloud-masked (Cloud Score+ `cs_cdf ≥ 0.6`) median composite.
  In Kalimantan, 2–3 month windows are usually needed to get a clear composite; the dry season
  (Jun–Oct) is cleaner.
- **Time series**: click a concession for a 3-year monthly median NDVI/NBR/NDMI chart. Months with
  no clear pixels are shown as gaps.

## Fire

- **Active fires** layer: FIRMS (MODIS, 1 km) hotspots for a 7-day window, coloured by recency;
  a slider walks the window through the dry season (from 1 June).
- **Burn scars (dNBR)** layer: Sentinel-2 NBR(before) − NBR(after); with a concession selected
  it also reports hectares above the USGS moderate (0.27) and high (0.66) severity thresholds.
- **Weekly fire chart** per concession: km² of fire pixels per week for 2015/2019/2023/2025/2026.
- **Island stories** (`/story`, `/story?island=sumatra`): a narrative page built from
  `outputs/{borneo,sumatra}_fire.json`, produced by
  `uv run python scripts/fire_analysis.py [borneo|sumatra]` (monthly FIRMS footprint + MCD64A1
  burned area per province, 2001–present, plus daily footprint for the current season; ~8 min
  each, fine to run in parallel). The page is date-driven: it headlines the last complete month
  and ranks it against every year in the record.

## Haze (blog post)

- `uv run python scripts/haze_export.py` → `outputs/sea_haze.json`: daily grids for maritime
  Southeast Asia from 15 July — CAMS NRT smoke (organic-matter AOD and surface PM2.5, 0.4°),
  FIRMS fire footprint per 0.1° cell, and city series. ~2 min.
- `uv run python scripts/export_blog.py` copies that plus a trimmed fire-season file into
  `../caleb-tutty.com/static/data/sea-haze/` for the post at `/posts/southeast-asia-haze-2026`.
- To refresh the post: run the two `fire_analysis.py` jobs, `haze_export.py`, then
  `export_blog.py`; then re-check the numbers quoted in the post's prose and figure captions
  (the "15 July – 17 September" / "to 17 Sep" strings are written out by hand).

## Layout

```
src/satimg/layers.py   Earth Engine: masking, composites, indices, tile URLs, time series
src/satimg/app.py      FastAPI API + static hosting (3 h tile-URL cache)
static/                MapLibre + Chart.js frontend (no build step); story.html = narrative
scripts/fire_analysis.py   Borneo-wide fire stats → outputs/borneo_fire.json
data/concessions.geojson   ⚠ approximate, hand-drawn boundaries — replace with official polygons
```

## Boundaries

`data/concessions.geojson` has three kinds of feature:

- **Concession licence boundaries** (`source: Kemenhut PBPH_AR_50K Dec 2023`) — PT Rimba Makmur
  Utama (Katingan Mentaya, 157,404 ha, active) and PT Rimba Raya Conservation (37,161 ha, licence
  status *dicabut* = revoked). From the Ministry of Forestry's public PBPH shapefile; see
  `docs/carbon-projects-indonesia.md` for the download URL.
- **Verra project areas** (`source: Verra registry doc …`, dashed on the map) — the carbon
  accounting boundaries from the registry KMLs: Katingan 149,704 ha, Rimba Raya 64,183 ha.
  Fetch others with `uv run python scripts/fetch_verra_kml.py <VCS ids>`.
- **National parks** (`source: WDPA`) — Sebangau, Tanjung Puting — from `WCMC/WDPA/current/polygons`
  in Earth Engine, simplified to 200 m. UNEP-WCMC terms apply.

`docs/carbon-projects-indonesia.md` lists all 42 Indonesian Verra AFOLU projects (with KML document
ids), the Plan Vivo / Gold Standard / ERC-only projects, and every boundary-data source checked.

## Next steps

- Swap in official concession boundaries.
- Add VIIRS/MODIS fire hotspots (`FIRMS` in EE) as a layer.
- Per-concession "area with dNDVI < −0.2" in hectares per month (an alert metric).
- Export PNG snapshots for reports.
