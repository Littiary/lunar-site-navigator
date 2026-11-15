import { SectionHead } from "../components/Actions";
import facts from "../site/facts";
import { GITHUB, LINKS } from "../site/links";

const STEPS = [
  { key: "data", title: "Data", sub: "Terrain and ephemeris",
    text: "NASA LOLA elevation models (5 m site models, 20 m and 60 m polar products, SLDEM2015 elsewhere) and SPICE with the DE440 ephemeris." },
  { key: "core", title: "Science core", sub: "Python, core/",
    text: "Traces the 360° terrain horizon out to 300 km and the Sun and Earth directions; finds visibility windows, rise and set events, blockers and landing windows." },
  { key: "pkg", title: "Packages", sub: `Contract ${facts.contract}`,
    text: `Versioned result packages for ${facts.sites.length} sites, every array with its SHA-256, described by a public contract.` },
  { key: "view", title: "Web and Unreal", sub: "Read only",
    text: "This site checks the SHA-256 of every array before it uses it; the Unreal Engine scene reads the same packages. Neither computes a science result." },
];

export function HowItWorks() {
  return (
    <section className="section wrap" id="how" aria-labelledby="how-h">
      <SectionHead id="how-h" eyebrow="How it works" title="One science core. Every viewer only reads its packages." />
      <ol className="flow">
        {STEPS.map(({ key, title, sub, text }, n) => (
          <li key={key} className={`flow-step ${key}`}>
            <div className="flow-n">{n + 1}</div>
            <h3>{title}</h3>
            <p className="flow-sub">{sub}</p>
            <p>{text}</p>
          </li>
        ))}
      </ol>
      <p className="source">
        Contract: <a href={LINKS.contract.href}>docs/contract/SPEC.md</a> · method notes:{" "}
        <a href={`${GITHUB}/tree/main/docs/method`}>docs/method/</a>
      </p>
    </section>
  );
}
