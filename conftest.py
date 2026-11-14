"""Repository-wide test configuration: the tests must run against the code of this checkout.

``lsncore`` and ``lsn_data`` are installed in editable mode, so an environment belongs to
the checkout it was created in. Running the tests of one checkout with the environment of
another (a second clone, a git worktree) silently tests the other checkout's code. That
is refused here with the remedy, instead of failing later in some unrelated place.
"""

import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent


def pytest_configure(config):
    foreign = []
    for name in ("lsncore", "lsn_data"):
        try:
            module = importlib.import_module(name)
        except ImportError:
            continue  # not installed: the tests that need it say so themselves
        location = Path(module.__file__).resolve().parent
        if ROOT not in location.parents:
            foreign.append(f"{name} is imported from {location}")
    if foreign:
        raise pytest.UsageError(
            f"This environment does not belong to this checkout ({ROOT}): {'; '.join(foreign)}. "
            "Create the environment of this checkout with `python scripts/bootstrap.py` (see docs/setup.md)."
        )
