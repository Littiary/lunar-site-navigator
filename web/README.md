# web/ : charts, evidence page and viewers

Everything in this folder reads packages written by the science core (contract: `docs/contract/SPEC.md` on the core branch) and draws them. Nothing here computes a scientific value. Numbers that are shown come from the package unchanged; only their formatting is done here.

## Static charts (`lsn_web/charts.py`)

| Chart | File | Content |
|---|---|---|
| Horizon panorama | `horizon_panorama__<site_id>.svg` | Terrain horizon elevation versus azimuth at the default observer height (`horizon.elevation_deg`), with the tracks of the Sun and Earth disc centres over the time window (`timeline.series.<BODY>.azimuth_deg` / `elevation_deg`) |
| Window strip | `window_strip.svg` | Sun, Earth and combined visibility windows (`timeline.windows`, default observer height) of one or more sites on one shared UTC axis, with the share of the window from `timeline.metrics` |

Each chart prints the package id and content digest, reference frame, sphere radius, site coordinates, observer height, UTC range, and the validation status of the method cards behind it. Packages with `synthetic: true` get a red "SYNTHETIC SAMPLE DATA" banner.

Build from frozen packages (Python 3.11 or newer, standard library only):

```
cd web
python -m lsn_web.charts <site package dir> [<site package dir> ...] --out <folder>
```

Before drawing, the reader checks each array file against the size and SHA-256 in its manifest, and refuses a package whose contract major version is not 0. The same package always gives the same bytes, so a chart can be regenerated and compared at any time.

Time-axis labels: dates at 00:00 UTC are placed as `start_utc` + elapsed seconds, which the contract allows only when `leap_seconds_in_range` is 0. Otherwise only the package's own UTC strings are used.

## Evidence page (`lsn_web/evidence.py`)

One self-contained HTML file per build. For each site package it shows the two charts, the site, frame, sphere radius and time window, the summary metrics and the rise and set events at the default observer height. It also shows every method card with its validation status, and the data and software versions. When given the ephemeris stream's `validation/card/validation_card.json`, it adds that card: checks, thresholds, measured values, what is not validated, and limits.

```
cd web
python -m lsn_web.evidence <site package dir> [...] --card <validation_card.json> --out <file.html>
```

The page loads nothing from the network: the charts are embedded as data URIs and the styles are inline. The same file is therefore the offline copy, and it opens without a login in a private window and on a phone. Charts and wide tables scroll sideways inside their own boxes on narrow screens, so the page itself never does. It follows the system light or dark setting.

Generated pages are not committed while only the synthetic sample exists. They will be built from the first frozen real package.

## Tests

```
python -I -m unittest discover -s web/tests -t web
```

`tests/fixtures/contract-sample/` is a byte-for-byte copy of `docs/contract/sample/packages` from the core branch at commit `dfc5221`. It is synthetic: invented values that describe no real place. Refresh it only by copying it again from the core branch, never by editing it.

`tests/fixtures/validation-card/validation_card.json` is a byte-for-byte copy of `validation/card/validation_card.json` from the ephemeris branch at commit `a8bbc5a`. The same rule applies.
