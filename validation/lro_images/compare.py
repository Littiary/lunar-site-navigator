"""Compare the sunlit or shadowed state the terrain horizon gives with dated LROC images.

Reads ``cases.json`` (committed before any computation and before the image of case B was
downloaded) and writes ``results/validation_table.json`` and ``.md``. Our states are
computed first and stored in ``results/our_states.json``; the image is read afterwards.

Usage (from the repository root; needs the LOLA data, and for case B the browse image,
which ``fetch`` stores outside the repository, and the Pillow library to read it)::

    python -m validation.lro_images.fetch
    python -m validation.lro_images.compare [--reuse-states]
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels
from validation.landers.compare import sub_point

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
BROWSE_NAME = "M146846913LC_pyr.tif"
REDUCED_PIXEL_M = 20.0
NEIGHBOURHOOD_M = 300.0
ROW_OFFSETS_M = (-700.0, 0.0, 700.0)
ALONG_STEP_M = 500.0
EDGE_M = 1000.0


def cache_dir() -> Path:
    from validation.lro_images import fetch

    return fetch.cache_dir()


def load() -> dict:
    return json.loads((HERE / "cases.json").read_text(encoding="utf-8"))


def mid_time(case: dict) -> float:
    p = case["published"]
    return 0.5 * (d.utc_to_et(p["start_time_utc"]) + d.utc_to_et(p["stop_time_utc"]))


# --------------------------------------------------------------------------- our state


def our_state(terrain, lat_deg: float, lon_deg: float, et: float) -> dict:
    """Sunlit or shadow at a surface point from the terrain horizon, with the numbers behind it."""
    from lsncore.horizon import HorizonSettings, compute_horizon

    result = compute_horizon(terrain, lat_deg, lon_deg, [0.0], 0.25, 300000.0, HorizonSettings())
    elevation = np.asarray(result.elevation_deg[0], dtype=np.float64)
    if not np.all(np.isfinite(elevation)):
        return {"state": None, "reason": "terrain horizon has gaps"}
    horizon = ev.Horizon(0.0, result.azimuth_step_deg, elevation, np.asarray(result.distance_m[0], dtype=np.float64))
    site = d.Site(lon_deg, lat_deg, result.surface_height_m / 1000.0)
    sun = d.topocentric_exact(site, et, "SUN")
    signals = ev.disc_signals(sun.az_deg, sun.el_deg, sun.angular_radius_deg, horizon)
    fraction = float(signals.visible_fraction[0])
    limiting = float(signals.upper_azimuth_deg[0])
    return {
        "state": "sunlit" if fraction >= 0.5 else "shadow",
        "visible_fraction": fraction,
        "upper_limb_margin_deg": float(signals.upper_margin_deg[0]),
        "centre_margin_deg": float(signals.center_margin_deg[0]),
        "sun_azimuth_deg": float(sun.az_deg[0]),
        "sun_elevation_deg": float(sun.el_deg[0]),
        "horizon_elevation_at_sun_azimuth_deg": float(horizon.elevation_at(sun.az_deg[0])),
        "obstacle_distance_m": float(horizon.distance_at(np.array([limiting]))[0]),
        "surface_height_m": float(result.surface_height_m),
    }


def strip_points(case: dict) -> list:
    """The points of case B: three rows along the strip, in image fractions and on the ground."""
    from lsn_data.georef import lonlat_to_xy, xy_to_lonlat

    c = case["published"]["corners_lat_lon_deg"]
    corner = {key: np.array(lonlat_to_xy(c[key][1], c[key][0])) for key in c}
    length = float(np.linalg.norm(0.5 * (corner["lower_left"] + corner["lower_right"]) - 0.5 * (corner["upper_left"] + corner["upper_right"])))
    width = 0.5 * float(np.linalg.norm(corner["upper_right"] - corner["upper_left"]) + np.linalg.norm(corner["lower_right"] - corner["lower_left"]))
    points = []
    for offset in ROW_OFFSETS_M:
        fs = 0.5 + offset / width
        for along in np.arange(EDGE_M, length - EDGE_M + 1e-6, ALONG_STEP_M):
            fl = along / length
            xy = (1 - fl) * ((1 - fs) * corner["upper_left"] + fs * corner["upper_right"]) + fl * ((1 - fs) * corner["lower_left"] + fs * corner["lower_right"])
            lon, lat = xy_to_lonlat(xy[0], xy[1])
            points.append({"id": f"row{offset:+.0f}_along{along:.0f}", "line_fraction": float(fl), "sample_fraction": float(fs), "x_m": float(xy[0]), "y_m": float(xy[1]), "lon_deg": float(lon), "lat_deg": float(lat)})
    return points, length, width


def compute_states() -> dict:
    from lsncore.dem import open_lola

    kernels.load()
    cases = {case["id"]: case for case in load()["cases"]}
    terrain = open_lola()
    a, b = cases["pole_in_shadow_2022"], cases["nadir_strip_2010"]
    et_a, et_b = mid_time(a), mid_time(b)
    points, length, width = strip_points(b)
    states = []
    for n, point in enumerate(points):
        states.append({**point, **our_state(terrain, point["lat_deg"], point["lon_deg"], et_b)})
        if (n + 1) % 25 == 0:
            print(f"{n + 1} of {len(points)} strip points", flush=True)
    out = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terrain": terrain.describe()["dem_set_id"], "kernel_set_id": kernels.kernel_set_id(),
        "pole_in_shadow_2022": {"utc": d.et_to_utc_z(et_a), "sub_solar_lon_lat_deg": list(sub_point(et_a, "SUN")), **our_state(terrain, a["point"]["lat_deg"], a["point"]["lon_deg"], et_a)},
        "nadir_strip_2010": {"utc": d.et_to_utc_z(et_b), "sub_solar_lon_lat_deg": list(sub_point(et_b, "SUN")), "strip_length_m": length, "strip_width_m": width, "points": states},
    }
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "our_states.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    return out


# --------------------------------------------------------------------------- image reading


def otsu_threshold(values: np.ndarray) -> float:
    """Otsu's threshold of 8-bit values: the cut that maximises the variance between the two classes."""
    histogram = np.bincount(values.astype(np.uint8).ravel(), minlength=256).astype(np.float64)
    total = histogram.sum()
    levels = np.arange(256)
    weight_low = np.cumsum(histogram)
    weight_high = total - weight_low
    sum_low = np.cumsum(histogram * levels)
    mean_low = np.divide(sum_low, weight_low, out=np.zeros(256), where=weight_low > 0)
    mean_high = np.divide(sum_low[-1] - sum_low, weight_high, out=np.zeros(256), where=weight_high > 0)
    between = weight_low * weight_high * (mean_low - mean_high) ** 2
    return float(np.argmax(between)) + 0.5


