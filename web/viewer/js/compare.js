// Split-screen comparison of two sites on one shared timeline (the home page of the site).
//
// The shared time is a sample of the time grid of site A (the left pane). Each pane shows the
// sample of its own package nearest to that instant and labels it with its own UTC string,
// so two packages with different grids are never silently mixed. Every number comes from a
// package unchanged; this file selects, compares and formats. No trigonometry, no science.
//
// Loading, in this order, so that the first screen is useful within about a second even on a
// phone: the index, the summary catalogue and the notice (small); the pair package; the summary
// of each selected site (windows, events, opportunities copied from its manifest, checked by
// SHA-256), which fills the status cards; then the two full site packages in parallel, each pane
// filled as soon as its own package and arrays are in (arrays checked by SHA-256 as before).
// Only the two selected sites are ever loaded.

import { loadIndex, loadSite, loadSitePairs, loadSiteSummary, loadSummaryCatalogue, PackageError } from "./package.js";
import { bandNote, createSky } from "./sky.js";
import {
  siteFileUrl, siteOptionsHtml, validationNoteHtml, loadNoticeFile,
  canLabelUtc, esc, etOfUtc, eventsHtml, fixed, footerHtml, inWindow, loadSiteData, metricText,
  metricsAtHeight, nearestSample, readoutHtml, renderHorizon, sampleEt, sampleUtc, terrainSourceHtml,
} from "./panel.js";
import { downloadCsv, seriesCsv } from "./csv.js";
import { calendarHtml, requirementIds, setCalendarTime } from "./calendar.js";
import { countdownHtml, statusCardsHtml } from "./status.js";
import { groundData, groundInput } from "./ground.js";

const params = new URLSearchParams(location.search);
// Defaults are site files resolved from the script location (see siteFileUrl), so a copy of this
// page at the site root reads the same files as the page in viewer/.
const INDEX_URL = params.get("index") || siteFileUrl("packages/index.json");
const NOTICE_URL = params.get("notice") || siteFileUrl("notice.json");
const SUMMARY_URL = params.get("summary") || siteFileUrl("summary/index.json");
const $ = (id) => document.getElementById(id);

// Package metrics shown side by side (ids as written by the core; absent ones are skipped).
const SUMMARY = [
  "sun_visible_fraction_of_time", "sun_longest_outage_s", "earth_visible_fraction_of_time",
  "earth_longest_outage_s", "dte_network_share", "dte_longest_outage_s", "dte_relay_need_level", "sun_eclipse_count",
];
// Windows shown as status chips at the shared time.
const CHIPS = [["sun_visible", "Sun visible"], ["earth_visible", "Earth visible"], ["earth_network_dsn", "DSN two-way link"], ["sun_eclipsed_by_earth", "Sun eclipsed by the Earth"]];

const VIEWS = ["chart", "sky", "ground", "calendar"];
const state = {
  index: null, summaries: null, panes: [], pairs: null, i: 0, timer: null, tables: {},
  view: VIEWS.includes(params.get("view")) ? params.get("view") : "chart", calendarKey: null, timeReady: false,
  timings: {},
};

function mark(name) {
  if (state.timings[name] === undefined) state.timings[name] = Math.round(performance.now());
}

function showError(message) {
  $("error").textContent = message;
  $("error").hidden = false;
}

function status(text) {
  $("load-status").textContent = text;
  $("load-status").hidden = !text;
}

function makePane(root) {
  root.appendChild($("pane-template").content.cloneNode(true));
  const q = (role) => root.querySelector(`[data-role="${role}"]`);
  return { root, q, site: null, summary: null, h: 0, data: null, k: null };
}

// What a pane can show now: the full package, or until it arrives the checked summary.
const viewOf = (pane) => pane.site || pane.summary;
const sizeText = (bytes) => (bytes > 1e6 ? `${fixed(bytes / 1e6, 1)} MB` : `${Math.round(bytes / 1e3)} kB`);

