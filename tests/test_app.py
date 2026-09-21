import json
from pathlib import Path

from fastapi.testclient import TestClient

from satimg import layers
from satimg.app import app

ROOT = Path(__file__).resolve().parents[1]


def test_concessions_geojson_is_valid():
    gj = json.loads((ROOT / "data" / "concessions.geojson").read_text())
    assert gj["type"] == "FeatureCollection"
    ids = [f["id"] for f in gj["features"]]
    assert len(ids) == len(set(ids))
    for f in gj["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            ring = poly[0]
            assert ring[0] == ring[-1], f"{f['id']} ring not closed"
            for lon, lat in ring:
                assert 111 < lon < 115 and -4 < lat < -1, f"{f['id']} outside Central Kalimantan"


def test_static_endpoints():
    with TestClient(app) as c:
        assert c.get("/").status_code == 200
        assert c.get("/api/concessions").json()["features"]
        ids = {row["id"] for row in c.get("/api/layers").json()}
        assert ids == set(layers.VIS) | {"change", "dnbr", "fire"}
        assert c.get("/story").status_code == 200
        assert c.get("/api/fire/borneo").status_code in (200, 404)
        assert c.get("/api/fire/sumatra").status_code in (200, 404)
        assert c.get("/api/fire/java").status_code == 404


def test_change_requires_before_window():
    with TestClient(app) as c:
        r = c.get("/api/tiles", params={"layer": "change", "start": "2026-05-01", "end": "2026-08-01"})
        assert r.status_code == 400


def test_unknown_concession_404():
    with TestClient(app) as c:
        r = c.get("/api/timeseries", params={"id": "nope", "start": "2025-01-01", "end": "2026-01-01"})
        assert r.status_code == 404
