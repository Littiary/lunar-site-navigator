import hero from "../../../viewer/img/hero.jpg";
import heroLoop from "../assets/hero_loop_720p.mp4";
import heroPoster from "../assets/hero_loop_poster.jpg";
import { Actions } from "../components/Actions";
import { LoopVideo } from "../components/LoopVideo";
import facts from "../site/facts";

// Background: a 9.8 s loop cut from the pitch video of the Unreal planner (the wide view of
// Shackleton rim crest while 36 h pass, then the camera move down to the lander; see
// src/assets/README.txt). With reduced motion, or where the clip cannot play, the still render
// of the south pole is shown instead.
export function Hero() {
  return (
    <section className="hero-l">
      <LoopVideo className="hero-media" src={heroLoop} poster={heroPoster} still={hero} eager
        label="Rendered south-polar terrain of the Moon in the Unreal planner" />
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
