// Split-screen comparison of two sites on one shared timeline.
//
// The shared time is a sample of the time grid of site A (the left pane). Each pane shows the
// sample of its own package nearest to that instant and labels it with its own UTC string,
// so two packages with different grids are never silently mixed. Every number comes from a
// package unchanged; this file selects, compares and formats. No trigonometry, no science.

import { loadIndex, loadSite, PackageError } from "./package.js";
import { bandNote, createSky } from "./sky.js";
import {
  siteFileUrl,
  canLabelUtc, esc, etOfUtc, eventsHtml, footerHtml, inWindow, loadNotice, loadSiteData, metricText,
  metricsAtHeight, nearestSample, readoutHtml, renderHorizon, sampleEt, sampleUtc,
} from "./panel.js";

const params = new URLSearchParams(location.search);
// Defaults are site files resolved from the script location (see siteFileUrl), so a copy of this
// page at the site root reads the same files as the page in viewer/.
const INDEX_URL = params.get("index") || siteFileUrl("packages/index.json");
const NOTICE_URL = params.get("notice") || siteFileUrl("notice.json");
const $ = (id) => document.getElementById(id);

// Package metrics shown side by side (ids as written by the core; absent ones are skipped).
const SUMMARY = [
  "sun_visible_fraction_of_time", "sun_longest_outage_s", "earth_visible_fraction_of_time",
  "earth_longest_outage_s", "dte_network_share", "dte_longest_outage_s", "dte_relay_need_level", "sun_eclipse_count",
];
// Windows shown as status chips at the shared time.
const CHIPS = [["sun_visible", "Sun visible"], ["earth_visible", "Earth visible"], ["earth_network_dsn", "DSN two-way link"], ["sun_eclipsed_by_earth", "Sun eclipsed by the Earth"]];

const state = { index: null, panes: [], i: 0, timer: null, view: params.get("view") === "sky" ? "sky" : "chart" };

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

function makePane(root) {
  root.appendChild($("pane-template").content.cloneNode(true));
  const q = (role) => root.querySelector(`[data-role="${role}"]`);
  return { root, q, site: null, h: 0, data: null };
}

async function setSite(pane, k, wantedH) {
  pane.site = await loadSite(state.index.base, state.index.sites[k]);
  pane.q("site").value = String(k);
  const hz = pane.site.manifest.horizon;
  pane.q("height").innerHTML = hz.observer_heights_m
    .map((v, j) => `<option value="${j}">${esc(v)} m${j === hz.default_height_index ? " (default)" : ""}</option>`).join("");
  pane.h = Number.isInteger(wantedH) && wantedH >= 0 && wantedH < hz.observer_heights_m.length ? wantedH : hz.default_height_index;
  pane.q("height").value = String(pane.h);
  pane.data = await loadSiteData(pane.site, pane.h);
}

function reference() {
  return state.panes[0].site;
}

function sharedEt() {
  return sampleEt(reference(), state.i);
}

function renderPane(pane) {
  const site = pane.site;
  if (!site || !pane.data) return;
  if (!site.timeline) {
    pane.q("note").textContent = "This package has no time window.";
    pane.q("note").hidden = false;
    return;
  }
  const et = sharedEt();
  const i = nearestSample(site, et);
  const exact = sampleEt(site, i) === et;
  pane.q("time").textContent = `Shown at ${sampleUtc(site, i)}`;
  pane.q("note").hidden = exact;
  if (!exact) pane.q("note").textContent = `This package has another time grid: shown at its nearest sample, ${sampleUtc(site, i)}.`;
  pane.q("chips").innerHTML = CHIPS.map(([id, label]) => {
    const v = inWindow(site, pane.h, id, sampleEt(site, i));
    return v === null ? "" : `<span class="chip ${v ? "on" : "off"}" title="window ${id}">${label}: ${v ? "yes" : "no"}</span>`;
  }).join("");
  const sky = state.view === "sky";
  pane.q("chart").hidden = sky;
  pane.q("sky").hidden = !sky;
  pane.q("band").hidden = !sky;
  if (sky) {
    // The same panorama module as the single-site viewer, one instance per pane.
    if (!pane.sky) pane.sky = createSky(pane.q("sky"), { onPick: (j) => setSample(nearestSample(reference(), sampleEt(site, j))) });
    const v = $("sky-span").value;
    pane.sky.update({ site, data: pane.data, h: pane.h, i, spanSamples: v === "all" ? site.timeline.time.count : Number(v) });
    pane.q("band").innerHTML = bandNote(site, pane.h);
  } else {
    renderHorizon(pane.q("horizon"), site, pane.data, i);
  }
  pane.q("readout").innerHTML = readoutHtml(site, pane.data, pane.h, i);
  const metrics = Object.fromEntries(metricsAtHeight(site, pane.h).map((m) => [m.id, m]));
  const rows = SUMMARY.filter((id) => metrics[id]).map((id) => `<tr><td>${esc(metrics[id].label)}</td><td class="num">${metricText(metrics[id])}</td>
    <td><code>${esc(metrics[id].method)}</code> [${esc(site.methodStatus(metrics[id].method))}]</td></tr>`);
  const t = site.timeline.time;
  pane.q("summary").innerHTML = `<thead><tr><th>Quantity (${esc(t.start_utc)} to ${esc(t.end_utc)})</th><th>Value</th><th>Method</th></tr></thead><tbody>${rows.join("")}</tbody>`;
  pane.q("events").innerHTML = eventsHtml(site, pane.h, i, 0, 4);
  pane.q("footer").innerHTML = footerHtml(site);
}

