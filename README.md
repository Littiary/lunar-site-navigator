# Lunar Site Navigator

Team **Kestro Aerospace** — NASA Space Apps Challenge 2026, Aachen.
Challenge: *Lunar Landing Site Navigator*.

For a chosen point on the Moon, the tool computes the local 360° terrain horizon from NASA LOLA elevation data and reports when the Sun and the Earth are above that horizon: the lighting and direct-to-Earth communication windows a mission planner needs when comparing landing sites and dates.

## Status

Work in progress during the hackathon (14–15 November 2026). This file is updated as parts land.

## Layout

| Folder | Content |
|---|---|
| `core/` | Science core (Python): horizon, ephemeris, event finding. Writes versioned result packages. |
| `data/` | Download and processing scripts for NASA data. No raw data is committed. |
| `web/` | Charts, evidence page and viewers. They only read packages. |
| `unreal/` | Unreal Engine scene and planner interface. It only reads packages. |
| `docs/` | Method notes, validation results, credits. |

## Reproducing the results

```
git clone https://github.com/Littiary/lunar-site-navigator.git
cd lunar-site-navigator
python scripts/bootstrap.py --test
```

This creates the Python environment, installs the packages, downloads the SPICE kernels, the LOLA elevation products and the validation inputs to a data folder outside the repository (`LSN_DATA_ROOT`), checks every download against a committed checksum and runs the tests. Options, the same steps as single commands, sizes and limits are in [docs/setup.md](docs/setup.md).

## Data and credits

Every third-party dataset, library and asset is listed with its licence and source in [CREDITS.md](CREDITS.md).

## Use of AI

Parts of the code and documentation in this repository were written with AI coding assistants. The team defines the scope, chooses the data, writes the acceptance thresholds and reviews every change. Details are recorded in [CREDITS.md](CREDITS.md).

## Licence

Apache License 2.0. See [LICENSE](LICENSE).
