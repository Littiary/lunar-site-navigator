"""The curated site list (data/sites/curated_sites.json): format, sources and consistency."""

import json
import math
import zipfile
from pathlib import Path

import pytest

from lsn_data.paths import data_root, repo_data_dir

PATH = repo_data_dir() / "sites" / "curated_sites.json"
REQUIRED = ("site_id", "name", "category", "kind", "programme", "lon_deg_east", "lat_deg", "reference_frame", "coordinate_source",
            "ground_height_m_above_1737.4km_sphere", "ground_radius_m", "terrain", "status")


@pytest.fixture(scope="module")
def doc():
    return json.loads(PATH.read_text(encoding="utf-8"))


def test_schema_and_required_fields(doc):
    assert doc["schema"].startswith("lunar-site-navigator site records")
    ids = [s["site_id"] for s in doc["sites"]]
    assert len(ids) == len(set(ids))
    for s in doc["sites"]:
        for k in REQUIRED:
            assert k in s, (s["site_id"], k)
        assert -90 <= s["lat_deg"] <= 90 and 0 <= s["lon_deg_east"] < 360
        src = s["coordinate_source"]
        assert src["url"].startswith("https://") and src["retrieved_utc"].endswith("Z")
        assert src.get("stated_uncertainty_m") is not None or src.get("stated_precision")
        t = s["terrain"]
        assert t["default"]["resolution_class"] in ("fine", "medium", "coarse")
        assert t["default"]["product_id"] and t["default"]["pixel_m"] > 0
        assert abs(s["ground_radius_m"] - 1_737_400.0 - s["ground_height_m_above_1737.4km_sphere"]) < 1e-6


def test_existing_three_are_kept_unchanged(doc):
    old = {s["site_id"]: s for s in json.loads((repo_data_dir() / "sites" / "sites.json").read_text(encoding="utf-8"))["sites"]}
    new = {s["site_id"]: s for s in doc["sites"]}
    for sid, s in old.items():
        assert new[sid]["lat_deg"] == s["lat_deg"] and new[sid]["lon_deg_east"] == s["lon_deg_east"]


def test_resolution_class_follows_pixel_size(doc):
    for s in doc["sites"]:
        for k in ("default", "near_field"):
            t = s["terrain"].get(k)
            if t is None:
                continue
            px = t["pixel_m"]
            expect = "fine" if px <= 20 else "medium" if px <= 60 else "coarse"
            assert t["resolution_class"] == expect, (s["site_id"], k, px)


def test_omitted_sites_have_reasons(doc):
    assert doc["omitted"]
    for o in doc["omitted"]:
        assert o["name"] and len(o["reason"]) > 20


@pytest.mark.needs_data
def test_lroc_coordinates_equal_the_source_table(doc):
    z = data_root() / "raw" / "catalogs" / "LROC_ANTHROPOGENIC" / "ANTHROPOGENIC_OBJECTS_360.ZIP"
    if not z.exists():
        pytest.skip("LROC table not under the data root")
    from lsn_data.curated_sites import read_lroc

    rows = {r["OBJECT_ID"]: r for r in read_lroc(z)}
    n = 0
    for s in doc["sites"]:
        oid = s["coordinate_source"].get("object_id")
        if s["coordinate_source"]["source"].startswith("LROC") and oid:
            r = rows[oid]
            assert math.isclose(s["lat_deg"], float(r["LATITUDE"]), abs_tol=1e-12)
            assert math.isclose(s["lon_deg_east"], float(r["LON_360"]), abs_tol=1e-12)
            n += 1
    assert n >= 15


def test_display_fields(doc):
    allowed = {"Apollo", "Surveyor", "Chang'e", "Chandrayaan", "SLIM", "CLPS", "Artemis", "Project sites"}
    for s in doc["sites"]:
        assert s["category"] in ("past landing", "candidate", "project site")
        assert s["programme"] in allowed
    by = {s["site_id"]: s for s in doc["sites"]}
    assert by["im_2_athena"]["programme"] == "CLPS" and by["apollo_11"]["category"] == "past landing"
    assert by["shackleton_rim_crest"]["programme"] == "Project sites" and by["shackleton_rim_crest"]["category"] == "project site"
