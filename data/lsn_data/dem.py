"""Reading LOLA polar DEMs (and the synthetic test DEM) with correct georeferencing.

Units: heights are metres above the reference sphere (label ``OFFSET`` =
1 737 400 m), ``radius_m = height_m + reference_radius_m`` is the distance from
the Moon's centre. The raw file stores ``DN`` as little-endian int16 and
``height_m = DN * SCALING_FACTOR`` (0.5 m).

Pyramids (overview levels) are built by :mod:`lsn_data.pyramid`. Level 0 is the
raw file itself (opened with ``numpy.memmap``, nothing is copied); level ``k``
has ``2**k`` times larger pixels.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .georef import PolarGrid, lonlat_to_xy
from .pdslabel import parse_label


@dataclass(frozen=True)
class Window:
    """A block of heights cut out of one level of one product.

    ``heights_m[i, j]`` is the height of the pixel centred at
    ``x = x_ul_m + (j + 0.5) * pixel_m``, ``y = y_ul_m - (i + 0.5) * pixel_m``
    (projection metres, see :mod:`lsn_data.georef`). Values outside the product
    are NaN.
    """

    heights_m: np.ndarray
    grid: PolarGrid
    product_id: str
    level: int
    statistic: str


class PolarDEM:
    """One polar product with its pyramid levels."""

    def __init__(
        self,
        label_path: str | Path,
        data_path: str | Path | None = None,
        pyramid_dir: str | Path | None = None,
    ):
        label_path = Path(label_path)
        self.label = parse_label(label_path)
        lab = self.label
        self.grid0 = PolarGrid.from_label(lab)
        self.product_id = str(lab["FILE_NAME"]).rsplit(".", 1)[0].upper()
        self.product_version = lab.get("PRODUCT_VERSION_ID")
        self.data_set_id = lab.get("DATA_SET_ID")
        if (lab["SAMPLE_TYPE"], int(lab["SAMPLE_BITS"])) != ("LSB_INTEGER", 16):
            raise ValueError(f"unsupported sample type {lab['SAMPLE_TYPE']} {lab['SAMPLE_BITS']}")
        if lab.get("UNIT") != "METER":
            raise ValueError(f"unexpected unit {lab.get('UNIT')!r}")
        self.scale = float(lab["SCALING_FACTOR"])
        self.reference_radius_m = float(lab["OFFSET"])
        if abs(self.reference_radius_m - self.grid0.radius_m) > 1e-6:
            raise ValueError("label OFFSET and body radius disagree")
        if data_path is None:
            data_path = label_path.with_name(str(lab["FILE_NAME"]).lower())
            if not data_path.exists():
                data_path = label_path.with_suffix(".img")
        self.data_path = Path(data_path)
        expect = self.grid0.n_rows * self.grid0.n_cols * 2
        if self.data_path.stat().st_size != expect:
            raise ValueError(f"{self.data_path.name}: size {self.data_path.stat().st_size} != {expect} from label")
        self._levels: dict[tuple[str, int], np.ndarray] = {
            ("mean", 0): np.memmap(self.data_path, dtype="<i2", mode="r", shape=(self.grid0.n_rows, self.grid0.n_cols))
        }
        self._pyr_meta: dict | None = None
        if pyramid_dir is not None:
            self._attach_pyramid(Path(pyramid_dir))

    # -- pyramid ---------------------------------------------------------------------------
    def _attach_pyramid(self, d: Path) -> None:
        meta_path = d / "pyramid.json"
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        self._pyr_meta = meta
        for stat in meta["statistics"]:
            for k in meta["levels"]:
                arr = np.load(d / f"{stat}_L{k}.npy", mmap_mode="r")
                g = self.grid0.decimated(2**k)
                if arr.shape != (g.n_rows, g.n_cols):
                    raise ValueError(f"pyramid level {stat} L{k} has shape {arr.shape}, expected {(g.n_rows, g.n_cols)}")
                self._levels[(stat, k)] = arr
        # Level 0 is both the mean and the max of itself.
        self._levels[("max", 0)] = self._levels[("mean", 0)]

    @property
    def levels(self) -> list[int]:
        return sorted({k for (_, k) in self._levels})

    def grid(self, level: int = 0) -> PolarGrid:
        return self.grid0.decimated(2**level)

    def pixel_m(self, level: int = 0) -> float:
        return self.grid0.pixel_m * 2**level

    def level_for_pixel(self, max_pixel_m: float | None, statistic: str = "mean") -> int:
        """Coarsest available level whose pixel size is <= ``max_pixel_m`` (finest if None or too small)."""
        if max_pixel_m is None:
            return 0
        ok = [k for k in self.levels if (statistic, k) in self._levels and self.pixel_m(k) <= max_pixel_m]
        return max(ok) if ok else 0

    def _array(self, level: int, statistic: str) -> np.ndarray:
        try:
            return self._levels[(statistic, level)]
        except KeyError:
            raise KeyError(
                f"{self.product_id}: no {statistic!r} level {level}; available {sorted(self._levels)}. "
                "Build pyramids with `python -m lsn_data pyramid`."
            ) from None

    # -- point sampling --------------------------------------------------------------------
    def height_xy(self, x_m, y_m, level: int = 0, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        """Heights (m above the reference sphere) at projection coordinates; NaN outside the raster."""
        g = self.grid(level)
        arr = self._array(level, statistic)
        x = np.asarray(x_m, dtype=np.float64)
        y = np.asarray(y_m, dtype=np.float64)
        shape = np.broadcast(x, y).shape
        x, y = np.broadcast_to(x, shape).ravel(), np.broadcast_to(y, shape).ravel()
        row, col = g.xy_to_rowcol(x, y)
        inside = g.covers_xy(x, y)
        out = np.full(x.shape, np.nan)
        if not inside.any():
            return out.reshape(shape)
        r, c = row[inside], col[inside]
        if method == "nearest":
            ri = np.clip(np.rint(r).astype(np.int64), 0, g.n_rows - 1)
            ci = np.clip(np.rint(c).astype(np.int64), 0, g.n_cols - 1)
            vals = arr[ri, ci].astype(np.float64)
        elif method == "bilinear":
            r = np.clip(r, 0.0, g.n_rows - 1.0)
            c = np.clip(c, 0.0, g.n_cols - 1.0)
            r0 = np.minimum(np.floor(r).astype(np.int64), g.n_rows - 2)
            c0 = np.minimum(np.floor(c).astype(np.int64), g.n_cols - 2)
            fr, fc = r - r0, c - c0
            v00 = arr[r0, c0].astype(np.float64)
            v01 = arr[r0, c0 + 1].astype(np.float64)
            v10 = arr[r0 + 1, c0].astype(np.float64)
            v11 = arr[r0 + 1, c0 + 1].astype(np.float64)
            vals = (v00 * (1 - fc) + v01 * fc) * (1 - fr) + (v10 * (1 - fc) + v11 * fc) * fr
        else:
            raise ValueError("method must be 'bilinear' or 'nearest'")
        out[inside] = vals * self.scale
        return out.reshape(shape)

    def height_m(self, lon_deg, lat_deg, level: int = 0, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        x, y = lonlat_to_xy(lon_deg, lat_deg, self.grid0.radius_m, self.grid0.pole)
        return self.height_xy(x, y, level, statistic, method)

    # -- windows ---------------------------------------------------------------------------
    def window_xy(self, x0_m: float, y0_m: float, x1_m: float, y1_m: float, level: int = 0, statistic: str = "mean") -> Window:
        """All pixels of ``level`` whose centres lie inside the box, as float32 metres (no interpolation)."""
        g = self.grid(level)
        arr = self._array(level, statistic)
        xa, xb = sorted((x0_m, x1_m))
        ya, yb = sorted((y0_m, y1_m))
        c_lo = int(np.ceil((xa - g.x_ul_m) / g.pixel_m - 0.5))
        c_hi = int(np.floor((xb - g.x_ul_m) / g.pixel_m - 0.5))
        r_lo = int(np.ceil((g.y_ul_m - yb) / g.pixel_m - 0.5))
        r_hi = int(np.floor((g.y_ul_m - ya) / g.pixel_m - 0.5))
        nr, nc = max(r_hi - r_lo + 1, 0), max(c_hi - c_lo + 1, 0)
        out = np.full((nr, nc), np.nan, dtype=np.float32)
        rs, re = max(r_lo, 0), min(r_hi + 1, g.n_rows)
        cs, ce = max(c_lo, 0), min(c_hi + 1, g.n_cols)
        if re > rs and ce > cs:
            out[rs - r_lo : re - r_lo, cs - c_lo : ce - c_lo] = arr[rs:re, cs:ce].astype(np.float32) * np.float32(self.scale)
        wg = PolarGrid(
            nr,
            nc,
            g.pixel_m,
            g.x_ul_m + c_lo * g.pixel_m,
            g.y_ul_m - r_lo * g.pixel_m,
            g.radius_m,
            g.pole,
        )
        return Window(out, wg, self.product_id, level, statistic)

    def window_around(self, lon_deg: float, lat_deg: float, half_width_m: float, level: int = 0, statistic: str = "mean") -> Window:
        x, y = lonlat_to_xy(lon_deg, lat_deg, self.grid0.radius_m, self.grid0.pole)
        return self.window_xy(x - half_width_m, y - half_width_m, x + half_width_m, y + half_width_m, level, statistic)


class Terrain:
    """Several products read together: the finest one that covers a point wins.

    ``radius_m`` is what a horizon computation needs: the distance from the
    Moon's centre to the surface at (lon, lat).
    """

    def __init__(self, products: list[PolarDEM]):
        if not products:
            raise ValueError("no products")
        self.products = sorted(products, key=lambda p: p.grid0.pixel_m)
        refs = {p.reference_radius_m for p in products}
        if len(refs) != 1:
            raise ValueError(f"products use different reference radii: {refs}")
        self.reference_radius_m = refs.pop()
        poles = {p.grid0.pole for p in products}
        if len(poles) != 1:
            raise ValueError("products belong to different poles")
        self.pole = poles.pop()

    def height_m(self, lon_deg, lat_deg, max_pixel_m=None, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        """Heights above the reference sphere in metres; NaN where no product covers the point.

        ``max_pixel_m`` (scalar or array broadcastable to the points): the pixel size is chosen
        as the coarsest level not larger than this. Use a growing value with distance so that
        far terrain is read from overviews. ``None`` means the finest data available.
        """
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        want_in = np.asarray(0.0 if max_pixel_m is None else max_pixel_m, dtype=np.float64)
        shape = np.broadcast(lon, lat, want_in).shape
        lon = np.broadcast_to(lon, shape).ravel()
        lat = np.broadcast_to(lat, shape).ravel()
        want = np.broadcast_to(want_in, shape).ravel()  # 0 means "finest available"
        x, y = lonlat_to_xy(lon, lat, self.products[0].grid0.radius_m, self.pole)
        out = np.full(lon.shape, np.nan)
        todo = np.ones(lon.shape, dtype=bool)
        # Rule: a point is read from the (product, level) pair with the coarsest pixel that is
        # not larger than the request and that covers the point. If the request is finer than
        # anything covering the point, the finest covering product is used at level 0.
        pairs = [(p, k) for p in self.products for k in p.levels if (statistic, k) in p._levels]
        pairs.sort(key=lambda pk: -pk[0].pixel_m(pk[1]))  # coarsest first
        for p, k in pairs:
            sel = todo & (want >= p.pixel_m(k)) & p.grid(k).covers_xy(x, y)
            if sel.any():
                out[sel] = p.height_xy(x[sel], y[sel], k, statistic, method)
                todo &= ~sel
        for p in self.products:  # finest first
            if not todo.any():
                break
            sel = todo & p.grid(0).covers_xy(x, y)
            if sel.any():
                out[sel] = p.height_xy(x[sel], y[sel], 0, "mean", method)
                todo &= ~sel
        return out.reshape(shape)

    def radius_m(self, lon_deg, lat_deg, max_pixel_m=None, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        return self.height_m(lon_deg, lat_deg, max_pixel_m, statistic, method) + self.reference_radius_m

    def provenance(self) -> list[dict]:
        return [
            {
                "product_id": p.product_id,
                "product_version": p.product_version,
                "data_set_id": p.data_set_id,
                "pixel_m": p.grid0.pixel_m,
                "reference_radius_m": p.reference_radius_m,
                "file": p.data_path.name,
            }
            for p in self.products
        ]
