import { LINKS } from "../site/links";

/** The main calls to action: open the comparison, the slides and (optionally) the code. */
export function Actions({ withCode = true }: { withCode?: boolean }) {
  return (
    <div className="ctas">
      <a className="btn btn-sun" href={LINKS.compare.href}>{LINKS.compare.label} <span aria-hidden="true">→</span></a>
      <a className="btn btn-ghost" href={LINKS.slides.href}>{LINKS.slides.label}</a>
      {withCode && <a className="btn btn-ghost" href={LINKS.github.href}>{LINKS.github.label}</a>}
    </div>
  );
}

/** Heading block of a landing section: eyebrow line and title. */
export function SectionHead({ eyebrow, title, id }: { eyebrow: string; title: string; id: string }) {
  return (
    <>
      <p className="eyebrow">{eyebrow}</p>
      <h2 id={id}>{title}</h2>
    </>
  );
}
