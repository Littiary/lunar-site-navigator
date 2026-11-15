import { Actions, SectionHead } from "../components/Actions";
import { LINKS } from "../site/links";

const READ_MORE = [
  { link: LINKS.learn, text: "The education page: how to read the charts, the status cards and the calendar." },
  { link: LINKS.accuracy, text: "What each result rests on, the validation card, and what was not validated." },
  { link: LINKS.evidence, text: "The horizon panorama and window strip of every site, as static charts." },
  { link: LINKS.viewer, text: "One site in depth: Moon globe, sky panorama, ground view with all its controls." },
];

export function ReadMore() {
  return (
    <section className="section wrap" aria-labelledby="more-h">
      <SectionHead id="more-h" eyebrow="Go deeper" title="Read the method, the limits and the evidence." />
      <div className="cards">
        {READ_MORE.map(({ link, text }) => (
          <a key={link.href} className="card" href={link.href}>
            <h3>{link.label} <span aria-hidden="true">→</span></h3>
            <p>{text}</p>
          </a>
        ))}
      </div>
    </section>
  );
}

const TEAM = [
  { initials: "KE", name: "Kaan Eşrefoğlu" },
  { initials: "BK", name: "Barkın Kocatepe" },
];

export function Team() {
  return (
    <section className="section wrap team" aria-labelledby="team-h">
      <div>
        <p className="eyebrow">NASA Space Apps Challenge 2026 · Aachen</p>
        <h2 id="team-h">Kestro Aerospace</h2>
        <p className="muted">Challenge: <em>Lunar Landing Site Navigator</em>.</p>
      </div>
      <ul className="people">
        {TEAM.map(({ initials, name }) => <li key={name}><span className="avatar" aria-hidden="true">{initials}</span>{name}</li>)}
      </ul>
      <Actions withCode={false} />
    </section>
  );
}
