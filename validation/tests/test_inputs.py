"""Downloaded inputs of the validation scripts: location outside the checkout, and the committed records as the reference.

None of these tests needs the downloads or the network.
"""

import hashlib
import io
import json
from pathlib import Path

import pytest

from lsncore.ephem import kernels
from validation import inputs
from validation.lro_images import fetch as lro_fetch
from validation.pgda import fetch as pgda_fetch

REPO = Path(__file__).resolve().parents[2]


class _Response(io.BytesIO):
    headers = {"Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _record(name: str, data: bytes) -> dict:
    return {"name": name, "url": "https://example.invalid/" + name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "server_last_modified": None, "retrieved_utc": "2026-11-14T00:00:00Z"}


def test_inputs_are_kept_outside_the_checkout_by_default(monkeypatch):
    for name in ("LSN_PGDA_DIR", "LSN_LRO_DIR", kernels.DATA_ROOT_ENV):
        monkeypatch.delenv(name, raising=False)
    for directory, expected in ((pgda_fetch.cache_dir(), "pgda"), (lro_fetch.cache_dir(), "lro")):
        assert directory == kernels.data_root() / "validation" / expected
        assert REPO != directory.resolve() and REPO not in directory.resolve().parents


def test_the_data_root_variable_moves_them_and_each_has_its_own_override(monkeypatch, tmp_path):
    monkeypatch.delenv("LSN_PGDA_DIR", raising=False)
    monkeypatch.delenv("LSN_LRO_DIR", raising=False)
    monkeypatch.setenv(kernels.DATA_ROOT_ENV, str(tmp_path))
    assert pgda_fetch.cache_dir() == tmp_path / "validation" / "pgda"
    assert lro_fetch.cache_dir() == tmp_path / "validation" / "lro"
    monkeypatch.setenv("LSN_LRO_DIR", str(tmp_path / "images"))
    assert lro_fetch.cache_dir() == tmp_path / "images"
    assert pgda_fetch.cache_dir() == tmp_path / "validation" / "pgda"


def test_committed_records_cover_every_file_the_fetch_scripts_download():
    recorded = inputs.read_records(pgda_fetch.MANIFEST)
    assert sorted(recorded) == sorted(relative.split("/")[-1] for relative in pgda_fetch.FILES)
    assert list(inputs.read_records(lro_fetch.MANIFEST)) == [lro_fetch.BROWSE_NAME]
    for record in list(recorded.values()) + list(inputs.read_records(lro_fetch.MANIFEST).values()):
        assert len(record["sha256"]) == 64 and record["bytes"] > 0 and record["url"].startswith("http") and record["retrieved_utc"]


def test_a_matching_download_keeps_the_record_and_a_present_file_is_not_fetched_again(monkeypatch, tmp_path):
    record, calls = _record("map.img", b"published map"), []

    def urlopen(request, timeout=0):
        calls.append(request.full_url)
        return _Response(b"published map")

    monkeypatch.setattr(inputs.urllib.request, "urlopen", urlopen)
    entry, done = inputs.fetch_file(record["url"], tmp_path / "map.img", record)
    assert entry is record and done == "fetched" and (tmp_path / "map.img").read_bytes() == b"published map"
    entry, done = inputs.fetch_file(record["url"], tmp_path / "map.img", record)
    assert entry is record and done == "cached" and len(calls) == 1


def test_a_download_that_differs_from_its_record_is_refused_and_nothing_is_kept(monkeypatch, tmp_path):
    record = _record("map.img", b"published map")
    monkeypatch.setattr(inputs.urllib.request, "urlopen", lambda request, timeout=0: _Response(b"a different file"))
    with pytest.raises(RuntimeError, match="is not the recorded one"):
        inputs.fetch_file(record["url"], tmp_path / "map.img", record)
    assert list(tmp_path.iterdir()) == []
    entry, done = inputs.fetch_file(record["url"], tmp_path / "map.img", record, update=True)
    assert done == "fetched and recorded" and entry["sha256"] == hashlib.sha256(b"a different file").hexdigest()


def test_the_manifest_is_rewritten_only_when_its_content_changes(tmp_path):
    path = tmp_path / "files.json"
    manifest = {"description": "test", "files": [_record("map.img", b"published map")]}
    assert inputs.write_manifest(path, manifest) is True
    stamp = path.stat().st_mtime_ns
    assert inputs.write_manifest(path, json.loads(json.dumps(manifest))) is False
    assert path.stat().st_mtime_ns == stamp
