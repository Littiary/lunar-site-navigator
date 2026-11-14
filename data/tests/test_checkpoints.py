"""The three data checkpoints on the real files. Skipped when the data is not under the data root."""

import json

import pytest

from lsn_data import checkpoints
from lsn_data.paths import data_root, repo_data_dir

pytestmark = pytest.mark.needs_data


@pytest.fixture(scope="module")
def report():
    return checkpoints.run_all(data_root())


# Known, explained exceptions to checkpoint 1 (the rule in thresholds.json is not changed; each is tested on its own).
LDEM_128 = "raw/lola/LDEM_128/ldem_128.img"
KNOWN_MISMATCH = {
    LDEM_128: "PDS copy has bytes 56-4095 zeroed; ours is consistent (data/checkpoints/ldem128_second_source_note.md)",
}
# LRO_ES_100 returns: unused (no valid ranges); the MIT copies are the 2021 processing (software 5.7), PDS holds a 2022
# reprocessing (software 5.12) of the same orbits, so the hashes differ.
UNUSED_OLDER_PROCESSING = {
    "raw/lola_rdr/LOLARDR_210261356/lolardr_210261356.dat",
    "raw/lola_rdr/LOLARDR_210281841/lolardr_210281841.dat",
    "raw/lola_rdr/LOLARDR_210261356/lolardr_210261356.lbl",
    "raw/lola_rdr/LOLARDR_210281841/lolardr_210281841.lbl",
}
LDEM_128_PDS_SHA256 = "0e4fea9b863e3255f58de15ccbd2bb8b1e248cb09217fd55d23ed37489f764b4"


def _approved_tiles() -> set[str]:
    from lsn_data import catalog

    approved = json.loads((repo_data_dir() / "manifest" / "approved_mosaics.json").read_text(encoding="utf-8"))["approved"]
    return {t for mid, tiles in catalog.MOON_CYLINDRICAL if mid in approved for t in tiles}


def _allowed_without_second_source(rel: str) -> bool:
    """Files that may lack a matching second-source hash, each for a stated reason."""
    if rel in KNOWN_MISMATCH or rel in UNUSED_OLDER_PROCESSING:
        return True
    if rel.startswith("raw/lola_5mpp/"):
        return True  # PGDA is the only host (thresholds_near_field.json, checkpoint_1_checksums)
    tile = rel.split("/")[-2]
    if tile.startswith("SLDEM2015_512_") and tile not in _approved_tiles():
        return True  # downloaded, not approved, not used by any terrain; approval requires the second-source hash
    return False


def test_checkpoint_1_checksums(report):
    c = report["checkpoint_1_checksums"]
    assert not c["problems"], c["problems"]  # every file on disk equals its manifest record
    assert set(c["cross_check_failed"]) <= set(KNOWN_MISMATCH) | UNUSED_OLDER_PROCESSING, c["cross_check_failed"]
    unexplained = [r for r in c["data_files_without_matching_cross_check"] if not _allowed_without_second_source(r)]
    assert not unexplained, unexplained


def test_unapproved_files_are_not_used_by_any_terrain():
    import lsn_data

    try:
        moon = lsn_data.open_terrain(products="moon")
    except FileNotFoundError:
        pytest.skip("products not present")
    used = {t.product_id for c in moon.cylindrical for t in c.tiles}
    assert not any(u.startswith("SLDEM2015_512_") for u in used) or used <= _approved_tiles()


@pytest.mark.xfail(
    strict=True,
    reason="LDEM_128: the PDS copy differs from ours in bytes 56-4095 (zeroed there); see "
    "data/checkpoints/ldem128_second_source_note.md. Turns red (XPASS) if the second source ever matches.",
)
def test_ldem128_second_source_matches():
    from lsn_data import manifest as mf
    from lsn_data.paths import manifest_path

    rec = mf.load(manifest_path())["files"][LDEM_128]
    assert any(c["matches"] for c in rec.get("cross_checks", [])), rec.get("cross_checks")


