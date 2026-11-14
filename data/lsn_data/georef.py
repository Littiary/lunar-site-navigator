"""Spherical polar stereographic projection and the pixel grid of a LOLA polar product.

Conventions (read from the PDS labels, see ``PolarGrid.from_label``)
---------------------------------------------------------------------
* The Moon is a sphere of radius ``radius_m`` (1 737 400 m for LOLA GDRs).
* Latitude is planetocentric (on a sphere this equals geodetic), degrees.
* Longitude is positive east, degrees, any range; the central meridian is 0.
* "True at the pole": distance from the pole is ``rho = 2 R tan(colatitude / 2)``,
  so the scale factor is 1 at the pole and grows with distance.
* South pole: ``x = rho sin(lon)``, ``y = rho cos(lon)`` (0 deg longitude points
  to +y, 90 deg east to +x). North pole: ``y`` changes sign.
* Pixels are area pixels. Row 0 is the top row (largest y), column 0 the left
  column. The pole is at a pixel corner, because the images have an even size.
  ``x_ul_m`` and ``y_ul_m`` are the coordinates of the outer corner of pixel (0, 0).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

REFERENCE_RADIUS_M = 1_737_400.0  # LOLA GDR reference sphere; the label value is used when a label is read


def lonlat_to_xy(lon_deg, lat_deg, radius_m: float = REFERENCE_RADIUS_M, pole: int = -1):
    """Projection coordinates in metres of (lon, lat). ``pole`` is -1 (south) or +1 (north)."""
    lon = np.radians(np.asarray(lon_deg, dtype=np.float64))
    lat = np.radians(np.asarray(lat_deg, dtype=np.float64))
    colat = (np.pi / 2) + lat if pole < 0 else (np.pi / 2) - lat  # angle from the pole
    rho = 2.0 * radius_m * np.tan(colat / 2.0)
    x = rho * np.sin(lon)
    y = rho * np.cos(lon) if pole < 0 else -rho * np.cos(lon)
    return x, y


def xy_to_lonlat(x_m, y_m, radius_m: float = REFERENCE_RADIUS_M, pole: int = -1):
    """Inverse of :func:`lonlat_to_xy`. Longitude is returned in [0, 360)."""
    x = np.asarray(x_m, dtype=np.float64)
    y = np.asarray(y_m, dtype=np.float64)
    rho = np.hypot(x, y)
    colat = 2.0 * np.arctan(rho / (2.0 * radius_m))
    lat = np.degrees(-(np.pi / 2) + colat) if pole < 0 else np.degrees((np.pi / 2) - colat)
    lon = np.degrees(np.arctan2(x, y if pole < 0 else -y)) % 360.0
    return lon, lat


@dataclass(frozen=True)
class PolarGrid:
    """Geometry of one polar stereographic raster (one pyramid level of one product)."""

    n_rows: int
    n_cols: int
    pixel_m: float
    x_ul_m: float
    y_ul_m: float
    radius_m: float = REFERENCE_RADIUS_M
    pole: int = -1

    @classmethod
    def from_label(cls, lab: dict) -> "PolarGrid":
        """Build the grid from a parsed PDS3 label (see :mod:`lsn_data.pdslabel`)."""
        if lab.get("MAP_PROJECTION_TYPE") != "POLAR STEREOGRAPHIC":
            raise ValueError(f"not a polar stereographic product: {lab.get('MAP_PROJECTION_TYPE')!r}")
        radii = {lab["A_AXIS_RADIUS"], lab["B_AXIS_RADIUS"], lab["C_AXIS_RADIUS"]}
        if len(radii) != 1:
            raise ValueError(f"the body is not a sphere in this label: {radii}")
        if lab["CENTER_LONGITUDE"] != 0 or lab.get("POSITIVE_LONGITUDE_DIRECTION") != "EAST":
            raise ValueError("unsupported central meridian or longitude direction")
        if lab.get("KEYWORD_LATITUDE_TYPE") != "PLANETOCENTRIC":
            raise ValueError("expected planetocentric latitude")
        clat = lab["CENTER_LATITUDE"]
        if clat not in (-90, 90):
            raise ValueError(f"not a polar product: CENTER_LATITUDE={clat}")
        px = float(lab["MAP_SCALE"])
        # PDS3 offsets count pixel centres from the first pixel centre (0-based here):
        # the pole is at pixel-centre coordinate OFFSET, so at OFFSET + 0.5 pixels from the corner.
        return cls(
            n_rows=int(lab["LINES"]),
            n_cols=int(lab["LINE_SAMPLES"]),
            pixel_m=px,
            x_ul_m=-(float(lab["SAMPLE_PROJECTION_OFFSET"]) + 0.5) * px,
            y_ul_m=(float(lab["LINE_PROJECTION_OFFSET"]) + 0.5) * px,
            radius_m=float(lab["A_AXIS_RADIUS"]) * 1000.0,
            pole=-1 if clat < 0 else 1,
        )

    # -- coordinate conversions ------------------------------------------------------------
    def xy_to_rowcol(self, x_m, y_m):
        """Fractional pixel-centre coordinates (row, col). Pixel (i, j) has its centre at (i, j)."""
        col = (np.asarray(x_m, dtype=np.float64) - self.x_ul_m) / self.pixel_m - 0.5
        row = (self.y_ul_m - np.asarray(y_m, dtype=np.float64)) / self.pixel_m - 0.5
        return row, col

    def rowcol_to_xy(self, row, col):
        x = self.x_ul_m + (np.asarray(col, dtype=np.float64) + 0.5) * self.pixel_m
        y = self.y_ul_m - (np.asarray(row, dtype=np.float64) + 0.5) * self.pixel_m
        return x, y

    def lonlat_to_rowcol(self, lon_deg, lat_deg):
        x, y = lonlat_to_xy(lon_deg, lat_deg, self.radius_m, self.pole)
        return self.xy_to_rowcol(x, y)

    def rowcol_to_lonlat(self, row, col):
        x, y = self.rowcol_to_xy(row, col)
        return xy_to_lonlat(x, y, self.radius_m, self.pole)

    # -- extent -----------------------------------------------------------------------------
    @property
    def x_lr_m(self) -> float:
        return self.x_ul_m + self.n_cols * self.pixel_m

    @property
    def y_lr_m(self) -> float:
        return self.y_ul_m - self.n_rows * self.pixel_m

    def covers_xy(self, x_m, y_m):
        """True where (x, y) lies inside the raster (pixel edges included)."""
        x = np.asarray(x_m)
        y = np.asarray(y_m)
        return (x >= self.x_ul_m) & (x <= self.x_lr_m) & (y <= self.y_ul_m) & (y >= self.y_lr_m)

    def decimated(self, factor: int) -> "PolarGrid":
        """The grid of a pyramid level with ``factor`` x ``factor`` pixel blocks."""
        if self.n_rows % factor or self.n_cols % factor:
            raise ValueError("raster size is not a multiple of the decimation factor")
        return PolarGrid(
            self.n_rows // factor,
            self.n_cols // factor,
            self.pixel_m * factor,
            self.x_ul_m,
            self.y_ul_m,
            self.radius_m,
            self.pole,
        )
