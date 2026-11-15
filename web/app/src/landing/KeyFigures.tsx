import type { ReactNode } from "react";
import { SectionHead } from "../components/Actions";
import facts from "../site/facts";
import { percent, wholeHours } from "../site/format";
import { repoFile } from "../site/links";

function Figure({ tone, value, children }: { tone?: "sun" | "band"; value: ReactNode; children: ReactNode }) {
  return (
    <article className={`figure ${tone ?? ""}`}>
      <div className="fig-num">{value}</div>
      <div className="fig-label">{children}</div>
    </article>
  );
}

const Unit = ({ children }: { children: string }) => <span> {children}</span>;

/** Three figures of the Shackleton rim: the first two from its package, the third from the method note. */
export function KeyFigures() {
  const r = facts.ridge;
  if (!r) return null;
  return (
    <section className="section wrap" aria-labelledby="figures-h">
      <SectionHead id="figures-h" eyebrow="One site, three numbers"
        title="At the Shackleton crater rim, one ridge costs hundreds of hours of sunlight." />
      <div className="figures">
        <Figure value={<>{Math.round(r.peak_distance_m)}<Unit>m</Unit></>}>
          away: the ridge that costs the most sunlight for a sensor {r.observer_height_m} m above the ground
        </Figure>
        <Figure tone="sun" value={<>{wholeHours(r.lost_s)}<Unit>h</Unit></>}>
          of sunlight it costs in two years: {percent(r.share_of_lost)} of everything the site loses to terrain
        </Figure>
        <Figure tone="band" value={<>74<Unit>h</Unit> <span className="arrow">→</span> 1.8<Unit>h</Unit></>}>
          spread of the Sun's rise time at this site once the 5 m site model replaces the 20 m product
        </Figure>
      </div>
      <p className="source">
        First two figures: site package <code>{r.package_id}</code> ({r.site_name}, observer {r.observer_height_m} m,{" "}
        {r.window_start_utc.slice(0, 10)} to {r.window_end_utc.slice(0, 10)}), its largest Sun blocker in{" "}
        <code>timeline.blockers</code>
        {r.near_field ? "; the package flags this ridge as within 1 km, where single pixels of the elevation model matter" : ""}.
        Third figure: the method note on the near field,{" "}
        <a href={repoFile("docs/method/near_field.md")}>docs/method/near_field.md</a> (section 4, Shackleton rim record,
        74.1 h on the 20 m product, 1.8 h with the 5 m near field).
      </p>
    </section>
  );
}
