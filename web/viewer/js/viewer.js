// Interactive viewer for one site (2-D and 3-D views).
//
// Rule: every number shown comes from a package unchanged. This file only selects (site,
// observer height, time sample) and wires the controls; lookups and rendering are in
// panel.js. It contains no trigonometry and computes no science.

import { loadIndex, loadSite, loadSummaryCatalogue, PackageError } from "./package.js";
import { calendarHtml, requirementIds, setCalendarTime } from "./calendar.js";
import { directionTableFor, groundData, groundInput } from "./ground.js";
import {
  siteFileUrl, siteOptionsHtml,
  BODIES, NAMES, esc, eventsAtHeight, fixed, footerHtml, inWindow, loadNoticeFile, validationNoteHtml, loadSiteData, nearestSample, readoutHtml, renderHorizon,
  sampleEt, sampleUtc, windowsHtml, eventsHtml, contract06Html, terrainSourceHtml,
} from "./panel.js";
import { downloadCsv, seriesCsv } from "./csv.js";

const params = new URLSearchParams(location.search);
// Defaults are site files resolved from the script location (see siteFileUrl), so a copy of this
// page at the site root reads the same files as the page in viewer/.
const INDEX_URL = params.get("index") || siteFileUrl("packages/index.json");
const NOTICE_URL = params.get("notice") || siteFileUrl("notice.json");

const $ = (id) => document.getElementById(id);
const state = { index: null, site: null, h: 0, i: 0, data: null, view3d: null, sky: null, globe: null, playing: null };

function showError(message) {
  const box = $("error");
  box.textContent = message;
  box.hidden = false;
}

async function selectSite(entry, keepTime) {
  state.site = await loadSite(state.index.base, entry);
  const hz = state.site.manifest.horizon;
  const heightSelect = $("height");
  heightSelect.innerHTML = hz.observer_heights_m
    .map((v, k) => `<option value="${k}">${esc(v)} m${k === hz.default_height_index ? " (default)" : ""}</option>`)
    .join("");
  // A link without h keeps the package's default height (Number(null) would be 0, the 0 m row).
  const hParam = params.get("h");
  const wantedH = hParam === null || hParam === "" ? NaN : Number(hParam);
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
  state.data = await loadSiteData(state.site, h);
  render();
}

function render() {
  if (!state.site || !state.data) return;
  const { site, data, h, i } = state;
  $("utc").textContent = site.timeline ? sampleUtc(site, i) : "no time window";
  renderHorizon($("horizon"), site, data, i);
  $("readout").innerHTML = readoutHtml(site, data, h, i);
  if (site.timeline) {
    $("windows").innerHTML = windowsHtml(site, h, i);
    $("events").innerHTML = eventsHtml(site, h, i);
  }
  $("package06").innerHTML = contract06Html(site, h);
  $("footer").innerHTML = footerHtml(site);
  $("terrain-source").innerHTML = terrainSourceHtml(site);
  $("terrain-source-3d").innerHTML = terrainSourceHtml(site);
  $("export-csv").disabled = !site.timeline;
  if (state.view3d) updateGround().catch((e) => showError(String(e.message || e)));
  if (state.sky && !$("panel-sky").hidden) updateSky();
  if (state.globe && !$("panel-globe").hidden) updateGlobe();
  if (!$("panel-calendar").hidden) updateCalendar();
  const q = new URLSearchParams(location.search);
  q.set("site", site.manifest.site.site_id); q.set("h", String(h)); q.set("i", String(i));
  history.replaceState(null, "", `?${q}`);
  // The comparison opens with this site, height and time in its left pane (its reference).
  const c = new URL(siteFileUrl("compare.html"));
  c.search = new URLSearchParams({ a: site.manifest.site.site_id, ha: String(h), i: String(i) }).toString();
  $("compare-link").href = c.href;
}

