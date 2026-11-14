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
  return value === null || value === undefined || Number.isNaN(value) ? "—" : Number(value).toFixed(digits);
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

export async function loadSiteData(site, h) {
  const m = site.manifest;
  const tl = site.timeline;
  const data = { horizon: (await site.array(m.horizon.elevation_deg)).row(h), series: {} };
  if (m.horizon.distance_m) data.distance = (await site.array(m.horizon.distance_m)).row(h);
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

const yesNo = (v) => (v === null ? "—" : v ? '<span class="yes">yes</span>' : '<span class="no">no</span>');

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
    <td class="num">${e.obstacle_distance_m === null ? "—" : fixed(e.obstacle_distance_m / 1000, 2) + " km"}</td></tr>`);
  return `<thead><tr><th>Time (UTC)</th><th></th><th>Body</th><th>Event</th><th>Body azimuth</th>
    <th>Terrain horizon elevation</th><th>Obstacle distance</th></tr></thead><tbody>${rows.join("") ||
    '<tr><td colspan="7">No rise or set event at this height.</td></tr>'}</tbody>`;
}

export function metricText(metric) {
  // Formatting only: fractions and shares as percentages, seconds as hours, flags and counts as stored.
  const v = metric.value;
  if (v === null || v === undefined) return "—";
  if (metric.unit === "1") return metric.id.includes("fraction") || metric.id.endsWith("_share") ? `${fixed(100 * v, 1)} %` : String(v);
  if (metric.unit === "s") return `${fixed(v / 3600, 1)} h`;
  return `${v} ${esc(metric.unit)}`;
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

export async function loadNotice(url) {
  const notice = await fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
  return notice && notice.notice ? notice.notice : null;
}
