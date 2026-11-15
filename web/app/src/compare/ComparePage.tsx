import { paneTemplate } from "virtual:lsn-classic";
import { LINKS } from "../site/links";
import { TimeBar } from "./TimeBar";
import { useClassicCompare } from "./useClassicCompare";

// The two-site comparison: a layout around the elements of the classic page. The panes, the
// time bar, the calendar and the pair table are filled by viewer/js/compare.js (see
// useClassicCompare), so every number is the one classic.html shows for the same address.
// This component has no state and renders once; after that the module owns the contents of
// the elements below.

const HEAD_LINKS = [
  { ...LINKS.viewer, id: "viewer-link" }, // compare.js points this link at site A, its height and time
  { ...LINKS.learn },
  { ...LINKS.accuracy },
  { ...LINKS.classic, label: "Classic page" },
];

export function ComparePage() {
  useClassicCompare();
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
            {HEAD_LINKS.map(({ href, label, ...rest }) => <a key={href} href={href} {...rest}>{label}</a>)}
          </p>
        </div>
        <div id="notice" className="banner" hidden></div>
        <div id="error" className="banner" hidden></div>
        <p className="loading-status small" id="load-status" role="status" aria-live="polite">Loading the list of sites…</p>
      </header>

      <TimeBar />

      <div className="wrap-wide">
        <section id="calendar-section" className="cal-card" aria-label="Opportunity calendar of both sites" hidden>
          <h2>Opportunity calendar</h2>
          <div id="calendar"></div>
          <p className="muted small">
            Both sites on one time axis, each at the observer height selected in its pane: lunar days of{" "}
            <code>timeline.calendar</code> and landing opportunities of <code>timeline.opportunities</code> for the
            requirement chosen above, as the packages give them; nothing is recomputed in the browser.
          </p>
        </section>
        <div className="split">
          <section className="pane" id="pane-a" aria-label="Site A"></section>
          <section className="pane" id="pane-b" aria-label="Site B"></section>
        </div>
        <section id="pair-results" className="pair-card" aria-label="Published site pair metrics"></section>
      </div>
      {/* Setting innerHTML of a <template> fills its content fragment, which compare.js clones per pane. */}
      <template id="pane-template" dangerouslySetInnerHTML={{ __html: paneTemplate }} />
    </main>
  );
}