// Data of the ground view that the other views do not need: the terrain patches, the angular
// radii of the Sun and the Earth, and the Earth's orientation from the direction table.
// Ground-view data of the selected site, read once per site (js/ground.js).
async function siteGroundData() {
  if (state.ground && state.ground.siteId === state.site.id) return state.ground;
  if (!state.tables) state.tables = {};
  state.ground = await groundData(state.site, state.index, state.tables);
  return state.ground;
}

async function updateGround() {
  if (!state.view3d || !state.site) return;
  const g = await siteGroundData();
  const v = groundInput({ site: state.site, h: state.h, i: state.i, data: state.data, g, view3dModule: state.view3dModule, missing: missingForGroundView(state.site) });
  state.view3d.update(v);
  showMissing(v.missing);
  const t = state.view3d.terrainCheck();
  if (t) {
    const worst = Math.max(...Object.values(t.patches).map((p) => p.maxDiff_m));
    $("check3d-terrain").textContent = `Terrain check: ${Object.keys(t.patches).length} patches; drawn vertices differ from the package nodes by at most ${worst} m.`;
  }
}

function showMissing(fields) {
  const v = esc(state.site.manifest.contract.version);
  const parts = [];
  if (fields.notDrawn.length) parts.push(`In this package (contract ${v}) but not drawn in this view: ${fields.notDrawn.map(esc).join("; ")}.`);
  if (fields.absent.length) parts.push(`Not in this package, so not shown: ${fields.absent.map(esc).join("; ")}.`);
  const terrain = state.site.manifest.terrain;
  // Finest first by spacing (SPEC 5.9: the list order is not part of the contract), with the
  // colour of each patch's outline in the view; the largest patch has none.
  const sorted = terrain && terrain.patches.length ? terrain.patches.slice().sort((a, b) => a.spacing_m - b.spacing_m) : [];
  const colours = (state.view3dModule && state.view3dModule.EDGE_COLORS) || [];
  parts.push(sorted.length
    ? `The ground is drawn from the package terrain patches, finest first: ${sorted.map((p, k) => `${esc(p.id)} ${esc(p.spacing_m)} m grid, ±${esc(p.half_width_m / 1000)} km${k < sorted.length - 1 && colours.length ? ` (outline ${colours[k % colours.length][1]})` : ""}`).join("; ")}. ${esc(terrain.notice || "They are for drawing only.")}`
    : "This package has no terrain patches: only the horizon profile is drawn.");
  $("missing3d").innerHTML = parts.join(" ");
}

// Package fields the ground view (Task 8 B) does not draw: those the package has (notDrawn) and
// those it lacks (absent). The view draws only the horizon profile, its distances and the Sun and Earth.
function missingForGroundView(site) {
  const m = site.manifest, hz = m.horizon, tl = m.timeline || {};
  const series = Object.values(tl.series || {});
  const checks = [
    ["horizon.obstacles and horizon.obstacle_id (outlines and labels of obstacles, contract 0.2)", hz.obstacles && hz.obstacle_id],
    ["timeline.blockers and series.<BODY>.blocker_azimuth_index (which obstacle hides the body, contract 0.2)", tl.blockers && series.some((s) => s.blocker_azimuth_index)],
    ["series.<BODY>.lit_fraction (lit share of the Sun, contract 0.2)", series.some((s) => s.lit_fraction)],
    ["horizon.elevation_lower_deg / elevation_upper_deg (uncertainty band of the profile, reserved)", hz.elevation_lower_deg && hz.elevation_upper_deg],
  ];
  return {
    notDrawn: checks.filter(([, present]) => present).map(([label]) => label),
    absent: checks.filter(([, present]) => !present).map(([label]) => label),
  };
}

function setSample(i) {
  const tl = state.site && state.site.timeline;
  if (!tl) return;
  state.i = Math.min(tl.time.count - 1, Math.max(0, i));
  $("slider").value = String(state.i);
  render();
}

