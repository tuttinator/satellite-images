"""Build data/context.geojson — the "everything else" map layers:

  concession  all forestry licences (PBPH) in the five Kalimantan provinces, from the Ministry of
              Forestry's Dec-2023 shapefile (downloaded if data/raw/pbph.zip is absent)
  verra       Verra VCS project areas (KMLs pulled from the registry for the ids below)
  protected   WDPA protected areas in Indonesia, via Earth Engine
  village_forest  Hutan Desa permits, Indonesia, from the Kemenhut ArcGIS REST API

Run:  uv run python scripts/build_context.py
"""

from __future__ import annotations

import io
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "context.geojson"
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

PBPH_URL = (
    "https://spatial.phl.kehutanan.go.id/portal/sharing/rest/content/items/"
    "455c9a4ca3194d4fb12c66345bb3dd75/data"
)
KALIMANTAN_PROV = {"61": "Kalbar", "62": "Kalteng", "63": "Kalsel", "64": "Kaltim", "65": "Kaltara"}
PROVINCES = {  # BPS codes
    "11": "Aceh", "12": "Sumut", "13": "Sumbar", "14": "Riau", "15": "Jambi", "16": "Sumsel",
    "17": "Bengkulu", "18": "Lampung", "19": "Babel", "21": "Kepri", "31": "Jakarta", "32": "Jabar",
    "33": "Jateng", "34": "DIY", "35": "Jatim", "36": "Banten", "51": "Bali", "52": "NTB", "53": "NTT",
    **KALIMANTAN_PROV, "71": "Sulut", "72": "Sulteng", "73": "Sulsel", "74": "Sultra", "75": "Gorontalo",
    "76": "Sulbar", "81": "Maluku", "82": "Malut", "91": "Papua", "92": "Papua Barat", "93": "Papua Selatan",
    "94": "Papua Tengah", "95": "Papua Pegunungan", "96": "Papua Barat Daya",
}
INDONESIA_BBOX = (94.5, -11.5, 141.5, 6.5)
# Legacy ecosystem-restoration (IUPHHK-RE) holders, per Silalahi et al. 2020 + PDD checks.
RE_HOLDERS = {
    "PT RIMBA MAKMUR UTAMA", "PT RIMBA RAYA CONSERVATION", "PT RESTORASI HABITAT ORANG HUTAN INDONESIA",
    "PT EKOSISTEM KHATULISTIWA LESTARI", "PT ALAM SUKSES LESTARI",
}
# All Indonesian Verra AFOLU projects known to have a KML on the registry
# (see docs/carbon-projects-indonesia.md; 3587, 3591, 4186, 5736, 6128 have none).
VERRA_IDS = [
    674, 1477, 1493, 1498, 1899, 2395, 2403, 3012, 3226, 4381, 4520, 4782, 4967, 5032, 5283, 5371,
    5448, 5458, 5475, 5520, 5524, 5545, 5585, 5620, 5631, 5695, 5722, 5796, 5798, 5799, 5834, 5845,
    5873, 5891, 5905, 6085,
]  # 5956 (rice methane, thousands of paddy plots) is excluded — not forest, 9 MB of geometry
BBOX = (108.5, -4.5, 119.5, 7.5)
SIMPLIFY = 0.001  # deg, ~100 m


