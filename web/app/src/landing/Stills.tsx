import stillTwoSites from "../assets/b_product_two_sites.jpg";
import stillRidge from "../assets/c_key_moment_near_ridge.jpg";
import stillLander from "../assets/e_lander_lit_side.jpg";

// Captions follow docs/unreal/pitch/README.txt, which says what each render shows.
const STILLS = [
  { src: stillTwoSites, title: "Two sites side by side",
    text: "Shackleton and de Gerlache crater rim crests at one instant, observer 2 m, each view lit by its own Sun." },
  { src: stillRidge, title: "The ridge that hides the Sun",
    text: "Shackleton rim crest, looking at the Sun's azimuth: the Sun is behind the ridge 673 m away, with its cost in hours." },
  { src: stillLander, title: "A lander on the sunlit side",
    text: "Shackleton rim crest in the Unreal Engine scene. Lander, mast and boulders are scale objects of the team's own design, not part of the package." },
];

export function Stills() {
  return (
    <section className="section stills-sec" aria-labelledby="stills-h">
      <div className="wrap">
        <p className="eyebrow">Rendered from the packages</p>
        <h2 id="stills-h">The same results in a real-time 3-D scene.</h2>
      </div>
      <div className="stills wrap">
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
