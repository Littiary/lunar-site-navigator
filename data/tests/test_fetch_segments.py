"""Parallel byte-range download: the assembled file equals the source, also when resuming a partial file."""

import hashlib
import http.server
import re
import threading

import pytest

from lsn_data import fetch


class _RangeHandler(http.server.BaseHTTPRequestHandler):
    payload = b""

    def log_message(self, *a):
        pass

    def do_GET(self):
        data = self.payload
        m = re.match(r"bytes=(\d+)-(\d*)", self.headers.get("Range", ""))
        if m:
            a = int(m.group(1))
            b = int(m.group(2)) if m.group(2) else len(data) - 1
            body = data[a : b + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {a}-{b}/{len(data)}")
        else:
            body = data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def server():
    _RangeHandler.payload = bytes((i * 7919) % 251 for i in range(3_000_000))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _RangeHandler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}/f.img", _RangeHandler.payload
    srv.shutdown()


@pytest.mark.parametrize("already", [0, 1_234_567])
def test_segmented_download_equals_source(tmp_path, server, monkeypatch, already):
    url, payload = server
    monkeypatch.setattr(fetch, "SEGMENT_MIN_BYTES", 1)
    dest = tmp_path / "f.img"
    if already:
        (tmp_path / "f.img.part").write_bytes(payload[:already])
    fetch.download(url, dest, len(payload), segments=5)
    assert hashlib.sha256(dest.read_bytes()).digest() == hashlib.sha256(payload).digest()
    assert not list(tmp_path.glob("*.seg*")) and not list(tmp_path.glob("*.segments"))
