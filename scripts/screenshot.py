"""Screenshot a viewer page after MapLibre has finished loading tiles, via Chrome DevTools.

    uv run --with websocket-client python scripts/screenshot.py URL OUT.png [JS]

JS (optional) runs once the map has loaded, before the tile wait — e.g.
"selectConcession('rimba-raya')" or "$('layer').value='fire'; loadImagery()".
Needs Google Chrome in /Applications.
"""

from __future__ import annotations

import base64
import json
import subprocess
import sys
import tempfile
import time
import urllib.request

import websocket

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PORT = 9333
READY_JS = (
    "typeof map !== 'undefined' && map.loaded() && (() => { const s = (document.getElementById('status')"
    "||{textContent:''}).textContent; return s.length > 0 && !s.includes('…'); })()"
)
TILE_SETTLE_S = 12  # Earth Engine tiles are computed on demand; give them a moment after "ready"


def main(url: str, out: str, pre_js: str | None, width=1400, height=900) -> None:
    profile = tempfile.mkdtemp(prefix="satimg-chrome-")
    proc = subprocess.Popen(
        [CHROME, "--headless=new", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
         "--hide-scrollbars", f"--window-size={width},{height}", f"--remote-debugging-port={PORT}",
         f"--user-data-dir={profile}", "about:blank"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        tabs = None
        for _ in range(100):
            try:
                tabs = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json", timeout=2))
                if tabs:
                    break
            except Exception:
                time.sleep(0.2)
        if not tabs:
            raise SystemExit("Chrome DevTools endpoint did not come up")
        page = next(t for t in tabs if t["type"] == "page")
        ws = websocket.create_connection(page["webSocketDebuggerUrl"], suppress_origin=True, timeout=30)
        mid = 0

        def call(method, **params):
            nonlocal mid
            mid += 1
            ws.send(json.dumps({"id": mid, "method": method, "params": params}))
            while True:
                msg = json.loads(ws.recv())
                if msg.get("id") == mid:
                    return msg.get("result", {})

        def js(expr):
            r = call("Runtime.evaluate", expression=expr, returnByValue=True, awaitPromise=True)
            return r.get("result", {}).get("value")

        call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=1, mobile=False)
        call("Page.navigate", url=url)
        for _ in range(120):
            if js("typeof map !== 'undefined' && map.loaded()"):
                break
            time.sleep(0.5)
        if pre_js:
            js(pre_js)
            time.sleep(1)
        t0 = time.time()
        for _ in range(240):
            if js(READY_JS):
                break
            time.sleep(0.5)
        print(f"ready after {time.time() - t0:.0f}s; status: {js('document.getElementById(\"status\").textContent')!r}")
        for _ in range(TILE_SETTLE_S * 2):
            if js("map.areTilesLoaded()"):
                break
            time.sleep(0.5)
        shot = call("Page.captureScreenshot", format="png")
        with open(out, "wb") as fh:
            fh.write(base64.b64decode(shot["data"]))
        print("wrote", out)
    finally:
        proc.kill()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
