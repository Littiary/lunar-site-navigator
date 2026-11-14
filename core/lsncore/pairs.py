"""Complementary site pairs: what two sites achieve together.

Pure arithmetic on the visibility windows of site packages that share one time range.
For a pair and a window (for example "Sun visible"):

    either  = A or B          neither = not (A or B)          both = A and B

The gain of pairing is the time "either" adds to the better of the two sites, and the
share of that site's outage which the other one covers. Nothing is said about how power
or data would get from one site to the other.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

from . import SCIENCE_VERSION
from . import packaging as pk
from .contract import PackageWriter
from .timeline import IntervalSet

DEFAULT_WINDOWS = ("sun_visible", "earth_visible", "sun_and_earth_visible")
SYNTHETIC_PAIRS_NOTICE = (
    "SYNTHETIC SAMPLE DATA. This comparison was computed from site packages that hold invented "
    "numbers. It describes no real places. Do not use it, quote it or present it as a result."
)


def pair_report(a: IntervalSet, b: IntervalSet) -> dict:
    """Totals of two windows and of their union, intersection and joint outage."""
    either, both = a.union(b), a.intersection(b)
    neither = either.complement()
    total = a.domain[1] - a.domain[0]
    better = max(a.total_s(), b.total_s())
    outage = total - better
    gain = either.total_s() - better
    return {
        "a_s": a.total_s(),
        "b_s": b.total_s(),
        "either_s": either.total_s(),
        "both_s": both.total_s(),
        "neither_s": neither.total_s(),
        "longest_neither_s": neither.longest_s(),
        "either_fraction": either.total_s() / total,
        "gain_over_better_s": gain if gain > 0.0 else 0.0,
        "covered_share_of_better_outage": None if outage <= 0.0 else min(max(gain / outage, 0.0), 1.0),
        "neither": neither,
    }


def _great_circle_m(lat1, lon1, lat2, lon2, radius_m) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return float(2.0 * radius_m * math.asin(min(1.0, math.sqrt(h))))


def build_pairs_package(out_root: Path | str, site_dirs: list, methods: dict, window_ids=DEFAULT_WINDOWS, scenario_id: str | None = None) -> Path | None:
    """Compare every pair of the given site packages and write a site_pairs package.

    Only packages with a timeline take part; they must share the same time grid. Each site
    is taken at its default observer height. Returns None if fewer than two sites qualify.
    UTC strings are taken from the site packages (every edge of a combined window is an
    edge of one of their windows), so no time conversion happens here.
    """
    manifests = []
    for path in site_dirs:
        manifest = json.loads((Path(path) / "manifest.json").read_text(encoding="utf-8"))
        if manifest["kind"] == "site" and "timeline" in manifest:
            manifests.append(manifest)
    if len(manifests) < 2:
        return None
    grid = manifests[0]["timeline"]["time"]
    if any(m["timeline"]["time"] != grid for m in manifests[1:]):
        raise ValueError("site packages must share the same time grid to be compared")
    domain = (grid["start_et_s"], grid["start_et_s"] + (grid["count"] - 1) * grid["step_s"])

    utc = {domain[0]: grid["start_utc"], domain[1]: grid["end_utc"]}
    windows = {}
    for m in manifests:
        h = m["horizon"]["default_height_index"]
        for record in m["timeline"]["windows"]:
            if record["height_index"] != h:
                continue
            for (a, b), (ua, ub) in zip(record["intervals_et_s"], record["intervals_utc"]):
                utc[a], utc[b] = ua, ub
            windows[(m["site"]["site_id"], record["id"])] = IntervalSet(record["intervals_et_s"], domain)

    sites = [
        {
            "site_id": m["site"]["site_id"],
            "name": m["site"]["name"],
            "lat_deg": m["site"]["lat_deg"],
            "lon_deg": m["site"]["lon_deg"],
            "package_id": m["package_id"],
            "observer_height_m": m["horizon"]["observer_heights_m"][m["horizon"]["default_height_index"]],
        }
        for m in manifests
    ]
    radius = manifests[0]["site"]["reference_radius_m"]["value"]
    pairs = []
    for i in range(len(sites)):
        for j in range(i + 1, len(sites)):
            a, b = sites[i], sites[j]
            rows = []
            for window_id in window_ids:
                wa, wb = windows.get((a["site_id"], window_id)), windows.get((b["site_id"], window_id))
                if wa is None or wb is None:
                    continue
                report = pair_report(wa, wb)
                neither = report.pop("neither")
                rows.append(
                    {
                        "window": window_id,
                        **report,
                        "neither_intervals_et_s": neither.as_list(),
                        "neither_intervals_utc": [[utc[s], utc[e]] for s, e in neither.intervals],
                        "method": pk.M_PAIRS,
                    }
                )
            pairs.append(
                {
                    "site_a": a["site_id"],
                    "site_b": b["site_id"],
                    "distance_m": _great_circle_m(a["lat_deg"], a["lon_deg"], b["lat_deg"], b["lon_deg"], radius),
                    "windows": rows,
                }
            )

    synthetic = any(m["synthetic"] for m in manifests)
    request = {"site_package_ids": [m["package_id"] for m in manifests], "windows": list(window_ids)}
    inputs = {
        "science_version": SCIENCE_VERSION,
        "site_packages": [
            {"site_id": m["site"]["site_id"], "package_id": m["package_id"], "content_sha256": m["content_sha256"]} for m in manifests
        ],
    }
    return PackageWriter("site_pairs").write(
        Path(out_root),
        None,
        status="ok",
        synthetic=synthetic,
        synthetic_notice=SYNTHETIC_PAIRS_NOTICE if synthetic else None,
        warnings=[],
        request=request,
        inputs=inputs,
        methods={pk.M_PAIRS: methods[pk.M_PAIRS]},
        sections={"time": grid, "sites": sites, "pairs": pairs},
        scenario_id=scenario_id,
    )