def read_browse(case: dict):
    """The browse image averaged to about 20 m per pixel, as an 8-bit array [rows, cols].

    The first page of the pyramid is the full-resolution image; it is reduced by block
    averaging with an integer factor.
    """
    from PIL import Image

    Image.MAX_IMAGE_PIXELS = None
    path = cache_dir() / BROWSE_NAME
    with Image.open(path) as source:
        if source.size != (case["published"]["samples"], case["published"]["lines"]):
            raise RuntimeError(f"browse image has {source.size}, the data page says {case['published']['samples']} x {case['published']['lines']}")
        full_pixel_m = case["published"]["resolution_m"]
        factor = int(round(REDUCED_PIXEL_M / full_pixel_m))
        image = np.asarray(source.convert("L").reduce(factor), dtype=np.uint8)
    return image, hashlib.sha256(path.read_bytes()).hexdigest(), full_pixel_m * factor


def image_states(case: dict, points: list) -> dict:
    image, sha256, full_pixel_m = read_browse(case)
    threshold = otsu_threshold(image)
    rows, cols = image.shape
    radius = int(round(NEIGHBOURHOOD_M / full_pixel_m))
    yy, xx = np.mgrid[-radius : radius + 1, -radius : radius + 1]
    disc = (yy * yy + xx * xx) <= radius * radius
    out = []
    for point in points:
        r, c = int(point["line_fraction"] * rows), int(point["sample_fraction"] * cols)
        r0, r1, c0, c1 = r - radius, r + radius + 1, c - radius, c + radius + 1
        if r0 < 0 or c0 < 0 or r1 > rows or c1 > cols:
            out.append({"image_state": "outside", "image_mean": None})
            continue
        patch = image[r0:r1, c0:c1][disc]
        state = "sunlit" if np.all(patch > threshold) else "shadow" if np.all(patch < threshold) else "mixed"
        out.append({"image_state": state, "image_mean": float(patch.mean()), "image_share_above_threshold": float(np.mean(patch > threshold))})
    return {"states": out, "threshold": threshold, "reduced_shape": [int(rows), int(cols)], "browse_sha256": sha256, "reduced_pixel_m": full_pixel_m,
            "share_of_image_above_threshold": float(np.mean(image > threshold))}


