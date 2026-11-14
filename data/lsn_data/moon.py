"""Terrain for any point of the Moon: polar products near the poles, cylindrical products elsewhere.

Product choice for a point (``MoonTerrain.source`` reports it):

1. If a south-polar product covers the point, the south polar :class:`lsn_data.dem.Terrain` decides, with exactly its
   rule (finest data, or the coarsest overview not larger than ``max_pixel_m``). The same for the north.
   So every point the south-only terrain of ``open_terrain()`` covers gets the same value here.
2. Otherwise the first cylindrical mosaic (finest first) that covers it, at the coarsest of its levels whose
   north-south pixel is not larger than ``max_pixel_m`` (level 0 if none is).
3. Otherwise NaN.

The polar squares reach about 48.5 degrees at their corners; inside them the polar product wins (it has the finer
pixel at those latitudes). All products must use the same reference sphere.
"""

from __future__ import annotations

import numpy as np

from .cylindrical import CylMosaic
from .dem import Terrain


class MoonTerrain:
    def __init__(self, polar: list[Terrain], cylindrical: list[CylMosaic], missing: list[str] | None = None):
        if not polar and not cylindrical:
            raise ValueError("no products")
        poles = [t.pole for t in polar]
        if len(set(poles)) != len(poles):
            raise ValueError("two polar terrains for the same pole")
        refs = {t.reference_radius_m for t in polar} | {c.reference_radius_m for c in cylindrical}
        if len(refs) != 1:
            raise ValueError(f"products use different reference radii: {refs}")
        self.reference_radius_m = refs.pop()
        self.polar = list(polar)
        self.cylindrical = sorted(cylindrical, key=lambda c: c.pixel_m(0))
        self.missing = list(missing or [])

    @property
    def products(self) -> list:
        return [p for t in self.polar for p in t.products] + list(self.cylindrical)

    def polar_terrain(self, pole: int) -> Terrain:
        for t in self.polar:
            if t.pole == pole:
                return t
        raise KeyError(pole)

    def product(self, product_id: str):
        for p in self.products:
            if p.product_id == product_id:
                return p
        raise KeyError(product_id)

    # -- selection -------------------------------------------------------------------------------
    def _plan(self, lon, lat, want, statistic):
        """Per point: group index (polar terrains first, then mosaics; -1 none)."""
        group = np.full(lon.shape, -1, dtype=np.int64)
        todo = np.ones(lon.shape, dtype=bool)
        for gi, t in enumerate(self.polar):
            sel = todo & t.covers(lon, lat)
            group[sel] = gi
            todo &= ~sel
        for ci, c in enumerate(self.cylindrical):
            if not todo.any():
                break
            sel = todo & c.covers(lon, lat)
            group[sel] = len(self.polar) + ci
            todo &= ~sel
        return group

    @staticmethod
    def _cyl_level(c: CylMosaic, want: np.ndarray, statistic: str) -> np.ndarray:
        level = np.zeros(want.shape, dtype=np.int64)
        for k in sorted(c.levels):
            if k and c.has_level(k, statistic):
                level[want >= c.pixel_m(k)] = k
        return level

    def _broadcast(self, lon_deg, lat_deg, max_pixel_m):
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        want_in = np.asarray(0.0 if max_pixel_m is None else max_pixel_m, dtype=np.float64)
        shape = np.broadcast(lon, lat, want_in).shape
        return (np.broadcast_to(lon, shape).ravel(), np.broadcast_to(lat, shape).ravel(),
                np.broadcast_to(want_in, shape).ravel(), shape)

    def height_m(self, lon_deg, lat_deg, max_pixel_m=None, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        """Heights above the reference sphere in metres, any latitude and longitude; NaN where nothing covers."""
        lon, lat, want, shape = self._broadcast(lon_deg, lat_deg, max_pixel_m)
        out = np.full(lon.shape, np.nan)
        group = self._plan(lon, lat, want, statistic)
        for gi, t in enumerate(self.polar):
            sel = group == gi
            if sel.any():
                out[sel] = t.height_m(lon[sel], lat[sel], want[sel], statistic, method)
        for ci, c in enumerate(self.cylindrical):
            sel = np.flatnonzero(group == len(self.polar) + ci)
            if sel.size == 0:
                continue
            level = self._cyl_level(c, want[sel], statistic)
            for k in np.unique(level):
                s = sel[level == k]
                st = statistic if k else "mean"
                out[s] = c.height_m(lon[s], lat[s], int(k), st, method)
        return out.reshape(shape)

    def radius_m(self, lon_deg, lat_deg, max_pixel_m=None, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        return self.height_m(lon_deg, lat_deg, max_pixel_m, statistic, method) + self.reference_radius_m

    def source(self, lon_deg, lat_deg, max_pixel_m=None, statistic: str = "mean"):
        """(product ids, levels) that ``height_m`` reads for each point; '' and -1 where nothing covers."""
        lon, lat, want, shape = self._broadcast(lon_deg, lat_deg, max_pixel_m)
        ids = np.full(lon.shape, "", dtype=object)
        levels = np.full(lon.shape, -1, dtype=np.int64)
        group = self._plan(lon, lat, want, statistic)
        for gi, t in enumerate(self.polar):
            sel = group == gi
            if sel.any():
                ids[sel], levels[sel] = t.source(lon[sel], lat[sel], want[sel], statistic)
        for ci, c in enumerate(self.cylindrical):
            sel = group == len(self.polar) + ci
            if sel.any():
                ids[sel] = c.product_id
                levels[sel] = self._cyl_level(c, want[sel], statistic)
        return ids.reshape(shape), levels.reshape(shape)

    def describe_point(self, lon_deg: float, lat_deg: float) -> dict:
        """Product, pixel size and terrain class of the finest data at one point, for provenance labels.

        ``terrain_class``: "polar" (a polar stereographic product, 20 m or 60 m for LOLA), "global_coarse" (a
        cylindrical mosaic: 118 m for SLDEM2015_256, 237 m for LDEM_128; terrain closer than a few pixels is not
        resolved, so horizons there are a coarser class than polar ones), or "none".
        """
        ids, _ = self.source(lon_deg, lat_deg)
        pid = str(np.asarray(ids).ravel()[0]) or None
        if pid is None:
            return {"product_id": None, "pixel_m": None, "terrain_class": "none", "note": "no terrain product covers the point"}
        p = self.product(pid)
        if isinstance(p, CylMosaic):
            px = p.pixel_m(0)
            return {"product_id": pid, "pixel_m": px, "terrain_class": "global_coarse",
                    "note": f"cylindrical product with {px:.0f} m pixels (north-south): terrain within a few pixels "
                            "(about {:.0f} m) is not resolved; horizons from it are a coarser class than from the polar products".format(3 * px)}
        return {"product_id": pid, "pixel_m": p.grid0.pixel_m, "terrain_class": "polar",
                "note": f"polar stereographic product with {p.grid0.pixel_m:.0f} m pixels"}

    # -- description -------------------------------------------------------------------------------
    def levels(self) -> list[dict]:
        out = [d for t in self.polar for d in t.levels()]
        for c in self.cylindrical:
            for k in c.levels:
                out.append({"product_id": c.product_id, "level": k, "statistic": "mean", "pixel_m": c.pixel_m(k),
                            "projection": "simple cylindrical", "pixel_m_is": "north-south; east-west is pixel_m * cos(lat)"})
        return sorted(out, key=lambda d: (d["pixel_m"], d["product_id"]))

    def provenance(self, manifest: dict | None = None) -> list[dict]:
        out = [rec for t in self.polar for rec in t.provenance(manifest)]
        out += [c.provenance(manifest) for c in self.cylindrical]
        return out

    def coverage(self) -> list[dict]:
        """The products in the order they are tried, with what they cover."""
        out = []
        for t in self.polar:
            for p in t.products:
                out.append({"product_id": p.product_id, "kind": "polar stereographic", "pole": "south" if t.pole < 0 else "north",
                            "pixel_m": p.grid0.pixel_m, "covers": "its square: +-%.0f km from the pole" % (p.grid0.x_lr_m / 1000)})
        for c in self.cylindrical:
            tiles = [(t.grid0.south_lat, t.grid0.north_lat, t.grid0.west_lon, t.grid0.east_lon) for t in c.tiles]
            out.append({"product_id": c.product_id, "kind": "simple cylindrical", "pixel_m": c.pixel_m(0),
                        "covers": "latitude %.0f..%.0f, %d tile(s)" % (min(t[0] for t in tiles), max(t[1] for t in tiles), len(tiles))})
        if self.missing:
            out.append({"missing_products": self.missing})
        return out
