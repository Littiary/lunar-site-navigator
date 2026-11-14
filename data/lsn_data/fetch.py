"""Resumable downloader that writes the manifest.

Only the standard library is used. Downloads go to ``<name>.part`` and are
renamed when the size equals the server's Content-Length.
"""

from __future__ import annotations

import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import catalog, manifest as mf
from .paths import manifest_path, raw_dir
from .pdslabel import parse_label

USER_AGENT = "lsn-data/0.1 (Kestro Aerospace; NASA Space Apps 2026 research code)"
CHUNK = 1 << 20
_print_lock = threading.Lock()
_manifest_lock = threading.Lock()


def log(msg: str) -> None:
    with _print_lock:
        print(msg, flush=True)


def _urls(spec: catalog.FileSpec, prefer: str) -> list[str]:
    pds = spec.pds_path if spec.pds_path.startswith("http") else f"{catalog.PDS_ROOT}/{spec.pds_path}"
    if spec.mit_path and spec.mit_path.startswith("http"):
        mit = spec.mit_path
    else:
        mit = f"{catalog.MIT_ROOT}/{spec.mit_path}" if spec.mit_path else None
    if prefer == "mit" and mit:
        return [mit, pds]
    return [pds] + ([mit] if mit else [])


def _open(url: str, headers: dict | None = None, method: str = "GET", timeout: float = 60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})}, method=method)
    return urllib.request.urlopen(req, timeout=timeout)


def head(url: str) -> dict:
    with _open(url, method="HEAD") as r:
        return {
            "size": int(r.headers["Content-Length"]),
            "last_modified": r.headers.get("Last-Modified"),
            "etag": r.headers.get("ETag"),
        }


SEGMENT_MIN_BYTES = 64 << 20


def _download_range(url: str, seg: Path, start: int, stop: int, retries: int = 12) -> None:
    """Bytes [start, stop) of ``url`` into ``seg``, resuming from what ``seg`` already holds."""
    attempt = 0
    while True:
        have = seg.stat().st_size if seg.exists() else 0
        if have == stop - start:
            return
        if have > stop - start:
            seg.unlink()
            continue
        try:
            with _open(url, {"Range": f"bytes={start + have}-{stop - 1}"}) as r:
                if r.status != 206:
                    raise OSError(f"server ignored the range request (status {r.status})")
                with open(seg, "ab") as f:
                    while block := r.read(CHUNK):
                        f.write(block)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            attempt += 1
            if attempt > retries:
                raise
            log(f"  {seg.name}: {type(e).__name__}: {e}; retry {attempt}/{retries}")
            time.sleep(min(5 * attempt, 30))


