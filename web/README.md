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

## Tests

```
python -I -m unittest discover -s web/tests -t web
```

`tests/fixtures/contract-sample/` is a byte-for-byte copy of `docs/contract/sample/packages` from the core branch at commit `dfc5221`. It is synthetic: invented values that describe no real place. Refresh it only by copying it again from the core branch, never by editing it.
