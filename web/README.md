# web/ : charts, evidence page and viewers

Everything in this folder reads packages written by the science core (contract: `docs/contract/SPEC.md` on the core branch) and draws them. Nothing here computes a scientific value. Numbers that are shown come from the package unchanged; only their formatting is done here (for example seconds shown as hours, or a fraction shown as a percentage).

## Contract versions

The reader accepts every `0.x` package (SPEC section 8: minor versions only add fields) and refuses any other major version. Fields from a later minor version are used when present and their views are hidden when absent:

| Field | Since | Shown as |
|---|---|---|
| `timeline.blockers` | 0.2 | "What blocks the view" table on the evidence page (SPEC 5.5) |
| `horizon.obstacles`, `obstacle_id`, `series.<BODY>.blocker_azimuth_index`, `lit_fraction` | 0.2 | not drawn yet |
| `timeline.calendar`, `timeline.opportunities` | 0.3 | Opportunity calendar of the viewer and the comparison (Task 9), landing status card |
| `terrain.patches` | 0.7 | Ground view surface, patches chosen by spacing, not list order (0.11) |
| `horizon.terrain_source` | 0.9 | Terrain class next to each site; a warning for every class other than fine |
| countdown `reference`, event `terrain_quality` | 0.10 | Details of each comparison pane, with the reference instant |
| `site.programme`, `site.category` | 0.11 | Site selectors grouped by programme, with the category |
| `request.default_height_m` | 0.12 | Not shown as such; the default height is marked from `horizon.default_height_index`, as before. The values that 0.12 corrects (`latest_landing`, `clipped_end`, `slip_tolerance_is_lower_bound`, `planned_landing` of `null`) are shown as the package gives them |

Packages can be given as directories or through an `index.json`, which lists every package under a package root.

## Static charts (`lsn_web/charts.py`)

| Chart | File | Content |
|---|---|---|
| Horizon panorama | `horizon_panorama__<site_id>.svg` | Terrain horizon elevation versus azimuth at the default observer height (`horizon.elevation_deg`), with the tracks of the Sun and Earth disc centres over the time window (`timeline.series.<BODY>.azimuth_deg` / `elevation_deg`) |
| Window strip | `window_strip.svg` | The windows `sun_visible`, `earth_visible`, `sun_and_earth_visible` and, when present, `earth_network_dsn` and `sun_eclipsed_by_earth` (`timeline.windows`, default observer height) of one or more sites on one shared UTC axis, with the share of the window from `timeline.metrics`. Rows are selected by window id, because a package holds several windows per subject. An interval narrower than 1.5 px also gets a marker line; its bar keeps its exact width |

Each chart prints the package id and content digest, reference frame, sphere radius, site coordinates, observer height, UTC range, and the validation status of the method cards behind it. Packages with `synthetic: true` get a red "SYNTHETIC SAMPLE DATA" banner. `--notice TEXT` adds a further red banner, for example to mark results as provisional.

Build from frozen packages (Python 3.11 or newer, standard library only):

```
cd web
python -m lsn_web.charts <site package dir | index.json> [...] --out <folder> [--notice TEXT]
```

Before drawing, the reader checks each array file against the size and SHA-256 in its manifest. The same package always gives the same bytes, so a chart can be regenerated and compared at any time.

Time-axis labels: dates at 00:00 UTC are placed as `start_utc` + elapsed seconds, which the contract allows only when `leap_seconds_in_range` is 0. Otherwise only the package's own UTC strings are used.

## Evidence page (`lsn_web/evidence.py`)

One HTML file. For each site package it shows:

- the two charts;
- the site, frame, sphere radius and time window;
- the summary metrics and the rise and set events at the default observer height;
- every window at that height with its definition;
- the obstacles that cost visible time (0.2 and later).

It also shows every method card with its validation status and the data and software versions. A package written by a core with uncommitted changes (`provenance.software.git_dirty`) gets a banner saying it cannot be reproduced from the repository alone. When given the ephemeris stream's `validation/card/validation_card.json`, the page adds that card: checks, thresholds, measured values, what is not validated, and limits.

```
cd web
python -m lsn_web.evidence <site package dir | index.json> [...] --card <validation_card.json> [--notice TEXT] --out <file.html>
```

