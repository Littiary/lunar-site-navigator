"""Fetch the Horizons reference data defined in ``cases.json``.

One request at a time, never in parallel, and never twice for the same case:
a response that is already stored is not requested again. Each response body
is written byte-for-byte to ``raw/<case>.json`` and described in
``raw/<case>.meta.json`` (full URL, parameters, retrieval time, HTTP status,
SHA-256). Nobody edits the files in ``raw/``.

Usage (from the repository root)::

    python -m validation.horizons.fetch [--dir validation/horizons_rts] [--only CASE_ID_SUBSTRING] [--limit N]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"

# Generic client name; no personal contact data is sent.
USER_AGENT = "lunar-ephemeris-validation/0.1 (python-urllib; sequential, cached)"
PAUSE_SECONDS = 1.5


def load_cases(base: Path = HERE) -> dict:
    return json.loads((base / "cases.json").read_text(encoding="utf-8"))


def iter_cases(cases: dict):
    """Yield (case_id, site, body, span, parameters) for every query.

    A case file either lists sites, targets and spans (every combination is a query) or
    lists explicit ``queries``, each with an id and its own parameters; then the query
    itself is yielded in place of the site, and body and span are None.
    """
    if "queries" in cases:
        for query in cases["queries"]:
            params = dict(cases["common_parameters"])
            params.update(query["parameters"])
            yield query["id"], query, None, None, params
        return
    for span in cases["spans"]:
        for site in cases["sites"]:
            for body, command in cases["targets"].items():
                params = dict(cases["common_parameters"])
                params.update(
                    {
                        "COMMAND": command,
                        "SITE_COORD": f"{site['lon_deg']},{site['lat_deg']},{site['height_km']}",
                        "START_TIME": span["start_utc"],
                        "STOP_TIME": span["stop_utc"],
                        "STEP_SIZE": span["step"],
                    }
                )
                yield f"{site['id']}__{body.lower()}__{span['id']}", site, body, span, params


def build_url(api: str, params: dict) -> str:
    """Horizons expects every value except ``format`` in single quotes."""
    quoted = {key: (value if key == "format" else f"'{value}'") for key, value in params.items()}
    return api + "?" + urllib.parse.urlencode(quoted, quote_via=urllib.parse.quote)


def fetch_one(case_id: str, url: str, params: dict, base: Path = HERE) -> str:
    raw = base / "raw"
    body_path, meta_path = raw / f"{case_id}.json", raw / f"{case_id}.meta.json"
    if body_path.exists() and meta_path.exists():
        return "cached"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            status, payload = response.status, response.read()
    except urllib.error.HTTPError as error:
        raise SystemExit(f"{case_id}: HTTP {error.code}; stopping instead of retrying") from error
    retrieved = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    document = json.loads(payload)
    if "error" in document or "$$SOE" not in document.get("result", ""):
        problem = base / f"rejected__{case_id}.json"
        problem.write_bytes(payload)
        raise SystemExit(f"{case_id}: Horizons returned no ephemeris; response kept in {problem.name}")
    raw.mkdir(parents=True, exist_ok=True)
    body_path.write_bytes(payload)
    meta = {
        "case_id": case_id,
        "url": url,
        "parameters": params,
        "retrieved_utc": retrieved,
        "http_status": status,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "api_signature": document.get("signature"),
        "user_agent": USER_AGENT,
    }
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return "fetched"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default="", help="fetch only cases whose id contains this text")
    parser.add_argument("--limit", type=int, default=0, help="stop after this many new requests")
    parser.add_argument("--dir", default=str(HERE), help="folder holding cases.json and raw/ (default: validation/horizons)")
    args = parser.parse_args()
    base = Path(args.dir).resolve()
    cases = load_cases(base)
    done = 0
    for case_id, _site, _body, _span, params in iter_cases(cases):
        if args.only and args.only not in case_id:
            continue
        outcome = fetch_one(case_id, build_url(cases["api"], params), params, base)
        print(f"{case_id}: {outcome}", flush=True)
        if outcome == "fetched":
            done += 1
            if args.limit and done >= args.limit:
                break
            time.sleep(PAUSE_SECONDS)


if __name__ == "__main__":
    main()