function paneStatus(pane, text) {
  const el = pane.q("loading");
  el.textContent = text || "";
  el.hidden = !text;
}

function fillHeights(pane, hz) {
  pane.q("height").innerHTML = hz.observer_heights_m
    .map((v, j) => `<option value="${j}">${esc(v)} m${j === hz.default_height_index ? " (default)" : ""}</option>`).join("");
  pane.q("height").value = String(pane.h);
}

// Load site k into a pane: first its summary (fast), then the full package and the arrays of the
// selected height. Only the latest request of a pane is applied: a slower earlier load that
// finishes later is dropped (returns false), so the pane shows what was chosen last.
// keepMetres: keep this observer height (in metres) if the new package has it.
async function setSite(pane, k, wantedH, keepMetres = null) {
  const token = (pane.loading = (pane.loading || 0) + 1);
  const entry = state.index.sites[k];
  const name = entry.name || entry.site_id;
  pane.k = k;
  pane.q("site").value = String(k);
  const pick = (hz) => {
    const same = keepMetres === null ? -1 : hz.observer_heights_m.indexOf(keepMetres);
    return Number.isInteger(wantedH) && wantedH >= 0 && wantedH < hz.observer_heights_m.length ? wantedH
      : same >= 0 ? same : hz.default_height_index;
  };
  paneStatus(pane, `Loading the summary of ${name}…`);
  let summary = null;
  try { summary = await loadSiteSummary(state.summaries, entry, state.index.base); } catch (e) { summary = null; }
  if (token !== pane.loading) return false;
  if (summary) {
    pane.summary = summary; pane.site = null; pane.data = null;
    pane.h = pick(summary.manifest.horizon);
    fillHeights(pane, summary.manifest.horizon);
    mark(`summary-${pane.root.id}`);
    onPaneChanged(pane);
    // The first chart: the horizon and the Sun and Earth directions, through the summary's array
    // references (checked by SHA-256), while the large manifest is still on its way.
    try {
      paneStatus(pane, `Loading the horizon chart of ${name}…`);
      const lean = await loadSiteData(summary, pane.h, { lean: true });
      if (token !== pane.loading) return false;
      if (!pane.site) { pane.data = lean; mark(`chart-${pane.root.id}`); onPaneChanged(pane); }
    } catch (e) { /* the full package below draws the chart */ }
  }
  const cat = state.summaries && state.summaries.bySite[entry.site_id];
  paneStatus(pane, `Loading the full package of ${name} (charts and details)…`);
  const site = await loadSite(state.index.base, entry);
  if (token !== pane.loading) return false;
  // Arrays already read and checked through the summary are the same files: do not fetch them again.
  if (summary && summary.id === site.id) for (const [file, value] of summary.cache) site.cache.set(file, value);
  const hz = site.manifest.horizon;
  const h = summary ? pane.h : pick(hz);
  if (summary && pane.data) {
    // The manifest is in: whole-period metrics, events and package details can be shown now.
    pane.site = site;
    fillHeights(pane, hz);
    mark(`manifest-${pane.root.id}`);
    onPaneChanged(pane);
  }
  paneStatus(pane, `Loading and checking the remaining arrays of ${name}${cat ? ` (summary was ${sizeText(cat.bytes)})` : ""}…`);
  const data = await loadSiteData(site, h);
  if (token !== pane.loading) return false;
  pane.site = site; pane.h = h; pane.data = data; pane.summary = summary;
  fillHeights(pane, hz);
  paneStatus(pane, "");
  mark(`full-${pane.root.id}`);
  onPaneChanged(pane);
  return true;
}

// A pane got new content: set up the shared time once site A is known, then draw.
function onPaneChanged(pane) {
  if (pane === state.panes[0] && !state.timeReady && viewOf(pane) && viewOf(pane).timeline) {
    state.timeReady = true;
    const wantedI = Number(params.get("i"));
    state.i = Number.isInteger(wantedI) ? wantedI : 0;
    configureTimeline(null);
    return;
  }
  if (state.timeReady) render();
}

