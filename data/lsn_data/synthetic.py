"""A small synthetic south-polar DEM for tests. NOT LOLA data.

It uses exactly the file format and label keys of the real LDEM_*S_* products, so
the same reader opens it. The surface is an analytic function of the projection
coordinates, so tests can compare against exact values:

* a base at height 0 (the 1 737 400 m sphere). The three terms below are summed, so the
  surface is flat only beyond about 15 km from the pole and away from the cone;
* a cone of height 1500 m with its apex at (x, y) = (+8000, 0) m, base radius 3000 m, linear flanks;
* a ring ridge: Gaussian crest of +800 m at 12 km from the pole, sigma 1 km, and a bowl
  of -400 m (Gaussian, sigma 6 km) at the pole.

Grid: 400 x 400 pixels of 100 m, pole at the centre corner, DN = round(height / 0.5).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .georef import REFERENCE_RADIUS_M

N = 400
PIXEL_M = 100.0
SCALE = 0.5
PRODUCT_ID = "SYNTH_S90_100M"

CONE_X, CONE_Y, CONE_H, CONE_R = 8000.0, 0.0, 1500.0, 3000.0
RING_R, RING_SIGMA, RING_H = 12000.0, 1000.0, 800.0
BOWL_SIGMA, BOWL_DEPTH = 6000.0, -400.0


def height_m(x_m, y_m):
    """Exact (unquantised) height in metres above the reference sphere."""
    x = np.asarray(x_m, dtype=np.float64)
    y = np.asarray(y_m, dtype=np.float64)
    rho = np.hypot(x, y)
    d = np.hypot(x - CONE_X, y - CONE_Y)
    cone = CONE_H * np.clip(1.0 - d / CONE_R, 0.0, None)
    ring = RING_H * np.exp(-0.5 * ((rho - RING_R) / RING_SIGMA) ** 2)
    bowl = BOWL_DEPTH * np.exp(-0.5 * (rho / BOWL_SIGMA) ** 2)
    return cone + ring + bowl


def dn_array(n: int = N, pixel_m: float = PIXEL_M) -> np.ndarray:
    half = n * pixel_m / 2
    c = (np.arange(n) + 0.5) * pixel_m
    x = -half + c[None, :]
    y = half - c[:, None]
    return np.rint(height_m(x, y) / SCALE).astype("<i2")


def label_text(dn: np.ndarray, n: int = N, pixel_m: float = PIXEL_M, product_id: str = PRODUCT_ID) -> str:
    return f'''PDS_VERSION_ID            = "PDS3"
PRODUCT_VERSION_ID        = "SYNTHETIC-1"
DATA_SET_ID               = "KESTRO-SYNTHETIC-TEST"
TARGET_NAME               = MOON
DESCRIPTION               = "SYNTHETIC TEST DEM. NOT LOLA DATA. Analytic surface for unit
   tests of the reader, see lsn_data/synthetic.py. Same layout as LDEM_80S_20M."

OBJECT                    = UNCOMPRESSED_FILE
FILE_NAME                 = "{product_id}.DAT"
RECORD_TYPE               = FIXED_LENGTH
FILE_RECORDS              = {n}
RECORD_BYTES              = {n * 2}
^IMAGE                    = "{product_id}.DAT"
  OBJECT                  = IMAGE
    NAME                  = HEIGHT
    LINES                 = {n}
    LINE_SAMPLES          = {n}
    DERIVED_MINIMUM       = {int(dn.min())}
    DERIVED_MAXIMUM       = {int(dn.max())}
    SAMPLE_TYPE           = LSB_INTEGER
    SAMPLE_BITS           = 16
    UNIT                  = METER
    SCALING_FACTOR        = {SCALE}
    OFFSET                = {REFERENCE_RADIUS_M:.0f}.
  END_OBJECT              = IMAGE
END_OBJECT                = UNCOMPRESSED_FILE

OBJECT                    = IMAGE_MAP_PROJECTION
 MAP_PROJECTION_TYPE          = "POLAR STEREOGRAPHIC"
 KEYWORD_LATITUDE_TYPE        = "PLANETOCENTRIC"
 A_AXIS_RADIUS                = {REFERENCE_RADIUS_M / 1000} <km>
 B_AXIS_RADIUS                = {REFERENCE_RADIUS_M / 1000} <km>
 C_AXIS_RADIUS                = {REFERENCE_RADIUS_M / 1000} <km>
 POSITIVE_LONGITUDE_DIRECTION = "EAST"
 CENTER_LATITUDE              = -90 <deg>
 CENTER_LONGITUDE             = 0 <deg>
 MAP_SCALE                    = {pixel_m:g} <m/pix>
 LINE_PROJECTION_OFFSET       = {n / 2 - 0.5} <pix>
 SAMPLE_PROJECTION_OFFSET     = {n / 2 - 0.5} <pix>
END_OBJECT                    = IMAGE_MAP_PROJECTION

END
'''


def write(out_dir: str | Path, n: int = N, pixel_m: float = PIXEL_M, product_id: str = PRODUCT_ID) -> tuple[Path, Path]:
    """Write ``<product_id>.lbl`` and ``.dat`` (deterministic bytes) into ``out_dir``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dn = dn_array(n, pixel_m)
    lbl = out / f"{product_id.lower()}.lbl"
    dat = out / f"{product_id.lower()}.dat"
    lbl.write_bytes(label_text(dn, n, pixel_m, product_id).encode("ascii"))
    dat.write_bytes(dn.tobytes())
    return lbl, dat


if __name__ == "__main__":
    import sys

    print(*write(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "fixtures"))