def _download_segments(url: str, part: Path, expected_size: int, segments: int) -> None:
    """Fetch the rest of ``part`` in ``segments`` parallel ranges, then append them in order.

    The mirror limits the rate per connection, so parallel ranges are much faster. Each range resumes on its own.
    """
    have = part.stat().st_size if part.exists() else 0
    edges = [have + (expected_size - have) * i // segments for i in range(segments + 1)]
    segs = [part.with_name(f"{part.name}.seg{i}") for i in range(segments)]
    # a set of segments from an earlier run with another split cannot be reused
    old = sorted(part.parent.glob(part.name + ".seg*"))
    meta = part.with_name(part.name + ".segments")
    plan = f"{have} {expected_size} {segments}"
    if old and (not meta.exists() or meta.read_text() != plan):
        for f in old:
            f.unlink()
    meta.write_text(plan)
    t0 = time.time()

    def progress():
        while not done.is_set():
            done.wait(30)
            got = sum(s.stat().st_size for s in segs if s.exists())
            log(f"  {part.name[:-5]}: {(have + got)/1e6:,.0f}/{expected_size/1e6:,.0f} MB, {got/1e6/max(time.time()-t0,1):.2f} MB/s")

    done = threading.Event()
    threading.Thread(target=progress, daemon=True).start()
    try:
        with ThreadPoolExecutor(max_workers=segments) as ex:
            list(ex.map(lambda i: _download_range(url, segs[i], edges[i], edges[i + 1]), range(segments)))
    finally:
        done.set()
    with open(part, "ab") as out:
        for sgm in segs:
            with open(sgm, "rb") as f:
                while block := f.read(CHUNK * 8):
                    out.write(block)
    for sgm in segs:
        sgm.unlink()
    meta.unlink()


def download(url: str, dest: Path, expected_size: int, retries: int = 12, segments: int = 1) -> None:
    """Download ``url`` to ``dest`` with resume and retries (``segments`` parallel ranges for large files)."""
    part = dest.with_name(dest.name + ".part")
    dest.parent.mkdir(parents=True, exist_ok=True)
    have0 = part.stat().st_size if part.exists() else 0
    if segments > 1 and expected_size - have0 >= SEGMENT_MIN_BYTES:
        _download_segments(url, part, expected_size, segments)
    attempt = 0
    t0 = time.time()
    last_report = 0.0
    while True:
        have = part.stat().st_size if part.exists() else 0
        if have == expected_size:
            break
        if have > expected_size:
            part.unlink()
            have = 0
        try:
            headers = {"Range": f"bytes={have}-"} if have else {}
            with _open(url, headers) as r:
                if have and r.status != 206:
                    have = 0  # server ignored Range: restart
                with open(part, "ab" if have else "wb") as f:
                    while block := r.read(CHUNK):
                        f.write(block)
                        have += len(block)
                        now = time.time()
                        if now - last_report > 20:
                            last_report = now
                            rate = have / max(now - t0, 1e-9) / 1e6
                            log(f"  {dest.name}: {have/1e6:,.0f}/{expected_size/1e6:,.0f} MB")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as e:
            attempt += 1
            if attempt > retries:
                raise
            log(f"  {dest.name}: {type(e).__name__}: {e}; retry {attempt}/{retries}")
            time.sleep(min(5 * attempt, 30))
            continue
        if part.stat().st_size != expected_size:
            attempt += 1
            if attempt > retries:
                raise RuntimeError(f"{dest.name}: size {part.stat().st_size} != {expected_size}")
            continue
        break
    part.replace(dest)


def _label_info(label_path: Path) -> dict:
    lab = parse_label(label_path)
    return {
        "product_id": str(lab.get("FILE_NAME", "")).removesuffix(".IMG").removesuffix(".img") or None,
        "product_version": lab.get("PRODUCT_VERSION_ID"),
        "data_set_id": lab.get("DATA_SET_ID"),
    }


def fetch_file(prod: catalog.Product, spec: catalog.FileSpec, root: Path, prefer: str, force: bool, mpath: Path, segments: int = 1) -> dict:
    dest = root / prod.base / prod.product_id / spec.local_name
    urls = _urls(spec, prefer)
    meta = None
    used = None
    err = None
    for u in urls:
        try:
            meta = head(u)
            used = u
            break
        except (urllib.error.URLError, OSError) as e:
            err = e
            log(f"  {spec.local_name}: {u} unreachable ({e}); trying next source")
    if meta is None:
        raise RuntimeError(f"{spec.local_name}: no source reachable: {err}")

    rel = dest.relative_to(root).as_posix()
    with _manifest_lock:
        prev = mf.load(mpath)["files"].get(rel)
    fetched_now = False
    if force or not dest.exists() or dest.stat().st_size != meta["size"]:
        log(f"fetch {rel} from {used} ({meta['size']/1e6:,.1f} MB)")
        download(used, dest, meta["size"], segments=segments)
        fetched_now = True
    digest = mf.sha256_file(dest)
    if prev and prev["sha256"] == digest and not fetched_now:
        retrieved = prev["retrieved_utc"]
        used_url = prev["source_url"]
        cross = prev.get("cross_checks", [])
    else:
        retrieved = mf.utc_now()
        used_url = used
        cross = []
    rec = {
        "path": rel,
        "role": spec.role,
        "product_id": prod.product_id,
        "product_version": None,
        "data_set_id": None,
        "source_url": used_url,
        "equivalent_urls": [u for u in urls if u != used_url],
        "size_bytes": dest.stat().st_size,
        "sha256": digest,
        "retrieved_utc": retrieved,
        "hashed_utc": mf.utc_now(),
        "http_last_modified": meta["last_modified"],
        "http_etag": meta["etag"],
        "cross_checks": cross,
    }
    return rec


def _fill_docs(m: dict, root: Path, prod: catalog.Product) -> None:
    """Archive-level documents: take identifier and version from the bundle label."""
    import re

    bundle = raw_dir(root) / prod.product_id / "bundle_lola_rdr.xml"
    if not bundle.exists():
        return
    text = bundle.read_text(encoding="utf-8", errors="replace")
    lid = re.search(r"<logical_identifier>([^<]+)</logical_identifier>", text)
    ver = re.search(r"<version_id>([^<]+)</version_id>", text)
    for spec in prod.files:
        rec = m["files"].get((raw_dir(root) / prod.product_id / spec.local_name).relative_to(root).as_posix())
        if rec:
            rec["product_id"] = lid.group(1) if lid else catalog.PDS_BUNDLE_LID
            rec["product_version"] = ver.group(1) if ver else None
            rec["data_set_id"] = None


def run_fetch(root: Path, products: list[str], prefer: str = "mit", force: bool = False, workers: int = 3, segments: int = 1) -> dict:
    mpath = manifest_path()
    jobs = []
    for pid in products:
        prod = catalog.PRODUCTS[pid]
        for spec in prod.files:
            jobs.append((prod, spec))
    # Labels first so that every record can take its version from them.
    order = {"label": 0, "label_xml": 1, "doc": 1, "reference": 1, "data": 2, "count": 2, "uncertainty": 2}
    jobs.sort(key=lambda j: order[j[1].role])

    def work(job):
        prod, spec = job
        rec = fetch_file(prod, spec, root, prefer, force, mpath, segments)
        with _manifest_lock:
            m = mf.load(mpath)
            m["files"][rec["path"]] = rec
            mf.save(mpath, m)
        log(f"done {rec['path']}  {rec['size_bytes']:,} B  sha256 {rec['sha256'][:16]}...")
        return rec

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(work, jobs))

    # Fill product id / version / data set id from the labels.
    with _manifest_lock:
        m = mf.load(mpath)
        for pid in products:
            prod = catalog.PRODUCTS[pid]
            lbl = next((s for s in prod.files if s.role == "label"), None)
            if lbl is None:
                if pid == "_docs":
                    _fill_docs(m, root, prod)
                continue
            pdir = root / prod.base / pid
            info = _label_info(pdir / lbl.local_name)
            for spec in prod.files:
                rec = m["files"][(pdir / spec.local_name).relative_to(root).as_posix()]
                rec["product_id"] = info["product_id"] or pid
                rec["product_version"] = info["product_version"]
                rec["data_set_id"] = info["data_set_id"]
        mf.save(mpath, m)
    return m


