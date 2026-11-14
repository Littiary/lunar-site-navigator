// Interactive viewer for result packages.
//
// Rule: every number shown comes from a package unchanged. This file only selects (site,
// observer height, time sample), looks values up, compares times, formats text and maps
// values to screen positions. It contains no trigonometry and computes no science.

import { loadIndex, loadSite, PackageError } from "./package.js";

const BODIES = ["SUN", "EARTH"];
const NAMES = { SUN: "Sun", EARTH: "Earth" };
const params = new URLSearchParams(location.search);
const INDEX_URL = params.get("index") || "../packages/index.json";
const NOTICE_URL = params.get("notice") || "../notice.json";

const $ = (id) => document.getElementById(id);
const state = { index: null, site: null, h: 0, i: 0, data: null, view3d: null, playing: null };

function showError(message) {
  const box = $("error");
  box.textContent = message;
  box.hidden = false;
}

function esc(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

function fixed(value, digits) {
  return value === null || value === undefined || Number.isNaN(value) ? "—" : Number(value).toFixed(digits);
}

// ------------------------------------------------------------------ time grid (SPEC 3.5)

function sampleEt(i) {
  const t = state.site.timeline.time;
  return t.start_et_s + i * t.step_s; // the definition of sample i of the time grid
}

function sampleUtc(i) {
  const t = state.site.timeline.time;
  // SPEC 3.5: a reader may label sample i as start_utc + i * step_s only without leap seconds.
  if (t.leap_seconds_in_range !== 0) return `sample ${i} of ${t.count} (UTC label not available: leap second in range)`;
  return new Date(Date.parse(t.start_utc) + i * t.step_s * 1000).toISOString();
}

function nearestSample(et) {
  const t = state.site.timeline.time;
  return Math.min(t.count - 1, Math.max(0, Math.round((et - t.start_et_s) / t.step_s)));
}

function containing(intervals, et) {
  // intervals are sorted and disjoint (SPEC 5.4): binary search by comparison only
  let lo = 0, hi = intervals.length - 1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (et < intervals[mid][0]) hi = mid - 1;
    else if (et > intervals[mid][1]) lo = mid + 1;
    else return mid;
  }
  return -1;
}

// ------------------------------------------------------------------ loading

async function loadData(site, h) {
  const m = site.manifest;
  const tl = site.timeline;
  const data = { horizon: (await site.array(m.horizon.elevation_deg)).row(h), series: {} };
  if (tl) {
    for (const body of BODIES) {
      const s = tl.series[body];
      if (!s) continue;
      data.series[body] = {
        az: (await site.array(s.azimuth_deg)).values,
        el: (await site.array(s.elevation_deg)).values,
        margin: (await site.array(s.margin_deg)).row(h),
        fraction: (await site.array(s.visible_fraction)).row(h),
      };
    }
  }
  return data;
}

async function selectSite(entry, keepTime) {
  state.site = await loadSite(state.index.base, entry);
  const hz = state.site.manifest.horizon;
  const heightSelect = $("height");
  heightSelect.innerHTML = hz.observer_heights_m
    .map((v, k) => `<option value="${k}">${esc(v)} m${k === hz.default_height_index ? " (default)" : ""}</option>`)
    .join("");
  const wantedH = Number(params.get("h"));
  state.h = keepTime && Number.isInteger(wantedH) && wantedH >= 0 && wantedH < hz.observer_heights_m.length ? wantedH : hz.default_height_index;
  heightSelect.value = String(state.h);
  const tl = state.site.timeline;
  const slider = $("slider");
  slider.max = tl ? String(tl.time.count - 1) : "0";
  const wantedI = Number(params.get("i"));
  state.i = keepTime && Number.isInteger(wantedI) && tl && wantedI >= 0 && wantedI < tl.time.count ? wantedI : 0;
  slider.value = String(state.i);
  await selectHeight(state.h);
}

async function selectHeight(h) {
  state.h = h;
  state.data = await loadData(state.site, h);
  render();
}

// ------------------------------------------------------------------ rendering

const W = 1000, H = 360, X0 = 52, X1 = 985, Y0 = 18, Y1 = 318;

function yRange() {
  // Axis limits for display: the extremes of what is drawn, padded to whole degrees.
  let lo = Infinity, hi = -Infinity;
  const take = (arr) => { for (const v of arr) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } };
  take(state.data.horizon);
  for (const body of BODIES) if (state.data.series[body]) take(state.data.series[body].el);
  return [Math.floor(lo) - 1, Math.ceil(hi) + 1];
}

