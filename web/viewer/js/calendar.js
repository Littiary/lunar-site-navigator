// 24-month opportunity calendar (Stage 2, Task 9).
//
// What is shown, and from which package field (SPEC 5.6):
//   - timeline.calendar: the lunar-day periods (start/end in ET seconds and the package's own
//     UTC strings, `complete`) and quantities[].values[h][p] in seconds, for the observer
//     height h selected for each site;
//   - timeline.opportunities[] of the chosen requirement at that height: the landing windows
//     (landing_windows_et_s), feasible_s_per_period, the summary numbers and planned_landing;
//   - request.timeline.requirements[]: the requirement's label and conditions, shown with every
//     number derived from it;
//   - the validation status of the method cards.
// Every site of a package set has the same periods (they do not depend on the site), so the
// rows of two sites line up on one axis. Positions on the axis are ET seconds of the packages,
// labels are the package's UTC strings. Nothing is computed here: values are selected,
// converted to hours for reading, and coloured on a display scale. No trigonometry.

import { esc, fixed } from "./panel.js";

const WIDTH = 960, LEFT = 230, RIGHT = 12, ROW = 20, GAP = 8, HEAD = 18, AXIS = 46;
const COLOURS = { sun: "#f0a54a", earth: "#6ea8fe", both: "#b392f0", outage: "#ff7b72", window: "#3fb950" };

function colourOf(id) {
  if (id.includes("outage")) return COLOURS.outage;
  if (id.startsWith("sun_and_earth")) return COLOURS.both;
  if (id.startsWith("earth")) return COLOURS.earth;
  return COLOURS.sun;
}

// Site name for the row label of the chart, shortened to fit (the full name is in the tooltip).
const shortName = (n) => (n.length > 30 ? `${n.slice(0, 29)}…` : n);

const hoursText = (s) => (s === null || s === undefined || Number.isNaN(s) ? "—" : `${fixed(s / 3600, 1)} h`);

// Requirement records of a package by id (request.timeline.requirements).
function requirementsOf(site) {
  const list = ((site.manifest.request || {}).timeline || {}).requirements || [];
  return Object.fromEntries(list.map((r) => [r.id, r]));
}

// The requirement ids offered for the selected sites, in the order the packages list them.
export function requirementIds(entries) {
  const ids = [];
  for (const { site } of entries) {
    for (const o of (site.timeline && site.timeline.opportunities) || []) if (!ids.includes(o.requirement_id)) ids.push(o.requirement_id);
  }
  return ids;
}

// A requirement's conditions as text (the package's fields; durations shown in hours).
function conditionsText(req) {
  const kinds = { visible_at_landing: "holds at landing", continuous_from_landing: "holds without a break from landing for", total_in_mission: "holds in total during the mission for" };
  const parts = (req.conditions || []).map((c) => `${esc(c.window)} ${esc(kinds[c.kind] || c.kind)}${c.min_s !== undefined ? ` ${hoursText(c.min_s)}` : ""}`);
  return `${parts.join("; ")}${req.mission_duration_s !== undefined ? `; mission duration ${hoursText(req.mission_duration_s)}` : ""}`;
}

