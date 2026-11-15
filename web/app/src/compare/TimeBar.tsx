// The shared time bar. Every id below is one viewer/js/compare.js looks up (Play, the UTC
// readout, the steps, the slider, the views, speed, date, requirement, sky paths, CSV export);
// the module wires them, React only lays them out.

const STEPS = [
  { step: "-24", label: "−1 d", title: "One day earlier" },
  { step: "-1", label: "−1 h", title: "One sample earlier" },
  { step: "1", label: "+1 h", title: "One sample later" },
  { step: "24", label: "+1 d", title: "One day later" },
];

const VIEWS = [
  { id: "view-chart", label: "Horizon chart", pressed: true },
  { id: "view-sky", label: "Sky panorama", pressed: false },
  { id: "view-ground", label: "Ground view", pressed: false },
  { id: "view-calendar", label: "Calendar", pressed: false },
];

const StepButton = ({ step, label, title }: (typeof STEPS)[number]) => (
  <button type="button" data-step={step} title={title}>{label}</button>
);

export function TimeBar() {
  return (
    <section className="timebar" aria-label="Shared time">
      <div className="wrap-wide">
        <div className="time-row tb-main">
          <button type="button" id="play" aria-pressed="false">Play</button>
          <output id="utc" className="mono"></output>
          <div className="tb-steps">
            {STEPS.slice(0, 2).map((s) => <StepButton key={s.step} {...s} />)}
            <input id="slider" type="range" min="0" defaultValue="0" step="1" aria-label="Time sample" />
            {STEPS.slice(2).map((s) => <StepButton key={s.step} {...s} />)}
          </div>
        </div>
        <div className="time-row tb-views" role="group" aria-label="Pane view">
          <span className="tb-label">View</span>
          <div className="segmented">
            {VIEWS.map(({ id, label, pressed }) => (
              <button key={id} type="button" id={id} aria-pressed={pressed}>{label}</button>
            ))}
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
            <label id="span-label" hidden>Paths for{" "}
              <select id="sky-span" defaultValue="168">
                <option value="24">±1 day</option>
                <option value="168">±7 days</option>
                <option value="360">±15 days</option>
                <option value="720">±30 days</option>
                <option value="all">the whole time window</option>
              </select>
            </label>
            <button type="button" id="export-csv" disabled>Export CSV</button>
          </div>
        </details>
      </div>
    </section>
  );
}