function reference() {
  return viewOf(state.panes[0]);
}

function sharedEt() {
  return sampleEt(reference(), state.i);
}

function renderPane(pane) {
  const site = viewOf(pane);
  if (!site) return;
  if (!site.timeline) {
    pane.q("note").textContent = "This package has no time window.";
    pane.q("note").hidden = false;
    return;
  }
  const et = sharedEt();
  const i = nearestSample(site, et);
  const exact = sampleEt(site, i) === et;
  const sEt = sampleEt(site, i);
  pane.q("time").textContent = `Shown at ${sampleUtc(site, i)}`;
  pane.q("cards").innerHTML = statusCardsHtml(site, pane.h, sEt, $("cal-req").value || null);
  if (!state.timings.cards && state.panes.every((p) => viewOf(p))) mark("cards");
  pane.q("terrain").innerHTML = terrainSourceHtml(site);
  pane.q("note").hidden = exact;
  if (!exact) pane.q("note").textContent = `This package has another time grid: shown at its nearest sample, ${sampleUtc(site, i)}.`;
  pane.q("chips").innerHTML = CHIPS.map(([id, label]) => {
    const v = inWindow(site, pane.h, id, sEt);
    return v === null ? "" : `<span class="chip ${v ? "on" : "off"}" title="window ${id}">${label}: ${v ? "yes" : "no"}</span>`;
  }).join("");
  const full = Boolean(pane.site && pane.data && !pane.data.lean);
  const sky = state.view === "sky", ground = state.view === "ground";
  const chartReady = Boolean(pane.data);
  pane.q("chart").hidden = state.view !== "chart" || !chartReady;
  if (state.view === "chart" && chartReady) renderHorizon(pane.q("horizon"), site, pane.data, i);
  pane.q("sky").hidden = !sky || !full;
  pane.q("band").hidden = !sky || !full;
  pane.q("ground").hidden = !ground || !full;
  pane.q("ground-link").hidden = !ground;
  pane.q("details").hidden = !pane.site;
  if (!pane.site) return;
  if (sky && full) {
    // The same panorama module as the single-site viewer, one instance per pane.
    if (!pane.sky) pane.sky = createSky(pane.q("sky"), { onPick: (j) => setSample(nearestSample(reference(), sampleEt(pane.site, j))) });
    const v = $("sky-span").value;
    pane.sky.update({ site: pane.site, data: pane.data, h: pane.h, i, spanSamples: v === "all" ? pane.site.timeline.time.count : Number(v) });
    pane.q("band").innerHTML = bandNote(pane.site, pane.h);
  } else if (ground && full) {
    updatePaneGround(pane, i);
  }
  pane.q("readout").innerHTML = full ? readoutHtml(pane.site, pane.data, pane.h, i)
    : '<tbody><tr><td class="loading-status">Loading the margin and visible-fraction arrays…</td></tr></tbody>';
  const metrics = Object.fromEntries(metricsAtHeight(pane.site, pane.h).map((m) => [m.id, m]));
  const rows = SUMMARY.filter((id) => metrics[id]).map((id) => `<tr><td>${esc(metrics[id].label)}</td><td class="num">${metricText(metrics[id])}</td>
    <td><code>${esc(metrics[id].method)}</code> [${esc(pane.site.methodStatus(metrics[id].method))}]</td></tr>`);
  const t = pane.site.timeline.time;
  pane.q("summary").innerHTML = `<thead><tr><th>Quantity (${esc(t.start_utc)} to ${esc(t.end_utc)})</th><th>Value</th><th>Method</th></tr></thead><tbody>${rows.join("")}</tbody>`;
  pane.q("events").innerHTML = eventsHtml(pane.site, pane.h, i, 0, 4);
  pane.q("countdown").innerHTML = countdownHtml(pane.site, pane.h);
  pane.q("footer").innerHTML = footerHtml(pane.site);
}