// entries: [{ site, h, name }] (one or two sites); options: { requirementId }.
export function calendarHtml(entries, { requirementId = null } = {}) {
  const usable = entries.filter((e) => e.site.timeline && e.site.timeline.calendar);
  const missing = entries.filter((e) => !(e.site.timeline && e.site.timeline.calendar))
    .map((e) => `<p class="note small">${esc(e.name)}: this package has no <code>timeline.calendar</code> (contract 0.3 or later, with a time window), so it has no calendar.</p>`);
  if (!usable.length) return missing.join("");

  // Axis: from the earliest period start to the latest period end of the shown sites.
  const periodsOf = (e) => e.site.timeline.calendar.periods;
  const t0 = Math.min(...usable.map((e) => periodsOf(e)[0].start_et_s));
  const t1 = Math.max(...usable.map((e) => periodsOf(e)[periodsOf(e).length - 1].end_et_s));
  const x = (t) => LEFT + ((t - t0) / (t1 - t0)) * (WIDTH - LEFT - RIGHT);

  // Rows: the calendar quantities in the order of the first package, then the landing windows.
  const ids = [];
  for (const e of usable) for (const q of e.site.timeline.calendar.quantities) if (!ids.includes(q.id)) ids.push(q.id);
  const label = (id) => { for (const e of usable) { const q = e.site.timeline.calendar.quantities.find((v) => v.id === id); if (q) return q.label; } return id; };

  let y = 4;
  const out = [];
  const hatch = `<defs><pattern id="cal-hatch" width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="6" stroke="#8b949e" stroke-width="2" opacity="0.6"/></pattern></defs>`;
  for (const id of ids) {
    // Display scale of the row: the largest value of this quantity among the shown sites.
    const values = usable.map((e) => {
      const q = e.site.timeline.calendar.quantities.find((v) => v.id === id);
      return q && q.values[e.h] ? q.values[e.h] : null;
    });
    const top = Math.max(1, ...values.flat().filter((v) => Number.isFinite(v)));
    out.push(`<text x="4" y="${y + 12}" class="cal-head">${esc(label(id))}</text>`);
    y += HEAD;
    usable.forEach((e, k) => {
      const row = values[k];
      out.push(`<text x="14" y="${y + 14}" class="cal-site"><title>${esc(e.name)}</title>${esc(shortName(e.name))} · ${esc(e.site.manifest.horizon.observer_heights_m[e.h])} m</text>`);
      periodsOf(e).forEach((p, j) => {
        const v = row ? row[j] : null;
        const x0 = x(p.start_et_s), w = Math.max(1, x(p.end_et_s) - x0);
        const tip = `${e.name}, ${label(id)}, lunar day ${p.index} (${p.start_utc} to ${p.end_utc})${p.complete ? "" : ", incomplete: cut by the end of the computed range, not a full lunar day"}: ${hoursText(v)}`;
        const has = Number.isFinite(v);
        out.push(`<g class="cal-cell" data-et="${p.start_et_s}" tabindex="-1"><title>${esc(tip)}</title>`
          + `<rect x="${x0.toFixed(2)}" y="${y}" width="${w.toFixed(2)}" height="${ROW - 2}" fill="${has ? colourOf(id) : "none"}" fill-opacity="${has ? (0.12 + 0.88 * (v / top)).toFixed(3) : 0}" stroke="#30363d"/>`
          + (p.complete ? "" : `<rect x="${x0.toFixed(2)}" y="${y}" width="${w.toFixed(2)}" height="${ROW - 2}" fill="url(#cal-hatch)" stroke="#8b949e" stroke-dasharray="3 2"/>`)
          + (w > 24 && has ? `<text x="${(x0 + w / 2).toFixed(2)}" y="${y + 13}" class="cal-val${v / top < 0.45 ? " light" : ""}">${fixed(v / 3600, 0)}</text>` : "")
          + `</g>`);
      });
      y += ROW;
    });
    y += GAP;
  }

  // Landing windows of the chosen requirement, per site at its height (package intervals).
  const reqId = requirementId || requirementIds(usable)[0] || null;
  if (reqId) {
    out.push(`<text x="4" y="${y + 12}" class="cal-head">Landing windows: ${esc(reqId)}</text>`);
    y += HEAD;
    usable.forEach((e) => {
      const o = ((e.site.timeline.opportunities) || []).find((r) => r.requirement_id === reqId && r.height_index === e.h);
      out.push(`<text x="14" y="${y + 14}" class="cal-site"><title>${esc(e.name)}</title>${esc(shortName(e.name))} · ${esc(e.site.manifest.horizon.observer_heights_m[e.h])} m</text>`);
      out.push(`<rect x="${LEFT}" y="${y}" width="${WIDTH - LEFT - RIGHT}" height="${ROW - 2}" fill="none" stroke="#30363d"/>`);
      if (!o) out.push(`<text x="${LEFT + 6}" y="${y + 13}" class="cal-site">No record for this requirement at this height.</text>`);
      else {
        o.landing_windows_et_s.forEach(([a, b], j) => {
          const [ua, ub] = o.landing_windows_utc[j] || ["", ""];
          out.push(`<g class="cal-cell" data-et="${a}"><title>${esc(`${e.name}, ${reqId}: landing window ${ua} to ${ub}`)}</title><rect x="${x(a).toFixed(2)}" y="${y + 3}" width="${Math.max(1.5, x(b) - x(a)).toFixed(2)}" height="${ROW - 8}" fill="${COLOURS.window}"/></g>`);
        });
        if (o.planned_landing) out.push(`<path d="M${x(o.planned_landing.et_s).toFixed(2)} ${y - 1} v${ROW}" stroke="#e6edf3" stroke-width="2"><title>${esc(`Planned landing ${o.planned_landing.utc}`)}</title></path>`);
        out.push(`<path d="M${x(o.latest_landing_et_s).toFixed(2)} ${y} v${ROW - 2}" stroke="#8b949e" stroke-dasharray="2 2"><title>${esc(`Latest landing that can be judged: ${o.latest_landing_utc}`)}</title></path>`);
      }
      y += ROW;
    });
    y += GAP;
  }

  // Axis: the period boundaries of the first site, labelled with the package's UTC dates.
  const axisY = y + 2;
  const first = periodsOf(usable[0]);
  out.push(`<line x1="${LEFT}" y1="${axisY}" x2="${WIDTH - RIGHT}" y2="${axisY}" stroke="#8b949e"/>`);
  first.forEach((p, j) => {
    const xp = x(p.start_et_s);
    out.push(`<line x1="${xp.toFixed(2)}" y1="${axisY}" x2="${xp.toFixed(2)}" y2="${axisY + 4}" stroke="#8b949e"/>`);
    if (j % 3 === 0) out.push(`<text x="${xp.toFixed(2)}" y="${axisY + 16}" class="cal-axis">${esc(p.start_utc.slice(0, 10))}</text>`);
  });
  out.push(`<text x="4" y="${axisY + 16}" class="cal-axis">Lunar day starts (UTC)</text>`);
  // Marker of the selected time, moved by setCalendarTime without redrawing the calendar.
  out.push(`<path class="cal-now" d="M0 0" data-bottom="${axisY}" stroke="#e6edf3" stroke-width="1.5" stroke-dasharray="4 3"><title>Selected time</title></path>`);
  const height = axisY + AXIS - 20;
  const svg = `<div class="cal-scroll"><svg class="calendar" data-t0="${t0}" data-t1="${t1}" viewBox="0 0 ${WIDTH} ${height}" width="${WIDTH}" height="${height}" role="img" aria-label="Opportunity calendar: visible time per lunar day for ${esc(usable.map((e) => e.name).join(" and "))}">${hatch}${out.join("")}</svg></div>`;

  return `${missing.join("")}${legendHtml(usable)}${svg}${opportunitiesHtml(usable, reqId)}${tableHtml(usable, ids, label, reqId)}`;
}