function renderHorizon() {
  const svg = $("horizon");
  const az = state.site.manifest.horizon.azimuth;
  const row = state.data.horizon;
  const [ymin, ymax] = state.yRange || (state.yRange = yRange());
  const px = (a) => X0 + (a / 360) * (X1 - X0);
  const py = (e) => Y1 - ((e - ymin) / (ymax - ymin)) * (Y1 - Y0);
  const parts = [];
  for (let a = 0; a <= 360; a += 45) {
    parts.push(`<line class="grid" x1="${px(a)}" x2="${px(a)}" y1="${Y0}" y2="${Y1}"/>`);
    const label = { 0: "N", 90: "E", 180: "S", 270: "W", 360: "N" }[a];
    parts.push(`<text x="${px(a)}" y="${Y1 + 16}" text-anchor="middle">${label ? label + " " : ""}${a}°</text>`);
  }
  const step = ymax - ymin > 12 ? 5 : ymax - ymin > 6 ? 2 : 1;
  for (let e = Math.ceil(ymin / step) * step; e <= ymax; e += step) {
    parts.push(`<line class="grid" x1="${X0}" x2="${X1}" y1="${py(e)}" y2="${py(e)}"/>`);
    parts.push(`<text x="${X0 - 6}" y="${py(e) + 4}" text-anchor="end">${e}°</text>`);
  }
  // Profile: sample k is at azimuth start_deg + k * step_deg (SPEC 5.3); the profile is periodic.
  const pts = [];
  for (let k = 0; k <= az.count; k++) pts.push(`${px(az.start_deg + k * az.step_deg).toFixed(2)},${py(row[k % az.count]).toFixed(2)}`);
  parts.push(`<polygon class="terrain" points="${X0},${Y1} ${pts.join(" ")} ${X1},${Y1}"/>`);
  parts.push(`<polyline class="horizon" points="${pts.join(" ")}"/>`);
  for (const body of BODIES) {
    const s = state.data.series[body];
    if (!s) continue;
    const a = s.az[state.i], e = s.el[state.i];
    if (!Number.isFinite(a) || !Number.isFinite(e)) continue;
    const x = px(a), y = Math.min(Y1, Math.max(Y0, py(e)));
    parts.push(`<circle class="${body.toLowerCase()}" cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="7"/>`);
    parts.push(`<text class="label" x="${(x + 10).toFixed(2)}" y="${(y - 8).toFixed(2)}">${NAMES[body]}</text>`);
  }
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = parts.join("");
}

function windowsAtHeight() {
  return (state.site.timeline ? state.site.timeline.windows : []).filter((w) => w.height_index === state.h);
}

function renderReadout() {
  const tl = state.site.timeline;
  const rows = [];
  const et = sampleEt(state.i);
  const visible = Object.fromEntries(windowsAtHeight().map((w) => [w.id, w]));
  for (const body of BODIES) {
    const s = state.data.series[body];
    if (!s) continue;
    const w = visible[`${body.toLowerCase()}_visible`];
    const inside = w ? containing(w.intervals_et_s, et) >= 0 : null;
    rows.push(`<tr><td>${NAMES[body]}</td>
      <td class="num">${fixed(s.az[state.i], 3)}°</td>
      <td class="num">${fixed(s.el[state.i], 3)}°</td>
      <td class="num">${fixed(s.margin[state.i], 3)}°</td>
      <td class="num">${fixed(100 * s.fraction[state.i], 1)} %</td>
      <td>${inside === null ? "—" : inside ? '<span class="yes">yes</span>' : '<span class="no">no</span>'}</td></tr>`);
  }
  const height = state.site.manifest.horizon.observer_heights_m[state.h];
  $("readout").innerHTML = `<thead><tr><th>Body</th><th>Azimuth of centre</th><th>Elevation of centre (no terrain)</th>
    <th>Margin above terrain horizon at ${esc(height)} m</th><th>Disc above terrain horizon</th><th>In window <code>&lt;body&gt;_visible</code></th></tr></thead>
    <tbody>${rows.join("")}</tbody>`;
  if (!tl) $("readout").innerHTML += '<tbody><tr><td colspan="6">This package has no time window.</td></tr></tbody>';
}

