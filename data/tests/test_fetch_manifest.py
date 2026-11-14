"""Download (resume, size check) and manifest tests against a local HTTP server. No network needed."""

import hashlib
import http.server
import threading

import pytest

from lsn_data import fetch, manifest as mf

PAYLOAD = bytes(range(256)) * 4000  # ~1 MB


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-Length", str(len(PAYLOAD)))
        self.send_header("Last-Modified", "Thu, 06 Jul 2017 13:47:16 GMT")
        self.end_headers()

    def do_GET(self):
        rng = self.headers.get("Range")
        if rng:
            start = int(rng.split("=")[1].split("-")[0])
            self.send_response(206)
            body = PAYLOAD[start:]
            self.send_header("Content-Range", f"bytes {start}-{len(PAYLOAD)-1}/{len(PAYLOAD)}")
        else:
            self.send_response(200)
            body = PAYLOAD
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def server():
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/file.bin"
    srv.shutdown()


def test_head_and_download(server, tmp_path):
    meta = fetch.head(server)
    assert meta["size"] == len(PAYLOAD)
    dest = tmp_path / "a" / "file.bin"
    fetch.download(server, dest, meta["size"])
    assert dest.read_bytes() == PAYLOAD
    assert not dest.with_name("file.bin.part").exists()


def test_download_resumes_a_partial_file(server, tmp_path):
    dest = tmp_path / "file.bin"
    part = tmp_path / "file.bin.part"
    part.write_bytes(PAYLOAD[:300_000])
    fetch.download(server, dest, len(PAYLOAD))
    assert hashlib.sha256(dest.read_bytes()).hexdigest() == hashlib.sha256(PAYLOAD).hexdigest()


def test_manifest_verify_detects_changes(tmp_path):
    f = tmp_path / "raw" / "x.bin"
    f.parent.mkdir()
    f.write_bytes(b"hello")
    m = {"files": {"raw/x.bin": {"size_bytes": 5, "sha256": mf.sha256_file(f)}}}
    assert mf.verify(m, tmp_path) == []
    f.write_bytes(b"hellp")
    assert "sha256 mismatch" in mf.verify(m, tmp_path)[0]
    f.write_bytes(b"hell")
    assert "size mismatch" in mf.verify(m, tmp_path)[0]
    f.unlink()
    assert "missing" in mf.verify(m, tmp_path)[0]
    assert mf.verify({"files": {}}, tmp_path)  # an empty manifest is a failure


def test_manifest_roundtrip(tmp_path):
    p = tmp_path / "m.json"
    mf.save(p, {"files": {"b": {"x": 1}, "a": {"x": 2}}})
    m = mf.load(p)
    assert list(m["files"]) == ["a", "b"] and m["schema_version"] == mf.SCHEMA_VERSION
