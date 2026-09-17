const $ = (id) => document.getElementById(id);

const COLORS = {
  "katingan-mentaya": "#ff7f00", "rimba-raya": "#e31a1c", sebangau: "#1f78b4", "tanjung-puting": "#6a3d9a",
  "katingan-verra": "#b35900", "rimba-raya-verra": "#99000d",
};
const LEGENDS = {
  ndvi: { min: 0, max: 0.9, palette: ["#a50026", "#f46d43", "#fee08b", "#d9ef8b", "#66bd63", "#006837"] },
  nbr: { min: -0.2, max: 0.8, palette: ["#7f3b08", "#fdb863", "#f7f7f7", "#b2abd2", "#542788"] },
  ndmi: { min: -0.2, max: 0.6, palette: ["#8c510a", "#f6e8c3", "#c7eae5", "#01665e"] },
  change: { min: -0.4, max: 0.4, palette: ["#b2182b", "#ef8a62", "#fddbc7", "#f7f7f7", "#d1e5f0", "#67a9cf", "#2166ac"] },
  dnbr: { min: 0.1, max: 0.8, palette: ["#fff7bc", "#fec44f", "#fe9929", "#d95f0e", "#993404", "#4d004b"],
    note: "dNBR = NBR before − after · 0.27+ moderate burn · 0.66+ high severity" },
  fire: { min: "older", max: "newest", palette: ["#67000d", "#cb181d", "#fb6a4a", "#fd8d3c", "#feb24c", "#ffff33"],
    note: "MODIS active-fire pixels (1 km), coloured by most recent detection" },
};
const YEAR_COLORS = { 2015: "#bbb", 2019: "#888", 2023: "#555", 2025: "#9ecae1", 2026: "#d7301f" };
const SEASON_START = new Date(new Date().getFullYear(), 5, 1); // 1 June

const iso = (d) => d.toISOString().slice(0, 10);
const today = new Date();
const monthsAgo = (n) => { const d = new Date(today); d.setMonth(d.getMonth() - n); return d; };

// Defaults: last 3 months vs the same window a year earlier.
$("end").value = iso(today);
$("start").value = iso(monthsAgo(3));
$("bend").value = iso(monthsAgo(12));
$("bstart").value = iso(monthsAgo(15));

const map = new maplibregl.Map({
  container: "map",
  style: {
    version: 8,
    sources: {
      osm: {
        type: "raster", tileSize: 256,
        tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
        attribution: "© OpenStreetMap contributors · Sentinel-2 © Copernicus / Google Earth Engine",
      },
    },
    layers: [{ id: "osm", type: "raster", source: "osm" }],
  },
  center: [113.2, -2.6],
  zoom: 8.3,
});
map.addControl(new maplibregl.NavigationControl(), "top-right");
map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-right");

let concessions, chart, activeId;
const hiddenFocus = new Set();

function applyFocusVisibility() {
  if (!map.getLayer("concessions-fill")) return;
  const shown = ["!", ["in", ["get", "id"], ["literal", [...hiddenFocus]]]];
  map.setFilter("concessions-fill", shown);
  map.setFilter("concessions-line", ["all", ["!", ["get", "verra"]], shown]);
  map.setFilter("verra-line", ["all", ["get", "verra"], shown]);
}

const panelReady = (async () => {
  const layers = await (await fetch("/api/layers")).json();
  for (const l of layers) $("layer").add(new Option(l.label, l.id));

  concessions = await (await fetch("/api/concessions")).json();
  for (const f of concessions.features) {
    f.properties.id = f.id;
    f.properties.color = COLORS[f.id] || "#333";
    f.properties.verra = f.id.endsWith("-verra");
  }
  const ul = $("list");
  for (const f of concessions.features) {
    const li = document.createElement("li");
    li.dataset.id = f.id;
    li.innerHTML = `<input type="checkbox" class="vis" checked title="show on map" />
      <span class="swatch" style="border-color:${f.properties.color};${f.properties.verra ? "border-style:dashed" : ""}"></span>
      <div>${f.properties.name}<small>${f.properties.type} · ~${f.properties.approx_area_ha.toLocaleString()} ha</small></div>`;
    li.querySelector("div").onclick = () => selectConcession(f.id);
    li.querySelector(".vis").onchange = (e) => {
      if (e.target.checked) hiddenFocus.delete(f.id); else hiddenFocus.add(f.id);
      applyFocusVisibility();
    };
    ul.append(li);
  }
})();

