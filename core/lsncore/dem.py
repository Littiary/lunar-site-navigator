"""Terrain interface of the horizon core.

The horizon code needs five things from a terrain source: the radius of the reference
sphere, the height above that sphere at given coordinates on the finest data, an upper
bound of the height in a neighbourhood of given points (so that stretches of a ray can be
proven irrelevant without walking them), the finest pixel size, and a description for
the package record. Real LOLA data comes from the data stream's reader (``lsn_data``),
wrapped by :class:`LolaTerrain`; tests use :class:`AnalyticTerrain`.
"""

from __future__ import annotations

import math
from typing import Callable, Protocol

import numpy as np


class Terrain(Protocol):
    reference_radius_m: float
    finest_pixel_m: float
    ceiling_height_m: float | None
    max_cover_radius_m: float

    def height_m(self, lon_deg, lat_deg) -> np.ndarray:
        """Height of the surface above the reference sphere in metres, on the finest data;
        NaN where there is no data. lon_deg (east positive) and lat_deg broadcast."""

    def cover_max_m(self, lon_deg, lat_deg, radius_m) -> np.ndarray:
        """Upper bound of height_m over all points within radius_m (arc length on the
        reference sphere) of each given point. NaN where there is no data in that
        neighbourhood. radius_m must not exceed max_cover_radius_m."""

    def crease_fractions(self, lon_deg, lat_deg) -> np.ndarray:
        """Where the surface has creases between consecutive points of a flat point list.

        Returns an array [P - 1, n]: for the segment from point i to point i + 1, the
        positions (as fractions 0..1 of the segment) at which the slope of the surface
        along the segment is discontinuous; NaN where there is none. A gridded bilinear
        surface has such creases where a segment crosses a line through pixel centres.
        """

    def describe(self) -> dict:
        """The ``inputs.dem`` object of the package contract."""

    def height_at_pixel_m(self, lon_deg, lat_deg, pixel_m: float) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        """Height on the coarsest stored level whose pixel is not larger than pixel_m (the
        finest data where there is no such level). Used for drawing, never for the horizon.

        Returns the heights, for every point the index of the source it was read from
        (-1 without data), and the sources: product_id, level, pixel_m, statistic, sha256
        and, for a derived level, derived_from_sha256.
        """


class AnalyticTerrain:
    """Terrain given by a function ``height(lon_deg, lat_deg)``: exact, no grid.

    max_slope is an upper bound of the surface gradient (rise over run). It makes the
    neighbourhood bound rigorous: within radius r the surface cannot exceed the centre
    value by more than max_slope * r.
    """

    def __init__(
        self,
        height: Callable,
        reference_radius_m: float,
        finest_pixel_m: float = 20.0,
        ceiling_height_m: float | None = None,
        dem_set_id: str = "ANALYTIC-test-surface",
        max_slope: float = 1.0,
    ):
        self._height = height
        self.reference_radius_m = float(reference_radius_m)
        self.finest_pixel_m = float(finest_pixel_m)
        self.ceiling_height_m = ceiling_height_m
        self.dem_set_id = dem_set_id
        self.max_slope = float(max_slope)
        self.max_cover_radius_m = math.inf
        self.is_synthetic = True

    def height_m(self, lon_deg, lat_deg) -> np.ndarray:
        return np.asarray(self._height(np.asarray(lon_deg, dtype=np.float64), np.asarray(lat_deg, dtype=np.float64)), dtype=np.float64)

    def cover_max_m(self, lon_deg, lat_deg, radius_m) -> np.ndarray:
        return self.height_m(lon_deg, lat_deg) + self.max_slope * np.asarray(radius_m, dtype=np.float64)

    def crease_fractions(self, lon_deg, lat_deg) -> np.ndarray:
        return np.full((max(np.asarray(lon_deg).size - 1, 0), 1), np.nan)  # no grid, no creases

    def describe(self) -> dict:
        return {"dem_set_id": self.dem_set_id, "layers": []}

    def height_at_pixel_m(self, lon_deg, lat_deg, pixel_m: float) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        height = self.height_m(lon_deg, lat_deg)
        source = {"product_id": self.dem_set_id, "level": 0, "pixel_m": self.finest_pixel_m, "statistic": "function", "sha256": None}
        return height, np.where(np.isfinite(height), 0, -1), [source]


