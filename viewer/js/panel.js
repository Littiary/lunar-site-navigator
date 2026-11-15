// Shared pieces of the viewer pages: look up package values for one site at one observer
// height and one time sample, and render them.
//
// Rule: every number shown comes from a package unchanged. These functions select values,
// compare times, format text and map values to screen positions. No trigonometry, no science.

// A file of the published site (packages/index.json, notice.json), resolved from the location of
// this module (site/viewer/js/), not from the page URL: pages are served from the site root and
// from viewer/, and both must read the same files.
export function siteFileUrl(name, moduleUrl = import.meta.url) {
  return new URL(`../../${name}`, moduleUrl).href;
}

export const BODIES = ["SUN", "EARTH"];
export const NAMES = { SUN: "Sun", EARTH: "Earth" };

export function esc(text) {
  return String(text).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" })[c]);
}

export function fixed(value, digits) {
  return value === null || value === undefined || Number.isNaN(value) ? "n/a" : Number(value).toFixed(digits);
}

// ------------------------------------------------------------------ time grid (SPEC 3.5)

export function sampleEt(site, i) {
  const t = site.timeline.time;
  return t.start_et_s + i * t.step_s; // the definition of sample i of the time grid
}

export function canLabelUtc(site) {
  return site.timeline.time.leap_seconds_in_range === 0;
}

export function sampleUtc(site, i) {
  const t = site.timeline.time;
  // SPEC 3.5: a reader may label sample i as start_utc + i * step_s only without leap seconds.
  if (!canLabelUtc(site)) return `sample ${i} of ${t.count} (UTC label not available: leap second in range)`;
  return new Date(Date.parse(t.start_utc) + i * t.step_s * 1000).toISOString();
}

export function nearestSample(site, et) {
  const t = site.timeline.time;
  return Math.min(t.count - 1, Math.max(0, Math.round((et - t.start_et_s) / t.step_s)));
}

// The time-grid instant labelled by a UTC string (only where SPEC 3.5 allows UTC labels).
export function etOfUtc(site, utcMs) {
  const t = site.timeline.time;
  return t.start_et_s + (utcMs - Date.parse(t.start_utc)) / 1000;
}

