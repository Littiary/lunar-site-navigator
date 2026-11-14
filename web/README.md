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

## Provisional outputs from the real site packages

The core stream handed over the three south-polar site packages and their direction table as `packages_sites.zip` (contract 0.1, written 2026-11-14 by core commit `6f74153` with uncommitted changes; they match `validation/sites/results/site_summary.json` of ephem commit `b90be63`). They are kept outside git under `build/packages/provisional-0.1/sites/` and the outputs under `web/dist/provisional-0.1/` (both folders are ignored). Every chart and the page carry a "PROVISIONAL RESULTS, NOT FINAL" banner. When the core stream commits updated packages, the outputs are rebuilt from those with the same two commands.

```
cd web
python -m lsn_web.charts ../build/packages/provisional-0.1/sites/index.json --out ../web/dist/provisional-0.1 --notice "<text>"
python -m lsn_web.evidence ../build/packages/provisional-0.1/sites/index.json --card <validation_card.json> --notice "<text>" --out ../web/dist/provisional-0.1/evidence.html
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

`tests/test_versions.py` also has a test that reads and draws the real packages. It runs only where they have been extracted under `build/packages/provisional-0.1/`, and is skipped elsewhere.
