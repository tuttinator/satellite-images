const css = (v) => getComputedStyle(document.documentElement).getPropertyValue(v).trim();
const fmt = (n) => Math.round(n).toLocaleString();
const iso = (d) => d.toISOString().slice(0, 10);

Chart.defaults.font.family = "system-ui, -apple-system, 'Segoe UI', sans-serif";
Chart.defaults.color = css("--muted");
Chart.defaults.borderColor = css("--grid");
Chart.defaults.animation = false;
Chart.defaults.plugins.tooltip.mode = "index";
Chart.defaults.plugins.tooltip.intersect = false;

(async () => {
  const data = await (await fetch("/api/borneo_fire")).json();
  const R = data.regions;
  const B = R.borneo.monthly;
  const thisYear = +data.generated.slice(0, 4);
  const thisMonth = +data.generated.slice(5, 7);
  const mkey = (y, m) => `${y}-${String(m).padStart(2, "0")}`;
  const CMP = [2015, 2019, 2023];

  // ---- stat tiles
  const augNow = B[mkey(thisYear, 8)].fire_km2;
  const augCmp = CMP.map((y) => B[mkey(y, 8)].fire_km2);
  const ytd = (y) => [...Array(8)].reduce((s, _, i) => s + B[mkey(y, i + 1)].fire_km2, 0);
  const provAug = Object.entries(R).filter(([k]) => k !== "borneo")
    .map(([k, v]) => [v.label, v.monthly[mkey(thisYear, 8)].fire_km2]).sort((a, b) => b[1] - a[1]);
  document.getElementById("tiles").innerHTML = [
    [fmt(augNow), `km² fire footprint, 1–21 Aug ${thisYear}`, true],
    [fmt(Math.max(...augCmp)), `previous August record (${CMP[augCmp.indexOf(Math.max(...augCmp))]})`],
    [`${(augNow / (augCmp.reduce((a, b) => a + b) / 3)).toFixed(1)}×`, "the Aug 2015 / 2019 / 2023 average"],
    [`${fmt((100 * provAug[0][1]) / augNow)}%`, `of August fire is in ${provAug[0][0]}`],
  ].map(([v, l, hero]) => `<div class="tile"><div class="v ${hero ? "hero" : ""}">${v}</div><div class="l">${l}</div></div>`).join("");

  // ---- map
  const seq = ["--seq1", "--seq2", "--seq3", "--seq4", "--seq5"].map(css);
  const maxAug = provAug[0][1];
  const breaks = [0.05, 0.15, 0.35, 0.65].map((f) => f * maxAug);
  document.getElementById("legend-ticks").textContent = `0 · ${breaks.map(fmt).join(" · ")} · ${fmt(maxAug)}`;
  const outlines = data.outlines;
  outlines.features = outlines.features.filter((f) => f.properties.key !== "borneo");
  for (const f of outlines.features) {
    const v = R[f.properties.key].monthly[mkey(thisYear, 8)].fire_km2;
    f.properties.aug = v;
    f.properties.color = seq[breaks.filter((b) => v > b).length];
  }
  const map = new maplibregl.Map({
    container: "map",
    style: { version: 8, sources: { osm: { type: "raster", tileSize: 256,
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"], attribution: "© OpenStreetMap · NASA FIRMS · Google Earth Engine" } },
      layers: [{ id: "osm", type: "raster", source: "osm", paint: { "raster-saturation": -0.9, "raster-opacity": 0.6 } }] },
    center: [114.2, 0.8], zoom: 5.2, attributionControl: true,
  });
  map.addControl(new maplibregl.NavigationControl({ showCompass: false }));
  map.on("load", async () => {
    map.addSource("prov", { type: "geojson", data: outlines });
    map.addLayer({ id: "prov-fill", type: "fill", source: "prov", paint: { "fill-color": ["get", "color"], "fill-opacity": 0.55 } });
    map.addLayer({ id: "prov-line", type: "line", source: "prov", paint: { "line-color": css("--ink2"), "line-width": 0.8 } });
    const end = new Date(data.generated); const start = new Date(end); start.setDate(start.getDate() - 7);
    try {
      const t = await (await fetch(`/api/tiles?layer=fire&start=${iso(start)}&end=${iso(end)}`)).json();
      if (t.url) {
        map.addSource("fire", { type: "raster", tiles: [t.url], tileSize: 256 });
        map.addLayer({ id: "fire", type: "raster", source: "fire" });
      }
    } catch {}
    const pop = new maplibregl.Popup({ closeButton: false, closeOnClick: false });
    map.on("mousemove", "prov-fill", (e) => {
      const p = e.features[0].properties;
      pop.setLngLat(e.lngLat).setHTML(`<b>${p.label}</b><br>${fmt(p.aug)} km² in Aug ${thisYear}`).addTo(map);
    });
    map.on("mouseleave", "prov-fill", () => pop.remove());
  });

  // ---- monthly comparison
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const ctx = ["--ctx1", "--ctx2", "--ctx3"].map(css);
  const labelEnd = {
    id: "labelEnd",
    afterDatasetsDraw(c) {
      const { ctx: g } = c;
      g.save(); g.font = "12px system-ui"; g.textBaseline = "middle";
      c.data.datasets.forEach((ds, i) => {
        if (ds.borderColor !== css("--hero")) return; // context years are named in the legend
        const meta = c.getDatasetMeta(i);
        const pts = meta.data.filter((p, j) => ds.data[j] != null);
        const last = pts[pts.length - 1]; if (!last) return;
        g.fillStyle = ds.borderColor; g.fillText(ds.label, last.x + 6, last.y);
      });
      g.restore();
    },
  };
  new Chart(document.getElementById("monthly"), {
    type: "line",
    plugins: [labelEnd],
    data: {
      labels: months,
      datasets: [
        ...CMP.map((y, i) => ({ label: String(y), data: months.map((_, m) => B[mkey(y, m + 1)].fire_km2),
          borderColor: ctx[i], borderWidth: 1.5, pointRadius: 0, tension: 0.25 })),
        { label: String(thisYear), data: months.map((_, m) => (m + 1 <= thisMonth ? B[mkey(thisYear, m + 1)].fire_km2 : null)),
          borderColor: css("--hero"), borderWidth: 2.5, pointRadius: 0, tension: 0.25 },
      ],
    },
    options: { layout: { padding: { right: 40 } }, plugins: { legend: { position: "bottom", labels: { boxWidth: 18, boxHeight: 2 } } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "km²" } }, x: { grid: { display: false } } } },
  });

  // ---- daily
  const daily = R.borneo.daily;
  const days = Object.keys(daily).slice(0, -2);
  const vals = days.map((d) => daily[d]);
  const roll = vals.map((_, i) => { const w = vals.slice(Math.max(0, i - 6), i + 1); return w.reduce((a, b) => a + b) / w.length; });
  new Chart(document.getElementById("daily"), {
    type: "bar",
    data: { labels: days.map((d) => d.slice(5)), datasets: [
      { type: "line", label: "7-day average", data: roll, borderColor: css("--hero"), borderWidth: 2.5, pointRadius: 0, tension: 0.3, order: 0 },
      { label: "daily", data: vals, backgroundColor: css("--ctx1"), borderRadius: 2, order: 1 },
    ] },
    options: { plugins: { legend: { position: "bottom", labels: { boxWidth: 12 } } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "km²" } }, x: { grid: { display: false }, ticks: { maxTicksLimit: 10 } } } },
  });

  // ---- annual burned area
  const years = [...new Set(Object.keys(B).map((k) => k.slice(0, 4)))];
  const annual = years.map((y) => Object.entries(B).filter(([k]) => k.startsWith(y)).reduce((s, [, v]) => s + v.burned_km2, 0));
  new Chart(document.getElementById("annual"), {
    type: "bar",
    data: { labels: years, datasets: [{ label: "burned km²", data: annual,
      backgroundColor: years.map((y) => (+y === thisYear ? css("--ctx1") : css("--seq4"))), borderRadius: 3 }] },
    options: { plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, title: { display: true, text: "km²" } }, x: { grid: { display: false } } } },
  });

  // ---- province table
  const rows = Object.entries(R).filter(([k]) => k !== "borneo")
    .sort((a, b) => b[1].monthly[mkey(thisYear, 8)].fire_km2 - a[1].monthly[mkey(thisYear, 8)].fire_km2);
  document.getElementById("provtable").innerHTML =
    `<tr><th>Province</th><th>Jun</th><th>Jul</th><th>Aug (to 21st)</th><th>Aug 2023</th></tr>` +
    rows.map(([, v]) => `<tr><td>${v.label}</td>${[6, 7, 8].map((m) => `<td>${fmt(v.monthly[mkey(thisYear, m)].fire_km2)}</td>`).join("")}<td>${fmt(v.monthly["2023-08"].fire_km2)}</td></tr>`).join("") +
    `<tr><th>Borneo</th>${[6, 7, 8].map((m) => `<th>${fmt(B[mkey(thisYear, m)].fire_km2)}</th>`).join("")}<th>${fmt(B["2023-08"].fire_km2)}</th></tr>`;
})();