The page loads nothing from the network and its styles are inline. Built with the command above, it embeds every chart as a data URI, so that one file is a complete offline copy. In the site build (`lsn_web.site`) it shows the chart files of `charts/` next to it instead (per site `horizon_panorama__<site_id>.svg` and `window_strip__<site_id>.svg`, the same bytes the command would embed), so that it does not carry all charts of all sites a second time: with the 20 published sites the page is about 2 MB instead of 25.6 MB. The site folder is then the offline copy. Either way it opens without a login in a private window and on a phone. Charts and wide tables scroll sideways inside their own boxes on narrow screens, so the page itself never does. It follows the system light or dark setting.

## Accuracy and limits page (`lsn_web/accuracy.py`)

One self-contained HTML file (`accuracy.html` in the site build), written for a reader who has to decide whether to rely on a number. It reads stored records and formats them; nothing is recomputed:

- the validation card: every check once, with its threshold, measured value and stored status. Checks against a source outside the project (card groups "Independent source", "Independent computation on terrain", "Dated image", "Published mission record") are kept apart from analytical and internal tests ("Closed form", "Internal consistency", "Independent implementation"); a group the page does not know gets its own table. Failed checks have their own section;
- what the card lists as not validated, and its limits;
- the real-mission cases of `validation/landers` and `validation/eclipse`: each published value as printed, its printed precision, whether the source calls it approximate, its source with the retrieval time, and the stored comparison rows;
- terrain: for every published site the elevation product under it, pixel size, resolution class, whether its package has an uncertainty band, and package warnings; the obstacles the packages mark as near field; the stored flags of the data stream's acceptance reports (`data/checkpoints/report.json`, `llr_report.json`, `near_field_report.json`), failures included;
- event times: the assumption sentence of the uncertainty band, the applied height errors, and example events with their earliest and latest times, all as stored in the packages;
- the status of every method in the packages, the assumptions, and links to the source records.

A record that is missing in a build is named as missing. `tests/test_accuracy.py` checks the page against the card, the case files and the reports.

```
cd web
python -m lsn_web.accuracy <site package dir | index.json> [...] --card <validation_card.json> [--notice TEXT] --out <file.html>
```

## Education page (`lsn_web/learn.py`, `lsn_web/learn_text.json`)

One self-contained HTML file (`learn.html` in the site build, linked as "How to read it"): four short explanations (the horizon, visibility windows, terrain uncertainty, landing opportunities), each with one example from a published package. The example sentences are templates whose placeholders are filled with package values (formatted only: seconds as hours, fractions as percentages); the package's own statements (the assumption of the uncertainty band, the label of the landing requirement) are quoted unchanged. The example site is chosen by comparing stored values: among the project's own sites with obstacles, a band and opportunities, the one whose costliest Sun obstacle costs most. An example whose fields a package lacks is left out, and the page says so.

**Languages.** `learn_text.json` holds one entry per language code with the same keys; the site build writes `learn.html` for `en` and `learn.<code>.html` for every further entry, with links between them. `tests/test_learn.py` holds every entry to the keys and placeholders of the English one. Only English is present: rule 11 of `CONTRIBUTING.md` (all text in the repository is English) and the submission guide (linked materials in English) stand against committing a Turkish entry without a team decision. Numbers, units, UTC times and quoted package statements are not translated in any language.

```
cd web
python -m lsn_web.learn <site package dir | index.json> [...] [--lang en] --out <file.html>
```

## Interactive viewer (`web/viewer/`)

A static page that reads the packages in the browser (Tasks 7 and 8):

- **Horizon and time:**
  - pick a site, an observer height and a time sample (slider, ±1 h, ±1 day, play, jump to the previous or next package event);
  - the SVG shows the terrain horizon (`horizon.elevation_deg`) and the Sun and the Earth at that sample (`timeline.series`);
  - tables list the values at that sample, every window that contains it, and the events around it.
- **Sky panorama (Task 7 C, `js/sky.js`):**
  - a 360° panorama: azimuth left to right, wrapping around, and elevation bottom to top;
  - the terrain horizon, plus the paths of the Sun and the Earth over ±1 day to the whole window around the selected time;
  - a path is solid where the package window `<body>_visible` contains the sample and faded elsewhere (a time comparison, no threshold);
  - drag to pan, use the wheel, a pinch or the buttons to zoom; pointing at a path shows that sample's package values, and clicking or tapping it selects that time;
  - angles map linearly to pixels, with no trigonometry; a built-in check reads the drawn horizon back and compares it with the package (it agrees to within floating-point rounding).