// Move the selected-time marker of a drawn calendar (et: ET seconds of the packages).
export function setCalendarTime(root, et) {
  const svg = root.querySelector("svg.calendar"), mark = root.querySelector(".cal-now");
  if (!svg || !mark) return;
  const t0 = Number(svg.dataset.t0), t1 = Number(svg.dataset.t1);
  if (!Number.isFinite(et) || et < t0 || et > t1) { mark.setAttribute("d", "M0 0"); return; }
  const xp = LEFT + ((et - t0) / (t1 - t0)) * (WIDTH - LEFT - RIGHT);
  mark.setAttribute("d", `M${xp.toFixed(2)} 0 V${mark.dataset.bottom}`);
}

function legendHtml(usable) {
  const e = usable[0], c = e.site.timeline.calendar;
  return `<p class="small">${esc(c.definition || "")} <span class="muted">[${esc(e.site.methodStatus(c.method))}]</span></p>
    <p class="small muted">Each cell is one lunar day; the number is the package value in hours, the shade its size relative to the largest value of that row (display only). Hatched, dashed cells are incomplete lunar days, cut by the ends of the computed range: their totals are not totals of a full lunar day. Green bars: landing windows of the chosen requirement; white line: planned landing; dotted line: latest landing that can be judged; dashed vertical line: the selected time. Point at a cell for the exact value; click it to go to the start of that lunar day.</p>`;
}