const CTX_STYLE = {
  concession: { color: "#8c6d31", fill: 0.08, width: 0.8 },
  verra: { color: "#b35900", fill: 0.0, width: 1.5, dash: [3, 2] },
  village_forest: { color: "#2ca25f", fill: 0.15, width: 0.8 },
  protected: { color: "#1f78b4", fill: 0.08, width: 1.2 },
};

function ctxPopup(p) {
  const ha = p.area_ha ? `${Math.round(p.area_ha).toLocaleString()} ha` : "";
  const lines = {
    concession: [`<b>${p.name}</b>`, `Forestry concession (PBPH)${p.restoration ? " — <b>ecosystem restoration holder</b>" : ""}`,
      `${p.province} · ${p.status} · ${ha}`, `${p.sk} (${p.sk_date})`],
    verra: [`<b>${p.name}</b>`, `Verra VCS ${p.vcs_id} · ${p.afolu}`, `${p.proponent}`, `${p.status} · ${ha}`],
    village_forest: [`<b>${p.name}</b>`, `Village forest (Hutan Desa) · ${p.subdistrict}, ${p.province}`, `${p.sk} (${p.sk_date}) · ${ha}`],
    protected: [`<b>${p.name}</b>`, `${p.designation}${p.iucn && p.iucn !== "Not Reported" ? ` · IUCN ${p.iucn}` : ""}`, `${ha}`],
  }[p.kind] || [`<b>${p.name}</b>`];
  return lines.join("<br>") + `<br><small>${p.source}</small>`;
}