// The ground view of a pane: the renderer of the single-site viewer (js/view3d.js), one per pane,
// started only when the view is chosen; its terrain arrays are read then, not before.
async function updatePaneGround(pane, i) {
  const site = pane.site;
  const v = new URL(siteFileUrl("viewer/index.html"));
  v.search = new URLSearchParams({ site: site.manifest.site.site_id, h: String(pane.h), i: String(i), tab: "3d" }).toString();
  const link = `<a href="${esc(v.href)}">Open this ground view with all its controls</a> (lighting, slope shading, patch edges).`;
  pane.q("ground-link").innerHTML = link;
  try {
    if (!state.view3dModule) state.view3dModule = await import("./view3d.js");
    if (!pane.view3d) pane.view3d = state.view3dModule.createView(pane.q("ground"), { onCheck: (text) => { pane.groundCheck = text; } });
    if (!pane.ground || pane.ground.siteId !== site.id) {
      paneStatus(pane, "Loading the terrain patches for the ground view…");
      pane.ground = await groundData(site, state.index, state.tables);
      paneStatus(pane, "");
    }
    if (pane.site !== site) return;
    pane.view3d.update(groundInput({ site, h: pane.h, i, data: pane.data, g: pane.ground, view3dModule: state.view3dModule }));
    const t = pane.view3d.terrainCheck();
    const worst = t ? Math.max(...Object.values(t.patches).map((p) => p.maxDiff_m)) : null;
    pane.q("ground-link").innerHTML = `${link} <span class="muted">${esc(pane.groundCheck || "")}${t ? ` Terrain check: ${Object.keys(t.patches).length} patches; drawn vertices differ from the package nodes by at most ${worst} m.` : ""}</span>`;
  } catch (e) {
    pane.q("ground").innerHTML = `<p class="banner">The ground view could not start: ${esc(e.message || e)}. The horizon chart and the sky panorama show the same package data without WebGL.</p>`;
  }
}

function render() {
  const ref = reference();
  if (!ref || !ref.timeline) return;
  renderPairs();
  $("export-csv").disabled = !state.panes.every((p) => p.site && p.data && p.site.timeline);
  $("utc").textContent = sampleUtc(ref, state.i);
  if (canLabelUtc(ref)) $("date").value = sampleUtc(ref, state.i).slice(0, 16);
  fillRequirements();
  state.panes.forEach(renderPane);
  renderCalendar();
  const loaded = state.panes.filter((p) => p.site).length;
  status(loaded === 2 ? "" : `Status from the site summaries; ${loaded === 1 ? "one full package of two is in" : "loading the full packages for charts and details"}…`);
  const views = state.panes.map(viewOf);
  if (views.every(Boolean)) {
    const q = new URLSearchParams(location.search);
    q.set("a", views[0].manifest.site.site_id); q.set("b", views[1].manifest.site.site_id);
    q.set("ha", String(state.panes[0].h)); q.set("hb", String(state.panes[1].h)); q.set("i", String(state.i)); q.set("view", state.view);
    history.replaceState(null, "", `?${q}`);
  }
  // The single-site viewer opens with site A, its height and the shared time (A is the reference).
  const v = new URL(siteFileUrl("viewer/index.html"));
  v.search = new URLSearchParams({ site: ref.manifest.site.site_id, h: String(state.panes[0].h), i: String(state.i) }).toString();
  $("viewer-link").href = v.href;
}

// The requirements of the two packages, for the status cards and the calendar.
function fillRequirements() {
  const entries = state.panes.map(viewOf).filter(Boolean).map((site) => ({ site }));
  const ids = requirementIds(entries);
  const sel = $("cal-req");
  if (sel.dataset.ids === ids.join("|")) return;
  const labels = {};
  for (const { site } of entries) for (const r of ((site.manifest.request || {}).timeline || {}).requirements || []) labels[r.id] = r.label || r.id;
  const keep = sel.value;
  sel.innerHTML = ids.length ? ids.map((id) => `<option value="${esc(id)}" title="${esc(labels[id] || id)}">${esc(id)}</option>`).join("") : "<option value=\"\">none stated in these packages</option>";
  sel.dataset.ids = ids.join("|");
  if (ids.includes(keep)) sel.value = keep;
}

