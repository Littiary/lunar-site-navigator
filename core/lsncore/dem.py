"""Terrain interface of the horizon core.

The horizon code only needs four things from a terrain source: the radius of the
reference sphere, the height above that sphere at given coordinates (optionally read at a
coarser pixel size), the finest pixel size near a site, and a description for the package
record. Real LOLA data comes from the data stream's reader (``lsn_data``), wrapped by
:class:`LolaTerrain`; tests use :class:`AnalyticTerrain`.
"""

from __future__ import annotations

from typing import Callable, Protocol

import numpy as np


class Terrain(Protocol):
    reference_radius_m: float
    finest_pixel_m: float
    ceiling_height_m: float | None

    def height_m(self, lon_deg, lat_deg, max_pixel_m=None) -> np.ndarray:
        """Height above the reference sphere in metres; NaN where there is no data.

        lon_deg (east positive) and lat_deg broadcast against max_pixel_m. A source with
        overview levels reads the coarsest level whose pixel is not larger than
        max_pixel_m; None means the finest data.
        """

    def describe(self) -> dict:
        """The ``inputs.dem`` object of the package contract."""


class AnalyticTerrain:
    """Terrain given by a function ``height(lon_deg, lat_deg)``: exact, no grid."""

    def __init__(
        self,
        height: Callable,
        reference_radius_m: float,
        finest_pixel_m: float = 20.0,
        ceiling_height_m: float | None = None,
        dem_set_id: str = "ANALYTIC-test-surface",
    ):
        self._height = height
        self.reference_radius_m = float(reference_radius_m)
        self.finest_pixel_m = float(finest_pixel_m)
        self.ceiling_height_m = ceiling_height_m
        self.dem_set_id = dem_set_id

    def height_m(self, lon_deg, lat_deg, max_pixel_m=None) -> np.ndarray:
        return np.asarray(self._height(np.asarray(lon_deg, dtype=np.float64), np.asarray(lat_deg, dtype=np.float64)), dtype=np.float64)

    def describe(self) -> dict:
        return {"dem_set_id": self.dem_set_id, "layers": []}


def open_lola(label_paths=None, statistic: str = "mean") -> "LolaTerrain":
    """Open LOLA terrain through the data stream's reader.

    label_paths: PDS3 labels to open; None opens the default products under the data root
    (LSN_DATA_ROOT), with their overview levels.
    """
    try:
        import lsn_data
    except ImportError as err:  # pragma: no cover - depends on the environment
        raise RuntimeError("the data reader is not installed: pip install -e data") from err
    return LolaTerrain(lsn_data.open_terrain(label_paths=label_paths), statistic=statistic)


class LolaTerrain:
    """Adapter around the data stream's ``lsn_data.dem.Terrain``.

    statistic: "mean" reads block-average overviews for far terrain (central estimate);
    "max" reads block-maximum overviews (upper bound of the horizon).
    """

    def __init__(self, terrain, statistic: str = "mean"):
        self._terrain = terrain
        self.statistic = statistic
        self.reference_radius_m = float(terrain.reference_radius_m)
        self.finest_pixel_m = float(min(p.grid0.pixel_m for p in terrain.products))
        self.ceiling_height_m = self._ceiling()

    def _ceiling(self) -> float | None:
        """Highest terrain in the products, from the coarsest block-maximum overview.

        Returns None when it cannot be had cheaply (large raster without overviews).
        """
        best = None
        for p in self._terrain.products:
            top = max(p.levels)
            g = p.grid(top)
            if g.n_rows * g.n_cols > 16_000_000:
                return None
            try:
                w = p.window_xy(g.x_ul_m, g.y_lr_m, g.x_lr_m, g.y_ul_m, level=top, statistic="max" if top else "mean")
            except KeyError:
                return None
            if w.heights_m.size:
                value = float(np.nanmax(w.heights_m))
                best = value if best is None else max(best, value)
        return best

    def height_m(self, lon_deg, lat_deg, max_pixel_m=None) -> np.ndarray:
        return self._terrain.height_m(lon_deg, lat_deg, max_pixel_m=max_pixel_m, statistic=self.statistic)

    @property
    def is_synthetic(self) -> bool:
        """True if any product declares itself a synthetic test surface."""
        return any(
            "SYNTH" in f"{p.product_id} {p.product_version} {p.data_set_id}".upper() for p in self._terrain.products
        )

    def describe(self) -> dict:
        layers = []
        for item in self._terrain.provenance():
            layers.append(
                {
                    "layer_id": str(item["product_id"]),
                    "product_id": str(item["product_id"]),
                    "version": str(item.get("product_version")),
                    "source_url": str(item.get("source_url", "")),
                    "sha256": item.get("sha256"),
                    "pixel_m": float(item["pixel_m"]),
                    "projection": "polar stereographic on a sphere, true scale at the pole",
                }
            )
        ids = "+".join(f"{layer['product_id']}@{layer['version']}" for layer in layers)
        return {"dem_set_id": f"lola:{ids}", "layers": layers}