# --------------------------------------------------------------------------- report


def run(recompute: bool = False) -> dict:
    cases = {case["id"]: case for case in load()["cases"]}
    stored = RESULTS / "our_states.json"
    ours = compute_states() if recompute or not stored.exists() else json.loads(stored.read_text(encoding="utf-8"))
    checks = []

    a, mine = cases["pole_in_shadow_2022"], ours["pole_in_shadow_2022"]
    checks.append({"id": "pole_2022_state", "published": "shadow (camera team)", "computed": mine["state"], "status": "PASS" if mine["state"] == "shadow" else "FAIL",
                   "detail": {k: mine[k] for k in ("utc", "visible_fraction", "upper_limb_margin_deg", "centre_margin_deg", "sun_azimuth_deg", "sun_elevation_deg", "horizon_elevation_at_sun_azimuth_deg", "obstacle_distance_m")}})

    def sub_solar(case, mine_point, check_id):
        d_lat = mine_point[1] - case["published"]["sub_solar_latitude_deg"]
        d_lon = (mine_point[0] - case["published"]["sub_solar_longitude_deg"] + 180.0) % 360.0 - 180.0
        checks.append({"id": check_id, "published": [case["published"]["sub_solar_latitude_deg"], case["published"]["sub_solar_longitude_deg"]], "computed": [mine_point[1], mine_point[0] % 360.0],
                       "difference_deg": [d_lat, d_lon], "threshold_deg": 0.02, "status": "PASS" if abs(d_lat) < 0.02 and abs(d_lon) < 0.02 else "FAIL"})

    sub_solar(a, mine["sub_solar_lon_lat_deg"], "pole_2022_sub_solar_point")

    b, strip = cases["nadir_strip_2010"], ours["nadir_strip_2010"]
    image = image_states(b, strip["points"])
    rows = [{**point, **state} for point, state in zip(strip["points"], image["states"])]
    judged = [r for r in rows if r["image_state"] in ("sunlit", "shadow") and r["state"] is not None]
    agree = [r for r in judged if r["image_state"] == r["state"]]
    table = {f"image_{i}_ours_{o}": sum(1 for r in judged if r["image_state"] == i and r["state"] == o) for i in ("sunlit", "shadow") for o in ("sunlit", "shadow")}
    both_states = len({r["image_state"] for r in judged}) == 2
    decided = len(judged) >= 30 and both_states
    share = len(agree) / len(judged) if judged else None
    checks.append({"id": "nadir_2010_agreement", "published": "state read from the image by the fixed rule", "computed": share, "threshold": 0.90,
                   "status": ("PASS" if share >= 0.90 else "FAIL") if decided else "NOT DECIDED",
                   "detail": {"points": len(rows), "judged": len(judged), "mixed_or_outside": len(rows) - len(judged), "agree": len(agree), **table,
                              "centre_row_agreement": _share([r for r in judged if abs(r["sample_fraction"] - 0.5) < 1e-9]),
                              "side_rows_agreement": _share([r for r in judged if abs(r["sample_fraction"] - 0.5) > 1e-9])}})
    sub_solar(b, strip["sub_solar_lon_lat_deg"], "nadir_2010_sub_solar_point")
    judged_checks = [c for c in checks if c["status"] in ("PASS", "FAIL")]

    # Added after the registered agreement check failed, to find the cause. Not a criterion.
    def brightness(state, subset):
        return np.array([r["image_mean"] for r in subset if r["state"] == state and r["image_mean"] is not None])

    def separation(subset):
        lit, dark = brightness("sunlit", subset), brightness("shadow", subset)
        if not lit.size or not dark.size:
            return None
        auc = ((lit[:, None] > dark[None, :]).sum() + 0.5 * (lit[:, None] == dark[None, :]).sum()) / (lit.size * dark.size)
        return {"our_sunlit_points": int(lit.size), "our_shadow_points": int(dark.size), "median_brightness_our_sunlit": float(np.median(lit)), "median_brightness_our_shadow": float(np.median(dark)),
                "probability_that_an_our_sunlit_point_is_brighter_than_an_our_shadow_point": float(auc)}

    disputed = [r for r in judged if r["image_state"] == "shadow" and r["state"] == "sunlit"]
    agreed_shadow = [r for r in judged if r["image_state"] == "shadow" and r["state"] == "shadow"]
    agreed_sunlit = [r for r in judged if r["image_state"] == "sunlit" and r["state"] == "sunlit"]
    exploratory = {
        "note": "Computed after the registered agreement check failed, to find the cause. These numbers are not a pass criterion and do not replace the registered result.",
        "judged_points": separation(judged),
        "all_points_inside_the_image": separation(rows),
        "image_shadow_ours_sunlit": None if not disputed else {
            "points": len(disputed),
            "image_brightness_min_median_max": [float(f([r["image_mean"] for r in disputed])) for f in (np.min, np.median, np.max)],
            "our_centre_margin_deg_min_median_max": [float(f([r["centre_margin_deg"] for r in disputed])) for f in (np.min, np.median, np.max)],
        },
        "image_shadow_ours_shadow_brightness_median": None if not agreed_shadow else float(np.median([r["image_mean"] for r in agreed_shadow])),
        "image_sunlit_ours_sunlit": None if not agreed_sunlit else {
            "points": len(agreed_sunlit),
            "image_brightness_min_median_max": [float(f([r["image_mean"] for r in agreed_sunlit])) for f in (np.min, np.median, np.max)],
            "our_centre_margin_deg_min_median_max": [float(f([r["centre_margin_deg"] for r in agreed_sunlit])) for f in (np.min, np.median, np.max)],
        },
    }
    if disputed and agreed_shadow:
        exploratory.update(_two_readings(judged, disputed, agreed_shadow))
    return {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "terrain": ours["terrain"], "kernel_set_id": ours["kernel_set_id"],
        "summary": {"checks": len(checks), "passed": sum(c["status"] == "PASS" for c in checks), "failed": sum(c["status"] == "FAIL" for c in checks), "not_decided": len(checks) - len(judged_checks)},
        "checks": checks,
        "image": {k: v for k, v in image.items() if k != "states"},
        "exploratory_after_the_result": exploratory,
        "strip_points": rows,
    }


