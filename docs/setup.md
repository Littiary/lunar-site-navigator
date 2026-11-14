# Setup from a fresh clone

This is the one setup path of the repository. It creates the Python environment, installs the two packages of the repository, downloads every input that is not committed, checks each download against a committed checksum, and runs the tests. It applies to the science core, the data scripts and the validation (`core/`, `data/`, `validation/`); the web pages and the Unreal scene only read the packages in `packages/` and have their own notes.

## Requirements

* Python 3.11 or newer (the committed results were computed with Python 3.14.7 on Windows 11).
* Git.
* About 6.5 GB of free disk space for the data root if the terrain is included, 250 MB without it.
* Network access to `naif.jpl.nasa.gov`, `imbrium.mit.edu`, `pds.lroc.im-ldi.com` and the Python package index.

## One command

```
git clone https://github.com/Littiary/lunar-site-navigator.git
cd lunar-site-navigator
python scripts/bootstrap.py --test
```

`scripts/bootstrap.py` prints every command before it runs it and stops at the first one that fails. Options:

| Option | Effect |
|---|---|
| `--data-root PATH` | Put all downloads under `PATH` (sets `LSN_DATA_ROOT` for this run; set the variable in your shell afterwards). |
| `--no-terrain` | Leave out the LOLA elevation products (3.7 GB download, 2.4 GB of overview levels built locally). Tests that need terrain are skipped. |
| `--no-validation-inputs` | Leave out the published illumination maps and the LROC browse image (162 MB). The two tests that read them are skipped. |
| `--test` | Run the whole test suite at the end. |

The script can be repeated: files that are present and match their record are not downloaded again, and overview levels that were built from the recorded elevation files are not rebuilt.

## The same steps by hand

From the repository root (on Linux and macOS the interpreter is `.venv/bin/python`):

```
python -m venv .venv
.venv/Scripts/python -m pip install -c scripts/constraints.txt -e "data[test]" -e "core[test,validation]"
.venv/Scripts/python -m lsncore.ephem.fetch_kernels
.venv/Scripts/python -m validation.pgda.fetch
.venv/Scripts/python -m validation.lro_images.fetch
.venv/Scripts/python -m lsn_data fetch
.venv/Scripts/python -m lsn_data verify              # see the note on verify below
.venv/Scripts/python -m lsn_data pyramid            # rebuilds the levels each time; the script skips this when they are present
.venv/Scripts/python -m pytest core validation data
```

`scripts/constraints.txt` pins the third-party versions with which the committed results were computed. The extras: `core[test]` is what the tests under `core/tests` need (pytest, SpiceyPy), `core[validation]` adds what `validation/` needs (Pillow), `data[test]` is pytest for `data/tests`.

Two notes on the elevation products, which the data scripts (`data/`) handle:

* `python -m lsn_data verify` compares every file of the committed manifest, which also lists whole-Moon products that the default download does not fetch; on a fresh data root it reports those as missing. The setup script compares only the files of the default products, with the manifest as committed, and downloads only if they are absent or differ.
* `python -m lsn_data fetch` writes the time of each download into the committed manifest, so after a first download `git status` shows `data/manifest/manifest.json` as changed. If `git diff` shows only times and no checksum, restore the file with `git checkout data/manifest/manifest.json`; the setup script says so at the end.

## Where the downloads go

Nothing is downloaded into the checkout. Everything goes to the **data root**, a folder outside the repository that several clones and worktrees can share:

* the environment variable `LSN_DATA_ROOT`, if set;
* otherwise `C:\lsn-data` on Windows and `~/lsn-data` elsewhere.

| Folder under the data root | Content | Size | Fetched by | Checked against |
|---|---|---|---|---|
| `kernels/` | NAIF SPICE kernels (9 files) | 79 MB | `python -m lsncore.ephem.fetch_kernels` | `core/lsncore/ephem/kernel_manifest.json` |
| `validation/pgda/` | LOLA illumination maps of the south pole (PGDA product 69) | 154 MB | `python -m validation.pgda.fetch` | `validation/pgda/files.json` |
| `validation/lro/` | one LROC NAC browse image | 8 MB | `python -m validation.lro_images.fetch` | `validation/lro_images/files.json` |
| `raw/lola/` | LOLA elevation products of the default set | 3.7 GB | `python -m lsn_data fetch` | `data/manifest/manifest.json` |
| `derived/` | overview levels of the elevation products, computed locally | 2.4 GB | `python -m lsn_data pyramid` | `pyramid.json` in each folder |

One variable moves everything. A single group can also be moved on its own with `LSN_KERNEL_DIR`, `LSN_PGDA_DIR` or `LSN_LRO_DIR`.

The committed records are the reference. For the kernels and the validation inputs, a download whose SHA-256 differs from its record is refused and nothing is kept; a download that matches leaves the record untouched, so the working tree of a fresh clone stays clean after the setup. Kernels are also checked against the manifest every time they are loaded.

## What the tests do without the inputs

Tests never read downloaded files from inside a checkout. A test that needs an input that is not in the data root is **skipped**, and the reason names the missing file and the command that fetches it:

| Missing | Effect |
|---|---|
| SPICE kernels | the ephemeris, event and validation tests that use SPICE are skipped |
| station kernels (same download) | the ground-station tests are skipped |
| LOLA products | tests marked as needing the terrain are skipped; validation results that need terrain are read from their stored tables |
| illumination maps, browse image | the two tests that re-read them are skipped; the stored results are still checked |

With every input present nothing is skipped. The suite then shows three expected failures (`xfailed`), each with its reason: two checkpoints of the data and core streams, and one validation check that fails its registered criterion and is kept visible (`validation/README.md`, section `lro_images/`).

## One environment per checkout

`lsncore` and `lsn_data` are installed in editable mode, so an environment imports the code of the checkout it was created in. Create the environment inside each clone or worktree (`scripts/bootstrap.py` does); the data root is shared. If the tests of one checkout are started with the environment of another, pytest stops at once and says so (`conftest.py` at the repository root).

## Limits

* The optional ground-station group of the kernel set includes a high-precision Earth orientation file (`earth_000101_270208_261113.bpc`, 5 MB). NAIF updates this file at least twice per week and its server holds only the current one (checked on 2026-11-14: one such file in `generic_kernels/pck/`). Once the recorded file is replaced, it can no longer be downloaded: `fetch_kernels` then says so and goes on, the ground-station tests are skipped, and the direct-to-Earth windows of the published packages can be recomputed exactly only with a copy of that file (a copy placed in the kernel folder is accepted if its checksum matches the manifest). The base set (directions of the Sun and the Earth, events, eclipses) uses dated files that NAIF keeps.
* The setup was tested on Windows 11 with Python 3.14.7. On other systems or Python versions the pinned versions may not be installable; without the constraints file the newest versions are installed and small numerical differences are possible.
* A first download of the elevation products was not repeated for this document: they were already in the data root and were checked against the manifest instead.