function wire() {
  $("export-csv").addEventListener("click", () => {
    try {
      if (!state.site || !state.data || !state.site.timeline) throw new PackageError("the selected site has no time-series package data");
      downloadCsv(`${state.site.manifest.site.site_id}-sun-earth.csv`, seriesCsv([{ site: state.site, data: state.data, height: state.h }]));
    } catch (e) { showError(String(e.message || e)); }
  });
  $("site").addEventListener("change", async (ev) => {
    await selectSite(state.index.sites[Number(ev.target.value)], false).catch((e) => showError(String(e.message || e)));
  });
  $("height").addEventListener("change", async (ev) => {
    await selectHeight(Number(ev.target.value)).catch((e) => showError(String(e.message || e)));
  });
  $("slider").addEventListener("input", (ev) => setSample(Number(ev.target.value)));
  document.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => {
    const per = Math.max(1, Math.round(86400 / state.site.timeline.time.step_s));
    const v = b.dataset.step;
    setSample(state.i + (v === "day" ? per : v === "-day" ? -per : Number(v)));
  }));
  const half = () => state.site.timeline.time.step_s / 2;
  $("next-event").addEventListener("click", () => {
    const e = eventsAtHeight(state.site, state.h).find((x) => x.et_s > sampleEt(state.site, state.i) + half());
    if (e) setSample(nearestSample(state.site, e.et_s));
  });
  $("prev-event").addEventListener("click", () => {
    const list = eventsAtHeight(state.site, state.h).filter((x) => x.et_s < sampleEt(state.site, state.i) - half());
    if (list.length) setSample(nearestSample(state.site, list[list.length - 1].et_s));
  });
  $("play").addEventListener("click", () => {
    const button = $("play");
    if (state.playing) { clearInterval(state.playing); state.playing = null; button.textContent = "Play"; button.setAttribute("aria-pressed", "false"); return; }
    button.textContent = "Pause"; button.setAttribute("aria-pressed", "true");
    state.playing = setInterval(() => setSample(state.i + 1 >= state.site.timeline.time.count ? 0 : state.i + 1), 120);
  });
  const tabs = [["tab-2d", "panel-2d"], ["tab-sky", "panel-sky"], ["tab-3d", "panel-3d"], ["tab-globe", "panel-globe"], ["tab-calendar", "panel-calendar"]];
  state.showTab = async (tab) => {
    tabs.forEach(([t, p]) => { $(t).setAttribute("aria-selected", String(t === tab)); $(p).hidden = t !== tab; });
    if (tab === "tab-3d") await open3d();
    if (tab === "tab-sky") await openSky();
    if (tab === "tab-globe") await openGlobe();
    if (tab === "tab-calendar") updateCalendar();
  };
  $("cal-req").addEventListener("change", () => { state.calendarKey = null; updateCalendar(); });
  // A click on a lunar day or a landing window goes to its start.
  $("calendar").addEventListener("click", (ev) => {
    const cell = ev.target.closest("[data-et]");
    if (cell && state.site && state.site.timeline) setSample(nearestSample(state.site, Number(cell.dataset.et)));
  });
  tabs.forEach(([tab]) => $(tab).addEventListener("click", () => state.showTab(tab)));
  ["globe-zoom-in", "globe-zoom-out", "globe-site", "globe-from-earth", "globe-from-sun", "globe-fit"].forEach((id) =>
    $(id).addEventListener("click", () => state.globe && state.globe.command(id)));
  $("sky-span").addEventListener("change", () => updateSky());
  ["sky-zoom-in", "sky-zoom-out", "sky-center-sun", "sky-center-earth", "sky-reset"].forEach((id) =>
    $(id).addEventListener("click", () => state.sky && state.sky.command(id)));
}

// ------------------------------------------------------------------ Opportunity calendar (Task 9)

