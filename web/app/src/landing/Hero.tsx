import hero from "../../../viewer/img/hero.jpg";
import { Actions } from "../components/Actions";
import facts from "../site/facts";

export function Hero() {
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
        <Actions />
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
