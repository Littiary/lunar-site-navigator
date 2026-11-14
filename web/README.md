# web/ : charts, evidence page and viewers

Everything in this folder reads packages written by the science core (contract: `docs/contract/SPEC.md` on the core branch) and draws them. Nothing here computes a scientific value. Numbers that are shown come from the package unchanged; only their formatting is done here (for example seconds shown as hours, or a fraction shown as a percentage).

## Contract versions

The reader accepts every `0.x` package (SPEC section 8: minor versions only add fields) and refuses any other major version. Fields from a later minor version are used when present and their views are hidden when absent:

| Field | Since | Shown as |
|---|---|---|
| `timeline.blockers` | 0.2 | "What blocks the view" table on the evidence page (SPEC 5.5) |
| `horizon.obstacles`, `obstacle_id`, `series.<BODY>.blocker_azimuth_index`, `lit_fraction` | 0.2 | not drawn yet |
| `timeline.calendar`, `timeline.opportunities` | 0.3 | not drawn yet (opportunity calendar is a later task) |

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

One self-contained HTML file per build. For each site package it shows:

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

The page loads nothing from the network: the charts are embedded as data URIs and the styles are inline. The same file is therefore the offline copy, and it opens without a login in a private window and on a phone. Charts and wide tables scroll sideways inside their own boxes on narrow screens, so the page itself never does. It follows the system light or dark setting.

## Public site (`lsn_web/site.py`)

One command builds the hosted site from the packages published by the core stream in `packages/`:

```
cd web
python -m lsn_web.site
```

It writes `web/dist/site/` (ignored by git): `index.html` (the evidence page), `charts/*.svg` (every chart as its own file, linked from the page) and `.nojekyll`. The defaults are `--packages ../packages/index.json`, `--card ../validation/card/validation_card.json`, `--notice-file site_notice.txt` and `--out dist/site`. The same inputs always give identical bytes.

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