def cross_check(root: Path, rel_paths: list[str] | None = None, workers: int = 3) -> list[str]:
    """Hash the same file from its other source and compare (nothing is stored)."""
    import hashlib

    mpath = manifest_path()
    m = mf.load(mpath)
    problems: list[str] = []
    todo = rel_paths or [r for r, rec in m["files"].items() if rec["equivalent_urls"]]

    def one(rel: str):
        rec = m["files"][rel]
        url = rec["equivalent_urls"][0]
        h = hashlib.sha256()
        n = 0
        with _open(url) as r:
            while block := r.read(CHUNK):
                h.update(block)
                n += len(block)
        res = {
            "url": url,
            "sha256": h.hexdigest(),
            "size_bytes": n,
            "matches": h.hexdigest() == rec["sha256"] and n == rec["size_bytes"],
            "checked_utc": mf.utc_now(),
        }
        with _manifest_lock:
            mm = mf.load(mpath)
            cc = [c for c in mm["files"][rel].get("cross_checks", []) if c["url"] != url]
            mm["files"][rel]["cross_checks"] = cc + [res]
            mf.save(mpath, mm)
        log(f"cross-check {rel} vs {url}: {'MATCH' if res['matches'] else 'DIFFERENT'}")
        if not res["matches"]:
            problems.append(rel)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(one, todo))
    return problems


def read_ranges(url: str, ranges: list[tuple[int, int]], per_request: int = 100, retries: int = 6) -> list[bytes]:
    """Bytes [a, b] (inclusive) of ``url`` for every (a, b) in ``ranges``, many ranges per HTTP request
    (multipart/byteranges). Order of the result follows ``ranges``."""
    import re

    out: dict[tuple[int, int], bytes] = {}
    for k in range(0, len(ranges), per_request):
        batch = ranges[k : k + per_request]
        spec = ",".join(f"{a}-{b}" for a, b in batch)
        for attempt in range(retries + 1):
            try:
                with _open(url, {"Range": f"bytes={spec}"}, timeout=180) as r:
                    ctype = r.headers.get("Content-Type", "")
                    body = r.read()
                    if r.status != 206:
                        raise OSError(f"range request not honoured (status {r.status})")
                    if len(batch) == 1 and "multipart" not in ctype:
                        out[batch[0]] = body
                        break
                    m = re.search(r"boundary=([^;]+)", ctype)
                    if not m:
                        raise OSError("no multipart boundary")
                    boundary = ("--" + m.group(1).strip().strip('"')).encode()
                    pos = 0
                    while True:
                        i = body.find(boundary, pos)
                        if i < 0:
                            break
                        j = body.find(b"\r\n\r\n", i)
                        if j < 0:
                            break
                        head = body[i:j].decode("latin1")
                        cr = re.search(r"Content-Range:\s*bytes\s+(\d+)-(\d+)/", head, re.I)
                        if not cr:
                            break
                        a, b = int(cr.group(1)), int(cr.group(2))
                        out[(a, b)] = body[j + 4 : j + 4 + (b - a + 1)]
                        pos = j + 4 + (b - a + 1)
                    missing = [rg for rg in batch if rg not in out]
                    if missing:
                        raise OSError(f"{len(missing)} ranges missing from the response")
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError):
                if attempt == retries:
                    raise
                time.sleep(min(5 * (attempt + 1), 30))
    return [out[rg] for rg in ranges]