- **3-D ground view (Task 8 B, three.js 0.160.0 stored in `viewer/vendor/three/`, so it works offline):**
  - the horizon profile is drawn as terrain around the observer, with the Sun and the Earth placed by their package directions behind it, so the terrain hides them when they are below its horizon;
  - the horizon ring is coloured by the distance of the terrain that sets the horizon (`horizon.distance_m`: < 1 km near field, 1–10 km, 10–100 km, ≥ 100 km; comparisons only);
  - a built-in check reads the drawn horizon line back against the package (about 2e-7°, float32 rounding);
  - without WebGL the tab says so and points to the 2-D views;
  - the panel names the newer package fields the ground view would use but the package lacks (obstacles, blockers, lit fraction, uncertainty arrays); nothing is drawn in their place.

**No science in the browser.**
- `js/package.js` checks every array against the byte length and SHA-256 in its manifest; Web Crypto needs https or localhost, and otherwise the footer says that checksums were not verified.
- `js/viewer.js` only looks values up, compares times and maps them to screen positions. Time labels use `start_utc` + i × `step_s`, which SPEC 3.5 allows only without leap seconds; otherwise the page shows sample numbers.
- `js/view3d.js` uses trigonometry only in its marked display transform.
- `tests/test_viewer.py` enforces these rules in the source.

- **Moon globe (Task 8 A, `js/globe.js`):** the Moon in its body-fixed frame with the NASA SVS colour map, lit along the direction table's Sun vector; site markers and labels are HTML (fixed size, hidden on the far side, clickable and reachable with the keyboard); sub-solar and sub-Earth points; a click opens the site's ground view at the same time.
- **Real terrain in the ground view:** the surface is the package's terrain patches (`js/terrain.js`), placed node for node and checked against the package (0 m); the package horizon line stays the reference. Display settings (lighting mode, slope shading, patch outlines) change only how it looks.
- **Opportunity calendar (Task 9, `js/calendar.js`):** lunar days of `timeline.calendar` on one UTC axis, every calendar quantity at the selected observer height, incomplete lunar days marked, landing windows and slip tolerance of `timeline.opportunities` with the requirement's label and status.
- **CSV export (Task 11, `js/csv.js`):** the Sun and Earth series of the selected site and height, every value as stored in the package (a runtime test compares each one).

**Home page: the comparison (`compare.html`).** It names the tool, says what it does, and shows a short validation note built from the validation card with a link to the evidence page. Loading is progressive (see "First-screen summaries" below): status cards first, then the horizon charts, then the details. Each pane starts with three status cards: the Sun and the Earth visible now and the time to the next published rise or set, and whether a landing now meets the chosen requirement (the shipped requirements are labelled as examples). Tables, identifiers and methods are behind a Details control. Pane views: horizon chart, sky panorama, ground view (the same renderer, `js/ground.js`), opportunity calendar. With no sites in the address it opens on the first pair of the published `site_pairs` package.

Two sites side by side on one shared timeline (Task 7, first milestone):
- **Shared controls:** play/pause, speed (1 h, 6 h, 1 day or 1 week per step), a UTC date field, a slider and ±1 h / ±1 day steps.
- **Each pane:** chooses its own site and observer height and shows
  - status chips for the windows `sun_visible`, `earth_visible`, `earth_network_dsn` and `sun_eclipsed_by_earth`;
  - the horizon with the Sun and the Earth;
  - the values at that time;
  - the package metrics for the whole window (visible shares, longest outages, DSN share, relay need, eclipses);
  - the next events.
- **Shared time:** a sample of the time grid of the left site. Each pane shows the sample of its own package nearest to that instant, labelled with its own UTC. If the grids ever differ, the pane says so.
- **Pane view:** one shared switch shows the horizon chart, the sky panorama, the ground view or the calendar in both panes. The panorama is the same `js/sky.js` module, one instance per pane. The "Paths for" span is shared, and clicking a path in either pane moves the shared timeline.
- **Uncertainty band:** shown only when a package has the windows `<body>_visible_uncertain` (contract 0.4 and later, SPEC 5.7). Path samples inside the band are dashed, and the package's assumption sentence is shown with it. Of the published packages (contract 0.12), the seven south-polar sites have the band; the 13 sites on SLDEM2015 have none, because no height error has been measured for that product, and the pane says so.
- **Layout:** the panes stack on narrow screens.
- **Shareable links:** `?a=<site_id>&b=<site_id>&ha=<height index>&hb=<height index>&i=<sample>` opens a selection.