function renderWindows() {
  const et = sampleEt(state.i);
  const rows = windowsAtHeight().map((w) => {
    const k = containing(w.intervals_et_s, et);
    const span = k >= 0 ? `${esc(w.intervals_utc[k][0])} to ${esc(w.intervals_utc[k][1])}` : "";
    return `<tr><td><code>${esc(w.id)}</code></td><td>${esc(w.definition || "")}</td>
      <td>${k >= 0 ? '<span class="yes">yes</span>' : '<span class="no">no</span>'}</td><td class="mono">${span}</td></tr>`;
  });
  $("windows").innerHTML = `<thead><tr><th>Window</th><th>Condition</th><th>Contains this time</th><th>Interval (UTC)</th></tr></thead><tbody>${rows.join("")}</tbody>`;
}

function eventsAtHeight() {
  return (state.site.timeline ? state.site.timeline.events : []).filter((e) => e.height_index === state.h);
}

function renderEvents() {
  const et = sampleEt(state.i);
  const events = eventsAtHeight();
  let next = events.findIndex((e) => e.et_s > et);
  if (next < 0) next = events.length;
  const shown = events.slice(Math.max(0, next - 3), next + 3);
  const rows = shown.map((e) => `<tr><td class="mono">${esc(e.utc)}</td><td>${e.et_s > et ? "next" : "past"}</td>
    <td>${NAMES[e.body] || esc(e.body)}</td><td>${esc(e.type)}</td><td class="num">${fixed(e.azimuth_deg, 2)}°</td>
    <td class="num">${fixed(e.horizon_elevation_deg, 3)}°</td>
    <td class="num">${e.obstacle_distance_m === null ? "—" : fixed(e.obstacle_distance_m / 1000, 2) + " km"}</td></tr>`);
  $("events").innerHTML = `<thead><tr><th>Time (UTC)</th><th></th><th>Body</th><th>Event</th><th>Body azimuth</th>
    <th>Terrain horizon elevation</th><th>Obstacle distance</th></tr></thead><tbody>${rows.join("") ||
    '<tr><td colspan="7">No rise or set event at this height.</td></tr>'}</tbody>`;
}

function renderFooter() {
  const m = state.site.manifest;
  const s = m.site;
  const t = m.timeline ? m.timeline.time : null;
  const radius = s.reference_radius_m && s.reference_radius_m.value;
  const statuses = ["horizon.elevation", "timeline.direction", "timeline.margin", "timeline.visible_fraction", "timeline.windows", "timeline.events"]
    .filter((id) => (m.methods || {})[id]).map((id) => `<code>${id}</code> [${esc(state.site.methodStatus(id))}]`).join(", ");
  const unverified = state.site.unverified.size
    ? `<br><strong>Checksums not verified</strong> for ${state.site.unverified.size} file(s): this browser offers no Web Crypto here (it needs https or localhost).`
    : "<br>Every array that was read matched the size and SHA-256 in its manifest.";
  $("footer").innerHTML = `Package <span class="mono">${esc(m.package_id)}</span> (contract ${esc(m.contract.version)}, status ${esc(m.status)}),
    content SHA-256 <span class="mono">${esc(m.content_sha256)}</span>.<br>
    Frame <span class="mono">${esc(s.frame)}</span>, reference sphere radius ${radius / 1000} km, site ${esc(s.lat_deg)}°, ${esc(s.lon_deg)}° (planetocentric, east-positive).<br>
    ${t ? `Time window ${esc(t.start_utc)} to ${esc(t.end_utc)} UTC, ${esc(t.scale)} grid, step ${esc(t.step_s)} s, ${esc(t.count)} samples.<br>` : ""}
    Validation status: ${statuses}.${unverified}`;
}

function render() {
  if (!state.site || !state.data) return;
  $("utc").textContent = state.site.timeline ? sampleUtc(state.i) : "no time window";
  renderHorizon();
  renderReadout();
  renderWindows();
  renderEvents();
  renderFooter();
  if (state.view3d) state.view3d.update(viewInput());
  const q = new URLSearchParams(location.search);
  q.set("site", state.site.manifest.site.site_id); q.set("h", String(state.h)); q.set("i", String(state.i));
  history.replaceState(null, "", `?${q}`);
}

