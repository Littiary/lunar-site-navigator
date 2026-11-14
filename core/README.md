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
python -m lsncore custom --lat -89.5 --lon 200 --start 2026-11-14 --out <package root>   # complete package, see below
python -m lsncore site --lat -89.5 --lon 200 --name "Test" --out <package root>          # horizon only
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

## One command for a custom coordinate

```
python -m lsncore custom --lat 26.1 --lon 3.6 --start 2026-11-14 --out <package root>
```

For a latitude, an east longitude (degrees) and a start date (UTC, `2026-11-14` or
`2026-11-14T06:00Z`) this writes a complete site package: the horizon and its obstacles,
the terrain patches, the Sun and Earth series over 30 days with events, windows and
countdowns, the lunar-day calendar, the landing windows and slip tolerance of the three
example requirements, the uncertainty band of the default height-error model and the
mast-height trade. There is no landing ellipse. The countdowns count from the start of
the window, or from `--landing-utc` if that lies inside it; each says which
(`reference`, contract 5.4). The package root has the layout every root has (direction
table, site package, `index.json`), so a viewer reads it like any other.

| Option | Default | Meaning |
|---|---|---|
| `--days` | 30 | Length of the window |
| `--name`, `--site-id` | `Custom site 26.1000 N, 3.6000 E`, `custom-26-1000n-3-6000e` | How the site is called |
| `--landing-utc` | none | Planned landing: reference of the countdowns and of the slip tolerance |
| `--preset <id>` | all three | Example requirements to state (repeatable; `none` for no landing windows) |
| `--no-band` | band on | Leave out the uncertainty band |
| `--near-field` | off | Use the 5 m site rasters where the site lies on one, as `run --near-field` does |
| `--tables <root>` | none | Another package root to look in for a direction table (repeatable) |
| `--step`, `--heights`, `--azimuth-step`, `--max-range-km`, `--jobs`, `--dem-label` | as for `run` and `site` | |

**Direction table.** A table already in the package root, or in a root named with
`--tables`, is used instead of computing one if it reaches one record beyond the window
on both sides, was computed from the kernel set installed here and passes the contract
validator; a table found elsewhere is copied into the package root so that the root stays
complete. Events on a reused table agree with those on a table of the window within 1 s
(`core/tests/test_custom_site.py`). Computing the table of a month takes under a second,
so reuse matters for long windows only.

**What it prints.** On standard output, one line per stage as the stage begins, then the
directories written and, last, the index:

```
progress 1/6 checking the kernels and opening the terrain
progress 2/6 Sun and Earth directions: computing them for the window
progress 3/6 terrain horizon: 1440 azimuths out to 300 km
progress 4/6 Sun and Earth visibility, events, countdowns and landing windows: 30 days from 2026-11-14T00:00:00.000Z
progress 5/6 uncertainty band
progress 6/6 terrain patches and package files
<package root>/direction_table/dirtab-8b0176a10b9b3c9b
<package root>/site/custom-26-1000n-3-6000e/site-43b399bf78b6c900
<package root>/index.json
```

A line that starts with `progress ` is `progress <k>/<n> <text>`: `k` counts from 1 to
`n` (5 with `--no-band`), and the text is for showing. Every line is written as soon as
it is known. Errors go to standard error as `error: <what>: <sentence>`.

| Exit code | Meaning |
|---|---|
| 0 | The packages are written and passed the validator |
| 2 | The request cannot be carried out as stated (a date that is not UTC, a latitude outside -90 to 90, an unknown preset); nothing is written |
| 3 | Something that must be installed on this machine is missing; one `error:` line for each thing, nothing is written |

**What must be installed** ([docs/setup.md](../docs/setup.md) does all of it):

1. Python 3.11 or newer with the two packages of the repository:
   `pip install -e "core[test]" -e data` (numpy, jsonschema, spiceypy).
2. The SPICE kernels, 79 MB, once: `python -m lsncore.ephem.fetch_kernels`. Five files
   are needed; with the four optional ones the direction table also holds the orientation
   of the Earth and the package the ground-station windows.
3. Elevation products that cover the site, under the data root (`LSN_DATA_ROOT`, default
   `C:\lsn-data` on Windows, `~/lsn-data` elsewhere): `python -m lsn_data fetch` and
   `python -m lsn_data pyramid` install the south-polar pair (3.7 GB and 2.4 GB of
   overview levels). A site elsewhere needs the north-polar pair or a global product;
   `python -m lsn_data fetch --help` lists them, [data/README.md](../data/README.md)
   describes them.

**What it prints when something is missing** (exit code 3, on standard error; folder
names are those of the machine):

```
error: kernels: 5 of 5 kernel files are missing in C:\lsn-data\kernels (naif0012.tls, pck00011.tpc, de440s.bsp, moon_pa_de440_200625.bpc, moon_de440_250416.tf). Download them once with: python -m lsncore.ephem.fetch_kernels (docs/setup.md)
error: terrain: no elevation product is installed. Data root: C:\lsn-data. Install the elevation products with: python -m lsn_data fetch, then python -m lsn_data pyramid (docs/setup.md)
```

If products are installed but none reaches the site, the terrain line says so instead and
names the products that are not installed:
`error: terrain: no elevation data within 300 km of latitude 26.1, longitude 3.6; products not installed: […]`.
Both lines appear together when both are missing.

**Time**, the whole process from its start to validated packages, 30 days, defaults, on
the laptop of the run times below (14 November 2026):

| Site | Processors at 3 % load | At about 30 % load from other work |
|---|---|---|
| 26.1 N, 3.6 E (global product, 118 m) | 12.3 s | 20.1 to 21.2 s |
| Shackleton rim record (20 m product) | 12.9 s (13.8 s with `--jobs 1`) | 25.3 to 26.9 s |

With `--near-field` on a 5 m raster one run each was measured, while other work was
running: 23.7 s at the Shackleton record and 32.6 s near Mons Malapert (11 s of it the
horizon). These two are not idle-machine figures. The test limit is 30 s without the
near field, best of three on a machine that is doing nothing else.

## Run times

Measured on 14 November 2026 on one laptop (20 logical processors, Windows 11), each as a
fresh `python -m lsncore ...` process from its start to validated packages. South-polar
LOLA products, hourly series, six observer heights, default `--jobs` (8 here).

| Request | Time |
|---|---|
| One custom site, horizon and terrain patches, no dates (`lsncore site`) | 3.5 to 4.4 s |
| One site, 30 days, calendar and mast trade | 11 s |
| One custom coordinate, 30 days, three presets and uncertainty band, no ellipse (`lsncore custom`) | 12.3 to 12.9 s |
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
