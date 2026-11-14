import json
from datetime import datetime

import pytest

from lsn_data import manifest as mf
from lsn_data.paths import manifest_path, repo_data_dir

SITES = json.loads((repo_data_dir() / "sites" / "sites.json").read_text(encoding="utf-8"))["sites"]
MANIFEST = mf.load(manifest_path())


def test_three_sites_with_provenance():
    assert [s["site_id"] for s in SITES] == ["shackleton_rim_crest", "de_gerlache_rim_crest", "malapert_massif_summit"]
    for s in SITES:
        assert -90 <= s["lat_deg"] <= -85 and 0 <= s["lon_deg_east"] < 360
        assert s["anchor"]["url"].startswith("https://planetarynames.wr.usgs.gov/Feature/")
        datetime.strptime(s["anchor"]["retrieved_utc"], "%Y-%m-%dT%H:%M:%SZ")
        assert "1737.4" in s["reference_frame"] and "east" in s["reference_frame"]
        assert s["terrain_product"]["sha256"] == MANIFEST["files"][s["terrain_product"]["file"]]["sha256"]
        assert "not an official landing site" in s["status"]


@pytest.mark.needs_data
def test_site_heights_match_the_dem():
    from lsn_data import open_terrain

    t = open_terrain()
    for s in SITES:
        h = float(t.height_m(s["lon_deg_east"], s["lat_deg"]))
        assert abs(h - s["ground_height_m_above_1737.4km_sphere"]) < 2.0, s["site_id"]