export function containing(intervals, et) {
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

export function windowsAtHeight(site, h) {
  return (site.timeline ? site.timeline.windows : []).filter((w) => w.height_index === h);
}

export function eventsAtHeight(site, h) {
  return (site.timeline ? site.timeline.events : []).filter((e) => e.height_index === h);
}

export function metricsAtHeight(site, h) {
  return (site.timeline ? site.timeline.metrics || [] : []).filter((m) => m.height_index === h || m.height_index === null);
}

// ------------------------------------------------------------------ loading

// The arrays of one observer height, fetched in parallel and checked by SitePackage.array().
// lean: only what the horizon chart draws (horizon, distances, Sun and Earth directions); the
// margin and visible-fraction rows (readouts, sky panorama, CSV) are left out (null).
export async function loadSiteData(site, h, { lean = false } = {}) {
  const m = site.manifest;
  const tl = site.timeline;
  const get = (ref) => site.array(ref);
  const [hz, dist] = await Promise.all([get(m.horizon.elevation_deg), m.horizon.distance_m ? get(m.horizon.distance_m) : null]);
  const data = { horizon: hz.row(h), series: {}, lean };
  if (dist) data.distance = dist.row(h);
  if (tl) {
    const bodies = BODIES.filter((b) => tl.series && tl.series[b]);
    const rows = await Promise.all(bodies.map((body) => {
      const s = tl.series[body];
      return Promise.all([get(s.azimuth_deg), get(s.elevation_deg), lean ? null : get(s.margin_deg), lean ? null : get(s.visible_fraction)]);
    }));
    bodies.forEach((body, k) => {
      const [az, el, margin, fraction] = rows[k];
      data.series[body] = { az: az.values, el: el.values, margin: margin ? margin.row(h) : null, fraction: fraction ? fraction.row(h) : null };
    });
  }
  data.yRange = displayRange(data);
  return data;
}

function displayRange(data) {
  // Axis limits for display: the extremes of what is drawn, padded to whole degrees.
  let lo = Infinity, hi = -Infinity;
  const take = (arr) => { for (const v of arr) if (Number.isFinite(v)) { if (v < lo) lo = v; if (v > hi) hi = v; } };
  take(data.horizon);
  for (const body of BODIES) if (data.series[body]) take(data.series[body].el);
  return [Math.floor(lo) - 1, Math.ceil(hi) + 1];
}

// ------------------------------------------------------------------ rendering

const W = 1000, H = 360, X0 = 52, X1 = 985, Y0 = 18, Y1 = 318;

export function renderHorizon(svg, site, data, i) {
  const az = site.manifest.horizon.azimuth;
  const row = data.horizon;
  const [ymin, ymax] = data.yRange;
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
  if (site.timeline) {
    for (const body of BODIES) {
      const s = data.series[body];
      if (!s) continue;
      const a = s.az[i], e = s.el[i];
      if (!Number.isFinite(a) || !Number.isFinite(e)) continue;
      const x = px(a), y = Math.min(Y1, Math.max(Y0, py(e)));
      parts.push(`<circle class="${body.toLowerCase()}" cx="${x.toFixed(2)}" cy="${y.toFixed(2)}" r="8"/>`);
      parts.push(`<text class="label" x="${(x + 11).toFixed(2)}" y="${(y - 9).toFixed(2)}">${NAMES[body]}</text>`);
    }
  }
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.innerHTML = parts.join("");
}

export function inWindow(site, h, id, et) {
  const w = windowsAtHeight(site, h).find((x) => x.id === id);
  return w ? containing(w.intervals_et_s, et) >= 0 : null;
}

const yesNo = (v) => (v === null ? "n/a" : v ? '<span class="yes">yes</span>' : '<span class="no">no</span>');

export function readoutHtml(site, data, h, i) {
  if (!site.timeline) return '<tbody><tr><td>This package has no time window.</td></tr></tbody>';
  const et = sampleEt(site, i);
  const height = site.manifest.horizon.observer_heights_m[h];
  const rows = BODIES.filter((b) => data.series[b]).map((body) => {
    const s = data.series[body];
    return `<tr><td>${NAMES[body]}</td><td class="num">${fixed(s.az[i], 3)}°</td><td class="num">${fixed(s.el[i], 3)}°</td>
      <td class="num">${fixed(s.margin[i], 3)}°</td><td class="num">${fixed(100 * s.fraction[i], 1)} %</td>
      <td>${yesNo(inWindow(site, h, `${body.toLowerCase()}_visible`, et))}</td></tr>`;
  });
  return `<thead><tr><th>Body</th><th>Azimuth of centre</th><th>Elevation of centre (no terrain)</th>
    <th>Margin above terrain horizon at ${esc(height)} m</th><th>Disc above terrain horizon</th><th>In window <code>&lt;body&gt;_visible</code></th></tr></thead>
    <tbody>${rows.join("")}</tbody>`;
}

export function windowsHtml(site, h, i) {
  const et = sampleEt(site, i);
  const rows = windowsAtHeight(site, h).map((w) => {
    const k = containing(w.intervals_et_s, et);
    const span = k >= 0 ? `${esc(w.intervals_utc[k][0])} to ${esc(w.intervals_utc[k][1])}` : "";
    return `<tr><td><code>${esc(w.id)}</code></td><td>${esc(w.definition || "")}</td>
      <td>${yesNo(k >= 0)}</td><td class="mono">${span}</td></tr>`;
  });
  return `<thead><tr><th>Window</th><th>Condition</th><th>Contains this time</th><th>Interval (UTC)</th></tr></thead><tbody>${rows.join("")}</tbody>`;
}

export function eventsHtml(site, h, i, before = 3, after = 3) {
  const et = sampleEt(site, i);
  const events = eventsAtHeight(site, h);
  let next = events.findIndex((e) => e.et_s > et);
  if (next < 0) next = events.length;
  const shown = events.slice(Math.max(0, next - before), next + after);
  const rows = shown.map((e) => `<tr><td class="mono">${esc(e.utc)}</td><td>${e.et_s > et ? "next" : "past"}</td>
    <td>${NAMES[e.body] || esc(e.body)}</td><td>${esc(e.type)}</td><td class="num">${fixed(e.azimuth_deg, 2)}°</td>
    <td class="num">${fixed(e.horizon_elevation_deg, 3)}°</td>
    <td class="num">${e.obstacle_distance_m === null || e.obstacle_distance_m === undefined ? "n/a" : fixed(e.obstacle_distance_m / 1000, 2) + " km"}</td>
    <td>${terrainQualityText(e)}</td></tr>`);
  return `<thead><tr><th>Time (UTC)</th><th></th><th>Body</th><th>Event</th><th>Body azimuth</th>
    <th>Terrain horizon elevation</th><th>Obstacle distance</th><th>Terrain quality</th></tr></thead><tbody>${rows.join("") ||
    '<tr><td colspan="8">No rise or set event at this height.</td></tr>'}</tbody>`;
}

export function metricText(metric) {
  // Formatting only: fractions and shares as percentages, seconds as hours, flags and counts as stored.
  const v = metric.value;
  if (v === null || v === undefined) return "n/a";
  if (metric.unit === "1") return metric.id.includes("fraction") || metric.id.endsWith("_share") ? `${fixed(100 * v, 1)} %` : String(v);
  if (metric.unit === "s") return `${fixed(v / 3600, 1)} h`;
  return `${v} ${esc(metric.unit)}`;
}

// Which elevation product served the site (contract 0.9, horizon.terrain_source) and how much
// detail its horizon can hold. A class other than "fine" is shown as a warning with the
// package's own warnings.
// Options of a site selector, value = position in the index. Grouped by the index field
// `programme` (contract 0.11, optional) in the order the groups first appear; a flat list when
// no site states one. Sites without a programme go to a group "Other sites".
export function siteOptionsHtml(sites, catalogue = null) {
  // Category (contract 0.11) and the terrain class of the site's package (from the summary
  // catalogue, so that no site package is loaded for the list); coarse terrain is flagged.
  const extra = (s) => {
    const c = catalogue && catalogue.bySite[s.site_id];
    const cls = c && c.terrain && c.terrain.resolution_class;
    return [s.category, cls ? `${cls} terrain${cls === "coarse" ? " (warning)" : ""}` : ""].filter(Boolean).join(", ");
  };
  const option = (s, k) => `<option value="${k}">${esc(s.name || s.site_id)}${extra(s) ? ` · ${esc(extra(s))}` : ""}</option>`;
  if (!sites.some((s) => s.programme)) return sites.map(option).join("");
  const groups = new Map();
  sites.forEach((s, k) => {
    const g = s.programme || "Other sites";
    if (!groups.has(g)) groups.set(g, []);
    groups.get(g).push(option(s, k));
  });
  return [...groups].map(([g, opts]) => `<optgroup label="${esc(g)}">${opts.join("")}</optgroup>`).join("");
}

export function terrainSourceHtml(site) {
  const ts = site.manifest.horizon && site.manifest.horizon.terrain_source;
  if (!ts) return "";
  const at = ts.at_site || {};
  // Pixel size to four significant figures for reading (118.45058759433391 -> 118.5); the
  // package value is unchanged in the CSV and in the package itself.
  const px = Number.isFinite(at.pixel_m) ? String(Number(at.pixel_m.toPrecision(4))) : esc(at.pixel_m);
  const text = `Terrain: ${esc(ts.resolution_class)} (${esc(at.product_id || "?")}, ${px} m pixels at the site)`;
  if (ts.resolution_class === "fine") return `<span class="terrain-ok">${text}</span>`;
  const warnings = (site.manifest.warnings || []).map(esc).join(" ");
  return `<span class="terrain-warn"><strong>${text}.</strong> Relief narrower than about two pixels is not in this horizon, and obstacles of that size cannot be shown.${warnings ? " " + warnings : ""}</span>`;
}

// The terrain quality of an event (contract 0.10): the class of the pixel that limits the
// horizon, the elevation product, the height error used for the uncertainty band and where that
// error comes from, and the earliest and latest time of the band. "n/a" where the package has none.
export function terrainQualityText(e) {
  const q = e.terrain_quality;
  if (!q) return "n/a";
  const parts = [q.limiting_pixel ? `pixel ${esc(q.limiting_pixel)}` : "", q.product_id ? esc(q.product_id) : "",
    q.height_error_m !== undefined && q.height_error_m !== null ? `height error ${esc(q.height_error_m)} m` : "",
    q.band_source ? `band from ${esc(q.band_source)}` : "",
    bandText(e)];
  return parts.filter(Boolean).join("; ");
}

// The earliest and latest time of an event's band, with its width. The dates are shown whenever
// the two ends fall on different days, so that a band of 41 h never reads as a few hours. An end
// cut by the computed range (earliest_clipped / latest_clipped) is shown as "before" / "after".
export function bandText(e) {
  if (!e.earliest_utc || !e.latest_utc) return "";
  const a = String(e.earliest_utc), b = String(e.latest_utc);
  const sameDay = a.slice(0, 10) === b.slice(0, 10);
  const end = (u) => (sameDay ? u.slice(11, 19) : `${u.slice(0, 10)} ${u.slice(11, 19)}`);
  const ms = Date.parse(b) - Date.parse(a);
  const width = Number.isFinite(ms) ? `${fixed(ms / 3.6e6, 1)} h, ` : "";
  const from = `${e.earliest_clipped ? "before " : ""}${esc(end(a))}`;
  const to = `${e.latest_clipped ? "after " : ""}${esc(end(b))}`;
  return `band ${width}${from} to ${to} UTC${sameDay ? ` on ${esc(a.slice(0, 10))}` : ""}`;
}

export function footerHtml(site) {
  const m = site.manifest;
  const s = m.site;
  const t = m.timeline ? m.timeline.time : null;
  const radius = s.reference_radius_m && s.reference_radius_m.value;
  const statuses = ["horizon.elevation", "timeline.direction", "timeline.margin", "timeline.visible_fraction", "timeline.windows", "timeline.events"]
    .filter((id) => (m.methods || {})[id]).map((id) => `<code>${id}</code> [${esc(site.methodStatus(id))}]`).join(", ");
  const unverified = site.unverified.size
    ? `<br><strong>Checksums not verified</strong> for ${site.unverified.size} file(s): this browser offers no Web Crypto here (it needs https or localhost).`
    : "<br>Every array that was read matched the size and SHA-256 in its manifest.";
  return `Package <span class="mono">${esc(m.package_id)}</span> (contract ${esc(m.contract.version)}, status ${esc(m.status)}),
    content SHA-256 <span class="mono">${esc(m.content_sha256)}</span>.<br>
    Frame <span class="mono">${esc(s.frame)}</span>, reference sphere radius ${radius / 1000} km, site ${esc(s.lat_deg)}°, ${esc(s.lon_deg)}° (planetocentric, east-positive).<br>
    ${t ? `Time window ${esc(t.start_utc)} to ${esc(t.end_utc)} UTC, ${esc(t.scale)} grid, step ${esc(t.step_s)} s, ${esc(t.count)} samples.<br>` : ""}
    Validation status: ${statuses}.${unverified}`;
}

function hours(seconds) {
  return seconds === null || seconds === undefined ? "n/a" : `${fixed(seconds / 3600, 1)} h`;
}

// A package value with its unit, formatted only (seconds as hours, fractions as percentages).
function valueText(value, unit, id = "") {
  if (value === null || value === undefined) return "n/a";
  if (unit === "s") return hours(value);
  if (unit === "1") return id.includes("fraction") || id.endsWith("_share") ? `${fixed(100 * value, 1)} %` : String(value);
  return `${value} ${esc(unit || "")}`.trim();
}

function statusOf(site, method) {
  return method ? ` <span class="muted">[${esc(site.methodStatus(method))}]</span>` : "";
}

// Fields added in contract 0.2 to 0.6, shown when the package has them (SPEC 8: a reader uses
// what is present and ignores what it does not know), whatever the minor version.
export function contract06Html(site, h) {
  const t = site.timeline;
  if (!t) return '<p class="muted">This package has no time window.</p>';
  const heights = site.manifest.horizon.observer_heights_m;
  const parts = [];

  const calendar = t.calendar;
  if (calendar) {
    parts.push(`<p class="small">Calendar: ${esc(calendar.period || "n/a")}, ${(calendar.periods || []).length} periods in the package (${esc(t.time.start_utc)} to ${esc(t.time.end_utc)})${statusOf(site, calendar.method)}.</p>`);
  }

  const u = t.uncertainty || {};
  if (u.horizon_error) {
    const e = u.horizon_error, a = e.applied_error_deg;
    const stated = [
      e.error_deg !== undefined ? `a common shift of ${esc(e.error_deg)}°` : null,
      e.dem_height_error_m !== undefined ? `a terrain height error of ${esc(e.dem_height_error_m)} m` : null,
    ].filter(Boolean).join(" and ");
    const applied = a ? ` Applied at the default observer height: least ${fixed(a.min, 3)}°, median ${fixed(a.median, 3)}°, largest ${fixed(a.max, 3)}°.` : "";
    parts.push(`<h3>Stated horizon error</h3><p class="small">The package states ${stated || "a horizon error"}.${applied}${statusOf(site, e.method)}</p>
      <p class="small"><strong>Assumption stated in the package:</strong> ${esc(e.assumption || "(none given)")}</p>`);
  }
  if (u.landing_ellipse) {
    const l = u.landing_ellipse;
    const vis = l.visible_s ? Object.entries(l.visible_s).map(([body, v]) => `<tr><td>${esc(NAMES[body] || body)}</td><td class="num">${hours(v.centre_s)}</td><td class="num">${hours(v.min_s)}</td><td class="num">${hours(v.median_s)}</td><td class="num">${hours(v.max_s)}</td></tr>`).join("") : "";
    const at = Number.isInteger(l.height_index) ? ` at ${esc(heights[l.height_index])} m` : "";
    parts.push(`<h3>Stated landing ellipse</h3><p class="small">${esc(l.semi_major_m)} m × ${esc(l.semi_minor_m)} m, major axis at ${esc(l.azimuth_deg)}°, ${(l.points || []).length} sample points, visible time computed${at}${statusOf(site, l.method)}.</p>
      ${vis ? `<div class="table"><table><thead><tr><th>Body</th><th>Visible time at the centre</th><th>Least</th><th>Median</th><th>Largest</th></tr></thead><tbody>${vis}</tbody></table></div>` : ""}
      <p class="small"><strong>Assumption stated in the package:</strong> ${esc(l.assumption || "(none given)")}</p>`);
  }

  const trade = t.height_trade;
  if (trade && trade.quantities) {
    const hs = trade.observer_heights_m || heights;
    const head = hs.map((v) => `<th>${esc(v)} m</th>`).join("");
    const rows = trade.quantities.map((q) => `<tr><td>${esc(q.label || q.id)}</td>${(q.values || []).map((v) => `<td class="num">${valueText(v, q.unit, q.id)}</td>`).join("")}</tr>`).join("");
    parts.push(`<h3>Observer-height trade-offs</h3><p class="small">One column per observer height above the terrain${statusOf(site, trade.method)}.</p>
      <div class="table"><table><thead><tr><th>Quantity</th>${head}</tr></thead><tbody>${rows}</tbody></table></div>`);
  }

  if (t.blockers) {
    const rows = t.blockers.filter((b) => b.height_index === h).map((b) => `<tr><td>${esc(NAMES[b.body] || b.body)}</td>
      <td class="num">${fixed(b.azimuth_start_deg, 2)}° to ${fixed(b.azimuth_end_deg, 2)}°</td>
      <td class="num">${b.peak_distance_m === null || b.peak_distance_m === undefined ? "n/a" : fixed(b.peak_distance_m / 1000, 2) + " km"}</td>
      <td>${b.near_field ? "yes (within 1 km: depends on single pixels of the elevation model)" : "no"}</td>
      <td class="num">${hours(b.lost_s)}</td><td class="num">${fixed(100 * b.share_of_lost, 1)} %</td><td><code>${esc(b.obstacle_id)}</code></td></tr>`).join("");
    parts.push(`<h3>Obstacles that cost visible time at ${esc(heights[h])} m</h3><p class="small">Time lost compared with a smooth sphere through the site, largest first${statusOf(site, (t.blockers[0] || {}).method)}.</p>
      <div class="table"><table><thead><tr><th>Body</th><th>Azimuth run</th><th>Peak distance</th><th>Near field</th><th>Time lost</th><th>Share of lost time</th><th>Obstacle id</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="7">No obstacle costs visible time at this height.</td></tr>'}</tbody></table></div>`);
  }

  if (t.opportunities) {
    const rows = t.opportunities.filter((o) => o.height_index === h).map((o) => {
      const p = o.planned_landing;
      if (!p) return `<tr><td>${esc(o.requirement_id)}</td><td colspan="4">No planned landing is stated in the scenario.</td></tr>`;
      const late = p.feasible ? `${p.slip_tolerance_is_lower_bound ? "at least " : ""}${hours(p.slip_tolerance_s)}` : "n/a";
      const wait = p.feasible ? "n/a" : p.wait_s === null || p.wait_s === undefined ? "no window in the computed range" : hours(p.wait_s);
      return `<tr><td>${esc(o.requirement_id)}</td><td>${esc(p.utc)}: ${p.feasible ? "requirement holds" : "requirement does not hold"}</td><td class="num">${late}</td><td class="num">${p.feasible ? hours(p.early_tolerance_s) : "n/a"}</td><td class="num">${wait}</td></tr>`;
    }).join("");
    parts.push(`<h3>Landing-date tolerance at ${esc(heights[h])} m</h3><p class="small">For each stated requirement: whether it holds for the planned landing, how much later or earlier the landing could be, or how long until the next landing window${statusOf(site, (t.opportunities[0] || {}).method)}.</p>
      <div class="table"><table><thead><tr><th>Requirement</th><th>Planned landing</th><th>Later by up to</th><th>Earlier by up to</th><th>Wait for the next window</th></tr></thead>
      <tbody>${rows || '<tr><td colspan="5">No requirement record at this height.</td></tr>'}</tbody></table></div>`);
  }

  if (!parts.length) return '<p class="muted">This package has none of the planning fields added in contract 0.2 to 0.6.</p>';
  return `<p class="small">Every value below is a package field, formatted only; no dates, tolerances or times are recalculated here.</p>${parts.join("")}`;
}

export async function loadNotice(url) {
  const notice = await fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  return notice && notice.notice ? notice.notice : null;
}

// The notice file with the validation summary of the card (written by the site build).
export async function loadNoticeFile(url) {
  return fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
}

// A short validation note with a link to the evidence page: the counts of the validation card and
// its first open item, as the card states them, and the notice text behind "More".
export function validationNoteHtml(file, evidenceHref) {
  if (!file) return "";
  const v = file.validation;
  const counts = v ? `${esc(v.passed)} of ${esc(v.checks)} validation checks pass${v.failed ? `, ${esc(v.failed)} fails` : ""}` : "";
  const open = v && v.not_validated && v.not_validated.length ? `; not yet validated: ${esc(v.not_validated[0].item.toLowerCase())} and ${v.not_validated.length - 1} more` : "";
  return `<strong>Provisional results.</strong> ${counts}${open}. <a href="${esc(evidenceHref)}">Evidence and limits</a>
    ${file.notice ? `<details class="inline"><summary>More</summary>${esc(file.notice)}</details>` : ""}`;
}