The viewer needs a web server; `fetch` does not work from `file://`. The site build below copies it to `viewer/`, with the packages next to it in `packages/`. To try it locally:

```
cd web && python -m lsn_web.site && python -m http.server 8000 --directory dist/site
```

Then open http://localhost:8000/viewer/. A link with `?site=<site_id>&h=<height index>&i=<sample>` opens that selection.

## First-screen summaries (`lsn_web/summary.py`)

The site build writes `summary/index.json` (one entry per site of the index: identity, terrain class, observer heights, the file and SHA-256 of its summary) and `summary/<site_id>.json`: the Sun and Earth windows, rise and set events, landing opportunities, requirements, countdown metrics and the array references of the horizon and the Sun and Earth directions, copied unchanged from the site manifest and naming its package id and content digest. The comparison checks each summary's SHA-256 and package id before it uses it, shows the status cards from it, fetches the chart arrays through its references (checked by SHA-256 as always), and replaces it by the full package when that arrives. Only the two selected sites are loaded; without summaries the page still works, more slowly. `tests/test_summary.py` checks that every value equals the manifest.

## Public site (`lsn_web/site.py`)

One command builds the hosted site from the packages published by the core stream in `packages/`:

```
cd web
python -m lsn_web.site
```

It writes `web/dist/site/` (ignored by git): `index.html` and `compare.html` (the split-screen comparison), `evidence.html` (the separate evidence page, showing the chart files), `accuracy.html` (the accuracy and limits page), `learn.html` (the education page), `charts/*.svg` (every chart as its own file: per site the panorama and the window strip, and the windows of all sites on one axis), `viewer/` (the single-site viewer), `packages/` (index.json and exactly the files it lists, copied byte for byte), `summary/` (the first-screen summaries), `notice.json` (the notice and the validation card's counts, for the pages) and `.nojekyll`. The folders it writes are cleared first, so nothing of an earlier build is published. The defaults are `--packages ../packages/index.json`, `--card ../validation/card/validation_card.json`, `--notice-file site_notice.txt` and `--out dist/site`. The same inputs always give identical bytes.

**Notice.** `web/site_notice.txt` holds the banner shown on the page and on every chart. It currently says that the results are provisional. An empty file removes the banner, so the freeze needs no code change.

**When the packages change:** fetch the branch that holds the new `packages/`, run `python -m lsn_web.site`, then publish `web/dist/site/` (see Hosting).

The packages were first handed over as `packages_sites.zip` (contract 0.1). Their content digests are identical to the published ones in `packages/` (commit `945546d`, generated from core commit `d1af9e6` with a clean working tree).

## Hosting

The site is static: any host that serves files works, with no build step and no server code. Publishing copies `web/dist/site/` to the hosting location as it is.

GitHub Pages serves the branch `gh-pages` (root folder) at https://littiary.github.io/lunar-site-navigator/. That branch holds only the built site, in its own history, and is never edited by hand. A repository admin switches Pages on once: Settings → Pages → Deploy from a branch → `gh-pages` / `(root)`. To publish a new build:

```
cd web && python -m lsn_web.site && cd ..
git worktree add <folder> gh-pages
# replace the content of <folder> with web/dist/site/ (including .nojekyll), then in <folder>:
git add -A && git commit -m "Publish the evidence site built from packages/ at <commit>" && git push origin gh-pages
```

## Tests

`tests/test_runtime.py` runs the viewer's JavaScript with Node (any recent version; the tests are skipped without it). It checks that every built page, including the copies at the site root, reads the same `packages/index.json` and `notice.json`. It also compares every value of a CSV export with the package, and exercises the planning-details block. The other viewer tests read the source.

```
python -I -m unittest discover -s web/tests -t web
```

Fixtures are byte-for-byte copies; refresh them only by copying again from their branch, never by editing them:

| Fixture | Source |
|---|---|
| `tests/fixtures/contract-sample/` | `docs/contract/sample/packages` of the core branch at `dfc5221` (contract 0.1, synthetic) |
| `tests/fixtures/contract-sample-0.3/` | the same folder at `ad40648` (contract 0.3, synthetic) |
| `tests/fixtures/validation-card/validation_card.json` | `validation/card/validation_card.json` of the ephemeris branch at `a8bbc5a` |

`tests/test_versions.py` also reads and draws the published real packages in `packages/`, checking every array against its manifest.
