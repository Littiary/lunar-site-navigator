# Science core

Python package `lsncore`. It computes every number of the project and writes it to
versioned packages; see [the contract](../docs/contract/SPEC.md). The horizon method, its
checks and its limits are in [docs/method/horizon.md](../docs/method/horizon.md).

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
python -m lsncore run <scenario.json> --out <package root>
python -m lsncore validate <package dir | json file> ...
python -m lsncore sample                                  # regenerate docs/contract/sample
```

`site` computes the terrain horizon of one point (options: `--heights`, `--azimuth-step`,
`--max-range-km`). `run` computes every site of a scenario file; when the ephemeris
modules are installed and the scenario has a time window, it also writes the direction
table and the timeline of each site.

Terrain: by default the LOLA products under the data root of the data stream
(`LSN_DATA_ROOT`). `--dem-label <file.lbl>` (repeatable) opens other products of the same
format, for example the synthetic test raster `data/fixtures/synth_s90_100m.lbl`; a
package computed from a synthetic surface is flagged `synthetic`. `--synthetic` skips the
computation and writes invented numbers (the walking skeleton behind the contract sample).

## Layout

| Module | Content | Stream |
|---|---|---|
| `lsncore/contract/` | Package writer, reader, validator | A |
| `lsncore/horizon.py` | Terrain horizon on a sphere, several observer heights in one pass, far-field bound | A |
| `lsncore/dem.py` | Terrain interface; adapter for the data stream's reader; analytic terrain for tests | A |
| `lsncore/pipeline.py` | Scenario in, packages out; method cards of the horizon | A |
| `lsncore/timeline.py` | `TimeGrid`, `IntervalSet` (window algebra) | A |
| `lsncore/geometry.py` | Site frame, great-circle steps, topocentric direction | A |
| `lsncore/scenario.py` | Scenario file | A |
| `lsncore/results.py`, `lsncore/packaging.py` | Result objects and the package builder | A |
| `lsncore/synthetic.py` | Invented stand-ins for the skeleton and the contract sample | A |
| `lsncore/ephem/`, `lsncore/events/` | Ephemeris, direction table, event finder | B |
