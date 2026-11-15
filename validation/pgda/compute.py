"""Our long-term Sun and Earth visibility shares at the comparison points.

For every point of ``points.json`` the terrain horizon is computed twice (run A: the 60 m
LOLA product alone; run B: the terrain the tool uses), and the share of hourly timesteps
over one nodal cycle at which any part of the Sun's disc, and of the Earth's disc, is above
that horizon is counted, for an observer at 0 m and at 2 m. Nothing of the published maps
is read here. Settings are those fixed in ``thresholds.json``. The result records the
commit of the code, the terrain layers and the settings of the horizon search, because
the horizon depends on all three.

Usage (from the repository root, with the LOLA data under LSN_DATA_ROOT)::

    python -m validation.pgda.compute
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import subprocess
import time
from pathlib import Path

import numpy as np

from lsncore import events as ev
from lsncore.ephem import directions as d
from lsncore.ephem import kernels

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"

PERIOD_START_UTC = "2020-01-01T00:00:00"
SECOND_PERIOD_START_UTC = "2000-01-01T00:00:00"
STEPS = 163161  # hourly steps in one nodal cycle of 6798.38 days
STEP_S = 3600.0
HEIGHTS_M = [0.0, 2.0]
AZIMUTH_STEP_DEG = 0.25
MAX_RANGE_M = 300000.0
CHUNK = 60000


def hourly_table(start_utc: str) -> d.DirectionTable:
    return d.direction_table(d.utc_to_et(start_utc) + STEP_S * np.arange(STEPS))


def shares(site: d.Site, table: d.DirectionTable, elevation_deg: np.ndarray) -> dict:
    """Share of the table epochs at which any part of each disc is above the horizon, per height."""
    out = {}
    topo = d.topocentric_from_table(site, table)
    for h, height in enumerate(HEIGHTS_M):
        horizon = ev.Horizon(0.0, AZIMUTH_STEP_DEG, np.asarray(elevation_deg[h], dtype=np.float64))
        entry = {}
        for body in d.BODIES:
            body_dir = topo[body]
            visible = 0
            for begin in range(0, table.et.size, CHUNK):
                part = slice(begin, begin + CHUNK)
                upper, _ = ev.limb_margins(body_dir.az_deg[part], body_dir.el_deg[part], body_dir.angular_radius_deg[part], horizon)
                visible += int(np.count_nonzero(upper > 0.0))
            entry[body.lower()] = visible / table.et.size
        out[f"{height:g}m"] = entry
    return out


def code_state() -> dict:
    """The commit of the working copy, and whether the code that gives these numbers differs from it."""

    def git(*args: str) -> str:
        return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True, check=True).stdout.strip()

    try:
        return {"git_commit": git("rev-parse", "--short", "HEAD"), "uncommitted_changes": bool(git("status", "--porcelain", "--", ":/core", ":/data", ":/validation/pgda/compute.py"))}
    except (OSError, subprocess.CalledProcessError):
        return {"git_commit": None, "uncommitted_changes": None}


def open_terrains() -> dict:
    """Run A: the 60 m LOLA product alone, as the published maps use it. Run B: the terrain the tool uses."""
    import lsn_data

    from lsncore.dem import LolaTerrain, open_lola

    return {"run_A_60m": LolaTerrain(lsn_data.open_terrain(products=("LDEM_60S_60M",))), "run_B_production": open_lola()}


def point_row(point: dict, terrains: dict, table: d.DirectionTable, settings, second: d.DirectionTable | None = None) -> dict:
    """Horizon and shares of one comparison point for every run; ``second`` adds the shares of run A over a second cycle."""
    from lsncore.horizon import compute_horizon

    row = {"id": point["id"], "stratum": point["stratum"]}
    for run, terrain in terrains.items():
        horizon = compute_horizon(terrain, point["lat_deg"], point["lon_deg"], HEIGHTS_M, AZIMUTH_STEP_DEG, MAX_RANGE_M, settings)
        elevation = np.asarray(horizon.elevation_deg, dtype=np.float64)
        if not np.all(np.isfinite(elevation)):
            raise RuntimeError(f"horizon has gaps at {point['id']}")
        site = d.Site(point["lon_deg"], point["lat_deg"], horizon.surface_height_m / 1000.0)
        row[run] = {
            "surface_height_m": float(horizon.surface_height_m),
            "horizon_min_deg": float(elevation[0].min()),
            "horizon_max_deg": float(elevation[0].max()),
            "share_of_horizon_set_closer_than_1km": float((np.asarray(horizon.distance_m[0]) < 1000.0).mean()),
            "coverage_complete": bool(horizon.coverage_complete),
            "shares": shares(site, table, elevation),
        }
        if run == "run_A_60m" and second is not None:
            row["run_A_60m"]["shares_second_cycle"] = shares(site, second, elevation)
    return row


def main() -> None:
    from lsncore.horizon import HorizonSettings

    kernels.load()
    points = json.loads((HERE / "points.json").read_text(encoding="utf-8"))["points"]
    terrains = open_terrains()
    table = hourly_table(PERIOD_START_UTC)
    second = hourly_table(SECOND_PERIOD_START_UTC)
    second_ids = {p["id"] for p in points if p["id"].endswith(("_01", "_02", "_03"))} | {"site_shackleton_rim_crest"}
    settings = HorizonSettings()
    out, t0 = [], time.perf_counter()
    for n, point in enumerate(points):
        out.append(point_row(point, terrains, table, settings, second if point["id"] in second_ids else None))
        if (n + 1) % 10 == 0:
            print(f"{n + 1} points, {time.perf_counter() - t0:.0f} s", flush=True)
    RESULTS.mkdir(exist_ok=True)
    result = {
        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "code": code_state(),
        "settings": {"period_start_utc": PERIOD_START_UTC, "second_period_start_utc": SECOND_PERIOD_START_UTC, "hourly_steps": STEPS, "observer_heights_m": HEIGHTS_M,
                     "azimuth_step_deg": AZIMUTH_STEP_DEG, "max_range_m": MAX_RANGE_M, "quantity": "share of timesteps with any part of the disc above the terrain horizon",
                     "frame": d.FRAME, "aberration_correction": d.ABCORR, "kernel_set_id": kernels.kernel_set_id()},
        "horizon_settings": dataclasses.asdict(settings),
        "terrain": {run: terrain.describe()["dem_set_id"] for run, terrain in terrains.items()},
        "terrain_layers": {run: terrain.describe().get("layers") for run, terrain in terrains.items()},
        "run_time_s": time.perf_counter() - t0,
        "points": out,
    }
    (RESULTS / "our_shares.json").write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    print(f"done in {time.perf_counter() - t0:.0f} s")


if __name__ == "__main__":
    main()