def open_lola(label_paths=None) -> "LolaTerrain":
    """Open LOLA terrain through the data stream's reader.

    label_paths: PDS3 labels to open; None opens the default products under the data root
    (LSN_DATA_ROOT), with their overview levels.
    """
    try:
        import lsn_data
    except ImportError as err:  # pragma: no cover - depends on the environment
        raise RuntimeError("the data reader is not installed: pip install -e data") from err
    return LolaTerrain(lsn_data.open_terrain(label_paths=label_paths))


class LolaTerrain:
    """Adapter around the data stream's ``lsn_data.dem.Terrain``.

    The surface is the bilinear interpolation of the finest product that covers a point,
    exactly as the data reader returns it. The neighbourhood bound is read from the
    block-maximum overview levels of the products.
    """

    # Margin on the neighbourhood radius for the change of map scale across a neighbourhood.
    _SCALE_MARGIN = 1.01

    def __init__(self, terrain):
        self._terrain = terrain
        self.reference_radius_m = float(terrain.reference_radius_m)
        self.finest_pixel_m = float(min(p.grid0.pixel_m for p in terrain.products))
        self._levels = {id(p): self._max_levels(p) for p in terrain.products}
        self.max_cover_radius_m = min(
            self._level_radius(p, max(self._levels[id(p)])) / (self._max_scale(p) * self._SCALE_MARGIN)
            for p in terrain.products
        )
        self.ceiling_height_m = self._ceiling()
        self._described: dict | None = None  # asked for often; the reader may hash files to answer
        self._sources: list | None = None

    # -- overview levels --------------------------------------------------------------------

    @staticmethod
    def _max_levels(product) -> list[int]:
        """Levels for which a block-maximum array exists (level 0 is the raster itself)."""
        found = [0]
        for k in product.levels:
            if k == 0:
                continue
            try:
                product._array(k, "max")
            except KeyError:
                continue
            found.append(k)
        return found

    @staticmethod
    def _level_radius(product, level: int) -> float:
        """Radius, in projection metres, that the 3 x 3 block neighbourhood of a level covers.

        The surface at a point is a weighted mean of the four finest pixels around it. At
        level 0 the 3 x 3 pixels around the nearest pixel contain those four for every point
        within half a pixel. At level k (blocks of 2**k pixels) the 3 x 3 blocks around the
        block that contains a point contain every finest pixel within one block size of
        it, hence the surface within one block size minus one finest pixel.
        """
        p0 = product.grid0.pixel_m
        return 0.5 * p0 if level == 0 else p0 * 2**level - p0

    def _max_scale(self, product) -> float:
        """Largest map scale factor (projection / sphere) at any point whose neighbourhood
        can touch the raster: its corners, moved outwards by the widest neighbourhood."""
        g = product.grid0
        pad = self._level_radius(product, max(self._levels[id(product)]))
        rho = math.hypot(max(abs(g.x_ul_m), abs(g.x_lr_m)) + pad, max(abs(g.y_ul_m), abs(g.y_lr_m)) + pad)
        return 1.0 + (rho / (2.0 * g.radius_m)) ** 2

    def _ceiling(self) -> float | None:
        """Highest terrain in the products, from the coarsest block-maximum overview.

        Returns None when it cannot be had cheaply (large raster without overviews).
        """
        best = None
        for p in self._terrain.products:
            top = max(self._levels[id(p)])
            arr = p._array(top, "max" if top else "mean")
            if arr.size > 16_000_000:
                return None
            value = float(np.max(arr)) * p.scale
            best = value if best is None else max(best, value)
        return best

    # -- the terrain interface --------------------------------------------------------------

    def height_m(self, lon_deg, lat_deg) -> np.ndarray:
        """Bilinear height on the finest product that covers each point.

        Same rule and same interpolation as ``lsn_data``'s ``Terrain.height_m`` without a
        pixel-size request, written out here to skip its search over overview levels.
        """
        from lsn_data.georef import lonlat_to_xy

        products = self._terrain.products  # finest first
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        shape = np.broadcast(lon, lat).shape
        x, y = lonlat_to_xy(np.broadcast_to(lon, shape).ravel(), np.broadcast_to(lat, shape).ravel(), products[0].grid0.radius_m, self._terrain.pole)
        first = products[0]
        inside = first.grid0.covers_xy(x, y)
        if inside.all():
            return first.height_xy(x, y, 0, "mean").reshape(shape)
        out = np.full(x.shape, np.nan)
        todo = np.ones(x.shape, dtype=bool)
        for p in products:
            sel = todo & p.grid0.covers_xy(x, y)
            if sel.any():
                out[sel] = p.height_xy(x[sel], y[sel], 0, "mean")
                todo &= ~sel
        return out.reshape(shape)

    def cover_max_m(self, lon_deg, lat_deg, radius_m) -> np.ndarray:
        from lsn_data.georef import lonlat_to_xy

        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        rad = np.asarray(radius_m, dtype=np.float64)
        shape = np.broadcast(lon, lat, rad).shape
        lon, lat, rad = (np.broadcast_to(a, shape).ravel() for a in (lon, lat, rad))
        out = np.full(lon.shape, np.nan)
        for p in self._terrain.products:
            g0 = p.grid0
            x, y = lonlat_to_xy(lon, lat, g0.radius_m, g0.pole)
            scale = 1.0 + (x * x + y * y) / (2.0 * g0.radius_m) ** 2  # conformal map scale
            need = rad * scale * self._SCALE_MARGIN
            levels = self._levels[id(p)]
            radii = np.array([self._level_radius(p, k) for k in levels])
            which = np.searchsorted(radii, need, side="left")  # finest level that is wide enough
            # Points whose widest neighbourhood cannot touch this raster get nothing from it.
            pad = radii[-1]
            near = (x >= g0.x_ul_m - pad) & (x <= g0.x_lr_m + pad) & (y <= g0.y_ul_m + pad) & (y >= g0.y_lr_m - pad)
            if np.any(near & (which >= len(levels))):
                raise ValueError("cover_max_m: radius exceeds max_cover_radius_m")
            for idx, k in enumerate(levels):
                sel = np.flatnonzero(near & (which == idx))
                if sel.size == 0:
                    continue
                g = p.grid(k)
                arr = p._array(k, "max" if k else "mean")
                row, col = g.xy_to_rowcol(x[sel], y[sel])
                ri = np.rint(row).astype(np.int64)
                ci = np.rint(col).astype(np.int64)
                best = np.full(sel.size, -np.inf)
                for dr in (-1, 0, 1):
                    r2 = ri + dr
                    r_ok = (r2 >= 0) & (r2 < g.n_rows)
                    r2 = np.clip(r2, 0, g.n_rows - 1)
                    for dc in (-1, 0, 1):
                        c2 = ci + dc
                        ok = r_ok & (c2 >= 0) & (c2 < g.n_cols)
                        v = arr[r2, np.clip(c2, 0, g.n_cols - 1)].astype(np.float64)
                        best = np.maximum(best, np.where(ok, v, -np.inf))
                value = np.where(np.isfinite(best), best * p.scale, np.nan)
                out[sel] = np.fmax(out[sel], value)
        return out.reshape(shape)

    def crease_fractions(self, lon_deg, lat_deg) -> np.ndarray:
        """Crossings of each segment with the lines through the pixel centres of the finest
        product that covers the segment's first point (one column line and one row line at
        most: segments are shorter than a pixel)."""
        from lsn_data.georef import lonlat_to_xy

        lon = np.asarray(lon_deg, dtype=np.float64).ravel()
        lat = np.asarray(lat_deg, dtype=np.float64).ravel()
        out = np.full((max(lon.size - 1, 0), 2), np.nan)
        if lon.size < 2:
            return out
        products = self._terrain.products
        x, y = lonlat_to_xy(lon, lat, products[0].grid0.radius_m, self._terrain.pole)
        todo = np.ones(lon.size - 1, dtype=bool)
        for p in products:  # finest first
            g = p.grid0
            sel = todo & g.covers_xy(x[:-1], y[:-1])
            if not sel.any():
                continue
            row, col = g.xy_to_rowcol(x, y)  # pixel centres are at integer coordinates
            for axis, c in enumerate((col, row)):
                a, b = c[:-1], c[1:]
                line = np.ceil(np.minimum(a, b))
                crossed = sel & (line > np.minimum(a, b)) & (line < np.maximum(a, b))
                with np.errstate(invalid="ignore", divide="ignore"):
                    out[:, axis] = np.where(crossed, (line - a) / (b - a), out[:, axis])
            todo &= ~sel
        return out

    def _level_sources(self) -> list[tuple[object, int, dict]]:
        """Every block-average level of every product, coarsest pixel first, with the
        checksum of the file it is stored in as the data reader reports it."""
        if self._sources is None:
            files = {item["product_id"]: item.get("files", []) for item in self._terrain.provenance()}
            stored = {(rec["product_id"], rec["level"]) for rec in self._terrain.levels() if rec["statistic"] == "mean"}
            found = []
            for p in self._terrain.products:
                base = next((f.get("sha256") for f in files.get(p.product_id, []) if f.get("role") == "data"), None)
                for k in p.levels:
                    if (p.product_id, k) not in stored:
                        continue
                    record = {"product_id": str(p.product_id), "level": int(k), "pixel_m": float(p.pixel_m(k)), "statistic": "mean", "sha256": base}
                    if k:
                        record["sha256"] = next((f.get("sha256") for f in files.get(p.product_id, []) if f.get("name") == f"mean_L{k}.npy"), None)
                        record["derived_from_sha256"] = base
                    found.append((p, int(k), record))
            self._sources = sorted(found, key=lambda item: -item[2]["pixel_m"])
        return self._sources

    def height_at_pixel_m(self, lon_deg, lat_deg, pixel_m: float) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        """Bilinear height on the block-average level with the coarsest pixel that is not
        larger than pixel_m and covers the point; the finest product at its own pixel where
        nothing that fine covers it. This is the rule of ``lsn_data``'s ``Terrain.height_m``
        with a pixel-size request, written out here to know which level each point came from.
        """
        from lsn_data.georef import lonlat_to_xy

        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        shape = np.broadcast(lon, lat).shape
        products = self._terrain.products  # finest first
        x, y = lonlat_to_xy(np.broadcast_to(lon, shape).ravel(), np.broadcast_to(lat, shape).ravel(), products[0].grid0.radius_m, self._terrain.pole)
        out = np.full(x.shape, np.nan)
        index = np.full(x.shape, -1, dtype=np.int64)
        todo = np.ones(x.shape, dtype=bool)
        sources = self._level_sources()
        order = [n for n, (_, _, rec) in enumerate(sources) if rec["pixel_m"] <= float(pixel_m)]
        order += sorted((n for n, (_, k, _) in enumerate(sources) if k == 0), key=lambda n: sources[n][2]["pixel_m"])
        for n in order:
            p, k, _ = sources[n]
            sel = todo & p.grid(k).covers_xy(x, y)
            if sel.any():
                out[sel] = p.height_xy(x[sel], y[sel], k, "mean")
                index[sel] = n
                todo &= ~sel
        index = np.where(np.isfinite(out), index, -1)
        return out.reshape(shape), index.reshape(shape), [rec for _, _, rec in sources]

    @property
    def is_synthetic(self) -> bool:
        """True if any product declares itself a synthetic test surface."""
        return any(
            "SYNTH" in f"{p.product_id} {p.product_version} {p.data_set_id}".upper() for p in self._terrain.products
        )

    def describe(self) -> dict:
        """The elevation layers for the package record: product, version, and the checksum
        and source address of the product's data file as the data reader reports them."""
        if self._described is None:
            layers = []
            for item in self._terrain.provenance():
                data_file = next((f for f in item.get("files", []) if f.get("role") == "data"), {})
                layers.append(
                    {
                        "layer_id": str(item["product_id"]),
                        "product_id": str(item["product_id"]),
                        "version": str(item.get("product_version")),
                        "source_url": str(data_file.get("source_url") or item.get("source_url") or ""),
                        "sha256": data_file.get("sha256") or item.get("sha256"),
                        "pixel_m": float(item["pixel_m"]),
                        "projection": "polar stereographic on a sphere, true scale at the pole",
                    }
                )
            ids = "+".join(f"{layer['product_id']}@{layer['version']}" for layer in layers)
            self._described = {"dem_set_id": f"lola:{ids}", "layers": layers}
        return self._described
