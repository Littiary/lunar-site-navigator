# Science core

Python package `lsncore`. It computes every number of the project and writes it to
versioned packages; see [the contract](../docs/contract/SPEC.md). The horizon method, its
checks and its limits are in [docs/method/horizon.md](../docs/method/horizon.md); the obstacle
report in [docs/method/obstacles.md](../docs/method/obstacles.md); the calendar and the slip tolerance in
[docs/method/calendar.md](../docs/method/calendar.md); the uncertainty band and the landing ellipse in
[docs/method/uncertainty.md](../docs/method/uncertainty.md); the mast-height trade and site pairs in
[docs/method/trade_pairs.md](../docs/method/trade_pairs.md); the terrain patches for drawing in
[docs/method/terrain_patch.md](../docs/method/terrain_patch.md); the orientation of the Earth for drawing it in
[docs/method/earth_view.md](../docs/method/earth_view.md); the 5 m near field and the band fed by the products' errors in
[docs/method/near_field.md](../docs/method/near_field.md).

## Setup

```
python -m venv .venv
.venv/Scripts/python -m pip install -e "core[dev]"     # Windows; use .venv/bin/python elsewhere
.venv/Scripts/python -m pip install -e data            # terrain reader of the data stream
.venv/Scripts/python -m pytest core
```

## Commands

```
python -m lsncore site --lat -89.5 --lon 200 --name "Test" --out <package root>
python -m lsncore scenario --sites data/sites/sites.json --id three-sites --start 2026-11-14T00:00:00.000Z --end 2028-11-14T00:00:00.000Z --out scenario.json
python -m lsncore run <scenario.json> --out <package root>
python -m lsncore validate <package dir | json file> ...
python -m lsncore sample                                  # regenerate docs/contract/sample
```

`site` computes the terrain horizon of one point (options: `--heights`, `--azimuth-step`,
`--max-range-km`). `scenario` writes a scenario file from the site records of the data
stream; options state what else is wanted: `--landing-utc` (planned landing),
`--preset <id>` (an example requirement from
[`docs/contract/presets`](../docs/contract/presets/README.md); repeatable, `all` for every
one) or `--requirements <file>` (your own requirements on the landing time),
`--horizon-error-deg`, `--height-error-preset default` (the measured height-error model;
`--dem-height-error-m` for a single number) and `--ellipse` (assumptions for the
uncertainty band and the landing-ellipse survey), `--heights` (mast heights to compare). `run` computes every site of a scenario file
(`--jobs N`: processes it may use, see run times below; `--near-field`: use the 5 m site
rasters where a site lies on one, [near_field.md](../docs/method/near_field.md)). With
a time window and the ephemeris modules installed, a site package then holds:

| Part | From |
|---|---|
| horizon, its obstacles, far-field bound | terrain |
| the ground around the site on three grids, for drawing only (no time window needed) | [terrain_patch.md](../docs/method/terrain_patch.md) |
| series, events, windows, metrics | direction table and event finder |
| blocker of every sample, time lost to each obstacle against a smooth sphere | [obstacles.md](../docs/method/obstacles.md) |
| lunar-day calendar; landing windows and slip tolerance of stated requirements | [calendar.md](../docs/method/calendar.md) |
| band for a stated horizon error; survey of a stated landing ellipse | [uncertainty.md](../docs/method/uncertainty.md) |
| mast-height trade table | [trade_pairs.md](../docs/method/trade_pairs.md) |

and with two or more sites a site-pairs package is written next to them.

Terrain: by default every LOLA product installed under the data root of the data stream
(`LSN_DATA_ROOT`): the polar products near the poles, the global latitude-longitude
product elsewhere, so a site anywhere gets a package that names the product and the
resolution class that served it ([horizon.md](../docs/method/horizon.md), section 9). `--dem-label <file.lbl>` (repeatable) opens other products of the same
format, for example the synthetic test raster `data/fixtures/synth_s90_100m.lbl`; a
package computed from a synthetic surface is flagged `synthetic`. `--synthetic` skips the
computation and writes invented numbers (the walking skeleton behind the contract sample).

## Run times

Measured on 14 November 2026 on one laptop (20 logical processors, Windows 11), each as a
fresh `python -m lsncore ...` process from its start to validated packages. South-polar
LOLA products, hourly series, six observer heights, default `--jobs` (8 here).

| Request | Time |
|---|---|
| One custom site, horizon and terrain patches, no dates (`lsncore site`) | 3.5 to 4.4 s |
| One site, 30 days, calendar and mast trade | 11 s |
| One site, 30 days, three presets, uncertainty band and landing ellipse of 13 points | 31 s (35 s in one process) |
| One site, 24 months, the same | 3.7 min (223 s) |
| Three sites, 24 months, calendar and mast trade | 2.7 min (159 s) |
| Three sites, 24 months, three presets, band and ellipse | 6.1 min (367 s); 16.2 min (970 s) in one process |

A site without dates, or with a month of them, is answered while the user waits. Two
years are a batch job of minutes. `run --jobs N` sets how many processes a run may use:
sites are computed side by side, and what is left over shares, inside each site, the
event searches of the uncertainty band and of the landing ellipse. The packages are
identical for any number of jobs (tests in `core/tests/test_pipeline.py`).

Where the time of a 24-month site goes (one process, 375 s while other work was
running): 77 % in the event searches, 72 of them per site with every option on (12 for
the windows themselves, 12 over a smooth sphere, 24 for the band, 24 for the ellipse),
about 4 s each; most of that is the visible fraction of the disc against the horizon
profile in the event finder. The horizon itself takes 2 s, the twelve horizons of the
ellipse points 16 s, the ground-station windows and the eclipses of the ephemeris modules
47 s and 39 s. A site on the global 237 m product costs about the same as a polar one
(2.6 to 2.9 s for the horizon, [horizon.md](../docs/method/horizon.md), section 9).

## Layout

| Module | Content | Stream |
|---|---|---|
| `lsncore/contract/` | Package writer, reader, validator | A |
| `lsncore/horizon.py` | Terrain horizon on a sphere, several observer heights in one pass, far-field bound | A |
| `lsncore/dem.py` | Terrain interface; adapters for the data stream's polar and whole-Moon readers; analytic terrain for tests | A |
| `lsncore/pipeline.py` | Scenario in, packages out; method cards of the horizon | A |
| `lsncore/obstacles.py`, `lsncore/blocking.py` | Obstacles of the horizon; which one limits a body; time lost to terrain against a smooth sphere | A |
| `lsncore/calendar.py` | Visible time per lunar day; landing windows of a stated requirement; slip tolerance | A |
| `lsncore/uncertainty.py` | Band for a stated horizon error; survey of a stated landing ellipse | A |
| `lsncore/earth_view.py` | Orientation of the Earth as seen from the Moon (sub-lunar point, position angle of the north pole), written into the direction table | A |
| `lsncore/terrain_patch.py` | Terrain patches for drawing: the surface on regular grids in the site frame | A |
| `lsncore/trade.py`, `lsncore/pairs.py` | Mast-height trade table; what two sites achieve together (site-pairs package) | A |
| `lsncore/timeline.py` | `TimeGrid`, `IntervalSet` (window algebra) | A |
| `lsncore/geometry.py` | Site frame, great-circle steps, topocentric direction | A |
| `lsncore/scenario.py` | Scenario file | A |
| `lsncore/results.py`, `lsncore/packaging.py` | Result objects and the package builder | A |
| `lsncore/synthetic.py` | Invented stand-ins for the skeleton and the contract sample | A |
| `lsncore/ephem/`, `lsncore/events/` | Ephemeris, direction table, event finder | B |
