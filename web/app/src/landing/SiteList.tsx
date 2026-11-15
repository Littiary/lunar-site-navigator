import { SectionHead } from "../components/Actions";
import facts, { type Site } from "../site/facts";
import { shortName } from "../site/format";
import { at } from "../site/links";

function byCategory(sites: Site[]): [string, Site[]][] {
  const groups = new Map<string, Site[]>();
  for (const site of sites) {
    const key = site.category || "other";
    groups.set(key, [...(groups.get(key) ?? []), site]);
  }
  return [...groups.entries()];
}

/** The published sites by category; each opens the comparison with it as site A. */
export function SiteList() {
  return (
    <section className="section wrap" aria-labelledby="sites-h">
      <SectionHead id="sites-h" eyebrow={`${facts.sites.length} published sites`} title="From Apollo 11 to the south-polar rims." />
      <p className="muted">Each one opens in the comparison as site A.</p>
      <div className="site-groups">
        {byCategory(facts.sites).map(([category, sites]) => (
          <div key={category} className="site-group">
            <h3>{category}</h3>
            <div className="site-chips">
              {sites.map((s) => (
                <a key={s.site_id} className="site-chip" href={at(`compare/?a=${encodeURIComponent(s.site_id)}`)}
                  title={`${s.name}: ${s.lat_deg.toFixed(2)}°, ${s.lon_deg.toFixed(2)}°`}>
                  {shortName(s.name)}
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
