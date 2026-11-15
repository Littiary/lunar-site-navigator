// Status cards of a comparison pane: is the Sun visible, is the Earth visible, would a landing
// meet the stated requirement, at the selected time and observer height.
//
// Every answer is a lookup in the package: the windows sun_visible and earth_visible, the rise and
// set events, the landing windows of timeline.opportunities. The only arithmetic is the time
// between the selected instant and a published instant ("in 3 d 4 h"), a date difference for
// reading. The package's own countdown metrics are counted from their `reference` instant, not
// from the selected time; they are shown separately (countdownHtml), labelled with that instant.
// No trigonometry, no new event.

import { containing, esc, eventsAtHeight, windowsAtHeight } from "./panel.js";

// A time span for reading: "3 d 4 h", "5 h 12 min", "12 min", "under 1 min".
export function durationText(seconds) {
  if (!Number.isFinite(seconds)) return "—";
  const m = Math.floor(seconds / 60), h = Math.floor(m / 60), d = Math.floor(h / 24);
  if (d > 0) return `${d} d ${h % 24} h`;
  if (h > 0) return `${h} h ${m % 60} min`;
  return m > 0 ? `${m} min` : "under 1 min";
}

const NAME = { SUN: "Sun", EARTH: "Earth" };

function bodyCard(site, h, et, body) {
  const id = `${body.toLowerCase()}_visible`;
  const w = windowsAtHeight(site, h).find((x) => x.id === id);
  if (!w) return `<div class="status-card unknown"><div class="status-title">${NAME[body]}</div><div class="status-big">Not in this package</div></div>`;
  const visible = containing(w.intervals_et_s, et) >= 0;
  const next = eventsAtHeight(site, h).find((e) => e.body === body && e.et_s > et);
  const end = site.timeline.time.end_utc;
  const change = next
    ? `${next.type === "set" ? "Sets" : next.type === "rise" ? "Rises" : esc(next.type)} in <strong>${durationText(next.et_s - et)}</strong>
       <span class="status-when">${esc(next.utc.slice(0, 16).replace("T", " "))} UTC</span>`
    : `No ${visible ? "set" : "rise"} before the end of the computed range (${esc(end.slice(0, 10))})`;
  return `<div class="status-card ${visible ? "yes" : "no"}" title="Window ${esc(id)} at the selected time; next ${NAME[body]} event of the package at this height">
    <div class="status-title">${NAME[body]}</div>
    <div class="status-big">${visible ? "Visible now" : "Not visible now"}</div>
    <div class="status-next">${change}</div></div>`;
}

// Is a requirement an example of the team rather than a mission's criterion? (SPEC 5.6: the
// shipped presets are labelled "EXAMPLE … not a NASA requirement".)
function isExample(req, id) {
  return /^example/i.test(id) || /\bexample\b/i.test((req && req.label) || "");
}

function landingCard(site, h, et, requirementId) {
  const t = site.timeline;
  const opps = (t.opportunities || []).filter((o) => o.height_index === h);
  if (!opps.length) {
    return `<div class="status-card unknown"><div class="status-title">Landing conditions</div><div class="status-big">Not specified</div>
      <div class="status-next">The package states no landing requirement.</div></div>`;
  }
  const o = opps.find((x) => x.requirement_id === requirementId) || opps[0];
  const req = (((site.manifest.request || {}).timeline || {}).requirements || []).find((r) => r.id === o.requirement_id);
  const tag = isExample(req, o.requirement_id) ? '<span class="status-tag">Example requirement, not a mission criterion</span>' : "";
  const foot = `<div class="status-foot">${tag} <span title="${esc((req && req.label) || o.requirement_id)}">${esc(o.requirement_id)}</span></div>`;
  if (et > o.latest_landing_et_s) {
    return `<div class="status-card unknown"><div class="status-title">Landing conditions</div><div class="status-big">Cannot be judged</div>
      <div class="status-next">After the latest landing that can be judged (${esc(o.latest_landing_utc.slice(0, 10))}).</div>${foot}</div>`;
  }
  const k = containing(o.landing_windows_et_s, et);
  if (k >= 0) {
    const close = o.landing_windows_et_s[k][1];
    const cut = k === o.landing_windows_et_s.length - 1 && o.clipped_end ? " (or later: the window reaches the end of what can be judged)" : "";
    return `<div class="status-card yes"><div class="status-title">Landing conditions</div><div class="status-big">Satisfied</div>
      <div class="status-next">A landing now meets the requirement; the window closes in <strong>${durationText(close - et)}</strong>${cut}.</div>${foot}</div>`;
  }
  const next = o.landing_windows_et_s.find(([a]) => a > et);
  return `<div class="status-card no"><div class="status-title">Landing conditions</div><div class="status-big">Not satisfied</div>
    <div class="status-next">${next ? `The next landing window opens in <strong>${durationText(next[0] - et)}</strong>.` : "No landing window after this time in the computed range."}</div>${foot}</div>`;
}

// The three cards of one pane at time et (ET seconds of the package) and observer height h.
export function statusCardsHtml(site, h, et, requirementId) {
  if (!site || !site.timeline) return '<p class="note small">This package has no time window, so no status at a time.</p>';
  return `<div class="status-cards" role="group" aria-label="Status at the selected time">${bodyCard(site, h, et, "SUN")}${bodyCard(site, h, et, "EARTH")}${landingCard(site, h, et, requirementId)}</div>
    <p class="status-caption">At the selected time and observer height, from the package's visibility windows, rise and set events and landing windows; "in …" is counted from the selected time.</p>`;
}

// The package's countdown metrics (SPEC 5.4), counted from their own reference instant. Since
// contract 0.10 each carries `reference`; before, the instant is the planned landing if it lies in
// the time window, else the start of the window (the documented rule).
export function countdownHtml(site, h) {
  const t = site.timeline;
  if (!t || !t.metrics) return "";
  const ids = ["sun_visible_at_reference", "sun_time_to_set_s", "sun_time_to_rise_s", "earth_visible_at_reference", "earth_time_to_set_s", "earth_time_to_rise_s"];
  const at = Object.fromEntries(t.metrics.filter((m) => m.height_index === h).map((m) => [m.id, m]));
  const rows = ids.filter((id) => at[id]).map((id) => {
    const m = at[id];
    const lower = at[id.replace(/_s$/, "_is_lower_bound")];
    const value = m.unit === "s" ? `${lower && lower.value === 1 ? "at least " : ""}${durationText(m.value)}` : m.value === 1 ? "yes" : "no";
    return `<tr><td>${esc(m.label)}</td><td class="num">${value}</td><td><code>${esc(id)}</code></td></tr>`;
  });
  if (!rows.length) return "";
  const any = at[ids.find((id) => at[id])];
  let ref;
  if (any.reference) ref = `${esc(any.reference.utc)} (${esc(any.reference.is)})`;
  else {
    const landing = ((site.manifest.request || {}).timeline || {}).landing_utc;
    const inRange = landing && landing >= t.time.start_utc && landing <= t.time.end_utc;
    ref = `${esc(inRange ? landing : t.time.start_utc)} (${inRange ? "planned landing" : "start of the time window"}; rule of SPEC 5.4 for packages before contract 0.10)`;
  }
  return `<h3>Package countdown</h3><p class="small">Counted from ${ref}, <strong>not from the selected time</strong> <span class="muted">[${esc(site.methodStatus(any.method))}]</span>.</p>
    <div class="table"><table><thead><tr><th>Quantity</th><th>Value</th><th>Metric</th></tr></thead><tbody>${rows.join("")}</tbody></table></div>`;
}