def concessions() -> gpd.GeoDataFrame:
    RAW.mkdir(parents=True, exist_ok=True)
    zpath = RAW / "pbph.zip"
    if not zpath.exists():
        print("downloading PBPH shapefile…")
        zpath.write_bytes(httpx.get(PBPH_URL, follow_redirects=True, timeout=300).content)
    with zipfile.ZipFile(zpath) as z:
        z.extractall(RAW / "pbph")
    shp = next((RAW / "pbph").glob("*.shp"))
    g = gpd.read_file(shp).to_crs(4326)
    g = g[g.KODE_PROV.astype(str).isin(KALIMANTAN_PROV)].copy()
    g["area_ha"] = g.to_crs("+proj=cea").area / 1e4
    out = gpd.GeoDataFrame(
        {
            "kind": "concession",
            "name": g.NAMOBJ.str.title(),
            "province": g.KODE_PROV.astype(str).map(KALIMANTAN_PROV),
            "status": g.STAT_IZIN,
            "sk": g.NO_SK,
            "sk_date": g.TGL_SK.astype(str).str[:10],
            "restoration": g.NAMOBJ.isin(RE_HOLDERS),
            "area_ha": g.area_ha.round(),
            "source": "Kemenhut PBPH_AR_50K Dec 2023",
        },
        geometry=g.geometry.simplify(SIMPLIFY),
        crs=4326,
    )
    print(f"concessions: {len(out)}")
    return out


def verra() -> gpd.GeoDataFrame:
    from fetch_verra_kml import fetch  # noqa: E402

    vdir = RAW / "verra"
    vdir.mkdir(parents=True, exist_ok=True)
    for i in VERRA_IDS:
        if not (vdir / f"{i}.json").exists():
            fetch(i, vdir)
    rows = []
    for i in VERRA_IDS:
        rec = json.loads((vdir / f"{i}.json").read_text())
        kmls = sorted(
            (p for p in vdir.glob(f"{i}_*") if p.suffix.lower() == ".kml" and ".unzipped" not in p.name),
            key=lambda p: p.stat().st_size,
        )
        if not kmls:
            continue
        # Prefer the file literally named as the project area; else the smallest (overview) KML.
        pick = next((k for k in kmls if "projectarea" in k.name.lower().replace("_", "").replace(" ", "")), kmls[0])
        import pyogrio

        if pick.read_bytes()[:2] == b"PK":  # a KMZ with a .kml name
            with zipfile.ZipFile(pick) as z:
                inner = next(n for n in z.namelist() if n.lower().endswith(".kml"))
                pick = pick.with_suffix(".unzipped.kml")
                pick.write_bytes(z.read(inner))
        parts = [gpd.read_file(pick, layer=lyr[0], engine="pyogrio") for lyr in pyogrio.list_layers(pick)]
        g = gpd.GeoDataFrame(pd.concat(parts, ignore_index=True), crs=4326)
        g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])]
        if g.empty:
            continue
        from shapely import make_valid

        fixed = g.geometry.apply(make_valid).buffer(0)
        try:
            u = fixed.union_all()
        except Exception:
            u = fixed.buffer(1e-6).union_all().buffer(-1e-6)
        if len(g) > 100:  # planting plots / ponds: merge into a landscape outline
            u = u.buffer(0.003).buffer(-0.003)
        rows.append(
            {
                "kind": "verra",
                "name": rec.get("project_name"),
                "vcs_id": i,
                "proponent": rec.get("account_name"),
                "status": rec.get("state_name"),
                "afolu": rec.get("afolu_names"),
                "area_ha": round(gpd.GeoSeries([u], crs=4326).to_crs("+proj=cea").area.iloc[0] / 1e4),
                "source": f"Verra registry ({pick.name})",
                "geometry": u.simplify(SIMPLIFY),
            }
        )
    out = gpd.GeoDataFrame(rows, crs=4326)
    print(f"verra: {len(out)}")
    return out


