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

    def source_at(self, lon_deg, lat_deg) -> tuple[np.ndarray, dict]:
        """Which product height_m reads at each point: an array of product ids ('' without
        data) and, per id, its pixel_m and projection."""


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

    def source_at(self, lon_deg, lat_deg) -> tuple[np.ndarray, dict]:
        height = self.height_m(lon_deg, lat_deg)
        ids = np.where(np.isfinite(height), self.dem_set_id, "").astype(object)
        return ids, {self.dem_set_id: {"pixel_m": self.finest_pixel_m, "projection": "analytic function, no grid"}}


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
        self._product_top = {}
        for p in self._terrain.products:
            top = max(self._levels[id(p)])
            arr = p._array(top, "max" if top else "mean")
            if arr.size > 16_000_000:
                return None
            value = float(np.max(arr)) * p.scale
            self._product_top[id(p)] = value
            best = value if best is None else max(best, value)
        return best

    def _disc_xy(self, product, lon, lat, rad):
        from lsn_data.georef import lonlat_to_xy

        g0 = product.grid0
        x, y = lonlat_to_xy(lon, lat, g0.radius_m, g0.pole)
        return x, y, rad * (1.0 + (x * x + y * y) / (2.0 * g0.radius_m) ** 2) * self._SCALE_MARGIN

    def contains_disc(self, lon_deg, lat_deg, radius_m) -> np.ndarray:
        """True where the disc of radius_m around a point lies wholly inside one product."""
        lon, lat, rad = (np.asarray(a, dtype=np.float64) for a in (lon_deg, lat_deg, radius_m))
        out = np.zeros(np.broadcast(lon, lat, rad).shape, dtype=bool)
        for p in self._terrain.products:
            g0 = p.grid0
            x, y, reach = self._disc_xy(p, lon, lat, rad)
            out |= (x - reach >= g0.x_ul_m) & (x + reach <= g0.x_lr_m) & (y + reach <= g0.y_ul_m) & (y - reach >= g0.y_lr_m)
        return out

    def cover_bound_m(self, lon_deg, lat_deg, radius_m) -> np.ndarray:
        """cover_max_m for any radius: a neighbourhood wider than the widest overview
        neighbourhood gets the highest terrain of every product it can touch."""
        lon, lat, rad = (np.asarray(a, dtype=np.float64) for a in (lon_deg, lat_deg, radius_m))
        shape = np.broadcast(lon, lat, rad).shape
        lon, lat, rad = (np.broadcast_to(a, shape).ravel() for a in (lon, lat, rad))
        out = np.full(lon.shape, np.nan)
        small = rad <= self.max_cover_radius_m
        if small.any():
            out[small] = self.cover_max_m(lon[small], lat[small], rad[small])
        wide = np.flatnonzero(~small)
        if wide.size:
            for p in self._terrain.products:
                g0 = p.grid0
                x, y, reach = self._disc_xy(p, lon[wide], lat[wide], rad[wide])
                touches = (x + reach >= g0.x_ul_m) & (x - reach <= g0.x_lr_m) & (y - reach <= g0.y_ul_m) & (y + reach >= g0.y_lr_m)
                if not touches.any():
                    continue
                if self.ceiling_height_m is None:
                    raise ValueError(f"{p.product_id}: a neighbourhood wider than its overview levels reach touches it and its highest terrain is not known; build the overview levels with `python -m lsn_data pyramid`")
                out[wide] = np.fmax(out[wide], np.where(touches, self._product_top[id(p)], np.nan))
        return out.reshape(shape)

    def source_at(self, lon_deg, lat_deg) -> tuple[np.ndarray, dict]:
        ids, _ = self._terrain.source(lon_deg, lat_deg)
        info = {str(p.product_id): {"pixel_m": float(p.grid0.pixel_m), "projection": "polar stereographic on a sphere, true scale at the pole"} for p in self._terrain.products}
        return ids, {pid: info[pid] for pid in set(ids.ravel()) - {""}}

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


