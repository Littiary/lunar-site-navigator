"""The manifest: one record per downloaded file, committed to git.

Record fields
-------------
path             file path relative to the data root (forward slashes)
role             data | label | label_xml | doc | reference (analysis reference, not terrain)
product_id       e.g. LDEM_80S_20M (read from the label's FILE_NAME), or ``_docs``
product_version  PRODUCT_VERSION_ID from the label (data and label files), else null
data_set_id      DATA_SET_ID from the label, else null
source_url       the URL the bytes were fetched from
equivalent_urls  other URLs that serve the same file
size_bytes       size on disk
sha256           SHA-256 of the file
retrieved_utc    when the bytes were fetched (ISO 8601, UTC)
hashed_utc       when the SHA-256 was last computed
http_last_modified, http_etag   as sent by the server at fetch time
cross_checks     list of {url, sha256, size_bytes, matches, checked_utc}: independent
                 re-reads of the same file from another source
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str | Path, chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def load(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": SCHEMA_VERSION, "files": {}}
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, manifest: dict) -> None:
    manifest["schema_version"] = SCHEMA_VERSION
    manifest["generated_utc"] = utc_now()
    manifest["files"] = dict(sorted(manifest["files"].items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)


def verify(manifest: dict, root: Path) -> list[str]:
    """Check every manifest record against the files on disk.

    Returns a list of problems; an empty list means every file exists and its
    size and SHA-256 match.
    """
    problems: list[str] = []
    if not manifest.get("files"):
        problems.append("manifest has no files")
    for rel, rec in manifest.get("files", {}).items():
        p = root / rel
        if not p.is_file():
            problems.append(f"missing: {rel}")
            continue
        size = p.stat().st_size
        if size != rec["size_bytes"]:
            problems.append(f"size mismatch: {rel}: disk {size}, manifest {rec['size_bytes']}")
            continue
        digest = sha256_file(p)
        if digest != rec["sha256"]:
            problems.append(f"sha256 mismatch: {rel}: disk {digest}, manifest {rec['sha256']}")
    return problems