function viewInput() {
  const pick = (body) => {
    const s = state.data.series[body];
    return s ? { az: s.az[state.i], el: s.el[state.i] } : null;
  };
  return { siteId: state.site.id, h: state.h, horizon: state.data.horizon, azimuth: state.site.manifest.horizon.azimuth, sun: pick("SUN"), earth: pick("EARTH") };
}

// ------------------------------------------------------------------ controls

function setSample(i) {
  const tl = state.site && state.site.timeline;
  if (!tl) return;
  state.i = Math.min(tl.time.count - 1, Math.max(0, i));
  $("slider").value = String(state.i);
  render();
}

function wire() {
  $("site").addEventListener("change", async (ev) => {
    state.yRange = null;
    await selectSite(state.index.sites[Number(ev.target.value)], false).catch((e) => showError(String(e.message || e)));
  });
  $("height").addEventListener("change", async (ev) => {
    state.yRange = null;
    await selectHeight(Number(ev.target.value)).catch((e) => showError(String(e.message || e)));
  });
  $("slider").addEventListener("input", (ev) => setSample(Number(ev.target.value)));
  document.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
    const per = Math.max(1, Math.round(86400 / state.site.timeline.time.step_s));
    const v = b.dataset.step;
    setSample(state.i + (v === "day" ? per : v === "-day" ? -per : Number(v)));
  }));
  $("next-event").addEventListener("click", () => {
    const e = eventsAtHeight().find((x) => x.et_s > sampleEt(state.i) + state.site.timeline.time.step_s / 2);
    if (e) setSample(nearestSample(e.et_s));
  });
  $("prev-event").addEventListener("click", () => {
    const list = eventsAtHeight().filter((x) => x.et_s < sampleEt(state.i) - state.site.timeline.time.step_s / 2);
    if (list.length) setSample(nearestSample(list[list.length - 1].et_s));
  });
  $("play").addEventListener("click", () => {
    const button = $("play");
    if (state.playing) { clearInterval(state.playing); state.playing = null; button.textContent = "Play"; button.setAttribute("aria-pressed", "false"); return; }
    button.textContent = "Pause"; button.setAttribute("aria-pressed", "true");
    state.playing = setInterval(() => setSample(state.i + 1 >= state.site.timeline.time.count ? 0 : state.i + 1), 120);
  });
  const tabs = [["tab-2d", "panel-2d"], ["tab-3d", "panel-3d"]];
  tabs.forEach(([tab, panel]) => $(tab).addEventListener("click", async () => {
    tabs.forEach(([t, p]) => { $(t).setAttribute("aria-selected", String(t === tab)); $(p).hidden = t !== tab; });
    if (tab === "tab-3d") await open3d();
  }));
}

async function open3d() {
  if (state.view3d) { state.view3d.resize(); return; }
  try {
    const { createView } = await import("./view3d.js");
    state.view3d = createView($("view3d"), {
      onCheck: (text) => { $("check3d").textContent = text; },
    });
    ["zoom-in", "zoom-out", "look-sun", "look-earth"].forEach((id) => $(id).addEventListener("click", () => state.view3d.command(id)));
    state.view3d.update(viewInput());
  } catch (e) {
    $("view3d").innerHTML = `<p class="banner">The 3-D view could not start: ${esc(e.message || e)}. It loads three.js from cdn.jsdelivr.net.</p>`;
  }
}

async function main() {
  wire();
  try {
    const notice = await fetch(NOTICE_URL).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    if (notice && notice.notice) { $("notice").textContent = notice.notice; $("notice").hidden = false; }
    state.index = await loadIndex(INDEX_URL);
    if (!state.index.sites.length) throw new PackageError("the index lists no site package");
    $("site").innerHTML = state.index.sites.map((s, k) => `<option value="${k}">${esc(s.name || s.site_id)}</option>`).join("");
    const wanted = state.index.sites.findIndex((s) => s.site_id === params.get("site"));
    $("site").value = String(Math.max(0, wanted));
    await selectSite(state.index.sites[Math.max(0, wanted)], wanted >= 0);
    if (state.site.manifest.synthetic) {
      const box = $("notice");
      box.textContent = `SYNTHETIC SAMPLE DATA — ${state.site.manifest.synthetic_notice || "invented values, not a result"}` + (box.hidden ? "" : ` ${box.textContent}`);
      box.hidden = false;
    }
  } catch (e) {
    showError(`Could not load the packages: ${e.message || e}`);
  }
}

window.lsnViewer = { state };
main();
