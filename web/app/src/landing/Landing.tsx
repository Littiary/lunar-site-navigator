import { ReadMore, Team } from "./Closing";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { KeyFigures } from "./KeyFigures";
import { SiteList } from "./SiteList";
import { Stills } from "./Stills";
import { Trust } from "./Trust";

/** The landing page, top to bottom. */
export function Landing() {
  return (
    <main className="landing">
      <Hero />
      <KeyFigures />
      <Stills />
      <HowItWorks />
      <SiteList />
      <Trust />
      <ReadMore />
      <Team />
    </main>
  );
}