def protected() -> gpd.GeoDataFrame:
    import ee

    from satimg import layers  # noqa: E402

    layers.init_ee()
    fc = (
        ee.FeatureCollection("WCMC/WDPA/current/polygons")
        .filterBounds(ee.Geometry.Rectangle(list(INDONESIA_BBOX)))
        .filter(ee.Filter.eq("ISO3", "IDN"))
        .filter(ee.Filter.gt("REP_AREA", 10))
        .map(lambda f: f.simplify(300).select(["NAME", "DESIG_ENG", "IUCN_CAT", "REP_AREA", "ISO3", "REALM"]))
    )
    # getInfo() caps at ~5000 features / payload size; page by chunks via toList.
    n = fc.size().getInfo()
    feats = []
    for start in range(0, n, 500):
        feats += ee.FeatureCollection(fc.toList(500, start)).getInfo()["features"]
    print(f"  WDPA IDN features: {n}")
    from shapely.geometry import MultiPolygon, Polygon, shape

    def polys_only(geom):  # EE's simplify() returns GeometryCollections with stray lines
        s = shape(geom)
        if s.geom_type == "GeometryCollection":
            parts = [p for q in s.geoms for p in (q.geoms if q.geom_type == "MultiPolygon" else [q]) if p.geom_type == "Polygon"]
            s = MultiPolygon(parts) if parts else Polygon()
        return s

    for f in feats:
        f["geometry"] = polys_only(f["geometry"]).__geo_interface__
    g = gpd.GeoDataFrame.from_features(feats, crs=4326)
    g = g[~g.geometry.is_empty]
    out = gpd.GeoDataFrame(
        {
            "kind": "protected",
            "name": g.NAME,
            "designation": g.DESIG_ENG,
            "iucn": g.IUCN_CAT,
            "country": g.ISO3,
            "national_park": g.DESIG_ENG.str.contains("National Park", na=False),
            "realm": g.REALM,
            "area_ha": (g.REP_AREA * 100).round(),
            "source": "WDPA (UNEP-WCMC) via Earth Engine",
        },
        geometry=g.geometry,
        crs=4326,
    )
    print(f"protected: {len(out)} ({int(out.national_park.sum())} national parks)")
    return out


KEMENHUT = "https://geoportal.planologi.kehutanan.go.id/server/rest/services/Peta_Interaktif_2026"


def village_forests() -> gpd.GeoDataFrame:
    """Hutan Desa (village forest) social-forestry permits, Kalimantan, from the Kemenhut REST API."""
    url = f"{KEMENHUT}/PPHD_AR_50K/MapServer/0/query"
    feats, offset = [], 0
    while True:
        r = httpx.get(
            url,
            params={
                "where": "1=1",
                "outFields": "KODE_PROV,NAMA_KEC,NAMA_DESA,NAMA_LD,NO_SK_PPHD,TGL_SK_PPHD,LUAS_PPHD",
                "returnGeometry": "true",
                "outSR": "4326",
                "f": "geojson",
                "resultOffset": offset,
                "resultRecordCount": 1000,
            },
            timeout=300,
        )
        r.raise_for_status()
        page = r.json()
        feats += page.get("features", [])
        if not page.get("properties", {}).get("exceededTransferLimit") and len(page.get("features", [])) < 1000:
            break
        offset += 1000
    g = gpd.GeoDataFrame.from_features(feats, crs=4326)
    out = gpd.GeoDataFrame(
        {
            "kind": "village_forest",
            "name": g.NAMA_LD.str.title() + " (" + g.NAMA_DESA + ")",
            "village": g.NAMA_DESA,
            "subdistrict": g.NAMA_KEC,
            "province": g.KODE_PROV.astype(str).map(PROVINCES),
            "sk": g.NO_SK_PPHD,
            "sk_date": pd.to_datetime(g.TGL_SK_PPHD, unit="ms", errors="coerce").dt.strftime("%Y-%m-%d"),
            "area_ha": g.LUAS_PPHD,
            "source": "Kemenhut PPHD_AR_50K (2026)",
        },
        geometry=g.geometry.simplify(SIMPLIFY),
        crs=4326,
    )
    print(f"village forests: {len(out)}")
    return out


def main() -> None:
    g = pd.concat([concessions(), verra(), protected(), village_forests()], ignore_index=True)
    g = gpd.GeoDataFrame(g, crs=4326)
    from shapely import make_valid

    g = g.set_geometry(g.geometry.apply(make_valid).buffer(0).set_precision(1e-5))
    g.to_file(OUT, driver="GeoJSON", COORDINATE_PRECISION=5)
    print("wrote", OUT, f"{OUT.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
