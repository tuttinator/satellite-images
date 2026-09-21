# satellite-images

Google Earth Engine tools for watching forest, fire and smoke in Indonesia, built for two blog posts
on [caleb-tutty.com](https://caleb-tutty.com):

- **Southeast Asia haze, 2026** — daily smoke and fire grids for maritime Southeast Asia and a
  26-year fire-season comparison for Sumatra and Borneo. See [`docs/sea-haze.md`](docs/sea-haze.md)
  for the method and data format, and the *Haze* section below to reproduce it.
- **Palangka Raya forest viewer** — a small web app that renders Sentinel-2 composites, vegetation
  indices, burn scars and FIRMS hotspots over the REDD+ concessions in Central Kalimantan.

Everything is computed on the fly from public datasets in the Earth Engine catalog. Nothing is
downloaded to disk except the small JSON summaries in `outputs/`.

The companion tree-cover-loss analysis lives in its own repo:
[github.com/tuttinator/indonesia-deforestation](https://github.com/tuttinator/indonesia-deforestation).

## Earth Engine setup

You need a Google account with Earth Engine access and a Google Cloud project to bill the (free,
for non-commercial use) compute against. This takes about ten minutes the first time.

1. **Register for Earth Engine** at <https://code.earthengine.google.com/register>. Pick
   *Unpaid usage* if you qualify (research, education, non-profit, personal). During registration
   you either create a new Cloud project or attach an existing one; either way, note the
   **project ID** (for example `my-ee-project`, not the display name).
2. **Enable the API** in that project if registration didn't do it for you:
   <https://console.cloud.google.com/apis/library/earthengine.googleapis.com>.
3. **Install the Google Cloud CLI** (`brew install google-cloud-sdk`, or see
   <https://cloud.google.com/sdk/docs/install>) and sign in with Application Default Credentials:

   ```bash
   gcloud auth application-default login
   ```

   This opens a browser and stores a token that the `earthengine-api` client picks up
   automatically. Tokens expire after a while; when the app or a script reports an
   authentication error, run the same command again.

   Alternatively, `uv run earthengine authenticate` stores Earth Engine-specific credentials in
   `~/.config/earthengine/`. Either method works; the code just calls `ee.Initialize(project=...)`.
4. **Tell this repo which project to use**:

   ```bash
   cp .env.example .env     # then set EE_PROJECT_ID=<your project id>
   ```

Datasets used, all public in the catalog with no extra access request:

| Dataset | Earth Engine ID | Used for |
| --- | --- | --- |
| Sentinel-2 surface reflectance | `COPERNICUS/S2_SR_HARMONIZED` | composites, NDVI / NBR / NDMI, dNBR |
| Cloud Score+ | `GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED` | cloud masking (`cs_cdf ≥ 0.6`) |
| FIRMS active fire (MODIS, 1 km) | `FIRMS` | hotspots, fire footprints, daily fire grids |
| MODIS burned area | `MODIS/061/MCD64A1` | monthly burned area per province |
| CAMS near-real-time atmosphere | `ECMWF/CAMS/NRT` | organic-matter AOD and surface PM2.5 |
| FAO GAUL 2015 admin-1 | `FAO/GAUL/2015/level1` | province boundaries |
| WDPA protected areas | `WCMC/WDPA/current/polygons` | national parks (UNEP-WCMC terms apply) |

## Install

Python 3.12 and [uv](https://docs.astral.sh/uv/). [mise](https://mise.jdx.dev/) is optional; it
installs both from `mise.toml`.

```bash
mise install      # optional
uv sync           # creates .venv with runtime + dev dependencies
make test         # sanity check; does not need Earth Engine
```

## Haze: daily smoke and fire grids

This is the pipeline behind the haze post. Three scripts, run in order:

```bash
make fire     # scripts/fire_analysis.py borneo & sumatra → outputs/{borneo,sumatra}_fire.json (~8 min each)
make haze     # scripts/haze_export.py → outputs/sea_haze.json (~2 min)
make blog DEST=path/to/site/static/data/sea-haze     # package both for a website
```

**`scripts/haze_export.py`** builds, for every UTC day from a start date (default 15 July of the
current year) to the latest complete FIRMS day:

- **Surface PM2.5** and **organic-matter aerosol optical depth** from CAMS NRT, averaged over the
  forecast steps with under 12 hours' lead, on the native 0.4° grid. AOD is the smoke in the whole
  column, which is what travels downwind. PM2.5 is a model estimate and under-reads extreme peat
  smoke near the source.
- **Fire footprint** from FIRMS: the fraction of each 0.1° cell covered by 1 km MODIS pixels with at
  least one detection that day, multiplied by cell area, so the unit is km². Stored sparse.
- **City series** of PM2.5 and AOD from the nearest CAMS cell for thirteen cities.

Grids are pulled with `ee.data.computePixels` in twelve-day chunks and stored as square-root
quantised uint8 frames in base64, which keeps two months of daily grids under 2 MB. The grid
extent, cities, start date and quantisation constants are all module-level constants at the top of
the script; change them there to cover another region.

**`scripts/fire_analysis.py [borneo|sumatra]`** builds the fire-season record: for each island and
each of its provinces, the monthly FIRMS fire footprint and MCD64A1 burned area from 2001 to the
present, plus a daily footprint for the current dry season (from 1 June) and simplified province
outlines. Provinces come from FAO GAUL 2015. Adding another island means adding a bounding box and
a province list to `ISLANDS`.

**`scripts/export_blog.py`** copies `sea_haze.json` and derives a compact `seasons.json` from the two
fire files. The destination defaults to the author's blog checkout; pass `--dest` or set
`BLOG_DATA_DIR`.

Caveats worth repeating wherever the numbers are shown: MODIS passes four times a day and cannot see
through thick cloud or smoke, so daily totals are noisy and the last two or three days are
provisional; only Terra was flying before mid-2002; CAMS surface concentrations are model output,
not measurements. The full method, the JSON schemas and the interpretation notes are in
[`docs/sea-haze.md`](docs/sea-haze.md).

## Viewer: Palangka Raya forest viewer

```bash
make dev      # http://127.0.0.1:8000
```

- **Layers**: true colour, false colour (NIR), SWIR, NDVI, NBR, NDMI, an **NDVI change** layer
  (after minus before; red is canopy loss, blue is regrowth), **burn scars (dNBR)** and
  **active fires** (FIRMS hotspots for a 7-day window, coloured by recency, with a slider that walks
  through the dry season).
- **Date windows**: any range. Composites are cloud-masked medians. In Kalimantan you usually need a
  two to three month window for a clear picture; the dry season (June to October) is cleaner.
- **Per concession**: click a polygon for a 3-year monthly NDVI / NBR / NDMI series, weekly fire
  footprint for 2015, 2019, 2023, 2025 and 2026, and hectares above the USGS moderate (0.27) and
  high (0.66) dNBR thresholds for the selected windows.
- **Island story** at `/story` (Borneo) and `/story?island=sumatra`: a narrative page generated from
  `outputs/{borneo,sumatra}_fire.json` that headlines the last complete month and ranks it against
  every year since 2001.

Tile URLs from Earth Engine expire after a few hours, so the server caches them for three.

`make screenshot` captures the viewer with headless Chrome once tiles have loaded (macOS path to
Chrome is hard-coded in `scripts/screenshot.py`).

## Boundaries

`data/concessions.geojson` is what the viewer uses. It has three kinds of feature:

- **Concession licence boundaries** (`source: Kemenhut PBPH_AR_50K Dec 2023`): PT Rimba Makmur
  Utama (Katingan Mentaya, 157,404 ha, active) and PT Rimba Raya Conservation (37,161 ha, licence
  revoked). From the Ministry of Forestry's public PBPH shapefile.
- **Verra project areas** (dashed on the map): the carbon-accounting boundaries from the registry
  KMLs. Katingan 149,704 ha, Rimba Raya 64,183 ha. Fetch others with
  `uv run python scripts/fetch_verra_kml.py <VCS ids>`.
- **National parks** (`source: WDPA`): Sebangau and Tanjung Puting, simplified to 200 m.

`data/context.geojson` is the wider context layer (all Kalimantan forestry licences, 36 Verra
project areas, WDPA protected areas, village forests). Rebuild it with
`uv run python scripts/build_context.py`; the raw downloads land in `data/raw/`, which is ignored.

[`docs/carbon-projects-indonesia.md`](docs/carbon-projects-indonesia.md) lists all 42 Indonesian
Verra AFOLU projects with their KML document IDs, the Plan Vivo / Gold Standard / ERC-only projects,
and every boundary-data source that was checked, working or not.

## Layout

```
src/satimg/layers.py        Earth Engine: auth, masking, composites, indices, tile URLs, time series
src/satimg/app.py           FastAPI JSON API + static hosting
static/                     MapLibre + Chart.js frontend, no build step; story.html is the narrative
scripts/haze_export.py      daily CAMS smoke + FIRMS fire grids → outputs/sea_haze.json
scripts/fire_analysis.py    island / province fire seasons 2001–now → outputs/<island>_fire.json
scripts/export_blog.py      package the two above for a website
scripts/build_context.py    data/context.geojson from Kemenhut, Verra, WDPA
scripts/fetch_verra_kml.py  Verra registry records + KMLs by VCS id
scripts/screenshot.py       headless-Chrome screenshot of the viewer
data/                       boundary GeoJSON (committed)
outputs/                    JSON summaries (committed, so the story page works without Earth Engine)
docs/                       method notes and data-source research
```

## Development

```bash
make test     # pytest; the API tests run without Earth Engine credentials
make lint     # ruff
```

## License

Code is released under the [MIT License](LICENSE). The data in `data/` and `outputs/` is derived
from third-party sources with their own terms: Sentinel-2 (Copernicus, free and open), FIRMS and
MODIS (NASA, public domain), CAMS (Copernicus Atmosphere Monitoring Service licence), FAO GAUL,
the Indonesian Ministry of Forestry's public PBPH shapefile, Verra registry KMLs, and WDPA
(UNEP-WCMC, non-commercial use and attribution required). Credit those sources when you republish
derived figures.
