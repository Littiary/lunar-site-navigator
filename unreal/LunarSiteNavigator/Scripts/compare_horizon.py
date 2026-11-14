"""Compare the horizon silhouette measured in the Unreal scene with the package.

The Unreal test Lsn.Scene.HorizonSilhouette writes, for every observer height and for
every azimuth sample and mid-sample, the elevation angle of the highest point of the scene
mesh seen from the observer. This script reads horizon.elevation_deg of the same package
with Python only (no Unreal reader involved) and repeats the comparison.

Usage: python compare_horizon.py <site package directory> <silhouette csv>
Exit code 0 if the largest difference is within the tolerance.
"""

import csv
import json
import struct
import sys
from pathlib import Path

# Same value as LsnTolerances::HorizonSilhouetteDeg; written before the first measurement.
TOLERANCE_DEG = 0.05


def main() -> int:
    package, csv_path = Path(sys.argv[1]), Path(sys.argv[2])
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    horizon = manifest["horizon"]
    ref = horizon["elevation_deg"]
    heights, count = ref["shape"]
    step = horizon["azimuth"]["step_deg"]
    if ref["dtype"] != "<f4":
        raise SystemExit(f"unexpected dtype {ref['dtype']}")
    raw = (package / ref["file"]).read_bytes()
    values = struct.unpack(f"<{heights * count}f", raw)

    def package_elevation(h: int, az_deg: float) -> float:
        # Linear, periodic interpolation between azimuth samples (SPEC 5.3).
        pos = (az_deg % 360.0) / step
        lo = int(pos) % count
        t = pos - int(pos)
        return (1.0 - t) * values[h * count + lo] + t * values[h * count + (lo + 1) % count]

    worst, worst_row, rows = 0.0, None, 0
    with csv_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            h, az, scene = int(row["height_index"]), float(row["azimuth_deg"]), float(row["scene_elevation_deg"])
            diff = abs(scene - package_elevation(h, az))
            rows += 1
            if diff > worst:
                worst, worst_row = diff, (h, az, scene)
    expected_rows = heights * count * 2
    ok = rows == expected_rows and worst <= TOLERANCE_DEG
    print(f"package        {manifest['package_id']} (synthetic: {manifest['synthetic']})")
    print(f"rows compared  {rows} (expected {expected_rows})")
    print(f"largest diff   {worst:.5f} deg at height index {worst_row[0]}, azimuth {worst_row[1]:.3f} deg")
    print(f"tolerance      {TOLERANCE_DEG} deg")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