function render() {
  const ref = reference();
  $("utc").textContent = sampleUtc(ref, state.i);
  if (canLabelUtc(ref)) $("date").value = sampleUtc(ref, state.i).slice(0, 16);
  state.panes.forEach(renderPane);
  const q = new URLSearchParams(location.search);
  q.set("a", state.panes[0].site.manifest.site.site_id); q.set("b", state.panes[1].site.manifest.site.site_id);
  q.set("ha", String(state.panes[0].h)); q.set("hb", String(state.panes[1].h)); q.set("i", String(state.i)); q.set("view", state.view);
  history.replaceState(null, "", `?${q}`);
}

function setSample(i) {
  const count = reference().timeline.time.count;
  state.i = Math.min(count - 1, Math.max(0, i));
  $("slider").value = String(state.i);
  render();
}

function configureTimeline(keepEt) {
  const ref = reference();
  const before = keepEt;
  $("slider").max = String(ref.timeline.time.count - 1);
  $("date").disabled = !canLabelUtc(ref);
  const t = ref.timeline.time;
  $("date").min = t.start_utc.slice(0, 16);
  $("date").max = t.end_utc.slice(0, 16);
  setSample(before === null ? state.i : nearestSample(ref, before));
}

function togglePlay(force) {
  const button = $("play");
  const play = force === undefined ? !state.timer : force;
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
  button.textContent = play ? "Pause" : "Play";
  button.setAttribute("aria-pressed", String(play));
  if (!play) return;
  state.timer = setInterval(() => {
    const step = Number($("speed").value);
    const count = reference().timeline.time.count;
    setSample(state.i + step >= count ? 0 : state.i + step);
  }, 150);
}

function setView(view) {
  state.view = view;
  $("view-chart").setAttribute("aria-pressed", String(view === "chart"));
  $("view-sky").setAttribute("aria-pressed", String(view === "sky"));
  $("span-label").hidden = view !== "sky";
  if (state.panes.every((p) => p.site)) render();
}

function wire() {
  $("view-chart").addEventListener("click", () => setView("chart"));
  $("view-sky").addEventListener("click", () => setView("sky"));
  $("sky-span").addEventListener("change", () => render());
  $("play").addEventListener("click", () => togglePlay());
  $("slider").addEventListener("input", (ev) => setSample(Number(ev.target.value)));
  document.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => setSample(state.i + Number(b.dataset.step))));
  $("date").addEventListener("change", (ev) => {
    if (!ev.target.value) return;
    const ms = Date.parse(`${ev.target.value}:00Z`); // the input is read as UTC
    if (Number.isFinite(ms)) setSample(nearestSample(reference(), etOfUtc(reference(), ms)));
  });
  state.panes.forEach((pane, n) => {
    pane.q("site").addEventListener("change", async (ev) => {
      try {
        const keep = sharedEt();
        await setSite(pane, Number(ev.target.value), null);
        if (n === 0) configureTimeline(keep); else render();
      } catch (e) { showError(String(e.message || e)); }
    });
    pane.q("height").addEventListener("change", async (ev) => {
      try {
        pane.h = Number(ev.target.value);
        pane.data = await loadSiteData(pane.site, pane.h);
        render();
      } catch (e) { showError(String(e.message || e)); }
    });
  });
}

async function main() {
  state.panes = [makePane($("pane-a")), makePane($("pane-b"))];
  wire();
  try {
    const notice = await loadNotice(NOTICE_URL);
    if (notice) { $("notice").textContent = notice; $("notice").hidden = false; }
    state.index = await loadIndex(INDEX_URL);
    const sites = state.index.sites;
    if (sites.length < 1) throw new PackageError("the index lists no site package");
    const options = sites.map((s, k) => `<option value="${k}">${esc(s.name || s.site_id)}</option>`).join("");
    state.panes.forEach((p) => { p.q("site").innerHTML = options; });
    const find = (id, fallback) => { const k = sites.findIndex((s) => s.site_id === id); return k >= 0 ? k : fallback; };
    const a = find(params.get("a"), 0), b = find(params.get("b"), Math.min(1, sites.length - 1));
    await setSite(state.panes[0], a, Number(params.get("ha") ?? NaN));
    await setSite(state.panes[1], b, Number(params.get("hb") ?? NaN));
    if (!reference().timeline) throw new PackageError("site A has no time window");
    const wantedI = Number(params.get("i"));
    state.i = Number.isInteger(wantedI) ? wantedI : 0;
    setView(state.view);
    configureTimeline(null);
    if (state.panes.some((p) => p.site.manifest.synthetic)) {
      const box = $("notice");
      box.textContent = "SYNTHETIC SAMPLE DATA — invented values, not results." + (box.hidden ? "" : ` ${box.textContent}`);
      box.hidden = false;
    }
  } catch (e) {
    showError(`Could not load the packages: ${e.message || e}`);
  }
}

window.lsnCompare = { state };
main();