function renderPairs() {
  const box = $("pair-results");
  if (!state.pairs) { box.innerHTML = ""; return; }
  const [pa, pb] = state.panes.map(viewOf);
  if (!pa || !pb) return;
  const a = pa.manifest.site.site_id;
  const b = pb.manifest.site.site_id;
  const pair = state.pairs.pairs.find((p) => (p.site_a === a && p.site_b === b) || (p.site_a === b && p.site_b === a));
  if (!pair) { box.innerHTML = "<p class=\"muted\">No published pair metrics for the selected sites.</p>"; return; }
  // The pair metrics belong to the site packages and observer heights named in site_pairs.sites.
  const info = Object.fromEntries((state.pairs.sites || []).map((s) => [s.site_id, s]));
  const notes = [];
  for (const [view, pane] of [[pa, state.panes[0]], [pb, state.panes[1]]]) {
    const id = view.manifest.site.site_id, entry = info[id];
    if (!entry) { notes.push(`${esc(id)} is not described in the pair package.`); continue; }
    if (entry.package_id !== view.id) notes.push(`${esc(entry.name || id)}: the pair package was computed from site package ${esc(entry.package_id)}, not from the loaded ${esc(view.id)}.`);
    const shown = view.manifest.horizon.observer_heights_m[pane.h];
    if (entry.observer_height_m !== shown) notes.push(`${esc(entry.name || id)}: the pair metrics are for ${esc(entry.observer_height_m)} m, the pane shows ${esc(shown)} m.`);
  }
  const heights = [a, b].map((id) => info[id] ? `${esc(info[id].name || id)} ${esc(info[id].observer_height_m)} m` : esc(id)).join(", ");
  const method = (pair.windows[0] || {}).method;
  const card = method && state.pairs.methods && state.pairs.methods[method];
  const status = card && card.validation ? card.validation.status : "unknown";
  // SPEC 6a: covered_share_of_better_outage is null when the better site lacks no time.
  const share = (v) => (v === null || v === undefined ? "none (no outage)" : `${fixed(v * 100, 1)} %`);
  const hours = (s) => `${fixed(s / 3600, 1)} h`;
  const nameOf = (id) => esc((info[id] && info[id].name) || id);
  const rows = pair.windows.map((w) => `<tr><td><code>${esc(w.window)}</code></td><td class="num">${hours(w.a_s)}</td><td class="num">${hours(w.b_s)}</td>
    <td class="num">${fixed(w.either_fraction * 100, 1)} %</td><td class="num">${hours(w.both_s)}</td><td class="num">${hours(w.neither_s)}</td>
    <td class="num">${hours(w.longest_neither_s)}</td><td class="num">${hours(w.gain_over_better_s)}</td><td class="num">${share(w.covered_share_of_better_outage)}</td></tr>`).join("");
  const range = state.pairs.time ? `${esc(state.pairs.time.start_utc)} to ${esc(state.pairs.time.end_utc)}` : "the scenario time range";
  const warnings = (state.pairs.warnings || []).map((x) => `<li>${esc(x)}</li>`).join("");
  box.innerHTML = `<h2>The two sites together</h2>
    ${notes.length ? `<p class="small note">${notes.join(" ")}</p>` : ""}
    ${warnings ? `<ul class="small note">${warnings}</ul>` : ""}
    <div class="table"><table><thead><tr><th>Window (${range})</th><th>At ${nameOf(pair.site_a)}</th><th>At ${nameOf(pair.site_b)}</th><th>Either site</th><th>Both</th><th>Neither (joint outage)</th><th>Longest joint outage</th><th>Gain over the better site</th><th>Share of the better site's outage covered</th></tr></thead><tbody>${rows}</tbody></table></div>
    <details class="details small"><summary>Details: pair package and method</summary>
      <p>Package <code>${esc(state.pairs.package_id)}</code>, method <code>${esc(method || "n/a")}</code> [${esc(status)}]; great-circle distance ${fixed(pair.distance_m, 0)} m.
      Computed at the observer heights ${heights} (the default heights of the site packages); read from <code>site_pairs</code>, not recomputed.
      The package says when at least one site sees the body; it does not say that power or data can be moved between the sites.</p></details>`;
}

