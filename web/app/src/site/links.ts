// Addresses of the site and of the repository. Every page of the site is published by
// `python -m lsn_web.site` under BASE ("/lunar-site-navigator/"), next to this app.

export const BASE: string = import.meta.env.BASE_URL;

/** A file of the published site, e.g. at("packages/index.json"). */
export const at = (path: string): string => `${BASE}${path}`;

export const GITHUB = "https://github.com/Littiary/lunar-site-navigator";

/** A file of the repository on GitHub (main branch). */
export const repoFile = (path: string): string => `${GITHUB}/blob/main/${path}`;

export interface Link {
  href: string;
  label: string;
}

/** The links every page uses; one place for their addresses and wording. */
export const LINKS = {
  home: { href: at(""), label: "Lunar Site Navigator" },
  compare: { href: at("compare/"), label: "Compare two sites" },
  learn: { href: at("learn.html"), label: "How to read it" },
  accuracy: { href: at("accuracy.html"), label: "Accuracy and limits" },
  evidence: { href: at("evidence.html"), label: "Evidence" },
  viewer: { href: at("viewer/index.html"), label: "Single-site viewer" },
  classic: { href: at("classic.html"), label: "Classic comparison page" },
  slides: { href: at("submission/Lunar_Site_Navigator_backup_slides.pdf"), label: "Download the slides (PDF)" },
  github: { href: GITHUB, label: "Code on GitHub" },
  contract: { href: repoFile("docs/contract/SPEC.md"), label: "Package contract" },
  card: { href: repoFile("validation/card/validation_card.md"), label: "Validation card" },
  license: { href: repoFile("LICENSE"), label: "Apache License 2.0" },
} satisfies Record<string, Link>;
