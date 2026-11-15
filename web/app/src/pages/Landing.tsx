import facts from "../facts";
import hero from "../../../viewer/img/hero.jpg";
import stillTwoSites from "../assets/b_product_two_sites.jpg";
import stillRidge from "../assets/c_key_moment_near_ridge.jpg";
import stillLander from "../assets/e_lander_lit_side.jpg";
import { at, GITHUB, repoFile, SLIDES } from "../lib";

const hours = (s: number) => Math.round(s / 3600);
const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)} %`;
const OP: Record<string, string> = { ">=": "≥", "<=": "≤", ">": ">", "<": "<" };

function value(v: { value: number; unit: string }, digits = 1) {
  return v.unit === "share of points" ? pct(v.value, digits) : `${v.value} ${v.unit}`;
}

export function Landing() {
  return (
    <main className="landing">
      <Hero />
      <Figures />
      <Stills />
      <HowItWorks />
      <Sites />
      <Trust />
      <ReadMore />
      <Team />
    </main>
  );
}

function Hero() {
  return (
    <section className="hero-l" style={{ backgroundImage: `url(${hero})` }}>
      <div className="hero-shade" />
      <div className="wrap hero-in">
        <p className="eyebrow sun">Lunar south pole · landing site and date planner</p>
        <h1>Where the Sun reaches a lunar landing site, and when.</h1>
        <p className="lead-l">
          Compare two lunar landing sites hour by hour over two years: when the Sun lights them, when the Earth is in
          view for radio contact, and when a landing would meet a stated requirement.
        </p>
        <div className="ctas">
          <a className="btn btn-sun" href={at("compare/")}>Compare two sites <span aria-hidden="true">→</span></a>
          <a className="btn btn-ghost" href={SLIDES}>Download the slides (PDF)</a>
          <a className="btn btn-ghost" href={GITHUB}>Code on GitHub</a>
        </div>
        <ul className="hero-tags" aria-label="What the results rest on">
          <li><strong>NASA LOLA</strong> terrain</li>
          <li><strong>SPICE</strong> Sun and Earth directions</li>
          <li><strong>{facts.sites.length}</strong> published sites</li>
          <li><strong>{facts.card.passed} of {facts.card.checks}</strong> validation checks pass</li>
        </ul>
      </div>
    </section>
  );
}

function Figures() {
  const r = facts.ridge;
  if (!r) return null;
  const years = "two years";
  return (
    <section className="section wrap" aria-labelledby="figures-h">
      <p className="eyebrow">One site, three numbers</p>
      <h2 id="figures-h">At the Shackleton crater rim, one ridge costs hundreds of hours of sunlight.</h2>
      <div className="figures">
        <article className="figure">
          <div className="fig-num">{Math.round(r.peak_distance_m)}<span> m</span></div>
          <div className="fig-label">away: the ridge that costs the most sunlight for a sensor {r.observer_height_m} m above the ground</div>
        </article>
        <article className="figure sun">
          <div className="fig-num">{hours(r.lost_s)}<span> h</span></div>
          <div className="fig-label">of sunlight it costs in {years}: {pct(r.share_of_lost)} of everything the site loses to terrain</div>
        </article>
        <article className="figure earth">
          <div className="fig-num">74<span> h</span> <span className="arrow">→</span> 1.8<span> h</span></div>
          <div className="fig-label">spread of the Sun's rise time at this site once the 5 m site model replaces the 20 m product</div>
        </article>
      </div>
      <p className="source">
        First two figures: site package <code>{r.package_id}</code> ({r.site_name}, observer {r.observer_height_m} m,{" "}
        {r.window_start_utc.slice(0, 10)} to {r.window_end_utc.slice(0, 10)}), its largest Sun blocker in <code>timeline.blockers</code>
        {r.near_field ? "; the package flags this ridge as within 1 km, where single pixels of the elevation model matter" : ""}.
        Third figure: the method note on the near field, <a href={repoFile("docs/method/near_field.md")}>docs/method/near_field.md</a> (section 4, Shackleton rim record, 74.1 h on the 20 m product, 1.8 h with the 5 m near field).
      </p>
    </section>
  );
}

function Stills() {
  const items: [string, string, string][] = [
    [stillTwoSites, "Two sites side by side", "Shackleton and de Gerlache crater rim crests at one instant, observer 2 m, each view lit by its own Sun."],
    [stillRidge, "The ridge that hides the Sun", "Shackleton rim crest, looking at the Sun's azimuth: the Sun is behind the ridge 673 m away, with its cost in hours."],
    [stillLander, "A lander on the sunlit side", "Shackleton rim crest in the Unreal Engine scene. Lander, mast and boulders are scale objects of the team's own design, not part of the package."],
  ];
  return (
    <section className="section stills-sec" aria-labelledby="stills-h">
      <div className="wrap">
        <p className="eyebrow">Rendered from the packages</p>
        <h2 id="stills-h">The same results in a real-time 3-D scene.</h2>
      </div>
      <div className="stills wrap">
        {items.map(([src, title, text]) => (
          <figure key={title} className="still">
            <img src={src} alt={`${title}. ${text}`} loading="lazy" decoding="async" width="1920" height="1080" />
            <figcaption><strong>{title}.</strong> {text}</figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

function HowItWorks() {
  const steps: [string, string, string, string][] = [
    ["data", "Data", "Terrain and ephemeris", "NASA LOLA elevation models (5 m site models, 20 m and 60 m polar products, SLDEM2015 elsewhere) and SPICE with the DE440 ephemeris."],
    ["core", "Science core", "Python, core/", "Traces the 360° terrain horizon out to 300 km and the Sun and Earth directions; finds visibility windows, rise and set events, blockers and landing windows."],
    ["pkg", "Packages", `Contract ${facts.contract}`, `Versioned result packages for ${facts.sites.length} sites, every array with its SHA-256, described by a public contract.`],
    ["view", "Web and Unreal", "Read only", "This site checks the SHA-256 of every array before it uses it; the Unreal Engine scene reads the same packages. Neither computes a science result."],
  ];
  return (
    <section className="section wrap" id="how" aria-labelledby="how-h">
      <p className="eyebrow">How it works</p>
      <h2 id="how-h">One science core. Every viewer only reads its packages.</h2>
      <ol className="flow">
        {steps.map(([key, title, sub, text], n) => (
          <li key={key} className={`flow-step ${key}`}>
            <div className="flow-n">{n + 1}</div>
            <h3>{title}</h3>
            <p className="flow-sub">{sub}</p>
            <p>{text}</p>
          </li>
        ))}
      </ol>
      <p className="source">Contract: <a href={repoFile("docs/contract/SPEC.md")}>docs/contract/SPEC.md</a> · method notes: <a href={`${GITHUB}/tree/main/docs/method`}>docs/method/</a></p>
    </section>
  );
}

function Sites() {
  const groups = new Map<string, typeof facts.sites>();
  for (const s of facts.sites) {
    const key = s.category || "other";
    groups.set(key, [...(groups.get(key) || []), s]);
  }
  return (
    <section className="section wrap" aria-labelledby="sites-h">
      <p className="eyebrow">{facts.sites.length} published sites</p>
      <h2 id="sites-h">From Apollo 11 to the south-polar rims.</h2>
      <p className="muted">Each one opens in the comparison as site A.</p>
      <div className="site-groups">
        {[...groups.entries()].map(([category, sites]) => (
          <div key={category} className="site-group">
            <h3>{category}</h3>
            <div className="site-chips">
              {sites.map((s) => (
                <a key={s.site_id} className="site-chip" href={at(`compare/?a=${encodeURIComponent(s.site_id)}`)} title={`${s.name}: ${s.lat_deg.toFixed(2)}°, ${s.lon_deg.toFixed(2)}°`}>
                  {s.name.replace(/\s*\(.*\)\s*$/, "")}
                  <span className="lat">{s.lat_deg.toFixed(1)}°</span>
                </a>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Trust() {
  const c = facts.card;
  const groups = new Map<string, typeof c.rows>();
  for (const row of c.rows) groups.set(row.group, [...(groups.get(row.group) || []), row]);
  const ring = 2 * Math.PI * 52;
  return (
    <section className="section trust-sec" id="trust" aria-labelledby="trust-h">
      <div className="wrap">
        <p className="eyebrow">Why the numbers can be trusted</p>
        <h2 id="trust-h">For every comparison with an outside source, the pass criterion was committed first.</h2>
        <div className="trust">
          <div className="trust-score">
            <svg viewBox="0 0 120 120" role="img" aria-label={`${c.passed} of ${c.checks} checks pass, ${c.failed} fails`}>
              <circle cx="60" cy="60" r="52" className="ring-bg" />
              <circle cx="60" cy="60" r="52" className="ring-pass" strokeDasharray={`${(ring * c.passed) / c.checks} ${ring}`} />
              <circle cx="60" cy="60" r="52" className="ring-fail" strokeDasharray={`${(ring * c.failed) / c.checks} ${ring}`} strokeDashoffset={-(ring * c.passed) / c.checks} />
            </svg>
            <div className="score-text"><strong>{c.passed}</strong><span>of {c.checks} pass</span></div>
            <p className="muted small">{c.failed} fails and stays on the card.</p>
          </div>
          <div className="trust-groups">
            {[...groups.entries()].map(([group, rows]) => (
              <div key={group} className="tg">
                <div className="tg-head"><span>{group}</span><span className="muted">{rows.filter((r) => r.status === "PASS").length}/{rows.length}</span></div>
                <div className="tg-dots">
                  {rows.map((r) => <span key={r.id} className={`dot ${r.status === "PASS" ? "pass" : "fail"}`} title={`${r.status}: ${r.quantity}`} />)}
                </div>
              </div>
            ))}
          </div>
        </div>
        {c.failedRows.map((f) => (
          <article key={f.id} className="failed-row" aria-label={`Failed check ${f.id}`}>
            <div className="fr-badge">FAIL</div>
            <div className="fr-body">
              <h3>{f.quantity}</h3>
              <dl>
                <div><dt>Checked against</dt><dd>{f.compared_against}</dd></div>
                <div><dt>Cases</dt><dd>{f.cases}</dd></div>
                <div><dt>Required</dt><dd>{OP[f.threshold.comparison] || f.threshold.comparison} {value(f.threshold, 0)}</dd></div>
                <div><dt>Measured</dt><dd className="fail-text">{value(f.measured)}</dd></div>
              </dl>
              <p className="fr-limit">{f.limit}</p>
              <p className="source">Check <code>{f.id}</code> · {f.evidence}</p>
            </div>
          </article>
        ))}
        <p className="source">
          From the validation card <a href={repoFile("validation/card/validation_card.md")}>validation/card/validation_card.md</a>{" "}
          ({c.title.replace(/^Validation card:\s*/, "")}, {c.generated_utc}). The limits of every result are on{" "}
          <a href={at("accuracy.html")}>Accuracy and limits</a>.
        </p>
      </div>
    </section>
  );
}

function ReadMore() {
  const cards: [string, string, string][] = [
    [at("learn.html"), "How to read it", "The education page: how to read the charts, the status cards and the calendar."],
    [at("accuracy.html"), "Accuracy and limits", "What each result rests on, the validation card, and what was not validated."],
    [at("evidence.html"), "Evidence", "The horizon panorama and window strip of every site, as static charts."],
    [at("viewer/index.html"), "Single-site viewer", "One site in depth: Moon globe, sky panorama, ground view with all its controls."],
  ];
  return (
    <section className="section wrap" aria-labelledby="more-h">
      <p className="eyebrow">Go deeper</p>
      <h2 id="more-h">Read the method, the limits and the evidence.</h2>
      <div className="cards">
        {cards.map(([href, title, text]) => (
          <a key={href} className="card" href={href}>
            <h3>{title} <span aria-hidden="true">→</span></h3>
            <p>{text}</p>
          </a>
        ))}
      </div>
    </section>
  );
}

function Team() {
  return (
    <section className="section wrap team" aria-labelledby="team-h">
      <div>
        <p className="eyebrow">NASA Space Apps Challenge 2026 · Aachen</p>
        <h2 id="team-h">Kestro Aerospace</h2>
        <p className="muted">Challenge: <em>Lunar Landing Site Navigator</em>.</p>
      </div>
      <ul className="people">
        <li><span className="avatar" aria-hidden="true">KE</span>Kaan Eşrefoğlu</li>
        <li><span className="avatar" aria-hidden="true">BK</span>Barkın Kocatepe</li>
      </ul>
      <div className="ctas">
        <a className="btn btn-sun" href={at("compare/")}>Compare two sites <span aria-hidden="true">→</span></a>
        <a className="btn btn-ghost" href={SLIDES}>Download the slides (PDF)</a>
      </div>
    </section>
  );
}