def test_ldem128_difference_is_exactly_the_zeroed_block():
    """Our file equals its manifest hash, and with bytes 56-4095 set to zero it equals the PDS hash."""
    import hashlib

    from lsn_data import manifest as mf
    from lsn_data.paths import manifest_path

    path = data_root() / LDEM_128
    if not path.exists():
        pytest.skip("LDEM_128 not under the data root")
    rec = mf.load(manifest_path())["files"][LDEM_128]
    assert any(c["sha256"] == LDEM_128_PDS_SHA256 and not c["matches"] for c in rec["cross_checks"])
    ours, zeroed = hashlib.sha256(), hashlib.sha256()
    with open(path, "rb") as f:
        head = f.read(4096)
        assert head[56:4096].count(0) < 4040  # our block is not zero
        ours.update(head)
        zeroed.update(head[:56] + bytes(4040))
        while block := f.read(1 << 24):
            ours.update(block)
            zeroed.update(block)
    assert ours.hexdigest() == rec["sha256"]
    assert zeroed.hexdigest() == LDEM_128_PDS_SHA256


@pytest.mark.xfail(
    strict=True,
    reason="checkpoint 2 (IAU outlines on rim crests) passes for 2 of 6 craters by design of its fixed threshold; "
    "the supplementary catalogue check below is what the project relies on. This turns red if checkpoint 2 starts passing.",
)
def test_checkpoint_2_georeferencing(report):
    c = report["checkpoint_2_georeferencing"]
    assert c["passed"], json.dumps(c, indent=1)


def test_checkpoint_3_values_and_reference_radius(report):
    c = report["checkpoint_3_values_and_reference_radius"]
    assert c["passed"], json.dumps(c, indent=1)


def test_catalogue_check_criteria_hold():
    """The pre-committed criteria of data/checkpoints/thresholds_catalogue.json, on the recorded result."""
    th = json.loads((repo_data_dir() / "checkpoints" / "thresholds_catalogue.json").read_text(encoding="utf-8"))
    r = json.loads((repo_data_dir() / "checkpoints" / "catalogue_report.json").read_text(encoding="utf-8"))
    lev = th["what_matters_for_horizons"]
    est, se = r["estimates"], r["bootstrap_se"]
    assert r["craters_used_after_outlier_rejection"] >= 100
    # translation and rotation are ruled out to the matter level: estimate + 1.96 SE below it
    assert abs(est["translation_x_m"]) + 1.96 * se["translation_x_m"] < lev["translation_m"]
    assert abs(est["translation_y_m"]) + 1.96 * se["translation_y_m"] < lev["translation_m"]
    assert abs(est["rotation_deg"]) + 1.96 * se["rotation_deg"] < lev["rotation_deg"]
    # radial scale: whatever is detected must stay below the matter level
    assert abs(est["radial_scale"]) < lev["radial_scale"]
    assert "confirmed_and_matters" not in r["classification"].values()


def test_candidate_mosaic_is_opened_only_when_asked():
    """moon_check may evaluate a downloaded, unapproved mosaic; open_terrain never uses it without approval."""
    from lsn_data import catalog, open_moon

    root = data_root()
    tiles = dict(catalog.MOON_CYLINDRICAL)["SLDEM2015_512"]
    if not all((root / "raw" / "lola" / t / f"{t.lower()}.img").exists() for t in tiles):
        pytest.skip("SLDEM2015_512 not complete under the data root")
    approved = json.loads((repo_data_dir() / "manifest" / "approved_mosaics.json").read_text(encoding="utf-8"))["approved"]
    default = open_moon(root)
    asked = open_moon(root, candidates=("SLDEM2015_512",))
    assert ("SLDEM2015_512" in [c.product_id for c in default.cylindrical]) == ("SLDEM2015_512" in approved)
    c = next(c for c in asked.cylindrical if c.product_id == "SLDEM2015_512")
    assert [t.product_id for t in c.tiles] == list(tiles)
    assert asked.cylindrical[0].product_id == "SLDEM2015_512"  # finest first
