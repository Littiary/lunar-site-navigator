import { useEffect } from "react";
import { at } from "../lib";

// The two-site comparison. This component only lays out the page: the panes, the shared time
// bar, the calendar and the pair table are filled by the comparison module of the classic page,
// web/viewer/js/compare.js, loaded at run time from the published viewer/ folder. It loads the
// packages (SHA-256 checked), draws the status cards, horizon charts, sky panorama, ground view
// and calendar, exactly as on classic.html, so every number is the one the classic page shows.
// The ids and data-role attributes below are the ones that module looks up; the markup around
// them is free.

// The pane template of web/viewer/compare.html, unchanged.
const PANE_TEMPLATE = `
  <div class="pane-head">
    <label>Site <select data-role="site"><option>loading…</option></select></label>
    <label>Observer height <select data-role="height"></select></label>
  </div>
  <p class="pane-time mono" data-role="time"></p>
  <div data-role="cards"><div class="status-cards skeleton" aria-hidden="true"><div class="status-card"></div><div class="status-card"></div><div class="status-card"></div></div></div>
  <p class="small" data-role="terrain"></p>
  <p class="note small" data-role="note" hidden></p>
  <p class="loading-status small" data-role="loading" role="status" aria-live="polite">Waiting for the list of sites…</p>
  <div class="chips" data-role="chips"></div>
  <div class="chart" data-role="chart"><svg data-role="horizon" role="img" aria-label="Terrain horizon with the Sun and the Earth"></svg></div>
  <div class="sky" data-role="sky" hidden></div>
  <div class="view3d pane-ground" data-role="ground" hidden></div>
  <p class="small note-band" data-role="band" hidden></p>
  <p class="small" data-role="ground-link" hidden></p>
  <details class="details" data-role="details">
    <summary>Details: values at this time, whole-period metrics, events with terrain quality, package and methods</summary>
    <h2>At this time</h2>
    <div class="table"><table data-role="readout"></table></div>
    <h2>Over the whole time window</h2>
    <div class="table"><table data-role="summary"></table></div>
    <h2>Next events</h2>
    <div class="table"><table data-role="events"></table></div>
    <div data-role="countdown"></div>
    <p class="muted small" data-role="footer"></p>
  </details>
`;

let started = false;

export function Compare() {
  useEffect(() => {
    if (started) return; // the module runs once per page load (React may run effects twice in development)
    started = true;
    const url = at("viewer/js/compare.js");
    import(/* @vite-ignore */ url).catch((e: unknown) => {
      const box = document.getElementById("error");
      if (box) {
        box.textContent = `The comparison module could not be loaded (${url}): ${e instanceof Error ? e.message : String(e)}`;
        box.hidden = false;
      }
    });
  }, []);

  return (
    <main className="cmp">
      <header className="cmp-head wrap-wide">
        <div className="cmp-title">
          <p className="eyebrow sun">Compare two sites</p>
          <h1>Two landing sites, one clock.</h1>
          <p className="lead-l">
            Pick any two published sites. Both panes follow one shared time: is the Sun up, is the Earth in view, would a
            landing now meet the stated requirement, and when does that change. Every value is read from the site packages
            and checked by SHA-256 before it is shown.
          </p>
        </div>
        <div className="cmp-aside">
          <p className="vnote" id="validation-note" role="note"></p>
          <p className="small links">
            <a href={at("viewer/index.html")} id="viewer-link">Single-site viewer</a>
            <a href={at("learn.html")}>How to read it</a>
            <a href={at("accuracy.html")}>Accuracy and limits</a>
            <a href={at("classic.html")}>Classic page</a>
          </p>
        </div>
        <div id="notice" className="banner" hidden></div>
        <div id="error" className="banner" hidden></div>
        <p className="loading-status small" id="load-status" role="status" aria-live="polite">Loading the list of sites…</p>
      </header>

      <section className="timebar" aria-label="Shared time">
        <div className="wrap-wide">
          <div className="time-row tb-main">
            <button type="button" id="play" aria-pressed="false">Play</button>
            <output id="utc" className="mono"></output>
            <div className="tb-steps">
              <button type="button" data-step="-24" title="One day earlier">−1 d</button>
              <button type="button" data-step="-1" title="One sample earlier">−1 h</button>
              <input id="slider" type="range" min="0" defaultValue="0" step="1" aria-label="Time sample" />
              <button type="button" data-step="1" title="One sample later">+1 h</button>
              <button type="button" data-step="24" title="One day later">+1 d</button>
            </div>
          </div>
          <div className="time-row tb-views" role="group" aria-label="Pane view">
            <span className="tb-label">View</span>
            <div className="segmented">
              <button type="button" id="view-chart" aria-pressed="true">Horizon chart</button>
              <button type="button" id="view-sky" aria-pressed="false">Sky panorama</button>
              <button type="button" id="view-ground" aria-pressed="false">Ground view</button>
              <button type="button" id="view-calendar" aria-pressed="false">Calendar</button>
            </div>
          </div>
          <details className="more-controls" id="more-controls" open>
            <summary>More controls: speed, date, landing requirement, sky paths, export</summary>
            <div className="time-row">
              <label>Speed
                <select id="speed" defaultValue="6">
                  <option value="1">1 hour per step</option>
                  <option value="6">6 hours per step</option>
                  <option value="24">1 day per step</option>
                  <option value="168">1 week per step</option>
                </select>
              </label>
              <label>Date (UTC) <input id="date" type="datetime-local" step="3600" /></label>
              <label>Landing requirement <select id="cal-req"><option value="">loading…</option></select></label>
              <label id="span-label" hidden>Paths for <select id="sky-span" defaultValue="168">
                <option value="24">±1 day</option>
                <option value="168">±7 days</option>
                <option value="360">±15 days</option>
                <option value="720">±30 days</option>
                <option value="all">the whole time window</option>
              </select></label>
              <button type="button" id="export-csv" disabled>Export CSV</button>
            </div>
          </details>
        </div>
      </section>

      <div className="wrap-wide">
        <section id="calendar-section" className="cal-card" aria-label="Opportunity calendar of both sites" hidden>
          <h2>Opportunity calendar</h2>
          <div id="calendar"></div>
          <p className="muted small">Both sites on one time axis, each at the observer height selected in its pane: lunar days of <code>timeline.calendar</code> and landing opportunities of <code>timeline.opportunities</code> for the requirement chosen above, as the packages give them; nothing is recomputed in the browser.</p>
        </section>
        <div className="split">
          <section className="pane" id="pane-a" aria-label="Site A"></section>
          <section className="pane" id="pane-b" aria-label="Site B"></section>
        </div>
        <section id="pair-results" className="pair-card" aria-label="Published site pair metrics"></section>
      </div>
      <template id="pane-template" dangerouslySetInnerHTML={{ __html: PANE_TEMPLATE }} />
    </main>
  );
}