class MoonTerrainAdapter:
    """Adapter around the data stream's ``lsn_data.moon.MoonTerrain``: any latitude and longitude.

    The surface is what that reader returns: a polar product where its square covers the
    point, a simple-cylindrical mosaic elsewhere, each bilinear on its own grid. Near the
    poles the proven adapter of the polar products does the work (:meth:`for_site` returns
    it unchanged when the whole search disc lies inside one pole's products, so results
    there are identical). Elsewhere the neighbourhood bound of a cylindrical mosaic is read
    from its block-maximum levels, and from its highest terrain where no level is wide
    enough.
    """

    _LATTICE_LATITUDE_DEG = 75.0  # beyond it the lattice no longer follows the east-west pixel of a cylindrical grid
    _MAX_CROSSINGS = 64  # column lines one lattice step may cross (reached within 0.2 degrees of a pole)

    def __init__(self, moon):
        self._moon = moon
        self.site_notes: list[str] = []
        self.reference_radius_m = float(moon.reference_radius_m)
        self._polar = [LolaTerrain(t) for t in moon.polar]
        self._cyl = list(moon.cylindrical)
        self._cyl_levels = {id(c): [k for k in c.levels if k == 0 or c.has_level(k, "max")] for c in self._cyl}
        self._cyl_top: dict[int, float | None] = {}
        self.max_cover_radius_m = math.inf  # a neighbourhood too wide for the overviews gets the ceiling of the layer
        pixels = [a.finest_pixel_m for a in self._polar] + [c.pixel_m(0) * 0.5 for c in self._cyl]  # east-west pixel at 60 degrees
        self.finest_pixel_m = float(min(pixels))
        tops = [a.ceiling_height_m for a in self._polar] + [self._cyl_ceiling(c) for c in self._cyl]
        self.ceiling_height_m = None if any(t is None for t in tops) else float(max(tops))
        self._described: dict | None = None
        self._records: dict | None = None

    # -- one site -----------------------------------------------------------------------------

    def _ring_points(self, lat_deg: float, lon_deg: float, range_m: float, fractions) -> tuple[np.ndarray, np.ndarray]:
        from .geometry import destination

        az = np.arange(0.0, 360.0, 5.0)
        lat, lon = destination(lat_deg, lon_deg, az[None, :], (np.asarray(fractions, dtype=np.float64) * range_m / self.reference_radius_m)[:, None])
        return np.append(lat.ravel(), lat_deg), np.append(lon.ravel(), lon_deg)

    def for_site(self, lat_deg: float, lon_deg: float, range_m: float):
        """The terrain to use for one site and search radius.

        Inside one pole's products: the adapter of those products, as if no other product
        existed. Otherwise this adapter with the lattice pixel of the finest product that
        the search disc touches.
        """
        lat_b, lon_b = self._ring_points(lat_deg, lon_deg, range_m, [1.002])
        for adapter, polar in zip(self._polar, self._moon.polar):
            if bool(np.all(polar.covers(lon_b, lat_b))):
                return adapter
        lat_s, lon_s = self._ring_points(lat_deg, lon_deg, range_m, [0.125, 0.25, 0.375, 0.5, 0.625, 0.75, 0.875, 1.0])
        ids, _ = self._moon.source(lon_s, lat_s)
        pixels, notes = [], []
        for pid in sorted(set(ids.ravel()) - {""}):
            product = self._moon.product(pid)
            if getattr(product, "kind", "") == "cylindrical":
                # The east-west pixel of a latitude-longitude grid shrinks towards the poles
                # without carrying more detail. The lattice follows it down to 75 degrees;
                # beyond that it keeps its width and every cell boundary a step crosses is
                # still evaluated (crease_fractions), at a higher cost per ray.
                reach = float(np.abs(lat_s[ids == pid]).max())
                pixels.append(product.pixel_m(0) * math.cos(math.radians(min(reach, self._LATTICE_LATITUDE_DEG))))
                if reach > self._LATTICE_LATITUDE_DEG:
                    notes.append(
                        f"terrain: the search reaches latitude {reach:.1f} on {pid}, a latitude-longitude grid; "
                        "a polar elevation product would serve this site better and faster"
                    )
            else:
                pixels.append(float(product.grid0.pixel_m))
        if not pixels:
            raise ValueError(f"no elevation data within {range_m / 1000.0:.0f} km of latitude {lat_deg}, longitude {lon_deg}; products not installed: {self._moon.missing}")
        import copy

        view = copy.copy(self)
        view.finest_pixel_m = float(min(pixels))
        view.site_notes = notes
        return view

    # -- cylindrical layers ---------------------------------------------------------------------

    def _cyl_ceiling(self, c) -> float | None:
        """Highest terrain of a mosaic, from its coarsest block-maximum level."""
        key = id(c)
        if key not in self._cyl_top:
            top = max(self._cyl_levels[key])
            block = 2**top / c.res_ppd
            if top == 0 or 360.0 / block * 180.0 / block > 16_000_000:
                self._cyl_top[key] = None
            else:
                lat = 90.0 - (np.arange(int(round(180.0 / block))) + 0.5) * block
                lon = (np.arange(int(round(360.0 / block))) + 0.5) * block
                values = c.height_m(lon[None, :], lat[:, None], top, "max", "nearest")
                self._cyl_top[key] = float(np.nanmax(values)) if np.isfinite(values).any() else None
        return self._cyl_top[key]

    def _cyl_bound(self, c, lon: np.ndarray, lat: np.ndarray, rad: np.ndarray) -> np.ndarray:
        """Upper bound of a mosaic's surface within rad (arc metres) of each point.

        A disc of angular radius rho around a point at latitude phi spans rho in latitude and
        asin(sin rho / cos phi) in longitude (all longitudes once it holds a pole). The 3 x 3
        blocks of a level around the block of the point reach one block beyond it, and the
        surface at a place depends on pixels up to one pixel away: a level bounds the disc if
        its block is at least the wider of the two spans plus one pixel (level 0: the 3 x 3
        pixels bound half a pixel).
        """
        pixel = 1.0 / c.res_ppd  # degrees
        rho = rad / self.reference_radius_m
        with np.errstate(invalid="ignore", divide="ignore"):
            ratio = np.sin(rho) / np.cos(np.radians(lat))
            span_lon = np.where((np.abs(lat) + np.degrees(rho) < 90.0) & (ratio < 1.0), np.degrees(np.arcsin(np.clip(ratio, 0.0, 1.0))), np.inf)
        need = np.maximum(np.degrees(rho), span_lon)
        levels = self._cyl_levels[id(c)]
        reach = np.array([0.5 * pixel if k == 0 else (2**k - 1) * pixel for k in levels])
        which = np.searchsorted(reach, need, side="left")
        out = np.full(lon.shape, np.nan)
        for idx, k in enumerate(levels):
            sel = np.flatnonzero(which == idx)
            if sel.size == 0:
                continue
            block = 2**k * pixel
            best = np.full(sel.size, np.nan)
            for di in (-1.0, 0.0, 1.0):
                la = np.clip(lat[sel] + di * block, -90.0 + 0.25 * pixel, 90.0 - 0.25 * pixel)
                for dj in (-1.0, 0.0, 1.0):
                    best = np.fmax(best, c.height_m(lon[sel] + dj * block, la, k, "max" if k else "mean", "nearest"))
            out[sel] = best
        wide = which >= len(levels)
        if wide.any():
            top = self._cyl_ceiling(c)
            if top is None:
                raise ValueError(f"{c.product_id}: no overview levels wide enough; build them with `python -m lsn_data pyramid`")
            out[wide] = top
        return out

    # -- the terrain interface --------------------------------------------------------------

    def height_m(self, lon_deg, lat_deg) -> np.ndarray:
        return self._moon.height_m(lon_deg, lat_deg)

    def cover_max_m(self, lon_deg, lat_deg, radius_m) -> np.ndarray:
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        rad = np.asarray(radius_m, dtype=np.float64)
        shape = np.broadcast(lon, lat, rad).shape
        lon, lat, rad = (np.broadcast_to(a, shape).ravel() for a in (lon, lat, rad))
        out = np.full(lon.shape, np.nan)
        inside = np.zeros(lon.shape, dtype=bool)  # discs that lie wholly inside one pole's products
        for adapter in self._polar:
            out = np.fmax(out, adapter.cover_bound_m(lon, lat, rad))
            inside |= adapter.contains_disc(lon, lat, rad)
        rest = np.flatnonzero(~inside)
        if rest.size:
            for c in self._cyl:
                out[rest] = np.fmax(out[rest], self._cyl_bound(c, lon[rest], lat[rest], rad[rest]))
        return out.reshape(shape)

    def crease_fractions(self, lon_deg, lat_deg) -> np.ndarray:
        """Crossings of each segment with the lines through the pixel centres of the product
        its first point is read from: a polar grid where a polar product covers it, the
        latitude-longitude grid of the finest mosaic elsewhere."""
        lon = np.asarray(lon_deg, dtype=np.float64).ravel()
        lat = np.asarray(lat_deg, dtype=np.float64).ravel()
        parts = [np.full((max(lon.size - 1, 0), 2), np.nan)]
        if lon.size < 2:
            return parts[0]
        todo = np.ones(lon.size - 1, dtype=bool)
        for adapter, polar in zip(self._polar, self._moon.polar):
            sel = todo & polar.covers(lon[:-1], lat[:-1])
            if sel.any():
                parts[0][sel] = adapter.crease_fractions(lon, lat)[sel]
                todo &= ~sel
        for c in self._cyl:
            sel = todo & c.covers(lon[:-1], lat[:-1])
            if not sel.any():
                continue
            n_cols = 360.0 * c.res_ppd
            col = np.mod(lon, 360.0) * c.res_ppd - 0.5  # pixel centres at integer coordinates
            row = (90.0 - lat) * c.res_ppd - 0.5
            for axis, coordinate in enumerate((col, row)):
                a, b = coordinate[:-1], coordinate[1:].copy()
                if axis == 0:  # a segment across the 0/360 meridian
                    b = np.where(b - a > 0.5 * n_cols, b - n_cols, np.where(a - b > 0.5 * n_cols, b + n_cols, b))
                low, high = np.minimum(a, b), np.maximum(a, b)
                first = np.ceil(low)
                # Row lines: one per step at most. Column lines: several near a pole, where
                # the columns are narrower than a lattice step.
                most = 1 if axis else int(min(self._MAX_CROSSINGS, max(1.0, float(np.max(np.where(sel, np.ceil(high) - first, 0.0))))))
                found = np.full((a.size, most), np.nan)
                with np.errstate(invalid="ignore", divide="ignore"):
                    for k in range(most):
                        line = first + k
                        found[:, k] = np.where(sel & (line > low) & (line < high), (line - a) / (b - a), np.nan)
                parts.append(found)
            todo &= ~sel
        return np.concatenate(parts, axis=1)

    # -- records --------------------------------------------------------------------------------

    def _product_records(self) -> dict:
        """Per product id: pixel, projection, and the checksums the data reader reports."""
        if self._records is None:
            records = {}
            for item in self._moon.provenance():
                files = item.get("files", [])
                data = [f for f in files if f.get("role") == "data"]
                records[str(item["product_id"])] = {
                    "pixel_m": float(item["pixel_m"]),
                    "version": str(item.get("product_version")),
                    "projection": "simple cylindrical (east-west pixel = pixel_m times the cosine of the latitude)" if item.get("projection") == "simple cylindrical" else "polar stereographic on a sphere, true scale at the pole",
                    "sha256": data[0].get("sha256") if len(data) == 1 else None,
                    "source_url": str(data[0].get("source_url") or "") if len(data) == 1 else "",
                    "levels": {f["name"]: f.get("sha256") for f in files if f.get("role") == "pyramid"} if len(data) == 1 else {},
                }
            self._records = records
        return self._records

    def describe(self) -> dict:
        if self._described is None:
            layers = [
                {"layer_id": pid, "product_id": pid, "version": rec["version"], "source_url": rec["source_url"], "sha256": rec["sha256"], "pixel_m": rec["pixel_m"], "projection": rec["projection"]}
                for pid, rec in self._product_records().items()
            ]
            ids = "+".join(f"{layer['product_id']}@{layer['version']}" for layer in layers)
            self._described = {"dem_set_id": f"lola:{ids}", "layers": layers}
        return self._described

    def source_at(self, lon_deg, lat_deg) -> tuple[np.ndarray, dict]:
        ids, _ = self._moon.source(lon_deg, lat_deg)
        records = self._product_records()
        return ids, {pid: {"pixel_m": records[pid]["pixel_m"], "projection": records[pid]["projection"]} for pid in set(ids.ravel()) - {""}}

    def height_at_pixel_m(self, lon_deg, lat_deg, pixel_m: float) -> tuple[np.ndarray, np.ndarray, list[dict]]:
        height = np.asarray(self._moon.height_m(lon_deg, lat_deg, max_pixel_m=float(pixel_m)))
        ids, levels = self._moon.source(lon_deg, lat_deg, float(pixel_m))
        records = self._product_records()
        index = np.full(height.shape, -1, dtype=np.int64)
        sources = []
        for pid, level in sorted({(str(p), int(k)) for p, k in zip(ids.ravel(), levels.ravel()) if p != ""}):
            rec = records[pid]
            source = {"product_id": pid, "level": level, "pixel_m": rec["pixel_m"] * 2**level, "statistic": "mean", "sha256": rec["sha256"]}
            if level:
                source["sha256"] = rec["levels"].get(f"mean_L{level}.npy")
                source["derived_from_sha256"] = rec["sha256"]
            index[(ids == pid) & (levels == level)] = len(sources)
            sources.append(source)
        return height, np.where(np.isfinite(height), index, -1), sources

    @property
    def is_synthetic(self) -> bool:
        return any("SYNTH" in f"{p.product_id} {getattr(p, 'product_version', '')} {getattr(p, 'data_set_id', '')}".upper() for p in self._moon.products)


def open_moon() -> MoonTerrainAdapter:
    """Open every elevation product installed under the data root as one terrain for any
    latitude and longitude (the polar products near the poles, cylindrical mosaics elsewhere)."""
    try:
        import lsn_data
    except ImportError as err:  # pragma: no cover - depends on the environment
        raise RuntimeError("the data reader is not installed: pip install -e data") from err
    return MoonTerrainAdapter(lsn_data.open_terrain(products="moon"))
