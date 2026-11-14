"""Compare the horizon silhouette of the Unreal terrain mesh with the package, in Python.

The Unreal test LunarSiteNavigator.Acceptance.HorizonExportForPython writes, for every
observer height and azimuth sample, the elevation angle of the highest point of the scene's
terrain mesh seen from the observer (Saved/Lsn/horizon_silhouette.csv). This script reads
horizon.elevation_deg of the same package with the Python standard library only, so the
comparison does not rest on the C++ package reader.

Usage: python compare_horizon.py [site package directory] [silhouette csv]
Without arguments it uses the pinned contract sample and the file the test writes.
Exit code 0 if every sample is present and within the tolerance.
"""

import csv
import json
import struct
import sys
from pathlib import Path

# Same value as SilhouetteToleranceDeg in Tests/LsnAcceptanceTests.cpp.
TOLERANCE_DEG = 0.001


def default_package(root: Path) -> Path:
    packages = root / "TestData" / "contract-sample" / "packages"
    index = json.loads((packages / "index.json").read_text(encoding="utf-8"))
    return packages / next(p["path"] for p in index["packages"] if p["kind"] == "site")


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    package = Path(sys.argv[1]) if len(sys.argv) > 1 else default_package(root)
    csv_path = Path(sys.argv[2]) if len(sys.argv) > 2 else root / "Saved" / "Lsn" / "horizon_silhouette.csv"

    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))
    horizon = manifest["horizon"]
    ref = horizon["elevation_deg"]
    heights, count = ref["shape"]
    start, step = horizon["azimuth"]["start_deg"], horizon["azimuth"]["step_deg"]
    if ref["dtype"] != "<f4":
        raise SystemExit(f"unexpected dtype {ref['dtype']}")
    values = struct.unpack(f"<{heights * count}f", (package / ref["file"]).read_bytes())

    worst, worst_row, rows = 0.0, None, 0
    with csv_path.open(newline="") as handle:
        for row in csv.DictReader(handle):
            h, az, scene = int(row["height_index"]), float(row["azimuth_deg"]), float(row["scene_elevation_deg"])
            a = round((az - start) / step)
            if abs(start + a * step - az) > 1e-6:
                raise SystemExit(f"azimuth {az} is not a sample of the package")
            diff = abs(scene - values[h * count + a % count])
            rows += 1
            if diff > worst:
                worst, worst_row = diff, (h, az)
    ok = rows == heights * count and worst <= TOLERANCE_DEG
    print(f"package        {manifest['package_id']} (synthetic: {manifest['synthetic']})")
    print(f"rows compared  {rows} (expected {heights * count})")
    if worst_row is not None:
        print(f"largest diff   {worst:.6f} deg at height index {worst_row[0]}, azimuth {worst_row[1]:.3f} deg")
    print(f"tolerance      {TOLERANCE_DEG} deg")
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
