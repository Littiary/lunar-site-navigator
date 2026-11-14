"""Exports what the scene needs to draw the stars where they stand: a star list and, per
site, the orientation of the sky.

The stars are decoration. No number on screen comes from them, and the Sun and the Earth
are drawn from the package as before. But a star field that is drawn should be the real
one, the right way round for the date, so this script takes

  * the star positions and magnitudes from the Yale Bright Star Catalogue, 5th revised
    edition (Hoffleit & Warren 1991; file bsc5.dat / catalog.gz, 9110 entries), and
  * the orientation of the Moon from the SPICE kernels the ephemeris stream uses,

and writes

  Content/LsnSky/stars.json, stars.f4
      [N, 5] float32: unit vector in the J2000 (ICRF) frame, visual magnitude, B-V colour
      index (NaN where the catalogue has none). Under version control: small, and the same
      for every package.
  Content/LsnSky/<site_id>/orientation.json, orientation.f8
      [T, 9] float64: for a list of times, the matrix that takes a J2000 vector to the
      site's east, north, up axes (rows east, north, up). The site axes are those of the
      package; the Moon's orientation at each time is SPICE's pxform(J2000 -> package frame).
      Tied to the package id; not under version control (like the terrain samples).
      "check" holds, for a few timeline samples, SPICE's direction of the Sun in J2000 as
      seen from the Moon's centre: the scene's tests turn it with the matrix and compare
      it with the Sun direction of the package, which checks the whole chain on real data.

The engine computes nothing of this itself; between two listed times it interpolates the
orientation for a smooth display. Not modelled: proper motion since J2000, aberration,
the difference between the site and the Moon's centre (all far below a pixel).

Usage (Python environment with numpy and spiceypy):
    python export_sky.py <package root> [--catalogue C:\\lsn-data\\raw\\bsc5\\catalog.gz]
                         [--kernels C:\\Projects\\lsn-ephem\\data\\kernels] [--step-hours 6]
"""

from __future__ import annotations

import argparse
import datetime
import gzip
import json
from pathlib import Path

import numpy as np
import spiceypy as spice

FAINTEST_MAG = 6.5
FORMAT_STARS = {"name": "lsn-unreal-stars", "version": "1"}
FORMAT_SKY = {"name": "lsn-unreal-sky-orientation", "version": "1"}


def read_catalogue(path: Path) -> np.ndarray:
    opener = gzip.open if path.suffix == ".gz" else open
    rows = []
    with opener(path, "rt", encoding="latin-1") as handle:
        for line in handle:
            # Byte positions of the catalogue's ReadMe: RA 76-83 and Dec 84-90 (J2000), Vmag 103-107, B-V 110-114.
            if len(line) < 107 or not line[75:77].strip() or not line[102:107].strip():
                continue  # the catalogue keeps a few numbers of objects that are no stars
            ra = (int(line[75:77]) + int(line[77:79]) / 60.0 + float(line[79:83]) / 3600.0) * 15.0
            dec = (int(line[84:86]) + int(line[86:88]) / 60.0 + int(line[88:90]) / 3600.0) * (-1.0 if line[83] == "-" else 1.0)
            mag = float(line[102:107])
            colour = float(line[109:114]) if line[109:114].strip() else float("nan")
            if mag <= FAINTEST_MAG:
                a, d = np.deg2rad(ra), np.deg2rad(dec)
                rows.append((np.cos(d) * np.cos(a), np.cos(d) * np.sin(a), np.sin(d), mag, colour))
    return np.asarray(rows, dtype="<f4")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("package_root", type=Path)
    parser.add_argument("--catalogue", type=Path, default=Path(r"C:\lsn-data\raw\bsc5\catalog.gz"))
    parser.add_argument("--kernels", type=Path, default=Path(r"C:\Projects\lsn-ephem\data\kernels"))
    parser.add_argument("--out", type=Path, default=Path(__file__).resolve().parent.parent / "Content" / "LsnSky")
    parser.add_argument("--step-hours", type=float, default=6.0)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    made = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    stars = read_catalogue(args.catalogue)
    (args.out / "stars.f4").write_bytes(stars.tobytes())
    (args.out / "stars.json").write_text(json.dumps({
        "format": FORMAT_STARS, "count": int(stars.shape[0]), "columns": ["x_j2000", "y_j2000", "z_j2000", "v_mag", "b_minus_v"],
        "file": "stars.f4", "dtype": "<f4", "faintest_mag": FAINTEST_MAG,
        "source": "Yale Bright Star Catalogue, 5th revised edition (Hoffleit & Warren 1991), positions J2000",
        "source_file": args.catalogue.name, "generated_utc": made,
    }, indent=1) + "\n", encoding="utf-8")
    print(f"{stars.shape[0]} stars to magnitude {FAINTEST_MAG} -> {args.out / 'stars.f4'}")

    kernels = sorted(p for p in args.kernels.iterdir() if p.suffix.lower() in (".tls", ".tpc", ".bpc", ".tf", ".bsp"))
    for kernel in kernels:
        spice.furnsh(str(kernel))
    index = json.loads((args.package_root / "index.json").read_text(encoding="utf-8"))
    for entry in index["packages"]:
        if entry["kind"] != "site" or not entry.get("has_timeline", True):
            continue
        manifest = json.loads((args.package_root / entry["path"] / "manifest.json").read_text(encoding="utf-8"))
        site, time = manifest["site"], manifest["timeline"]["time"]
        frame = site["frame"] if "frame" in site else manifest["site"]["enu"].get("frame")
        axes = np.array([site["enu"]["east"], site["enu"]["north"], site["enu"]["up"]], dtype=np.float64)
        start, end = time["start_et_s"], time["start_et_s"] + time["step_s"] * (time["count"] - 1)
        step = args.step_hours * 3600.0
        count = int(np.ceil((end - start) / step)) + 1
        matrices = np.empty((count, 9), dtype="<f8")
        for i in range(count):
            body_from_j2000 = np.asarray(spice.pxform("J2000", frame, start + i * step))
            matrices[i] = (axes @ body_from_j2000).ravel()
        checks = []
        for sample in np.linspace(0, time["count"] - 1, 9).astype(int):
            et = time["start_et_s"] + time["step_s"] * int(sample)
            position, _ = spice.spkpos("SUN", et, "J2000", "LT+S", "MOON")
            checks.append({"sample": int(sample), "et_s": et, "sun_j2000": (np.asarray(position) / np.linalg.norm(position)).tolist()})
        folder = args.out / site["site_id"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "orientation.f8").write_bytes(matrices.tobytes())
        (folder / "orientation.json").write_text(json.dumps({
            "format": FORMAT_SKY, "site_id": site["site_id"], "package_id": manifest["package_id"], "frame": frame,
            "start_et_s": start, "step_s": step, "count": count, "file": "orientation.f8", "dtype": "<f8",
            "rows": ["east", "north", "up"], "kernels": [k.name for k in kernels], "check": checks, "generated_utc": made,
        }, indent=1) + "\n", encoding="utf-8")
        print(f"{site['site_id']}: {count} orientations every {args.step_hours:g} h for {manifest['package_id']} -> {folder}")


if __name__ == "__main__":
    main()