// Requirement and opportunity summary per site at its height, with the requirement's label.
function opportunitiesHtml(usable, reqId) {
  if (!reqId) return `<p class="small muted">No landing requirement is stated in these packages, so no landing windows or slip tolerance are shown.</p>`;
  const rows = usable.map((e) => {
    const o = (e.site.timeline.opportunities || []).find((r) => r.requirement_id === reqId && r.height_index === e.h);
    const h = esc(e.site.manifest.horizon.observer_heights_m[e.h]);
    if (!o) return `<tr><td>${esc(e.name)} · ${h} m</td><td colspan="7">No record for this requirement at this height.</td></tr>`;
    const p = o.planned_landing;
    let planned = "No planned landing is stated in the scenario, so there is no slip tolerance or wait time.";
    if (p) {
      const later = p.feasible ? `${p.slip_tolerance_is_lower_bound ? "at least " : ""}${hoursText(p.slip_tolerance_s)}` : "—";
      const wait = p.feasible ? "—" : p.wait_s === null || p.wait_s === undefined ? "no window in the computed range" : hoursText(p.wait_s);
      const next = p.next_window_start_utc ? `; next window ${esc(p.next_window_start_utc)} (${hoursText(p.next_window_length_s)})` : "";
      planned = `${esc(p.utc)}: requirement ${p.feasible ? "holds" : "does not hold"}; later by up to ${later}; earlier by up to ${p.feasible ? hoursText(p.early_tolerance_s) : "—"}; wait ${wait}${next}`;
    }
    const clipped = [o.clipped_start ? "the first window starts at the start of the range" : "", o.clipped_end ? "the last window ends at the latest landing that can be judged" : ""].filter(Boolean).join("; ");
    return `<tr><td>${esc(e.name)} · ${h} m</td><td class="num">${fixed(o.feasible_fraction * 100, 1)} %</td><td class="num">${esc(o.window_count)}</td>
      <td class="num">${hoursText(o.longest_window_s)}</td><td class="num">${hoursText(o.median_window_s)}</td><td>${esc(o.latest_landing_utc)}${clipped ? ` (true extent unknown: ${clipped})` : ""}</td>
      <td>${planned}</td><td class="muted">[${esc(e.site.methodStatus(o.method))}]</td></tr>`;
  }).join("");
  const req = requirementsOf(usable[0].site)[reqId];
  const about = req
    ? `<p class="small"><strong>${esc(req.label || reqId)}</strong> (<code>${esc(reqId)}</code>): ${conditionsText(req)}. The requirement is an input of the scenario; the package cannot tell whether it is the right one.</p>`
    : `<p class="small"><code>${esc(reqId)}</code>: the requirement record is not in this package.</p>`;
  return `<h3>Landing opportunities</h3>${about}
    <div class="table"><table><thead><tr><th>Site · height</th><th>Feasible share of the judged range</th><th>Windows</th><th>Longest window</th><th>Median window</th><th>Latest landing that can be judged (UTC)</th><th>Planned landing</th><th>Status</th></tr></thead><tbody>${rows}</tbody></table></div>`;
}

// The full values for reading without the chart: one row per lunar day.
function tableHtml(usable, ids, label, reqId) {
  const cols = [];
  for (const e of usable) {
    for (const id of ids) cols.push({ e, head: `${e.name}: ${label(id)}`, get: (j) => { const q = e.site.timeline.calendar.quantities.find((v) => v.id === id); return q && q.values[e.h] ? q.values[e.h][j] : null; } });
    if (reqId) {
      const o = (e.site.timeline.opportunities || []).find((r) => r.requirement_id === reqId && r.height_index === e.h);
      if (o) cols.push({ e, head: `${e.name}: feasible landing time (${reqId})`, get: (j) => o.feasible_s_per_period[j] });
    }
  }
  const periods = usable[0].site.timeline.calendar.periods;
  const body = periods.map((p, j) => `<tr><td>${esc(p.index)}</td><td>${esc(p.start_utc)}</td><td>${esc(p.end_utc)}</td><td>${p.complete ? "complete" : "incomplete"}</td>${cols.map((c) => `<td class="num">${hoursText(c.get(j))}</td>`).join("")}</tr>`).join("");
  return `<details class="small"><summary>All values per lunar day (hours)</summary><div class="table"><table><thead><tr><th>Lunar day</th><th>Start (UTC)</th><th>End (UTC)</th><th>Period</th>${cols.map((c) => `<th>${esc(c.head)}</th>`).join("")}</tr></thead><tbody>${body}</tbody></table></div></details>`;
}
