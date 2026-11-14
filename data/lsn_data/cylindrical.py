"""Reading LOLA and LOLA/Kaguya simple-cylindrical products (global grids and tiles).

Projection (LOLA projection catalog DSMAP.CAT, the PDS3 convention): for the pixel centre at 1-based
``SAMPLE``, ``LINE``

    LON = CENTER_LONGITUDE + (SAMPLE - SAMPLE_PROJECTION_OFFSET - 1) / RES
    LAT = CENTER_LATITUDE  - (LINE   - LINE_PROJECTION_OFFSET   - 1) / RES

so with 0-based pixel-centre coordinates (``col = SAMPLE - 1``, ``row = LINE - 1``)

    col = SAMPLE_PROJECTION_OFFSET + RES * (LON - CENTER_LONGITUDE)
    row = LINE_PROJECTION_OFFSET   - RES * (LAT - CENTER_LATITUDE)

Pixels are areas; the upper-left pixel's outer corner is at (MAXIMUM_LATITUDE, WESTERNMOST_LONGITUDE).
Latitude is planetocentric, longitude east positive, sphere of radius A_AXIS_RADIUS.

Several tiles of one resolution form a :class:`CylMosaic` on the global grid of that resolution (column 0 starts at
0 deg east, row 0 at 90 deg north). Bilinear interpolation takes its four neighbours from whichever tile holds them,
so tile seams are invisible; across the 0/360 meridian the global grid wraps.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import manifest as mf
from .paths import manifest_path
from .pdslabel import parse_label


@dataclass(frozen=True)
class CylGrid:
    n_rows: int
    n_cols: int
    res_ppd: float          # pixels per degree
    center_lon: float
    center_lat: float
    line_offset: float      # LINE_PROJECTION_OFFSET (0-based pixel-centre row of CENTER_LATITUDE)
    sample_offset: float    # SAMPLE_PROJECTION_OFFSET
    radius_m: float

    @classmethod
    def from_label(cls, lab: dict) -> "CylGrid":
        if lab.get("MAP_PROJECTION_TYPE") != "SIMPLE CYLINDRICAL":
            raise ValueError(f"not a simple cylindrical product: {lab.get('MAP_PROJECTION_TYPE')!r}")
        radii = {float(lab["A_AXIS_RADIUS"]), float(lab["B_AXIS_RADIUS"]), float(lab["C_AXIS_RADIUS"])}
        if len(radii) != 1:
            raise ValueError(f"the body is not a sphere in this label: {radii}")
        if lab.get("POSITIVE_LONGITUDE_DIRECTION") != "EAST":
            raise ValueError("expected east-positive longitude")
        lt = lab.get("KEYWORD_LATITUDE_TYPE", "PLANETOCENTRIC")
        if lt != "PLANETOCENTRIC":
            raise ValueError(f"expected planetocentric latitude, got {lt!r}")
        if float(lab.get("CENTER_LATITUDE", 0.0)) != 0.0:
            raise ValueError("expected CENTER_LATITUDE = 0")
        return cls(
            n_rows=int(lab["LINES"]),
            n_cols=int(lab["LINE_SAMPLES"]),
            res_ppd=float(lab["MAP_RESOLUTION"]),
            center_lon=float(lab["CENTER_LONGITUDE"]),
            center_lat=float(lab.get("CENTER_LATITUDE", 0.0)),
            line_offset=float(lab["LINE_PROJECTION_OFFSET"]),
            sample_offset=float(lab["SAMPLE_PROJECTION_OFFSET"]),
            radius_m=float(lab["A_AXIS_RADIUS"]) * 1000.0,
        )

    # extent (outer pixel edges) ------------------------------------------------------------
    @property
    def west_lon(self) -> float:
        return self.center_lon + (-0.5 - self.sample_offset) / self.res_ppd

    @property
    def east_lon(self) -> float:
        return self.west_lon + self.n_cols / self.res_ppd

    @property
    def north_lat(self) -> float:
        return self.center_lat + (self.line_offset + 0.5) / self.res_ppd

    @property
    def south_lat(self) -> float:
        return self.north_lat - self.n_rows / self.res_ppd

    @property
    def is_global_in_lon(self) -> bool:
        return abs(self.n_cols / self.res_ppd - 360.0) < 1e-9

    @property
    def pixel_m(self) -> float:
        """Pixel height (north-south) in metres; east-west it is this times cos(latitude)."""
        return 2 * math.pi * self.radius_m / 360.0 / self.res_ppd

    def lon_into_range(self, lon_deg):
        lon = np.asarray(lon_deg, dtype=np.float64)
        return self.west_lon + np.mod(lon - self.west_lon, 360.0)

    def lonlat_to_rowcol(self, lon_deg, lat_deg):
        lon = self.lon_into_range(lon_deg)
        col = self.sample_offset + self.res_ppd * (lon - self.center_lon)
        row = self.line_offset - self.res_ppd * (np.asarray(lat_deg, dtype=np.float64) - self.center_lat)
        return row, col

    def rowcol_to_lonlat(self, row, col):
        lon = self.center_lon + (np.asarray(col, dtype=np.float64) - self.sample_offset) / self.res_ppd
        lat = self.center_lat - (np.asarray(row, dtype=np.float64) - self.line_offset) / self.res_ppd
        return np.mod(lon, 360.0), lat

    def covers(self, lon_deg, lat_deg):
        lat = np.asarray(lat_deg, dtype=np.float64)
        lon = self.lon_into_range(lon_deg)
        ok_lat = (lat <= self.north_lat + 1e-12) & (lat >= self.south_lat - 1e-12)
        if self.is_global_in_lon:
            return ok_lat & np.ones_like(lon, dtype=bool)
        return ok_lat & (lon <= self.east_lon + 1e-12)

    def decimated(self, factor: int) -> "CylGrid":
        if self.n_rows % factor or self.n_cols % factor:
            raise ValueError("raster size is not a multiple of the decimation factor")
        return CylGrid(
            self.n_rows // factor,
            self.n_cols // factor,
            self.res_ppd / factor,
            self.center_lon,
            self.center_lat,
            (self.line_offset + 0.5) / factor - 0.5,
            (self.sample_offset + 0.5) / factor - 0.5,
            self.radius_m,
        )

    # position of this grid inside the global grid of the same resolution
    @property
    def global_origin(self) -> tuple[int, int]:
        r0 = (90.0 - self.north_lat) * self.res_ppd
        c0 = (self.west_lon % 360.0) * self.res_ppd
        if abs(r0 - round(r0)) > 1e-6 or abs(c0 - round(c0)) > 1e-6:
            raise ValueError("grid is not aligned with the global grid of its resolution")
        return int(round(r0)), int(round(c0))


_DTYPES = {("LSB_INTEGER", 16): "<i2", ("PC_REAL", 32): "<f4", ("LSB_UNSIGNED_INTEGER", 16): "<u2"}


class CylDEM:
    """One simple-cylindrical product file (a global grid or one tile) with optional pyramid levels."""

    kind = "cylindrical"

    def __init__(self, label_path: str | Path, data_path: str | Path | None = None, pyramid_dir: str | Path | None = None):
        label_path = Path(label_path)
        lab = parse_label(label_path)
        self.label = lab
        self.grid0 = CylGrid.from_label(lab)
        self.product_id = str(lab.get("PRODUCT_ID") or str(lab["FILE_NAME"]).rsplit(".", 1)[0]).upper()
        self.product_version = lab.get("PRODUCT_VERSION_ID")
        self.data_set_id = lab.get("DATA_SET_ID")
        key = (lab["SAMPLE_TYPE"], int(lab["SAMPLE_BITS"]))
        if key not in _DTYPES:
            raise ValueError(f"unsupported sample type {key}")
        self.dtype = _DTYPES[key]
        unit = str(lab.get("UNIT", "METER")).upper()
        if unit not in ("METER", "KILOMETER"):
            raise ValueError(f"unexpected unit {unit!r}")
        to_m = 1000.0 if unit == "KILOMETER" else 1.0
        self.scale = float(lab.get("SCALING_FACTOR", 1.0)) * to_m  # DN -> metres above the reference sphere
        self.reference_radius_m = float(lab["OFFSET"]) * to_m
        if abs(self.reference_radius_m - self.grid0.radius_m) > 1e-6:
            raise ValueError("label OFFSET and body radius disagree")
        if data_path is None:
            data_path = label_path.with_name(str(lab["FILE_NAME"]).lower())
            if not data_path.exists():
                data_path = label_path.with_suffix(".img")
        self.label_path = label_path
        self.data_path = Path(data_path)
        expect = self.grid0.n_rows * self.grid0.n_cols * np.dtype(self.dtype).itemsize
        if self.data_path.stat().st_size != expect:
            raise ValueError(f"{self.data_path.name}: size {self.data_path.stat().st_size} != {expect} from label")
        self._levels: dict[tuple[str, int], np.ndarray] = {
            ("mean", 0): np.memmap(self.data_path, dtype=self.dtype, mode="r", shape=(self.grid0.n_rows, self.grid0.n_cols))
        }
        self._levels[("max", 0)] = self._levels[("mean", 0)]
        self._touched: set[tuple[str, int]] = set()
        self._pyr_meta = None
        self._pyr_dir = None
        self._hash_cache: dict[str, str] = {}
        if pyramid_dir is not None:
            self._attach_pyramid(Path(pyramid_dir))

    def _attach_pyramid(self, d: Path) -> None:
        meta_path = d / "pyramid.json"
        if not meta_path.exists():
            return
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        for stat in meta["statistics"]:
            for k in meta["levels"]:
                arr = np.load(d / f"{stat}_L{k}.npy", mmap_mode="r")
                g = self.grid(k)
                if arr.shape != (g.n_rows, g.n_cols):
                    raise ValueError(f"pyramid level {stat} L{k} has shape {arr.shape}")
                self._levels[(stat, k)] = arr
        self._pyr_meta, self._pyr_dir = meta, d

    @property
    def levels(self) -> list[int]:
        return sorted({k for (_, k) in self._levels})

    def grid(self, level: int = 0) -> CylGrid:
        return self.grid0 if level == 0 else self.grid0.decimated(2**level)

    def pixel_m(self, level: int = 0) -> float:
        return self.grid0.pixel_m * 2**level

    def _array(self, level: int, statistic: str) -> np.ndarray:
        arr = self._levels[(statistic, level)]
        self._touched.add((statistic, level))
        return arr

    def values_at(self, rows: np.ndarray, cols: np.ndarray, level: int, statistic: str) -> np.ndarray:
        """Heights in metres of integer pixels (rows, cols) of one level; NaN for fill values."""
        v = self._array(level, statistic)[rows, cols].astype(np.float64) * self.scale
        v[~np.isfinite(v) | (v < -1e7)] = np.nan
        return v

    def provenance(self, manifest: dict | None = None) -> dict:
        try:
            m = (manifest if manifest is not None else mf.load(manifest_path()))["files"]
        except Exception:
            m = {}
        files = []
        for path, role, read in (
            (self.data_path, "data", ("mean", 0) in self._touched or ("max", 0) in self._touched),
            (self.label_path, "label", True),
        ):
            rel = next((k for k in m if k.endswith("/" + path.parent.name + "/" + path.name)), None)
            rec = m.get(rel) if rel else None
            e = {"name": path.name, "role": role, "size_bytes": path.stat().st_size, "read": read}
            if rec and rec["size_bytes"] == e["size_bytes"]:
                e.update(sha256=rec["sha256"], sha256_from="manifest", source_url=rec["source_url"],
                         manifest_path=rec["path"], retrieved_utc=rec["retrieved_utc"])
            else:
                key = str(path)
                if key not in self._hash_cache:
                    self._hash_cache[key] = mf.sha256_file(path)
                e.update(sha256=self._hash_cache[key], sha256_from="computed", source_url=None, manifest_path=None, retrieved_utc=None)
            files.append(e)
        if self._pyr_meta is not None:
            for stat in self._pyr_meta["statistics"]:
                for k in self._pyr_meta["levels"]:
                    f = self._pyr_dir / f"{stat}_L{k}.npy"
                    rec = self._pyr_meta.get("files", {}).get(f.name, {})
                    files.append({"name": f.name, "role": "pyramid", "size_bytes": f.stat().st_size,
                                  "sha256": rec.get("sha256"), "sha256_from": "pyramid.json",
                                  "derived_from_sha256": self._pyr_meta.get("base_sha256"),
                                  "read": (stat, k) in self._touched})
        return {
            "product_id": self.product_id,
            "product_version": self.product_version,
            "data_set_id": self.data_set_id,
            "projection": "simple cylindrical",
            "pixel_m": self.grid0.pixel_m,
            "reference_radius_m": self.reference_radius_m,
            "file": self.data_path.name,
            "files": files,
        }


class CylMosaic:
    """Tiles (or one global file) of one resolution read as a single product on the global grid."""

    kind = "cylindrical"

    def __init__(self, tiles: list[CylDEM], product_id: str | None = None):
        if not tiles:
            raise ValueError("no tiles")
        res = {t.grid0.res_ppd for t in tiles}
        refs = {t.reference_radius_m for t in tiles}
        if len(res) != 1 or len(refs) != 1:
            raise ValueError(f"tiles differ in resolution {res} or reference radius {refs}")
        self.tiles = tiles
        self.res_ppd = res.pop()
        self.reference_radius_m = refs.pop()
        self.radius_m = tiles[0].grid0.radius_m
        self.product_id = product_id or tiles[0].product_id
        self.product_version = tiles[0].product_version
        levels = set(tiles[0].levels)
        for t in tiles[1:]:
            levels &= set(t.levels)
        self._level_set = sorted(levels)
        self._origins = {k: [self._origin(t, k) for t in tiles] for k in self._level_set}
        # latitude bands covered over all 360 deg by the tiles that share them: covers() answers there from latitude alone
        bands: dict[tuple[float, float], float] = {}
        for t in tiles:
            key = (t.grid0.south_lat, t.grid0.north_lat)
            bands[key] = bands.get(key, 0.0) + (t.grid0.east_lon - t.grid0.west_lon)
        self._full_bands = [b for b, span in bands.items() if abs(span - 360.0) < 1e-9]
        self._partial_tiles = [t for t in tiles if (t.grid0.south_lat, t.grid0.north_lat) not in self._full_bands]

    @staticmethod
    def _origin(t: CylDEM, k: int):
        g = t.grid(k)
        r0, c0 = g.global_origin
        return r0, c0, g.n_rows, g.n_cols

    @property
    def levels(self) -> list[int]:
        return self._level_set

    def has_level(self, k: int, statistic: str) -> bool:
        return k in self._level_set and all((statistic, k) in t._levels for t in self.tiles)

    def pixel_m(self, level: int = 0) -> float:
        return 2 * math.pi * self.radius_m / 360.0 / self.res_ppd * 2**level

    def covers(self, lon_deg, lat_deg):
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        shape = np.broadcast(lon, lat).shape
        out = np.zeros(shape, dtype=bool)
        latb = np.broadcast_to(lat, shape)
        for south, north in self._full_bands:  # same edge tolerance as CylGrid.covers
            out |= (latb <= north + 1e-12) & (latb >= south - 1e-12)
        if self._partial_tiles:
            todo = ~out
            if todo.any():
                lonb = np.broadcast_to(lon, shape)
                part = np.zeros(int(todo.sum()), dtype=bool)
                for t in self._partial_tiles:
                    part |= t.grid0.covers(lonb[todo], latb[todo])
                out[todo] = part
        return out

    def _gather(self, gr: np.ndarray, gc: np.ndarray, k: int, statistic: str) -> np.ndarray:
        out = np.full(gr.shape, np.nan)
        for t, (r0, c0, nr, nc) in zip(self.tiles, self._origins[k]):
            sel = (gr >= r0) & (gr < r0 + nr) & (gc >= c0) & (gc < c0 + nc)
            if sel.any():
                out[sel] = t.values_at(gr[sel] - r0, gc[sel] - c0, k, statistic)
        return out

    def height_m(self, lon_deg, lat_deg, level: int = 0, statistic: str = "mean", method: str = "bilinear") -> np.ndarray:
        """Heights (m above the reference sphere); NaN outside every tile. Bilinear across tile seams."""
        lon = np.asarray(lon_deg, dtype=np.float64)
        lat = np.asarray(lat_deg, dtype=np.float64)
        shape = np.broadcast(lon, lat).shape
        lon = np.broadcast_to(lon, shape).ravel()
        lat = np.broadcast_to(lat, shape).ravel()
        res = self.res_ppd / 2**level
        n_cols, n_rows = int(round(360 * res)), int(round(180 * res))
        fc = np.mod(lon, 360.0) * res - 0.5
        fr = (90.0 - lat) * res - 0.5
        inside = self.covers(lon, lat)
        out = np.full(lon.shape, np.nan)
        if not inside.any():
            return out.reshape(shape)
        fc, fr = fc[inside], fr[inside]
        if method == "nearest":
            r = np.clip(np.rint(fr).astype(np.int64), 0, n_rows - 1)
            c = np.mod(np.rint(fc).astype(np.int64), n_cols)
            out[inside] = self._gather(r, c, level, statistic)
            return out.reshape(shape)
        if method != "bilinear":
            raise ValueError("method must be 'bilinear' or 'nearest'")
        fr = np.clip(fr, 0.0, n_rows - 1.0)
        r0 = np.minimum(np.floor(fr).astype(np.int64), n_rows - 2)
        c0 = np.floor(fc).astype(np.int64)
        wr, wc = fr - r0, fc - c0
        acc = np.zeros(fr.shape)
        wsum = np.zeros(fr.shape)
        for dr, dc, w in ((0, 0, (1 - wr) * (1 - wc)), (0, 1, (1 - wr) * wc), (1, 0, wr * (1 - wc)), (1, 1, wr * wc)):
            v = self._gather(r0 + dr, np.mod(c0 + dc, n_cols), level, statistic)
            ok = np.isfinite(v)
            acc[ok] += w[ok] * v[ok]
            wsum[ok] += w[ok]
        # At the outer edge of a tile set (e.g. 60 deg for a 60S-60N product) missing neighbours are left out
        # and the remaining weights renormalised, so the value degrades to the nearest pixels, never to NaN.
        val = np.where(wsum > 0, acc / np.where(wsum > 0, wsum, 1.0), np.nan)
        out[inside] = val
        return out.reshape(shape)

    def provenance(self, manifest: dict | None = None) -> dict:
        tiles = [t.provenance(manifest) for t in self.tiles]
        return {
            "product_id": self.product_id,
            "product_version": self.product_version,
            "data_set_id": self.tiles[0].data_set_id,
            "projection": "simple cylindrical",
            "pixel_m": self.pixel_m(0),
            "reference_radius_m": self.reference_radius_m,
            "file": ", ".join(t.data_path.name for t in self.tiles),
            "files": [f for tp in tiles for f in tp["files"]],
            "tiles": [tp["product_id"] for tp in tiles],
        }
