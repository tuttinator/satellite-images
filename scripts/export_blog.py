"""Package the haze / fire-season outputs for a website's static data directory.

Reads   outputs/sea_haze.json, outputs/{sumatra,borneo}_fire.json
Writes  <dest>/haze.json      — outputs/sea_haze.json, copied as-is
        <dest>/seasons.json   — a trimmed view of the two fire-season files: monthly island totals
                                by year, this year's monthly totals per province, and the last
                                day the FIRMS record runs to

Run:  uv run python scripts/export_blog.py [--dest DIR]

The default destination is the author's blog checkout next to this repo
(../caleb-tutty.com/static/data/sea-haze). Pass --dest, or set BLOG_DATA_DIR, to write anywhere
else. The JSON shapes are documented in docs/sea-haze.md.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEST = ROOT.parent / "caleb-tutty.com" / "static" / "data" / "sea-haze"


def seasons() -> dict:
    out: dict = {"islands": {}}
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
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "--dest",
        type=Path,
        default=Path(os.environ.get("BLOG_DATA_DIR", DEFAULT_DEST)),
        help="directory to write haze.json and seasons.json into (default: %(default)s)",
    )
    dest = p.parse_args().dest
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / "outputs" / "sea_haze.json", dest / "haze.json")
    (dest / "seasons.json").write_text(json.dumps(seasons(), separators=(",", ":")))
    for name in ("haze.json", "seasons.json"):
        print(f"{(dest / name).stat().st_size / 1e3:8.0f} KB  {dest / name}")


if __name__ == "__main__":
    main()
