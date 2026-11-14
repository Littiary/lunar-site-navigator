"""Small synthetic simple-cylindrical tiles and a synthetic north-polar DEM for tests. NOT LOLA data.

The cylindrical tiles use the label keys of the LOLA/SLDEM2015 cylindrical products (CENTER_LONGITUDE = 180,
offsets counted as in DSMAP.CAT) so the same reader opens them. Heights are an analytic function of latitude and
longitude, ``height_m(lon, lat) = 10 * lat + 0.5 * lon_east_0_360`` (metres), linear inside every cell, so bilinear
interpolation reproduces it exactly except across the 0/360 meridian.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from . import synthetic
from .georef import REFERENCE_RADIUS_M


def height_m(lon_deg, lat_deg):
    return 10.0 * np.asarray(lat_deg, dtype=np.float64) + 0.5 * np.mod(np.asarray(lon_deg, dtype=np.float64), 360.0)


def write_tile(out_dir, product_id: str, res_ppd: float, lat_s: float, lat_n: float, lon_w: float, lon_e: float,
               dtype: str = "<f4", unit: str = "KILOMETER") -> Path:
    """Write ``<product_id>.lbl`` / ``.img``: a tile covering [lat_s, lat_n] x [lon_w, lon_e] at ``res_ppd``."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    n_rows = int(round((lat_n - lat_s) * res_ppd))
    n_cols = int(round((lon_e - lon_w) * res_ppd))
    lat = lat_n - (np.arange(n_rows) + 0.5) / res_ppd
    lon = lon_w + (np.arange(n_cols) + 0.5) / res_ppd
    h = height_m(lon[None, :], lat[:, None])
    if dtype == "<f4":
        sample = ("PC_REAL", 32)
        to_unit = 1e-3 if unit == "KILOMETER" else 1.0
        data = (h * to_unit).astype("<f4")
        scale, offset = 1, (REFERENCE_RADIUS_M / 1000 if unit == "KILOMETER" else REFERENCE_RADIUS_M)
    else:
        sample = ("LSB_INTEGER", 16)
        unit, scale, offset = "METER", 0.5, REFERENCE_RADIUS_M
        data = np.rint(h / 0.5).astype("<i2")
    # DSMAP.CAT: col = SAMPLE_PROJECTION_OFFSET + RES * (LON - 180), row = LINE_PROJECTION_OFFSET - RES * LAT
    spo = -0.5 - res_ppd * (lon_w - 180.0)
    lpo = res_ppd * lat_n - 0.5
    lbl = out / f"{product_id.lower()}.lbl"
    lbl.write_text(f'''PDS_VERSION_ID            = "PDS3"
PRODUCT_VERSION_ID        = "SYNTHETIC-1"
DATA_SET_ID               = "KESTRO-SYNTHETIC-TEST"
PRODUCT_ID                = "{product_id}"
DESCRIPTION               = "SYNTHETIC TEST TILE. NOT LOLA DATA."
OBJECT                    = UNCOMPRESSED_FILE
FILE_NAME                 = "{product_id}.IMG"
^IMAGE                    = "{product_id}.IMG"
  OBJECT                  = IMAGE
    LINES                 = {n_rows}
    LINE_SAMPLES          = {n_cols}
    SAMPLE_TYPE           = {sample[0]}
    SAMPLE_BITS           = {sample[1]}
    UNIT                  = {unit}
    SCALING_FACTOR        = {scale}
    OFFSET                = {offset}
  END_OBJECT              = IMAGE
END_OBJECT                = UNCOMPRESSED_FILE
OBJECT                    = IMAGE_MAP_PROJECTION
 MAP_PROJECTION_TYPE          = "SIMPLE CYLINDRICAL"
 MAP_RESOLUTION               = {res_ppd:g} <pix/deg>
 A_AXIS_RADIUS                = {REFERENCE_RADIUS_M / 1000} <km>
 B_AXIS_RADIUS                = {REFERENCE_RADIUS_M / 1000} <km>
 C_AXIS_RADIUS                = {REFERENCE_RADIUS_M / 1000} <km>
 POSITIVE_LONGITUDE_DIRECTION = "EAST"
 CENTER_LATITUDE              = 0. <deg>
 CENTER_LONGITUDE             = 180. <deg>
 MAXIMUM_LATITUDE             = {lat_n:g} <deg>
 MINIMUM_LATITUDE             = {lat_s:g} <deg>
 WESTERNMOST_LONGITUDE        = {lon_w:g} <deg>
 EASTERNMOST_LONGITUDE        = {lon_e:g} <deg>
 LINE_PROJECTION_OFFSET       = {lpo} <pix>
 SAMPLE_PROJECTION_OFFSET     = {spo} <pix>
END_OBJECT                    = IMAGE_MAP_PROJECTION
END
''', encoding="ascii")
    (out / f"{product_id.lower()}.img").write_bytes(data.tobytes())
    return lbl


def write_north_polar(out_dir, product_id: str = "SYNTH_N90_100M") -> Path:
    """The south synthetic DEM's array relabelled as a north-polar product (same array, mirrored geography)."""
    out = Path(out_dir)
    lbl, dat = synthetic.write(out, product_id=product_id)
    text = lbl.read_text(encoding="ascii").replace("CENTER_LATITUDE              = -90 <deg>", "CENTER_LATITUDE              = 90 <deg>")
    lbl.write_text(text, encoding="ascii")
    return lbl
