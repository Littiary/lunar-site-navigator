// Interactive viewer for one site (2-D and 3-D views).
//
// Rule: every number shown comes from a package unchanged. This file only selects (site,
// observer height, time sample) and wires the controls; lookups and rendering are in
// panel.js. It contains no trigonometry and computes no science.

import { loadIndex, loadSite, PackageError } from "./package.js";
import {
  esc, eventsAtHeight, footerHtml, loadNotice, loadSiteData, nearestSample, readoutHtml, renderHorizon,
  sampleEt, sampleUtc, windowsHtml, eventsHtml,
} from "./panel.js";

const params = new URLSearchParams(location.search);
const INDEX_URL = params.get("index") || "../packages/index.json";
const NOTICE_URL = params.get("notice") || "../notice.json";

const $ = (id) => document.getElementById(id);
const state = { index: null, site: null, h: 0, i: 0, data: null, view3d: null, sky: null, playing: null };

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
  $("footer").innerHTML = footerHtml(site);
  if (state.view3d) { const v = viewInput(); state.view3d.update(v); showMissing(v.missing); }
  if (state.sky && !$("panel-sky").hidden) updateSky();
  const q = new URLSearchParams(location.search);
  q.set("site", site.manifest.site.site_id); q.set("h", String(h)); q.set("i", String(i));
  history.replaceState(null, "", `?${q}`);
}

function viewInput() {
  const pick = (body) => {
    const s = state.data.series[body];
    return s ? { az: s.az[state.i], el: s.el[state.i] } : null;
  };
  return { siteId: state.site.id, h: state.h, horizon: state.data.horizon, distance: state.data.distance, azimuth: state.site.manifest.horizon.azimuth,
    sun: pick("SUN"), earth: pick("EARTH"), missing: missingForGroundView(state.site) };
}

function showMissing(missing) {
  $("missing3d").innerHTML = missing.length
    ? `Not shown, because this package (contract ${esc(state.site.manifest.contract.version)}) does not contain them: ${missing.map(esc).join("; ")}. A terrain surface around the site is not part of the package contract.`
    : "";
}

// Package fields the ground view (Task 8 B) would use but this package does not have.
function missingForGroundView(site) {
  const m = site.manifest, hz = m.horizon, tl = m.timeline || {};
  const series = Object.values(tl.series || {});
  const checks = [
    ["horizon.obstacles and horizon.obstacle_id (outlines and labels of obstacles, contract 0.2)", hz.obstacles && hz.obstacle_id],
    ["timeline.blockers and series.<BODY>.blocker_azimuth_index (which obstacle hides the body, contract 0.2)", tl.blockers && series.some((s) => s.blocker_azimuth_index)],
    ["series.<BODY>.lit_fraction (lit share of the Sun, contract 0.2)", series.some((s) => s.lit_fraction)],
    ["horizon.elevation_lower_deg / elevation_upper_deg (uncertainty band of the profile, reserved)", hz.elevation_lower_deg && hz.elevation_upper_deg],
  ];
  return checks.filter(([, present]) => !present).map(([label]) => label);
}

function setSample(i) {
  const tl = state.site && state.site.timeline;
  if (!tl) return;
  state.i = Math.min(tl.time.count - 1, Math.max(0, i));
  $("slider").value = String(state.i);
  render();
}

function wire() {
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
  const tabs = [["tab-2d", "panel-2d"], ["tab-sky", "panel-sky"], ["tab-3d", "panel-3d"]];
  tabs.forEach(([tab, panel]) => $(tab).addEventListener("click", async () => {
    tabs.forEach(([t, p]) => { $(t).setAttribute("aria-selected", String(t === tab)); $(p).hidden = t !== tab; });
    if (tab === "tab-3d") await open3d();
    if (tab === "tab-sky") await openSky();
  }));
  $("sky-span").addEventListener("change", () => updateSky());
  ["sky-zoom-in", "sky-zoom-out", "sky-center-sun", "sky-center-earth", "sky-reset"].forEach((id) =>
    $(id).addEventListener("click", () => state.sky && state.sky.command(id)));
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
    const { createView } = await import("./view3d.js");
    state.view3d = createView($("view3d"), { onCheck: (text) => { $("check3d").textContent = text; } });
    ["zoom-in", "zoom-out", "look-sun", "look-earth"].forEach((id) => $(id).addEventListener("click", () => state.view3d.command(id)));
    const v = viewInput();
    state.view3d.update(v);
    showMissing(v.missing);
  } catch (e) {
    $("view3d").innerHTML = `<p class="banner">The 3-D view could not start: ${esc(e.message || e)}. The views "Horizon and time" and "Sky panorama" show the same package data without WebGL.</p>`;
  }
}

async function main() {
  wire();
  try {
    const notice = await loadNotice(NOTICE_URL);
    if (notice) { $("notice").textContent = notice; $("notice").hidden = false; }
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
