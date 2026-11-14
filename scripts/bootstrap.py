"""Set up a fresh clone so that every result can be reproduced and every test can run.

Run with the system Python (3.11 or newer), from any folder::

    python scripts/bootstrap.py [--data-root PATH] [--no-terrain] [--no-validation-inputs] [--test]

What it does, in this order (each command is printed before it runs):

1. creates the virtual environment ``.venv`` in this checkout;
2. installs the two packages of the repository in editable mode (``data`` and ``core``)
   with the third-party versions of ``scripts/constraints.txt``;
3. checks that the environment imports the code of this checkout;
4. downloads the SPICE kernels (79 MB) and checks them against the committed checksums;
5. downloads the inputs of the validation scripts (published illumination maps, 154 MB,
   and one LROC browse image, 8 MB) and checks them against the committed checksums;
6. downloads the LOLA elevation products (3.7 GB), checks them against the committed
   manifest and builds their overview levels (2.4 GB, computed locally);
7. says whether the setup left the working tree unchanged, and how to run the tests.

Nothing is downloaded into the checkout. Everything goes to the data root: ``--data-root``
or the environment variable ``LSN_DATA_ROOT``; without either, ``C:\\lsn-data`` on Windows
and ``~/lsn-data`` elsewhere. Files that are already there and match their record are not
downloaded again, so the script can be repeated and several checkouts can share one data
root. ``--no-terrain`` and ``--no-validation-inputs`` leave out steps 6 and 5; the tests
that need those inputs are then skipped, each with the command that fetches its input.

The same steps as single commands are in ``docs/setup.md``.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV = ROOT / ".venv"
PYTHON = VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
MINIMUM = (3, 11)


def run(command: list, env: dict, check: bool = True) -> int:
    print(f"\n$ {' '.join(str(part) for part in command)}", flush=True)
    code = subprocess.run([str(part) for part in command], cwd=ROOT, env=env).returncode
    if check and code != 0:
        sys.exit(f"\nSetup stopped: the command above ended with exit code {code}.")
    return code


def output(command: list, env: dict) -> str:
    return subprocess.run([str(part) for part in command], cwd=ROOT, env=env, capture_output=True, text=True).stdout.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-root", help="folder for all downloaded inputs (sets LSN_DATA_ROOT for this run)")
    parser.add_argument("--no-terrain", action="store_true", help="do not download the LOLA elevation products (3.7 GB) or build their overview levels")
    parser.add_argument("--no-validation-inputs", action="store_true", help="do not download the published illumination maps and the LROC browse image (162 MB)")
    parser.add_argument("--test", action="store_true", help="run the whole test suite at the end")
    args = parser.parse_args()

    if sys.version_info < MINIMUM:
        sys.exit(f"Python {MINIMUM[0]}.{MINIMUM[1]} or newer is needed; this is {sys.version.split()[0]}.")

    env = dict(os.environ)
    if args.data_root:
        env["LSN_DATA_ROOT"] = str(Path(args.data_root).resolve())
    before = output(["git", "status", "--porcelain"], env)

    # 1. environment
    if not PYTHON.exists():
        run([sys.executable, "-m", "venv", VENV], env)

    # 2. packages of this repository, editable, with pinned third-party versions
    run([PYTHON, "-m", "pip", "install", "--quiet", "--disable-pip-version-check", "-c", "scripts/constraints.txt", "-e", "data[test]", "-e", "core[test,validation]"], env)

    # 3. the environment must import this checkout
    for name in ("lsncore", "lsn_data"):
        found = output([PYTHON, "-c", f"import {name}, pathlib; print(pathlib.Path({name}.__file__).resolve().parent)"], env)
        if not found:
            sys.exit(f"
Setup stopped: {name} cannot be imported in {VENV}.")
        location = Path(found)
        if ROOT not in location.parents:
            sys.exit(f"\nSetup stopped: {name} is imported from {location}, not from this checkout ({ROOT}).")
    print(f"\nlsncore and lsn_data are imported from this checkout ({ROOT}).")

    # 4. SPICE kernels
    run([PYTHON, "-m", "lsncore.ephem.fetch_kernels"], env)

    # 5. inputs of the validation scripts
    if not args.no_validation_inputs:
        run([PYTHON, "-m", "validation.pgda.fetch"], env)
        run([PYTHON, "-m", "validation.lro_images.fetch"], env)

    # 6. LOLA elevation products
    if not args.no_terrain:
        run([PYTHON, "-m", "lsn_data", "fetch"], env)
        run([PYTHON, "-m", "lsn_data", "verify"], env)
        run([PYTHON, "-m", "lsn_data", "pyramid"], env)

    # 7. summary
    data_root = output([PYTHON, "-c", "from lsncore.ephem import kernels; print(kernels.data_root())"], env)
    after = output(["git", "status", "--porcelain"], env)
    print("\nSetup finished.")
    print(f"  Data root: {data_root}")
    if args.data_root:
        print(f"  This run used --data-root. Set LSN_DATA_ROOT={env['LSN_DATA_ROOT']} in your shell before running the tests or the tools.")
    print("  Working tree: " + ("unchanged by the setup." if after == before else "CHANGED by the setup; `git status` shows the files. A download did not match its committed record."))
    tests = [PYTHON.relative_to(ROOT).as_posix(), "-m", "pytest", "core", "validation", "data"]
    print(f"  Run the tests from the repository root: {' '.join(tests)}")
    if args.test:
        sys.exit(run([PYTHON, "-m", "pytest", "core", "validation", "data"], env, check=False))


if __name__ == "__main__":
    main()
