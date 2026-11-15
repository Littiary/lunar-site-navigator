"""Near-field layers are used only when approved and their checkpoints passed (data/manifest/approved_near_field.json)."""

import json

import numpy as np
import pytest

from lsn_data.paths import data_root, repo_data_dir

CP = repo_data_dir() / "checkpoints"


def _report():
    return json.loads((CP / "near_field_report.json").read_text(encoding="utf-8"))


def _approved():
    return json.loads((repo_data_dir() / "manifest" / "approved_near_field.json").read_text(encoding="utf-8"))["approved"]


def test_approved_list_is_exactly_the_layers_that_passed():
    rep = _report()
    passed = {pid for pid, s in rep["sites"].items() if s["passed"] and s["seam"]["passed"]}
    assert set(_approved()) == passed
    assert "LOLA5MPP_SITE23" not in _approved()


def test_gate_rule_needs_both_the_list_and_the_report():
    from lsn_data import near_field_usable

    rep = {"sites": {"A": {"passed": True, "seam": {"passed": True}}, "B": {"passed": True, "seam": {"passed": False}},
                     "C": {"passed": False, "seam": {"passed": True}}}}
    assert near_field_usable("A", {"A": "", "B": "", "C": ""}, rep)
    assert not near_field_usable("B", {"A": "", "B": "", "C": ""}, rep)  # listed, but its seam failed
    assert not near_field_usable("C", {"A": "", "B": "", "C": ""}, rep)
    assert not near_field_usable("A", {}, rep)  # passed, but not listed
    assert not near_field_usable("D", {"D": ""}, rep)  # listed, never checked


SITES = {"shackleton_rim_crest": "LOLA5MPP_SITE04", "de_gerlache_rim_crest": "LOLA5MPP_SITE11",
         "malapert_massif_summit": "LOLA5MPP_SITE23"}


@pytest.mark.needs_data
@pytest.mark.parametrize("products", ["default", "moon"])
def test_open_terrain_near_field_serves_site04_and_site11_but_not_site23(products):
    import lsn_data

    if not (data_root() / "raw" / "lola_5mpp" / "LOLA5MPP_SITE23").exists():
        pytest.skip("5 m site DEMs not under the data root")
    t = lsn_data.open_terrain(near_field=True) if products == "default" else lsn_data.open_terrain(products="moon", near_field=True)
    recs = {s["site_id"]: s for s in json.loads((repo_data_dir() / "sites" / "sites.json").read_text(encoding="utf-8"))["sites"]}
    for sid, pid in SITES.items():
        lon, lat = np.array([recs[sid]["lon_deg_east"]]), np.array([recs[sid]["lat_deg"]])
        src = t.source(lon, lat, max_pixel_m=None)[0][0]
        if pid == "LOLA5MPP_SITE23":
            assert src == "LDEM_80S_20M", (sid, src)
        else:
            assert src == pid, (sid, src)
    if products == "moon":
        assert any("LOLA5MPP_SITE23" in m and "not approved" in m for m in t.missing)


@pytest.mark.needs_data
def test_the_check_itself_still_opens_every_layer():
    from lsn_data import site_dems

    if not (data_root() / "raw" / "lola_5mpp" / "LOLA5MPP_SITE23").exists():
        pytest.skip("5 m site DEMs not under the data root")
    assert {d.product_id for d in site_dems(include_unapproved=True)} == set(SITES.values())
    assert {d.product_id for d in site_dems()} == {"LOLA5MPP_SITE04", "LOLA5MPP_SITE11"}
