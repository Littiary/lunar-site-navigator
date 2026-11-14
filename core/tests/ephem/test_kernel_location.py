"""Where the kernels live, and what happens when they are absent or differ from their record.

None of these tests needs the kernels or the network.
"""

import hashlib
import io
import json
import urllib.error
from pathlib import Path

import pytest

from lsncore.ephem import kernels

REPO = Path(__file__).resolve().parents[3]


@pytest.fixture
def clean_pool():
    """Leave the SPICE kernel pool as it was found."""
    loaded, stations = kernels._LOADED, kernels._STATIONS_LOADED
    kernels.unload()
    yield
    kernels.unload()
    if stations:
        kernels.load_stations()
    elif loaded:
        kernels.load()


def test_kernels_are_kept_outside_the_checkout_by_default(monkeypatch):
    monkeypatch.delenv(kernels.KERNEL_DIR_ENV, raising=False)
    monkeypatch.delenv(kernels.DATA_ROOT_ENV, raising=False)
    directory = kernels.kernel_dir().resolve()
    assert directory == (kernels.data_root() / "kernels").resolve()
    assert REPO != directory and REPO not in directory.parents


def test_one_variable_moves_the_data_root_and_a_second_one_only_the_kernels(monkeypatch, tmp_path):
    monkeypatch.delenv(kernels.KERNEL_DIR_ENV, raising=False)
    monkeypatch.setenv(kernels.DATA_ROOT_ENV, str(tmp_path / "root"))
    assert kernels.kernel_dir() == tmp_path / "root" / "kernels"
    monkeypatch.setenv(kernels.KERNEL_DIR_ENV, str(tmp_path / "elsewhere"))
    assert kernels.kernel_dir() == tmp_path / "elsewhere"
    assert kernels.data_root() == tmp_path / "root"


def test_data_root_is_the_one_of_the_data_stream(monkeypatch, tmp_path):
    paths = pytest.importorskip("lsn_data.paths")
    monkeypatch.delenv(kernels.DATA_ROOT_ENV, raising=False)
    assert kernels.data_root() == paths.data_root()
    monkeypatch.setenv(kernels.DATA_ROOT_ENV, str(tmp_path))
    assert kernels.data_root() == paths.data_root() == tmp_path


def test_loading_without_kernels_names_the_file_the_folder_and_the_command(clean_pool, monkeypatch, tmp_path):
    monkeypatch.setenv(kernels.KERNEL_DIR_ENV, str(tmp_path))
    assert kernels.missing() == [kernel.name for kernel in kernels.KERNEL_SET]
    with pytest.raises(kernels.KernelsMissing) as error:
        kernels.load()
    message = str(error.value)
    assert "naif0012.tls" in message and str(tmp_path) in message and kernels.FETCH_COMMAND in message
    assert isinstance(error.value, FileNotFoundError)


class _Response(io.BytesIO):
    headers = {"Last-Modified": "Thu, 01 Jan 2026 00:00:00 GMT"}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def _manifest_for(tmp_path, monkeypatch, payloads: dict) -> Path:
    """A manifest in a temporary place that records ``payloads`` for the first base and the first station kernel."""
    base, station = kernels.KERNEL_SET[0], kernels.STATION_KERNEL_SET[0]
    monkeypatch.setattr(kernels, "KERNEL_SET", (base,))
    monkeypatch.setattr(kernels, "STATION_KERNEL_SET", (station,))
    monkeypatch.setenv(kernels.KERNEL_DIR_ENV, str(tmp_path / "kernels"))

    def entry(kernel):
        data = payloads[kernel.name]
        return {"name": kernel.name, "kind": kernel.kind, "role": kernel.role, "url": kernel.url, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                "server_last_modified": None, "retrieved_utc": "2026-11-14T00:00:00Z"}

    manifest = {"description": kernels.MANIFEST_DESCRIPTION, "source_root": kernels.NAIF_ROOT, "kernels": [entry(base)], "station_kernels": [entry(station)]}
    path = tmp_path / "kernel_manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    monkeypatch.setattr(kernels, "MANIFEST_PATH", path)
    return path


def test_a_matching_download_leaves_the_committed_record_untouched(monkeypatch, tmp_path):
    base, station = kernels.KERNEL_SET[0], kernels.STATION_KERNEL_SET[0]
    served = {base.name: b"base kernel", station.name: b"station kernel"}
    path = _manifest_for(tmp_path, monkeypatch, served)
    before = path.read_bytes()
    monkeypatch.setattr(kernels.urllib.request, "urlopen", lambda request, timeout=0: _Response(served[request.full_url.rsplit("/", 1)[-1]]))
    manifest = kernels.fetch()
    assert path.read_bytes() == before
    assert manifest["kernels"][0]["retrieved_utc"] == "2026-11-14T00:00:00Z"
    assert (tmp_path / "kernels" / base.name).read_bytes() == b"base kernel"
    assert kernels.missing(stations=True) == []


def test_a_download_that_differs_from_its_record_is_refused_and_nothing_is_written(monkeypatch, tmp_path):
    base, station = kernels.KERNEL_SET[0], kernels.STATION_KERNEL_SET[0]
    path = _manifest_for(tmp_path, monkeypatch, {base.name: b"base kernel", station.name: b"station kernel"})
    before = path.read_bytes()
    monkeypatch.setattr(kernels.urllib.request, "urlopen", lambda request, timeout=0: _Response(b"another file under the same name"))
    with pytest.raises(RuntimeError, match="is not the recorded one"):
        kernels.fetch()
    assert path.read_bytes() == before
    assert not (tmp_path / "kernels" / base.name).exists()


def test_a_station_kernel_the_server_no_longer_offers_does_not_stop_the_base_set(monkeypatch, tmp_path):
    base, station = kernels.KERNEL_SET[0], kernels.STATION_KERNEL_SET[0]
    path = _manifest_for(tmp_path, monkeypatch, {base.name: b"base kernel", station.name: b"station kernel"})
    before = path.read_bytes()

    def urlopen(request, timeout=0):
        if request.full_url.endswith(station.name):
            raise urllib.error.HTTPError(request.full_url, 404, "Not Found", None, None)
        return _Response(b"base kernel")

    monkeypatch.setattr(kernels.urllib.request, "urlopen", urlopen)
    unavailable = []
    kernels.fetch(unavailable=unavailable)
    assert [item["name"] for item in unavailable] == [station.name]
    assert path.read_bytes() == before
    assert kernels.missing() == [] and kernels.missing(stations=True) == [station.name]
    assert kernels.stations_available() is False
    # Without the list for unavailable files the same situation is an error, as it is for the base set.
    with pytest.raises(RuntimeError, match="could not be downloaded"):
        kernels.fetch()
