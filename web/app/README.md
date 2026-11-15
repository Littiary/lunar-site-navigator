# web/app: the public site (React)

The landing page and the two-site comparison of https://littiary.github.io/lunar-site-navigator/, built with React 18, Vite 5 and TypeScript into static files for the project path `/lunar-site-navigator/`. Like every viewer of the project it computes no science: it shows values of the published packages and of the validation card.

```
cd web/app
npm ci           # dependencies exactly as in package-lock.json
npm run build    # type check (tsc), then dist/  (ignored by git)
cd .. && python -m lsn_web.site   # copies dist/ to the site root, next to everything else
```

`python -m lsn_web.site` places `dist/index.html`, `dist/compare/` and `dist/assets/` at the root of `web/dist/site/`, next to the packages, the summaries, `viewer/` and the accuracy, learn and evidence pages, which the app links or loads at run time. The classic comparison page stays at `compare.html` and `classic.html`. Without a build in `dist/` the root `index.html` is the classic page, as before. Tests: `web/tests/test_app.py` (build step, the link to the classic module, the built pages) and `web/tests/test_moon_texture.py`.

## Two pages, two kinds of data

| Page | Source | Data | When it is read |
|---|---|---|---|
| `index.html` (landing) | `src/landing/` | Shackleton figures, the list of sites, the validation card | at build time, by `plugins/facts.ts` |
| `index.html`, section "See it in 3-D" | `src/landing/GroundView.tsx` | the Shackleton and de Gerlache rim packages, terrain patches, direction table | at run time, by `web/viewer/js/ground-scene.js`, when the section nears the screen |
| `compare/index.html` | `src/compare/` | the site packages, summaries, pair package, notice | at run time, by `web/viewer/js/compare.js` |
| both | `src/components/`, `src/site/` | `notice.json` (banner) | at run time |

**Landing.** `plugins/facts.ts` reads `packages/index.json`, the Shackleton rim manifest and `validation/card/validation_card.json` while Vite builds, and hands the page a small typed object (`virtual:lsn-facts`): the site list, the largest Sun blocker of the Shackleton package at its default observer height (distance, hours lost, share of the loss, package id), and the card's counts, rows and failed checks. Every value is copied unchanged; `src/site/format.ts` only rounds and adds units. The third key figure (74.1 h to 1.8 h) is not in a package: it is quoted from `docs/method/near_field.md`, section 4, and the page links that note. A rebuild after a package or card change gives new figures.

**Comparison.** The page does not reimplement the comparison. `src/compare/ComparePage.tsx` lays out the elements of the classic page (same ids and `data-role`s) and `useClassicCompare` loads `viewer/js/compare.js` from the published `viewer/` folder with a run-time `import()`. That one module, unchanged and shared with `classic.html`, loads the index, the summaries and the two site packages with their SHA-256 checks and fills the status cards, the horizon chart, the sky panorama, the ground view (`view3d.js`, three.js from `viewer/vendor` through the import map in `compare/index.html`), the calendar and the pair table. The per-pane template is not copied either: `plugins/classic.ts` reads `<template id="pane-template">` from `web/viewer/compare.html` at build time (`virtual:lsn-classic`). For the same address both pages therefore show the same numbers; this was checked in a browser by comparing the HTML of both panes, the pair table and the time readout between `classic.html` and `compare/` for two site pairs (identical), and `test_app.py` checks that every element the module looks up exists on the React page.

**3-D section of the landing page.** Right after the key figures, the landing page shows the live ground view of the planner at 2026-12-07 04:00 UTC, observer 2 m: at Shackleton rim crest the package gives the Sun as hidden behind the terrain 673 m away; a switch shows de Gerlache rim crest at the same instant. `web/viewer/js/ground-scene.js` runs the steps of a comparison pane (site package with its checks, nearest sample, `loadSiteData`, `groundData`, `groundInput`, `view3d.createView`) and returns the package values the caption prints, including the Sun blocker of `timeline.blockers` that holds that sample. The module, three.js and the packages are fetched only when the section comes within 300 px of the screen (`useInView`), so the top of the page stays light; the landing page carries the import map for three.js. "Open in the planner" opens `compare/` with both sites, 2 m and the ground view at the same sample. Without WebGL the section shows the Unreal render of the same moment and says why.

## Layout of the source

```
index.html, compare/index.html   page shells (Vite entries); both hold the import map for three.js
plugins/facts.ts                 build-time facts of the landing page (virtual:lsn-facts)
plugins/classic.ts               build-time pane template of the classic page (virtual:lsn-classic)
src/main-landing.tsx             entry of the landing page
src/main-compare.tsx             entry of the comparison; loads viewer/viewer.css, then the site styles
src/site/links.ts                site and repository addresses, the shared link list (LINKS)
src/site/notice.ts               notice.json of the site build (banner)
src/site/facts.ts                typed access to virtual:lsn-facts
src/site/format.ts               rounding and units for display
src/components/                  Shell (frame of every page), Nav, Footer, Mark, Actions, SectionHead, useInView
src/landing/                     one component per landing section (Hero, KeyFigures, GroundView, Stills, HowItWorks, SiteList, Trust, Closing)
src/compare/                     ComparePage, TimeBar, useClassicCompare
src/styles.css, src/compare.css  palette (background #0b0d12, Sun #ffd966, Earth #9ccbf5, failure #f28b82) and layout
src/assets/                      three Unreal renders scaled to 1600 px (originals in docs/unreal/pitch/)
```

## Moon globe texture

The Moon globe of the single-site viewer (`viewer/index.html`, `web/viewer/js/globe.js`) shows the 2K NASA SVS colour map first and then replaces it with a sharper copy of the same map: 4K (1.4 MB) wherever WebGL accepts a 4096-pixel texture, 8K (4.8 MB) only on a large screen with a fine pointer. The copies, their source, conversion and checksums are recorded in `web/viewer/vendor/moon/HD_TEXTURES.md` and in `CREDITS.md`. The texture is for orientation only; positions, lighting and numbers do not depend on it. No decorative texture was added to the ground view.

## Notes

- Paths: Vite writes absolute asset URLs under `/lunar-site-navigator/` (`base` in `vite.config.ts`). To look at a build locally, serve a folder whose `lunar-site-navigator/` points to `web/dist/site`, for example `python -m http.server 8000 --directory serve`, and open http://localhost:8000/lunar-site-navigator/.
- `npm run dev` serves the React pages, but the files they read at run time (`viewer/`, `packages/`, `notice.json`) exist only in a site build, so check the comparison on a served build.
- Screenshots at 1440 px and 390 px: `docs/web/react/`.
