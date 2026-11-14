"""Contract 0.2: obstacles of the horizon, the blocker of every sample, time lost to terrain."""

import copy
import json
import shutil

import numpy as np
import pytest

from lsncore.contract import ContractError, contract_dir, read_package, validate_document, validate_package
from lsncore.scenario import load_scenario
from lsncore.synthetic import run_synthetic_scenario
from lsncore.timeline import IntervalSet

SAMPLE = contract_dir() / "sample"


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    out = tmp_path_factory.mktemp("packages")
    paths = run_synthetic_scenario(load_scenario(SAMPLE / "SYNTHETIC_scenario.json"), out)
    path = next(p for p in paths if p.name.startswith("site-"))
    validate_package(path)
    return read_package(path)


def test_obstacle_list_and_array_agree(site):
    hz = site.manifest["horizon"]
    ids = site.array(hz["obstacle_id"])
    n_az = hz["azimuth"]["count"]
    assert ids.dtype == np.dtype("<i4") and ids.shape == (len(hz["observer_heights_m"]), n_az)
    assert len(hz["obstacles"]) > len(hz["observer_heights_m"])  # the sample has several per height
    elevation = site.array(hz["elevation_deg"])
    distance = site.array(hz["distance_m"])
    for k, ob in enumerate(hz["obstacles"]):
        assert ob["id"] == k and ob["method"] in site.manifest["methods"]
        h = ob["height_index"]
        idx = (ob["azimuth_start_index"] + np.arange(ob["azimuth_count"])) % n_az
        assert np.all(ids[h, idx] == k)
        peak = int(round(ob["peak_azimuth_deg"] / hz["azimuth"]["step_deg"]))
        assert peak in idx
        assert ob["peak_elevation_deg"] == pytest.approx(float(elevation[h, idx].max()), abs=1e-5)
        assert ob["peak_distance_m"] == pytest.approx(float(distance[h, peak]), rel=1e-6)
        assert ob["distance_min_m"] <= ob["peak_distance_m"] <= ob["distance_max_m"]
    assert (ids >= 0).all()


def test_every_sample_names_its_limiting_horizon_sample(site):
    hz, tl = site.manifest["horizon"], site.manifest["timeline"]
    n = tl["time"]["count"]
    for body in tl["bodies"]:
        index = site.array(tl["series"][body]["blocker_azimuth_index"])
        assert index.shape == (len(hz["observer_heights_m"]), n)
        assert index.min() >= 0 and index.max() < hz["azimuth"]["count"]
        # the limiting sample lies under the disc: within its angular radius (plus a step) of the centre
        az = site.array(tl["series"][body]["azimuth_deg"])
        radius = site.array(tl["series"][body]["angular_radius_deg"])
        offset = (index * hz["azimuth"]["step_deg"] - az[None, :] + 180.0) % 360.0 - 180.0
        assert np.all(np.abs(offset) <= radius[None, :] * 1.01 + hz["azimuth"]["step_deg"])


def test_lost_and_gained_time_close_the_balance(site):
    """visible over terrain = visible over a smooth sphere - lost + gained, for every body
    and height; and the blockers add up to the lost time."""
    tl = site.manifest["timeline"]
    grid = tl["time"]
    domain = (grid["start_et_s"], grid["start_et_s"] + (grid["count"] - 1) * grid["step_s"])
    heights = range(len(site.manifest["horizon"]["observer_heights_m"]))

    def window(wid, h):
        (record,) = [w for w in tl["windows"] if w["id"] == wid and w["height_index"] == h]
        return IntervalSet(record["intervals_et_s"], domain), record

    def metric(mid, h):
        (record,) = [m for m in tl["metrics"] if m["id"] == mid and m["height_index"] == h]
        return record["value"]

    some_loss = False
    for body in tl["bodies"]:
        tag = body.lower()
        for h in heights:
            terrain, _ = window(f"{tag}_visible", h)
            smooth, smooth_record = window(f"{tag}_visible_smooth_sphere", h)
            lost, _ = window(f"{tag}_lost_to_terrain", h)
            gained, _ = window(f"{tag}_gained_from_terrain", h)
            assert lost == smooth.intersection(terrain.complement())
            assert gained == terrain.intersection(smooth.complement())
            assert terrain.total_s() == pytest.approx(smooth.total_s() - lost.total_s() + gained.total_s(), abs=1e-6)
            assert metric(f"{tag}_lost_to_terrain_s", h) == pytest.approx(lost.total_s(), abs=1e-6)
            assert metric(f"{tag}_visible_s", h) == pytest.approx(terrain.total_s(), abs=1e-6)
            assert smooth_record["threshold"] == site.manifest["request"]["timeline"]["thresholds"][body]
            mine = [b for b in tl["blockers"] if b["body"] == body and b["height_index"] == h]
            assert sum(b["lost_s"] for b in mine) == pytest.approx(lost.total_s(), abs=1e-6)
            assert sum(b["share_of_lost"] for b in mine) == pytest.approx(1.0 if mine else 0.0, abs=1e-9)
            assert mine == sorted(mine, key=lambda b: -b["lost_s"])
            for b in mine:
                ob = site.manifest["horizon"]["obstacles"][b["obstacle_id"]]
                assert ob["height_index"] == h and b["peak_distance_m"] == ob["peak_distance_m"]
                assert len(b["intervals_utc"]) == len(b["intervals_et_s"])
            some_loss = some_loss or lost.total_s() > 0
    assert some_loss  # the sample shows the feature


def test_reader_of_this_version_accepts_older_minor_versions_only(site):
    manifest = copy.deepcopy(site.manifest)
    validate_document(manifest)
    # a 0.1 package has none of the 0.2 fields
    older = copy.deepcopy(manifest)
    older["contract"]["version"] = "0.1"
    for key in ("obstacle_id", "obstacles"):
        older["horizon"].pop(key)
    older["timeline"].pop("blockers")
    for body in older["timeline"]["bodies"]:
        older["timeline"]["series"][body].pop("blocker_azimuth_index")
    validate_document(older)
    for version in ("0.3", "1.0", "0.2.1", "x"):
        newer = copy.deepcopy(manifest)
        newer["contract"]["version"] = version
        with pytest.raises(ContractError):
            validate_document(newer)


@pytest.mark.parametrize(
    "case, change, expected",
    [
        ("blocker names an unknown obstacle", lambda m: m["timeline"]["blockers"][0].update(obstacle_id=10_000), "obstacle_id"),
        ("obstacle list without the array", lambda m: m["horizon"].pop("obstacle_id"), "obstacle_id"),
        ("obstacle id out of order", lambda m: m["horizon"]["obstacles"][0].update(id=3), "position in the list"),
        ("blocker without a method", lambda m: m["timeline"]["blockers"][0].pop("method"), "method"),
    ],
)
def test_validator_rejects_broken_0_2_fields(site, tmp_path, case, change, expected):
    dst = tmp_path / site.path.name
    shutil.copytree(site.path, dst)
    manifest = json.loads((dst / "manifest.json").read_text())
    change(manifest)
    (dst / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ContractError) as info:
        validate_package(dst)
    assert expected in str(info.value)