def _two_readings(judged: list, disputed: list, agreed_shadow: list) -> dict:
    """Numbers for and against the two causes that fit a one-sided disagreement. Exploratory, not a criterion."""
    mean = np.array([r["image_mean"] for r in judged])
    ours = np.array([r["state"] == "sunlit" for r in judged])
    scan = [(float(t), float(((mean > t) == ours).mean())) for t in np.arange(2.5, 80.0, 1.0)]
    good = [t for t, share in scan if share >= 0.9]
    best = max(scan, key=lambda item: item[1])
    near = [r["image_mean"] for r in agreed_shadow if -1.0 <= r["centre_margin_deg"] < 0.0]

    def rank(values):
        return np.argsort(np.argsort(values))

    brightness, margin = [r["image_mean"] for r in disputed], [r["centre_margin_deg"] for r in disputed]
    return {
        "one_threshold_on_the_point_brightness": {"best_threshold": best[0], "best_agreement": best[1], "thresholds_with_agreement_of_at_least_0.9": [min(good), max(good)] if good else None},
        "agreed_shadow_with_our_sun_centre_less_than_1_deg_below_the_horizon": {"points": len(near), "image_brightness_min_max": [float(min(near)), float(max(near))]} if near else None,
        "rank_correlation_of_brightness_with_our_centre_margin_at_the_disputed_points": float(np.corrcoef(rank(brightness), rank(margin))[0, 1]) if len(disputed) > 2 else None,
    }



