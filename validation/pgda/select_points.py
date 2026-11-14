"""Choose the comparison points for the PGDA illumination check, before any map value is read.

The points are pixel centres of the 60 m south-polar grid of the published maps
(AVGVISIB_85S_060M_201608). They are chosen from the LOLA elevation model alone, by a
fixed rule with a fixed seed, so that ridges and rims, plains and slopes, and floors are
all represented:

1. draw candidate pixels uniformly over the area within 145 km of the pole;
2. compute for each a topographic position index: its height minus the mean height on a
   ring of 1.5 km radius (60 m LOLA product);
3. take 33 points at random from the highest tenth (ridges and rims), 33 from the lowest
   tenth (floors), 31 from the middle tenth (plains and slopes);
4. add the three site records of the data stream, moved to the nearest pixel centre.

Usage (from the repository root, with the LOLA data under LSN_DATA_ROOT)::

    python -m validation.pgda.select_points
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent

SEED = 20261114
N_CANDIDATES = 4000
MAX_RADIUS_M = 145_000.0
RING_RADIUS_M = 1500.0
RING_POINTS = 16
QUOTA = {"ridge_or_rim": 33, "floor": 33, "plain_or_slope": 31}

# Grid of the published maps, from their PDS labels: 5058 x 5058 pixels of 60 m, polar
# stereographic on the 1737.4 km sphere, pole at line and sample offset 2528.5.
GRID = {"lines": 5058, "samples": 5058, "pixel_m": 60.0, "projection_offset": 2528.5, "radius_m": 1_737_400.0}


def grid():
    from lsn_data.georef import PolarGrid

    edge = (GRID["projection_offset"] + 0.5) * GRID["pixel_m"]
    return PolarGrid(GRID["lines"], GRID["samples"], GRID["pixel_m"], -edge, edge, GRID["radius_m"], -1)


def main() -> None:
    import lsn_data
    from lsn_data.georef import lonlat_to_xy, xy_to_lonlat

    g = grid()
    reader = lsn_data.open_terrain(products=("LDEM_60S_60M",))
    rng = np.random.default_rng(SEED)

    rows, cols = [], []
    while len(rows) < N_CANDIDATES:
        r = rng.integers(0, g.n_rows, 2 * N_CANDIDATES)
        c = rng.integers(0, g.n_cols, 2 * N_CANDIDATES)
        x, y = g.rowcol_to_xy(r, c)
        keep = np.hypot(x, y) <= MAX_RADIUS_M
        rows += list(r[keep])
        cols += list(c[keep])
    rows, cols = np.array(rows[:N_CANDIDATES]), np.array(cols[:N_CANDIDATES])
    x, y = g.rowcol_to_xy(rows, cols)
    lon, lat = xy_to_lonlat(x, y, g.radius_m, -1)
    height = reader.height_m(lon, lat)
    angles = 2.0 * np.pi * np.arange(RING_POINTS) / RING_POINTS
    ring_lon, ring_lat = xy_to_lonlat(x[:, None] + RING_RADIUS_M * np.cos(angles), y[:, None] + RING_RADIUS_M * np.sin(angles), g.radius_m, -1)
    tpi = height - reader.height_m(ring_lon, ring_lat).mean(axis=1)
    if not np.all(np.isfinite(tpi)):
        raise RuntimeError("elevation data missing at a candidate point")

    q = np.quantile(tpi, [0.10, 0.45, 0.55, 0.90])
    strata = {"ridge_or_rim": np.nonzero(tpi >= q[3])[0], "floor": np.nonzero(tpi <= q[0])[0], "plain_or_slope": np.nonzero((tpi >= q[1]) & (tpi <= q[2]))[0]}
    points = []
    for name, quota in QUOTA.items():
        for k in sorted(rng.choice(strata[name], quota, replace=False)):
            points.append({"id": f"{name}_{len([p for p in points if p['stratum'] == name]) + 1:02d}", "stratum": name, "line": int(rows[k]), "sample": int(cols[k]),
                           "x_m": float(x[k]), "y_m": float(y[k]), "lon_deg": float(lon[k]), "lat_deg": float(lat[k]),
                           "height_m": float(height[k]), "topographic_position_m": float(tpi[k])})

    records = json.loads((REPO / "data" / "sites" / "sites.json").read_text(encoding="utf-8"))["sites"]
    for record in records:
        sx, sy = lonlat_to_xy(record["lon_deg_east"], record["lat_deg"], g.radius_m, -1)
        r, c = (int(round(float(v))) for v in g.xy_to_rowcol(sx, sy))
        px, py = g.rowcol_to_xy(r, c)
        plon, plat = xy_to_lonlat(px, py, g.radius_m, -1)
        points.append({"id": "site_" + record["site_id"], "stratum": "site_record", "line": r, "sample": c, "x_m": float(px), "y_m": float(py),
                       "lon_deg": float(plon), "lat_deg": float(plat), "height_m": float(reader.height_m(plon, plat)), "topographic_position_m": None,
                       "note": f"pixel centre nearest to the site record, {float(np.hypot(px - sx, py - sy)):.1f} m from it"})

    out = {
        "description": "Comparison points for the PGDA illumination check: pixel centres of the 60 m south-polar grid of the published maps, chosen from the LOLA elevation model alone before any map value was read. Lines and samples are 0-based; x and y are polar stereographic metres (x = rho sin(lon), y = rho cos(lon)).",
        "rule": {"seed": SEED, "candidates": N_CANDIDATES, "max_radius_m": MAX_RADIUS_M, "ring_radius_m": RING_RADIUS_M, "ring_points": RING_POINTS, "quota": QUOTA,
                 "strata": "ridge_or_rim: topographic position in the highest tenth of the candidates; floor: lowest tenth; plain_or_slope: 45th to 55th percentile; site_record: the three site records of the data stream",
                 "elevation_model": "LDEM_60S_60M (LOLA, 60 m)", "quantiles_m": {"p10": float(q[0]), "p45": float(q[1]), "p55": float(q[2]), "p90": float(q[3])}},
        "grid": GRID,
        "points": points,
    }
    (HERE / "points.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    for name in list(QUOTA) + ["site_record"]:
        chosen = [p for p in points if p["stratum"] == name]
        tp = [p["topographic_position_m"] for p in chosen if p["topographic_position_m"] is not None]
        lats = [p["lat_deg"] for p in chosen]
        print(f"{name:15s} {len(chosen):3d} points; latitude {min(lats):.2f} to {max(lats):.2f}" + (f"; topographic position {min(tp):+.0f} to {max(tp):+.0f} m" if tp else ""))
    print(len(points), "points written")


if __name__ == "__main__":
    main()
