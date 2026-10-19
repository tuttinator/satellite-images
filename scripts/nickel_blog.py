"""Package outputs/nickel for the blog's static data directory.

Copies sites.json and air.json (minified) and each site's cleared.png, and re-encodes the yearly
frames as progressive JPEG at quality 74, which roughly halves Earth Engine's thumbnails without
visible loss at the size the post shows them.

Run:  uv run --with pillow python scripts/nickel_blog.py [--dest DIR]
      (default: ../caleb-tutty.com/static/data/nickel-boom, or $BLOG_DATA_DIR)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "outputs" / "nickel"
DEFAULT_DEST = ROOT.parent / "caleb-tutty.com" / "static" / "data" / "nickel-boom"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dest", type=Path, default=Path(os.environ.get("BLOG_DATA_DIR", DEFAULT_DEST)))
    dest = p.parse_args().dest
    dest.mkdir(parents=True, exist_ok=True)

    for name in ("sites.json", "air.json"):
        (dest / name).write_text(json.dumps(json.loads((SRC / name).read_text()), separators=(",", ":")))

    sites = json.loads((SRC / "sites.json").read_text())["sites"]
    for site in sites:
        src, out = SRC / site["id"], dest / site["id"]
        out.mkdir(exist_ok=True)
        shutil.copyfile(src / "cleared.png", out / "cleared.png")
        for jpg in sorted(src.glob("*.jpg")):
            Image.open(jpg).save(out / jpg.name, "JPEG", quality=74, progressive=True, optimize=True)

    total = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file())
    print(f"{total / 1e6:.1f} MB in {dest}")


if __name__ == "__main__":
    main()