// Drawn again only when the site, the height or the requirement changes; the time marker moves
// on every time step. Reads the manifest of the selected site only (no arrays).
function updateCalendar() {
  const site = state.site;
  if (!site) return;
  const entries = [{ site, h: state.h, name: site.manifest.site.name || site.manifest.site.site_id }];
  const ids = requirementIds(entries);
  const sel = $("cal-req");
  const wanted = ids.includes(sel.value) ? sel.value : ids[0] || "";
  if (sel.dataset.ids !== ids.join("|")) {
    sel.innerHTML = ids.length ? ids.map((id) => `<option value="${esc(id)}">${esc(id)}</option>`).join("") : "<option value=\"\">none in this package</option>";
    sel.dataset.ids = ids.join("|");
  }
  sel.value = wanted;
  const key = `${site.id}:${state.h}:${wanted}`;
  if (state.calendarKey !== key) {
    $("calendar").innerHTML = calendarHtml(entries, { requirementId: wanted || null });
    state.calendarKey = key;
  }
  if (site.timeline) setCalendarTime($("calendar"), sampleEt(site, state.i));
}

// ------------------------------------------------------------------ Moon globe (Task 8 A)

async function openGlobe() {
  try {
    if (!state.globe) {
      const { createGlobe } = await import("./globe.js");
      // Every site package of the index (manifests only) and the direction table of this site.
      // Markers from the index (SPEC 7: site_id, name, lat_deg, lon_deg), so that the globe does not
      // load every site package: with many sites that would be many megabytes.
      state.globeSites = state.index.sites.map((e) => ({ site_id: e.site_id, name: e.name || e.site_id, lat_deg: e.lat_deg, lon_deg: e.lon_deg }));
      state.globe = createGlobe($("globe"), { onPickSite: (id) => openGroundView(id) });
    }
    await updateGlobe();
    state.globe.resize();
  } catch (e) {
    $("globe").innerHTML = `<p class="banner">The Moon globe could not start: ${esc(e.message || e)}. The other views show the package data without WebGL.</p>`;
  }
}

async function directionTable() {
  if (!state.tables) state.tables = {};
  return directionTableFor(state.index, state.site, state.tables);
}

async function updateGlobe() {
  if (!state.globe || !state.site) return;
  const t = await directionTable();
  const site = state.site;
  const sites = state.globeSites; // from the index, built once in openGlobe
  let sun = null, earth = null;
  if (t && site.timeline) {
    // The record of the direction table at the selected instant (SPEC 3.5 and 6): lookup, no interpolation.
    const grid = t.table.manifest.time, et = sampleEt(site, state.i);
    const k = Math.min(grid.count - 1, Math.max(0, Math.round((et - grid.start_et_s) / grid.step_s)));
    const B = t.table.manifest.bodies.length;
    const vec = (name) => {
      const b = t.table.manifest.bodies.indexOf(name);
      return b < 0 ? null : Array.from(t.positions.values.subarray((k * B + b) * 3, (k * B + b) * 3 + 3));
    };
    sun = vec("SUN"); earth = vec("EARTH");
    const exact = grid.start_et_s + k * grid.step_s === et;
    const label = grid.leap_seconds_in_range === 0 ? new Date(Date.parse(grid.start_utc) + k * grid.step_s * 1000).toISOString() : `record ${k}`;
    $("globe-time").innerHTML = `Directions from direction table <span class="mono">${esc(t.table.id)}</span> (frame <span class="mono">${esc(t.table.manifest.frame)}</span>, correction ${esc(t.table.manifest.aberration_correction)}, observer at the centre of the Moon), record ${k} at ${esc(label)}${exact ? "" : " (nearest record to the selected time)"}; positions [${esc(t.table.methodStatus("dirtab.positions"))}].`;
    state.globeInput = { k, sun, earth };
  }
  const radiusKm = site.manifest.site.reference_radius_m.value / 1000;
  state.globe.update({ sites, scale: 1 / radiusKm, sun, earth, selectedId: site.manifest.site.site_id });
  const c = state.globe.check({ site_id: site.manifest.site.site_id, position_km: site.manifest.site.position_km });
  if (c) {
    const worst = Math.max(c.sunLightDiff, c.subSolarDiff, c.subEarthDiff, c.siteDirectionDiff);
    $("check-globe").textContent = `Check: the selected site's marker, the light and the sub-points differ from the package vectors by at most ${worst.toExponential(1)} (unit-vector components).`;
  }
}

