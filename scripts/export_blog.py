"""Sync the haze / fire-season outputs into the blog's static data.

Reads  outputs/sea_haze.json, outputs/{sumatra,borneo}_fire.json
Writes ../caleb-tutty.com/static/data/sea-haze/{haze,seasons}.json

Run:  uv run python scripts/export_blog.py
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT.parent / "caleb-tutty.com" / "static" / "data" / "sea-haze"


def seasons() -> dict:
    out = {"islands": {}}
    for island in ("sumatra", "borneo"):
        d = json.loads((ROOT / "outputs" / f"{island}_fire.json").read_text())
        monthly = d["regions"][island]["monthly"]
        years: dict[str, list] = {}
        for key, v in monthly.items():
            y, m = key.split("-")
            years.setdefault(y, [None] * 12)[int(m) - 1] = v["fire_km2"]
        this_year = d["generated"][:4]
        daily = d["regions"][island]["daily"]
        # FIRMS lands a day or so late: the series runs to the last day with any detection.
        through = max(k for k, v in daily.items() if v > 0)
        provinces = [
            {
                "label": r["label"],
                "months": {k[5:]: v["fire_km2"] for k, v in r["monthly"].items() if k.startswith(this_year)},
            }
            for k, r in d["regions"].items()
            if k != island
        ]
        out["islands"][island] = {"label": d["regions"][island]["label"], "years": years, "provinces": provinces}
        out["generated"] = d["generated"]
        out["through"] = min(out.get("through", through), through)
    return out


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "outputs" / "sea_haze.json", DEST / "haze.json")
    (DEST / "seasons.json").write_text(json.dumps(seasons(), separators=(",", ":")))
    for p in sorted(DEST.iterdir()):
        print(f"{p.stat().st_size / 1e3:8.0f} KB  {p.name}")


if __name__ == "__main__":
    main()
