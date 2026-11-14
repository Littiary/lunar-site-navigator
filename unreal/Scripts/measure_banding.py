"""Measures whether the bands on the near ground at a very low Sun come from the elevation data.

The LOLA polar products store heights as 16-bit numbers of 0.5 m. Between two 20 m pixels
a height can therefore only differ by a multiple of 0.5 m, so a slope can only take the
values atan(k * 0.5 / 20) = k * 1.43 degrees. With the Sun one or two degrees above the
horizon, one such step changes the sine of the Sun's height above the surface by a large
factor, and that is what the eye sees as bands.

This script reads the finest data around every published site through the data stream's
reader and prints:
  1. the share of pixel heights that are exact multiples of 0.5 m;
  2. the slope steps between neighbouring pixels (their distinct values);
  3. along the azimuth of the Sun at a low-Sun sample of the package, the slope of the
     bilinear surface metre by metre: how many distinct slope values there are, how far
     apart the changes lie, and by what factor the grazing illumination changes at them.

Usage (Python environment with the data stream's reader and the LOLA files):
    python measure_banding.py <package root>
"""

from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

import numpy as np

import lsn_data


def destination(site, azimuth_deg, arc_m, radius_m):
    east, north, up = (np.asarray(site["enu"][k]) for k in ("east", "north", "up"))
    az = np.deg2rad(azimuth_deg)
    arc = np.asarray(arc_m) / radius_m
    heading = np.sin(az) * east + np.cos(az) * north
    p = np.cos(arc)[:, None] * up + np.sin(arc)[:, None] * heading
    return np.rad2deg(np.arctan2(p[:, 2], np.hypot(p[:, 0], p[:, 1]))), np.rad2deg(np.arctan2(p[:, 1], p[:, 0]))


def main() -> None:
    root = Path(sys.argv[1])
    terrain = lsn_data.open_terrain()
    dem = terrain.product("LDEM_80S_20M")
    index = json.loads((root / "index.json").read_text(encoding="utf-8"))
    for entry in index["packages"]:
        if entry["kind"] != "site":
            continue
        d = root / entry["path"]
        m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        site = m["site"]
        radius = site["reference_radius_m"]["value"]
        window = dem.window_around(site["lon_deg"], site["lat_deg"], 300.0, 0)
        h = np.asarray(window.heights_m, dtype=np.float64)
        pixel = float(window.grid.pixel_m) if hasattr(window.grid, "pixel_m") else 20.0
        multiples = np.abs(h / 0.5 - np.round(h / 0.5)) < 1e-6
        steps = np.concatenate([np.diff(h, axis=0).ravel(), np.diff(h, axis=1).ravel()])
        slopes = np.rad2deg(np.arctan(steps / pixel))
        distinct = np.unique(np.round(slopes, 3))
        print(f"== {site['site_id']} ({m['package_id']}), {h.shape[0]} x {h.shape[1]} pixels of {pixel:.0f} m around the site")
        print(f"   1. heights that are exact multiples of 0.5 m: {100.0 * multiples.mean():.2f} %")
        print(f"   2. slope between neighbouring pixels takes {distinct.size} distinct values; the smallest steps are "
              f"{', '.join(f'{v:+.3f}' for v in distinct[np.argsort(np.abs(distinct))][:5])} deg (0.5 m over {pixel:.0f} m is {np.rad2deg(np.arctan(0.5 / pixel)):.3f} deg)")

        # A low-Sun sample of the package: the first with the Sun fully visible and lower than 3 degrees.
        t = m["timeline"]
        n = t["time"]["count"]
        heights = len(m["horizon"]["observer_heights_m"])
        hi = m["horizon"]["default_height_index"]
        az = struct.unpack(f"<{n}f", (d / t["series"]["SUN"]["azimuth_deg"]["file"]).read_bytes())
        el = struct.unpack(f"<{n}f", (d / t["series"]["SUN"]["elevation_deg"]["file"]).read_bytes())
        vis = struct.unpack(f"<{heights * n}f", (d / t["series"]["SUN"]["visible_fraction"]["file"]).read_bytes())
        sample = next(i for i in range(n) if vis[hi * n + i] >= 1.0 and 0.5 < el[i] < 3.0)
        sun_az, sun_el = az[sample], el[sample]
        s = np.arange(2.0, 300.0, 1.0)
        lat, lon = destination(site, sun_az, s, radius)
        profile = np.asarray(terrain.height_m(lon, lat), dtype=np.float64)
        slope = np.rad2deg(np.arctan(np.diff(profile) / np.diff(s)))  # positive: rising towards the Sun
        changes = np.where(np.abs(np.diff(slope)) > 0.05)[0]
        # Sine of the Sun's height above the local surface along that line (the surface faces the Sun more where it rises towards it).
        grazing = np.sin(np.deg2rad(sun_el + slope))
        lit = grazing > 0
        ratio = grazing[lit].max() / max(grazing[lit].min(), 1e-6) if lit.any() else float("nan")
        spacing = np.diff(s[changes]) if changes.size > 1 else np.array([np.nan])
        print(f"   3. sample {sample}: Sun azimuth {sun_az:.1f} deg, elevation {sun_el:.2f} deg. Along that azimuth, 2 to 300 m from the site, metre by metre:")
        print(f"      slope of the surface towards the Sun: {slope.min():+.2f} to {slope.max():+.2f} deg, {np.unique(np.round(slope, 2)).size} distinct values over {slope.size} metres;")
        print(f"      it changes by more than 0.05 deg at {changes.size} places, on average {np.nanmean(spacing):.1f} m apart (median {np.nanmedian(spacing):.1f} m); sizes of the changes: "
              f"median {np.median(np.abs(np.diff(slope))[changes]):.2f} deg, largest {np.abs(np.diff(slope)).max():.2f} deg;")
        print(f"      sine of the Sun's height above the surface: {grazing.min():+.4f} to {grazing.max():+.4f}; share of the line facing away from the Sun {100.0 * (~lit).mean():.0f} %; "
              f"brightest to darkest lit metre {ratio:.1f} to 1 (a level plane would be {np.sin(np.deg2rad(sun_el)):.4f} everywhere)")


if __name__ == "__main__":
    main()
