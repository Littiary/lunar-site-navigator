# Science core

Python package `lsncore`. It computes every number of the project and writes it to
versioned packages; see [the contract](../docs/contract/SPEC.md).

## Setup

```
python -m venv .venv
.venv/Scripts/python -m pip install -e "core[dev]"     # Windows; use .venv/bin/python elsewhere
.venv/Scripts/python -m pytest core
```

## Commands

```
python -m lsncore run <scenario.json> --out <package root>      # every site of a scenario
python -m lsncore site --lat -89.5 --lon 200 --name "Test" --out <package root> --synthetic
python -m lsncore sample                                        # regenerate docs/contract/sample
python -m lsncore validate <package dir | json file> ...        # check against the contract
```

At this stage `run` and `site` only execute the synthetic generator (`--synthetic`, or a
scenario with `"synthetic": true`): the walking skeleton. Its numbers are invented and
flagged as such.

## Layout

| Module | Content | Stream |
|---|---|---|
| `lsncore/contract/` | Package writer, reader, validator | A |
| `lsncore/timeline.py` | `TimeGrid`, `IntervalSet` (window algebra) | A |
| `lsncore/geometry.py` | Site frame, great-circle steps, topocentric direction | A |
| `lsncore/scenario.py` | Scenario file | A |
| `lsncore/results.py`, `lsncore/packaging.py` | Result objects and the package builder | A |
| `lsncore/synthetic.py` | Invented stand-ins for the skeleton and the contract sample | A |
| `lsncore/ephem/`, `lsncore/events/` | Ephemeris, direction table, event finder | B |