async function addContextLayers() {
  const data = await (await fetch("/api/context")).json();
  map.addSource("ctx", { type: "geojson", data });
  const counts = {};
  for (const f of data.features) counts[f.properties.kind] = (counts[f.properties.kind] || 0) + 1;
  document.querySelectorAll("#ctx-toggles input").forEach((cb) => {
    const n = cb.parentElement.querySelector("span.n");
    if (n) n.textContent = counts[cb.dataset.kind] || 0;
  });
  for (const [kind, s] of Object.entries(CTX_STYLE)) {
    map.addLayer({ id: `ctx-${kind}-fill`, type: "fill", source: "ctx", filter: ["==", ["get", "kind"], kind],
      paint: { "fill-color": s.color, "fill-opacity": s.fill } });
    map.addLayer({ id: `ctx-${kind}-line`, type: "line", source: "ctx", filter: ["==", ["get", "kind"], kind],
      paint: { "line-color": s.color, "line-width": s.width, ...(s.dash ? { "line-dasharray": s.dash } : {}) } });
    map.on("click", `ctx-${kind}-fill`, (e) => {
      if (map.queryRenderedFeatures(e.point, { layers: ["concessions-fill"] }).length) return;
      new maplibregl.Popup().setLngLat(e.lngLat).setHTML(ctxPopup(e.features[0].properties)).addTo(map);
    });
    map.on("mouseenter", `ctx-${kind}-fill`, () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", `ctx-${kind}-fill`, () => (map.getCanvas().style.cursor = ""));
  }
  document.querySelectorAll("#ctx-toggles input").forEach((cb) => {
    cb.onchange = () => {
      const v = cb.checked ? "visible" : "none";
      map.setLayoutProperty(`ctx-${cb.dataset.kind}-fill`, "visibility", v);
      map.setLayoutProperty(`ctx-${cb.dataset.kind}-line`, "visibility", v);
    };
  });
}

map.on("load", async () => {
  await panelReady;
  await addContextLayers();
  map.addSource("concessions", { type: "geojson", data: concessions });
  map.addLayer({
    id: "concessions-fill", type: "fill", source: "concessions",
    paint: { "fill-color": ["get", "color"], "fill-opacity": 0.06 },
  });
  map.addLayer({
    id: "concessions-line", type: "line", source: "concessions",
    filter: ["!", ["get", "verra"]],
    paint: { "line-color": ["get", "color"], "line-width": 2.5 },
  });
  map.addLayer({
    id: "verra-line", type: "line", source: "concessions",
    filter: ["get", "verra"],
    paint: { "line-color": ["get", "color"], "line-width": 2, "line-dasharray": [3, 2] },
  });
  applyFocusVisibility();
  map.on("click", "concessions-fill", (e) => selectConcession(e.features[0].properties.id));
  map.on("mouseenter", "concessions-fill", () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", "concessions-fill", () => (map.getCanvas().style.cursor = ""));

  loadImagery();
});

const seasonDays = Math.round((today - SEASON_START) / 86400000);
$("fire-slider").max = seasonDays;
$("fire-slider").value = seasonDays;

function fireWindow() {
  const end = new Date(SEASON_START); end.setDate(end.getDate() + +$("fire-slider").value + 1);
  const start = new Date(end); start.setDate(start.getDate() - 7);
  return [iso(start), iso(end)];
}

$("layer").onchange = () => {
  const l = $("layer").value;
  $("before").classList.toggle("hidden", !(l === "change" || l === "dnbr"));
  $("firectl").classList.toggle("hidden", l !== "fire");
  if (l === "dnbr") {
    // default: pre-season vs now
    $("bstart").value = iso(new Date(today.getFullYear(), 2, 1));
    $("bend").value = iso(new Date(today.getFullYear(), 5, 15));
    $("start").value = iso(new Date(today.getFullYear(), 7, 1));
  }
};
let sliderTimer;
$("fire-slider").oninput = () => {
  $("fire-date").textContent = fireWindow()[1];
  clearTimeout(sliderTimer);
  sliderTimer = setTimeout(loadImagery, 350);
};
$("fire-date").textContent = fireWindow()[1];
$("apply").onclick = loadImagery;
$("opacity").oninput = () => {
  if (map.getLayer("s2")) map.setPaintProperty("s2", "raster-opacity", +$("opacity").value);
};
$("ts-index").onchange = () => activeId && loadTimeseries(activeId);

async function loadImagery() {
  const layer = $("layer").value;
  const q = new URLSearchParams({ layer, start: $("start").value, end: $("end").value });
  if (layer === "fire") {
    const [s, e] = fireWindow();
    q.set("start", s); q.set("end", e);
  }
  if (layer === "change" || layer === "dnbr") {
    q.set("before_start", $("bstart").value);
    q.set("before_end", $("bend").value);
  }
  setStatus("status", "Building composite…");
  $("apply").disabled = true;
  try {
    const res = await fetch(`/api/tiles?${q}`);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);
    if (map.getLayer("s2")) { map.removeLayer("s2"); map.removeSource("s2"); }
    map.addSource("s2", { type: "raster", tiles: [body.url], tileSize: 256 });
    map.addLayer(
      { id: "s2", type: "raster", source: "s2", paint: { "raster-opacity": +$("opacity").value } },
      map.getLayer("ctx-concession-fill") ? "ctx-concession-fill" : "concessions-fill",
    );
    setStatus("status", `${$("layer").selectedOptions[0].text} · ${body.start} → ${body.end}`);
    renderLegend(layer);
    if (layer === "dnbr" && activeId) loadBurned(activeId);
  } catch (err) {
    setStatus("status", err.message, true);
  } finally {
    $("apply").disabled = false;
  }
}

function renderLegend(layer) {
  const lg = LEGENDS[layer];
  const el = $("legend");
  if (!lg) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="bar" style="background:linear-gradient(90deg,${lg.palette.join(",")})"></div>
    <div class="ticks"><span>${lg.min}</span><span>${typeof lg.min === "number" ? (lg.min + lg.max) / 2 : ""}</span><span>${lg.max}</span></div>
    ${layer === "change" ? "<div>red = canopy loss · blue = regrowth · |Δ| < 0.08 hidden</div>" : ""}
    ${lg.note ? `<div>${lg.note}</div>` : ""}`;
}

async function loadBurned(id) {
  const q = new URLSearchParams({
    id, before_start: $("bstart").value, before_end: $("bend").value, start: $("start").value, end: $("end").value,
  });
  const el = $("burned");
  el.classList.remove("hidden");
  el.textContent = "Computing burned area (Sentinel-2 dNBR, ~30 s)…";
  try {
    const res = await fetch(`/api/fire/burned?${q}`);
    const b = await res.json();
    if (!res.ok) throw new Error(b.detail);
    if (id !== activeId) return;
    const pct = (x) => (b.valid ? ((100 * x) / b.valid).toFixed(1) : "–");
    el.innerHTML = `<b>Burn scars ${$("bstart").value}…${$("bend").value} → ${$("start").value}…${$("end").value}</b><br>
      moderate+ (dNBR > 0.27): <b>${b.moderate.toLocaleString()} ha</b> (${pct(b.moderate)}% of clear pixels)<br>
      high severity (dNBR > 0.66): <b>${b.high.toLocaleString()} ha</b> (${pct(b.high)}%)<br>
      <small>clear in both windows: ${b.valid.toLocaleString()} ha</small>`;
  } catch (err) {
    el.textContent = err.message;
  }
}

let fireChart;
async function loadFireChart(id) {
  setStatus("fire-status", "Computing weekly fire footprint for 2015/2019/2023/2025/2026…");
  try {
    const res = await fetch(`/api/fire/weekly?${new URLSearchParams({ id })}`);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail);
    if (id !== activeId) return;
    fireChart?.destroy();
    const weeks = Array.from({ length: 52 }, (_, i) => i + 1);
    const thisYear = new Date().getFullYear();
    fireChart = new Chart($("firechart"), {
      type: "line",
      data: {
        labels: weeks,
        datasets: Object.entries(body.years).map(([y, vals]) => ({
          label: y, data: vals,
          borderColor: YEAR_COLORS[y] || "#999", borderWidth: +y === thisYear ? 2.5 : 1.2,
          pointRadius: 0, tension: 0.2,
        })),
      },
      options: {
        animation: false,
        plugins: { legend: { display: true, labels: { boxWidth: 10, font: { size: 10 } } } },
        scales: { x: { title: { display: true, text: "week of year" }, ticks: { maxTicksLimit: 12 } }, y: { beginAtZero: true } },
      },
    });
    setStatus("fire-status", "km² of 1 km MODIS pixels with ≥1 detection per week. 2026 data to latest FIRMS date.");
  } catch (err) {
    setStatus("fire-status", err.message, true);
  }
}

function selectConcession(id) {
  activeId = id;
  document.querySelectorAll("#list li").forEach((li) => li.classList.toggle("active", li.dataset.id === id));
  const f = concessions.features.find((f) => f.id === id);
  const bounds = new maplibregl.LngLatBounds();
  const rings = f.geometry.type === "MultiPolygon" ? f.geometry.coordinates.flat() : f.geometry.coordinates;
  rings.forEach((ring) => ring.forEach((c) => bounds.extend(c)));
  map.fitBounds(bounds, { padding: { top: 40, bottom: 40, left: 380, right: 40 } });
  $("ts").classList.remove("hidden");
  $("ts-title").textContent = f.properties.name;
  loadTimeseries(id);
  loadFireChart(id);
  if ($("layer").value === "dnbr") loadBurned(id);
  else $("burned").classList.add("hidden");
}

async function loadTimeseries(id) {
  const index = $("ts-index").value;
  const end = $("end").value;
  const start = iso(new Date(new Date(end).setFullYear(new Date(end).getFullYear() - 3)));
  setStatus("ts-status", `Computing monthly ${index} (3 years)… this can take ~30 s`);
  try {
    const res = await fetch(`/api/timeseries?${new URLSearchParams({ id, start, end, index })}`);
    const body = await res.json();
    if (!res.ok) throw new Error(body.detail || res.statusText);
    if (id !== activeId) return;
    drawChart(body.rows, index, COLORS[id]);
    const gaps = body.rows.filter((r) => r.value == null).length;
    setStatus("ts-status", gaps ? `${gaps} month(s) with no clear pixels (cloud).` : "");
  } catch (err) {
    setStatus("ts-status", err.message, true);
  }
}

function drawChart(rows, index, color) {
  chart?.destroy();
  chart = new Chart($("chart"), {
    type: "line",
    data: {
      labels: rows.map((r) => r.month),
      datasets: [{
        label: `median ${index}`, data: rows.map((r) => r.value),
        borderColor: color, backgroundColor: color, spanGaps: true, tension: 0.25, pointRadius: 2,
      }],
    },
    options: {
      animation: false,
      plugins: { legend: { display: false } },
      scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { suggestedMin: 0, suggestedMax: 0.9 } },
    },
  });
}

function setStatus(id, msg, err = false) {
  $(id).textContent = msg;
  $(id).classList.toggle("err", err);
}