async function openGroundView(siteId) {
  const k = state.index.sites.findIndex((s) => s.site_id === siteId);
  if (k < 0) return;
  const et = state.site.timeline ? sampleEt(state.site, state.i) : null;
  $("site").value = String(k);
  await selectSite(state.index.sites[k], false);
  if (et !== null && state.site.timeline) setSample(nearestSample(state.site, et));
  await state.showTab("tab-3d");
}

async function openSky() {
  if (!state.sky) {
    const sky = await import("./sky.js");
    state.skyModule = sky;
    state.sky = sky.createSky($("sky"), { onPick: (j) => setSample(j) });
  }
  updateSky();
  state.sky.resize();
}

function updateSky() {
  if (!state.sky || !state.site) return;
  const v = $("sky-span").value;
  const span = v === "all" && state.site.timeline ? state.site.timeline.time.count : Number(v);
  state.sky.update({ site: state.site, data: state.data, h: state.h, i: state.i, spanSamples: span });
  $("band-sky").innerHTML = state.skyModule.bandNote(state.site, state.h);
  const c = state.sky.check();
  if (c) $("check-sky").textContent = `Horizon check: ${c.vertices} vertices read back from the drawing differ from the package profile by at most ${c.maxElevationDiffDeg.toExponential(1)}° in elevation and ${c.maxAzimuthDiffDeg.toExponential(1)}° in azimuth.`;
}

async function open3d() {
  if (state.view3d) { state.view3d.resize(); return; }
  try {
    state.view3dModule = await import("./view3d.js");
    state.view3d = state.view3dModule.createView($("view3d"), { onCheck: (text) => { $("check3d").textContent = text; } });
    ["zoom-in", "zoom-out", "look-sun", "look-earth"].forEach((id) => $(id).addEventListener("click", () => state.view3d.command(id)));
    ["toggle-profile", "toggle-lighting", "toggle-slope", "toggle-edges"].forEach((id) => $(id).addEventListener("click", (ev) => { const on = state.view3d.command(id); ev.currentTarget.setAttribute("aria-pressed", String(Boolean(on))); }));
    $("reset-view").addEventListener("click", () => state.view3d.command("reset-view"));
    await updateGround();
  } catch (e) {
    $("view3d").innerHTML = `<p class="banner">The 3-D view could not start: ${esc(e.message || e)}. The views "Horizon and time" and "Sky panorama" show the same package data without WebGL.</p>`;
  }
}

async function main() {
  wire();
  try {
    const [noticeFile, index, summaries] = await Promise.all([loadNoticeFile(NOTICE_URL), loadIndex(INDEX_URL), loadSummaryCatalogue(siteFileUrl("summary/index.json"))]);
    $("validation-note").innerHTML = validationNoteHtml(noticeFile, siteFileUrl("evidence.html"));
    state.index = index;
    if (!state.index.sites.length) throw new PackageError("the index lists no site package");
    $("site").innerHTML = siteOptionsHtml(state.index.sites, summaries);
    const wanted = state.index.sites.findIndex((s) => s.site_id === params.get("site"));
    $("site").value = String(Math.max(0, wanted));
    await selectSite(state.index.sites[Math.max(0, wanted)], wanted >= 0);
    if (state.site.manifest.synthetic) {
      const box = $("notice");
      box.textContent = `SYNTHETIC SAMPLE DATA — ${state.site.manifest.synthetic_notice || "invented values, not a result"}`;
      box.hidden = false;
    }
    // ?tab=3d (or 2d, sky, globe, calendar) opens that view, for links from the comparison.
    const tab = params.get("tab");
    if (tab && $(`tab-${tab}`)) await state.showTab(`tab-${tab}`);
  } catch (e) {
    showError(`Could not load the packages: ${e.message || e}`);
  }
}

window.lsnViewer = { state };
main();
