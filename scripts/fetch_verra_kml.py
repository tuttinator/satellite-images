"""Fetch project metadata and boundary KMLs from the Verra registry (post-Jul-2026 S&P platform).

    uv run python scripts/fetch_verra_kml.py 1477 674 1899 --out data/verra

For each VCS id: writes <id>.json (registry record) and every KML in its document list.
Endpoints and headers were discovered from https://registry.verra.org/config/environment.config.json;
they are the same ones the registry's own web app uses.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

API = "https://prod-us.api.platts.com/ci-raas-prod/br-reg/rest"
HEADERS = {
    "appkey": "wOKHFGuxKApQaujPSKgF",
    "application": "Markit",
    "X-XSRF-TOKEN": "t20",
    "Cookie": "XSRF-TOKEN=t20",
    "standardId": "150000000000001",
    "standardAcronym": "VCS",
    "Origin": "https://registry.verra.org",
    "Referer": "https://registry.verra.org/",
}


def fetch(vcs_id: int, out: Path) -> None:
    r = httpx.get(f"{API}/public-report-manager/getProjectById/{vcs_id}/Markit", headers=HEADERS, timeout=60)
    r.raise_for_status()
    rec = r.json()
    (out / f"{vcs_id}.json").write_text(json.dumps(rec, indent=1))
    docs = rec.get("documentList") or []
    kmls = [d for d in docs if str(d.get("document_name", "")).lower().endswith((".kml", ".kmz"))]
    print(f"VCS {vcs_id}: {rec.get('project_name')} [{rec.get('state_name')}] — {len(kmls)} KML(s)")
    for d in kmls:
        did = d["id"]
        name = d["document_name"]
        dl = httpx.post(
            f"{API}/document-manager/public/downloadDocumentById",
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"id": did},
            timeout=120,
        )
        dl.raise_for_status()
        path = out / f"{vcs_id}_{did}_{name}"
        path.write_bytes(dl.content)
        print(f"  {path.name} ({len(dl.content) // 1024} KB)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("ids", nargs="+", type=int)
    p.add_argument("--out", default="data/verra")
    a = p.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for i in a.ids:
        fetch(i, out)
