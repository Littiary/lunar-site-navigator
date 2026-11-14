"""Locations of the data root and the committed manifest.

The data root is outside git. Set ``LSN_DATA_ROOT`` to move it; the default is
``C:\\lsn-data`` on Windows and ``~/lsn-data`` elsewhere. Layout::

    <root>/raw/lola/<PRODUCT_ID>/...      files exactly as fetched
    <root>/raw/lola/_docs/...             archive-level documents
    <root>/derived/<PRODUCT_ID>/...       pyramids and other derived files
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_VAR = "LSN_DATA_ROOT"


def data_root() -> Path:
    env = os.environ.get(ENV_VAR)
    if env:
        return Path(env)
    if os.name == "nt":
        return Path("C:/lsn-data")
    return Path.home() / "lsn-data"


def raw_dir(root: Path | None = None) -> Path:
    return (root or data_root()) / "raw" / "lola"


def derived_dir(root: Path | None = None) -> Path:
    return (root or data_root()) / "derived"


def repo_data_dir() -> Path:
    """The ``data/`` folder of the repository (parent of this package)."""
    return Path(__file__).resolve().parent.parent


def manifest_path() -> Path:
    return repo_data_dir() / "manifest" / "manifest.json"
