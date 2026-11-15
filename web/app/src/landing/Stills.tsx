import stillTwoSites from "../assets/b_product_two_sites.jpg";
import stillRidge from "../assets/c_key_moment_near_ridge.jpg";
import stillLander from "../assets/e_lander_lit_side.jpg";
import ridgeClip from "../assets/key_moment_ridge_720p.mp4";
import ridgePoster from "../assets/key_moment_ridge_poster.jpg";
import { LoopVideo } from "../components/LoopVideo";

// Captions follow docs/unreal/pitch/README.txt, which says what each render shows.
const KEY_MOMENT = {
  title: "The key moment",
  text: "Shackleton rim crest, observer 2 m, 9 s of the planner: the Sun goes behind the ridge 673 m away; the outline of the ridge lights up and a card gives its cost.",
};
const STILLS = [
  { src: stillTwoSites, title: "Two sites side by side",
    text: "Shackleton and de Gerlache crater rim crests at one instant, observer 2 m, each view lit by its own Sun." },
  { src: stillLander, title: "A lander on the sunlit side",
    text: "Shackleton rim crest in the Unreal Engine scene. Lander, mast and boulders are scale objects of the team's own design, not part of the package." },
];

export function Stills() {
  return (
    <section className="section stills-sec" aria-labelledby="stills-h">
      <div className="wrap">
        <p className="eyebrow">Rendered from the packages</p>
        <h2 id="stills-h">The same results in a real-time 3-D scene.</h2>
        <p className="muted">The Unreal Engine planner reads the same packages as this site; every clip and picture below is a render of it.</p>
      </div>
      <div className="stills wrap">
        <figure className="still">
          <LoopVideo src={ridgeClip} poster={ridgePoster} still={stillRidge} label={`${KEY_MOMENT.title}. ${KEY_MOMENT.text}`} />
          <figcaption><strong>{KEY_MOMENT.title}.</strong> {KEY_MOMENT.text}</figcaption>
        </figure>
        {STILLS.map(({ src, title, text }) => (
          <figure key={title} className="still">
            <img src={src} alt={`${title}. ${text}`} loading="lazy" decoding="async" width="1600" height="900" />
            <figcaption><strong>{title}.</strong> {text}</figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