// The calendar of both panes on one axis, drawn again only when a site, a height or the
// requirement changes; the marker of the shared time moves on every step. It needs the full
// packages (timeline.calendar is not in the summaries).
function renderCalendar() {
  const box = $("calendar-section");
  box.hidden = state.view !== "calendar";
  if (box.hidden) return;
  if (!state.panes.every((p) => p.site)) { $("calendar").innerHTML = '<p class="loading-status small">Waiting for the full packages of both sites…</p>'; state.calendarKey = null; return; }
  const entries = state.panes.map((p) => ({ site: p.site, h: p.h, name: p.site.manifest.site.name || p.site.manifest.site.site_id }));
  const wanted = $("cal-req").value;
  const key = entries.map((e) => `${e.site.id}:${e.h}`).join("|") + `:${wanted}`;
  if (state.calendarKey !== key) {
    $("calendar").innerHTML = calendarHtml(entries, { requirementId: wanted || null });
    state.calendarKey = key;
  }
  setCalendarTime($("calendar"), sharedEt());
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

// Hours to samples of the reference grid (at least one sample).
function samplesFor(hours) {
  const n = Math.round((Math.abs(hours) * 3600) / reference().timeline.time.step_s);
  return Math.sign(hours) * Math.max(1, n);
}

function togglePlay(force) {
  const button = $("play");
  const play = force === undefined ? !state.timer : force;
  if (state.timer) { clearInterval(state.timer); state.timer = null; }
  button.textContent = play ? "Pause" : "Play";
  button.setAttribute("aria-pressed", String(play));
  if (!play) return;
  state.timer = setInterval(() => {
    if (!reference()) return;
    const step = samplesFor(Number($("speed").value));
    const count = reference().timeline.time.count;
    setSample(state.i + step >= count ? 0 : state.i + step);
  }, 150);
}

function setView(view) {
  state.view = view;
  for (const v of VIEWS) $(`view-${v}`).setAttribute("aria-pressed", String(view === v));
  $("span-label").hidden = view !== "sky";
  if (state.timeReady) render();
}

function wire() {
  $("export-csv").addEventListener("click", () => {
    try {
      if (!state.panes.every((p) => p.site && p.data && p.site.timeline)) {
        throw new PackageError("both selected sites must have time-series package data");
      }
      const shared = reference().timeline.time;
      downloadCsv("lunar-site-comparison-sun-earth.csv", seriesCsv(state.panes.map((p) => ({
        site: p.site, data: p.data, height: p.h,
      })), [shared.start_utc, shared.end_utc]));
    } catch (e) { showError(String(e.message || e)); }
  });
  for (const v of VIEWS) $(`view-${v}`).addEventListener("click", () => setView(v));
  $("cal-req").addEventListener("change", () => { state.calendarKey = null; if (state.timeReady) render(); });
  // A click on a lunar day or a landing window goes to its start (nearest sample of site A).
  $("calendar").addEventListener("click", (ev) => {
    const cell = ev.target.closest("[data-et]");
    if (cell) setSample(nearestSample(reference(), Number(cell.dataset.et)));
  });
  $("sky-span").addEventListener("change", () => render());
  $("play").addEventListener("click", () => togglePlay());
  $("slider").addEventListener("input", (ev) => setSample(Number(ev.target.value)));
  document.querySelectorAll("[data-step]").forEach((b) => b.addEventListener("click", () => reference() && setSample(state.i + samplesFor(Number(b.dataset.step)))));
  $("date").addEventListener("change", (ev) => {
    if (!ev.target.value || !reference()) return;
    const ms = Date.parse(`${ev.target.value}:00Z`); // the input is read as UTC
    if (Number.isFinite(ms)) setSample(nearestSample(reference(), etOfUtc(reference(), ms)));
  });
  state.panes.forEach((pane, n) => {
    pane.q("site").addEventListener("change", async (ev) => {
      try {
        const view = viewOf(pane);
        const keep = state.timeReady ? sharedEt() : null, metres = view ? view.manifest.horizon.observer_heights_m[pane.h] : null;
        const done = setSite(pane, Number(ev.target.value), null, metres);
        if (!(await done)) return;
        if (n === 0 && keep !== null) configureTimeline(keep); else render();
      } catch (e) { showError(String(e.message || e)); }
    });
    pane.q("height").addEventListener("change", async (ev) => {
      try {
        const token = (pane.loading = (pane.loading || 0) + 1), h = Number(ev.target.value);
        // Before the full package: the cards follow at once, the chart from the summary's arrays.
        const data = await loadSiteData(viewOf(pane), h, { lean: !pane.site });
        if (token !== pane.loading) return;
        pane.h = h; pane.data = data;
        render();
      } catch (e) { showError(String(e.message || e)); }
    });
  });
}

// Initial sites when the address names none: the first pair of the published site_pairs
// package (so that the pair metrics are there), otherwise the first two sites of the index.
function initialSites(sites) {
  const find = (id) => sites.findIndex((s) => s.site_id === id);
  let a = find(params.get("a")), b = find(params.get("b"));
  const pair = state.pairs && state.pairs.pairs[0];
  if (a < 0 && b < 0 && pair && find(pair.site_a) >= 0 && find(pair.site_b) >= 0) return [find(pair.site_a), find(pair.site_b)];
  if (a < 0) a = 0;
  if (b < 0) b = sites.length > 1 ? (a === 0 ? 1 : 0) : 0;
  return [a, b];
}

async function main() {
  mark("script");
  // On a phone the status cards come first: the less used controls start folded (still one tap away).
  if (window.matchMedia && window.matchMedia("(max-width: 600px)").matches && !params.get("view")) $("more-controls").open = false;
  state.panes = [makePane($("pane-a")), makePane($("pane-b"))];
  wire();
  try {
    const [noticeFile, index, summaries] = await Promise.all([loadNoticeFile(NOTICE_URL), loadIndex(INDEX_URL), loadSummaryCatalogue(SUMMARY_URL)]);
    $("validation-note").innerHTML = validationNoteHtml(noticeFile, siteFileUrl("evidence.html"));
    state.index = index; state.summaries = summaries;
    const sites = state.index.sites;
    if (sites.length < 1) throw new PackageError("the index lists no site package");
    status(`${sites.length} sites in the published set; reading the site pairs…`);
    const pairEntry = state.index.index.packages.find((p) => p.kind === "site_pairs");
    if (pairEntry) state.pairs = await loadSitePairs(state.index.base, pairEntry);
    const options = siteOptionsHtml(sites, summaries);
    state.panes.forEach((p) => { p.q("site").innerHTML = options; });
    mark("selectors");
    const [a, b] = initialSites(sites);
    status("Loading the two selected sites…");
    const ha = Number(params.get("ha") ?? NaN), hb = Number(params.get("hb") ?? NaN);
    const loads = [setSite(state.panes[0], a, ha), setSite(state.panes[1], b, hb)];
    setView(state.view);
    await Promise.all(loads);
    if (!reference() || !reference().timeline) throw new PackageError("site A has no time window");
    mark("full");
    if (state.panes.some((p) => p.site.manifest.synthetic)) {
      const box = $("notice");
      box.textContent = "SYNTHETIC SAMPLE DATA: invented values, not results.";
      box.hidden = false;
    }
  } catch (e) {
    showError(`Could not load the packages: ${e.message || e}`);
    status("");
  }
}

window.lsnCompare = { state };
main();