def _share(rows: list):
    return None if not rows else sum(1 for r in rows if r["image_state"] == r["state"]) / len(rows)


def to_markdown(report: dict) -> str:
    s = report["summary"]
    c = {check["id"]: check for check in report["checks"]}
    pole, strip = c["pole_2022_state"], c["nadir_2010_agreement"]
    pd_, sd = pole["detail"], strip["detail"]
    lines = [
        "# Validation table: sunlit or shadowed state against dated LROC images",
        "",
        f"Generated {report['generated_utc']} by `validation/lro_images/compare.py`. Do not edit by hand.",
        "",
        f"**{s['passed']} of {s['checks']} registered checks pass, {s['failed']} fail, {s['not_decided']} not decided.** Cases, reading rule and criteria are in `cases.json`, committed before any computation and before the image was downloaded (commit fb05da0). Terrain: `{report['terrain']}`.",
        "",
        "| Check | Published or read from the image | Computed | Result |",
        "|---|---|---|---|",
        f"| South pole at {pd_['utc']} (NAC M1407524099) | shadow, as documented by the camera team | {pole['computed']}: visible fraction of the Sun {pd_['visible_fraction']:.3f}, upper limb {pd_['upper_limb_margin_deg']:+.3f} deg, centre {pd_['centre_margin_deg']:+.3f} deg against the horizon | **{pole['status']}** |",
        f"| Sub-solar point for that image | {c['pole_2022_sub_solar_point']['published'][0]} N, {c['pole_2022_sub_solar_point']['published'][1]} E | {c['pole_2022_sub_solar_point']['computed'][0]:.3f} N, {c['pole_2022_sub_solar_point']['computed'][1]:.3f} E | **{c['pole_2022_sub_solar_point']['status']}** |",
        f"| Nadir strip of 2010-12-13 (NAC M146846913L): agreement of states at the judged points | {sd['judged']} of {sd['points']} points readable ({sd['mixed_or_outside']} mixed or outside) | " + ("no judged point" if strip["computed"] is None else f"{100 * strip['computed']:.1f} % agree ({sd['agree']} of {sd['judged']})") + f" | **{strip['status']}** |",
        f"| Sub-solar point for that image | {c['nadir_2010_sub_solar_point']['published'][0]} N, {c['nadir_2010_sub_solar_point']['published'][1]} E | {c['nadir_2010_sub_solar_point']['computed'][0]:.3f} N, {c['nadir_2010_sub_solar_point']['computed'][1]:.3f} E | **{c['nadir_2010_sub_solar_point']['status']}** |",
        "",
        f"South pole detail: Sun at azimuth {pd_['sun_azimuth_deg']:.2f} deg, elevation {pd_['sun_elevation_deg']:+.3f} deg; terrain horizon there {pd_['horizon_elevation_at_sun_azimuth_deg']:+.3f} deg; limiting terrain {pd_['obstacle_distance_m'] / 1000.0:.2f} km away.",
        "",
        f"Nadir strip detail: image sunlit and ours sunlit {sd['image_sunlit_ours_sunlit']}; image sunlit, ours shadow {sd['image_sunlit_ours_shadow']}; image shadow, ours sunlit {sd['image_shadow_ours_sunlit']}; image shadow and ours shadow {sd['image_shadow_ours_shadow']}. "
        + f"Centre row agreement {_pct(sd['centre_row_agreement'])}, side rows {_pct(sd['side_rows_agreement'])}. Brightness threshold (Otsu) {report['image']['threshold']:.1f} of 255; {100 * report['image']['share_of_image_above_threshold']:.1f} % of the reduced image is above it.",
    ]
    e = report["exploratory_after_the_result"]
    if strip["status"] == "FAIL" and e["image_shadow_ours_sunlit"] and e["judged_points"]:
        d_, j = e["image_shadow_ours_sunlit"], e["judged_points"]
        low, high = d_["our_centre_margin_deg_min_median_max"][0], d_["our_centre_margin_deg_min_median_max"][2]
        scan, near, rho = e["one_threshold_on_the_point_brightness"], e["agreed_shadow_with_our_sun_centre_less_than_1_deg_below_the_horizon"], e["rank_correlation_of_brightness_with_our_centre_margin_at_the_disputed_points"]
        lines += [
            "",
            "## What the failed strip check shows (looked at after the result; not a criterion)",
            "",
            f"All {d_['points']} disagreements go one way: the image rule reads shadow, our state is sunlit, with the centre of our Sun {low:+.2f} to {high:+.2f} deg above the terrain horizon. "
            "Two causes fit this pattern, and these data do not decide between them.",
            "",
            f"1. The image rule. It uses one brightness threshold for the whole image (Otsu, {report['image']['threshold']:.1f} of 255), which settles between the bright Sun-facing slopes and everything else, so ground lit at a grazing angle would be read as shadow. "
            f"For this cause: the disputed points are brighter than agreed shadow in the median ({d_['image_brightness_min_median_max'][1]:.0f} against {e['image_shadow_ours_shadow_brightness_median']:.0f}); "
            f"with one threshold on the brightness of a point between {scan['thresholds_with_agreement_of_at_least_0.9'][0]:.1f} and {scan['thresholds_with_agreement_of_at_least_0.9'][1]:.1f} the agreement would be 90 % or more "
            f"(at best {100 * scan['best_agreement']:.1f} % at {scan['best_threshold']:.1f}); and without any threshold, among the {j['our_sunlit_points'] + j['our_shadow_points']} judged points, a point our model calls sunlit is brighter in the image "
            f"than a point it calls shadow with probability {j['probability_that_an_our_sunlit_point_is_brighter_than_an_our_shadow_point']:.3f}.",
            f"2. Our horizon. A terrain horizon that is {low:.2f} to {high:.2f} deg too low at these points gives the same one-sided pattern. "
            f"For this cause: the brightness of the disputed points ({d_['image_brightness_min_median_max'][0]:.0f} to {d_['image_brightness_min_median_max'][2]:.0f}) overlaps that of the {near['points']} points which both sides call shadow "
            f"with our Sun less than 1 deg below the horizon ({near['image_brightness_min_max'][0]:.0f} to {near['image_brightness_min_max'][1]:.0f}); and among the disputed points the brightness follows the height of our Sun only weakly (rank correlation {rho:.2f}).",
            "",
            "These numbers were computed after seeing the result. They are not a criterion; the registered check stays failed.",
        ]
    return "\n".join(lines) + "\n"


def _pct(value) -> str:
    return "n/a" if value is None else f"{100 * value:.1f} %"


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reuse-states", action="store_true", help="read results/our_states.json instead of recomputing our states from the terrain")
    args = parser.parse_args()
    report = run(recompute=not args.reuse_states)
    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "validation_table.json").write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8")
    (RESULTS / "validation_table.md").write_text(to_markdown(report), encoding="utf-8")
    for check in report["checks"]:
        print(check["id"], check["status"], check.get("computed"), check.get("difference_deg", ""), json.dumps(check.get("detail", {}))[:420])
    print(report["image"])
    print(report["summary"])


if __name__ == "__main__":
    main()
