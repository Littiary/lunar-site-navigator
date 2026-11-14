"""Crater records from the IAU Gazetteer of Planetary Nomenclature (USGS), for georeferencing checks.

Each feature page lists one or more determinations (centre, diameter and, for the LOLA-based ones, an
outline polygon in WKT). The page text is parsed as shown; nothing is edited. The retrieved records are
committed in ``data/checkpoints/features.json`` with the URL and retrieval time.
"""

from __future__ import annotations

import json
import re
import urllib.request

from . import manifest as mf

BASE = "https://planetarynames.wr.usgs.gov/Feature"
UA = "lsn-data/0.1 (Kestro Aerospace; NASA Space Apps 2026 research code)"


def _page(feature_id: int) -> str:
    req = urllib.request.Request(f"{BASE}/{feature_id}", headers={"User-Agent": UA})
    html = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", "replace")
    html = re.sub(r"<script.*?</script>", "", html, flags=re.S)
    html = re.sub(r"<[^>]+>", "|", html)
    return re.sub(r"[|\s]*\|[|\s]*", "|", html)


def fetch_feature(feature_id: int) -> dict:
    t = _page(feature_id)
    name = re.search(r"Feature Name\|([^|]+)", t).group(1)
    system = re.search(r"Coordinate System\|([^|]+)", t).group(1)
    approval = re.search(r"Approval Status\|([^|]+)\|Approval Date\|([^|]+)", t)
    blocks = []
    pat = re.compile(
        r"Diameter\|([\d.]+)\|km\|Center Latitude\|(-?[\d.]+)[^|]*\|Center Longitude\|(-?[\d.]+)[^|]*\|WKT String\|([^|]+)"
    )
    for m in pat.finditer(t):
        wkt = m.group(4)
        pts = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+\.?\d*) (-?\d+\.?\d*)", wkt)]
        blocks.append(
            {
                "diameter_km": float(m.group(1)),
                "center_lat_deg": float(m.group(2)),
                "center_lon_deg": float(m.group(3)),
                "wkt_type": wkt.split("(")[0].strip(),
                "outline_lon_lat_deg": pts if "POLYGON" in wkt else [],
            }
        )
    return {
        "feature_id": feature_id,
        "name": name,
        "source_url": f"{BASE}/{feature_id}",
        "retrieved_utc": mf.utc_now(),
        "coordinate_system": system,
        "iau_status": approval.group(1) if approval else None,
        "iau_approval_date": approval.group(2) if approval else None,
        "determinations": blocks,
    }


def main(ids: list[int], out_path: str) -> None:
    recs = [fetch_feature(i) for i in ids]
    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"source": "IAU Gazetteer of Planetary Nomenclature, USGS Astrogeology", "features": recs}, f, indent=1)
        f.write("\n")
    for r in recs:
        print(r["name"], [(d["diameter_km"], d["center_lat_deg"], d["center_lon_deg"], len(d["outline_lon_lat_deg"])) for d in r["determinations"]])


if __name__ == "__main__":
    import sys

    main([int(x) for x in sys.argv[2:]], sys.argv[1])
