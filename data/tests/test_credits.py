"""Every product in data/manifest/manifest.json has a row in the Data table of CREDITS.md."""

import json
import re

from lsn_data.paths import repo_data_dir

# product_id (exact, or prefix ending in "_") -> text that identifies its row in the first two columns of CREDITS.md
ROW_KEY = {
    "LDEC_80S_20M": "LDEC_80S_20M",
    "LDEM_16": "LDEM_16",
    "LDEM_128": "LDEM_128",
    "LDEM_80S_20M": "LDEM_80S_20M",
    "LDEM_60S_60M": "LDEM_60S_60M",
    "LDEM_80N_20M": "LDEM_80N_20M",
    "LDEM_60N_60M": "LDEM_60N_60M",
    "LOLA5MPP_": "LOLA 5 m/pixel site DEMs",
    "_pgda_docs": "LOLA 5 m/pixel site DEMs",
    "LOLARDR_": "LOLA RDR laser returns",
    "_rdr_docs": "LOLA RDR laser returns",
    "urn:nasa:pds:lro_lola_rdr": "LOLA RDR bundle documents",
    "LROC_ANTHROPOGENIC": "LROC Anthropogenic Features",
    "ROBBINS_2018": "Lunar crater database v1",
    "SLDEM2015_256_": "SLDEM2015_256:",
    "SLDEM2015_512_": "SLDEM2015_512:",
}


def _data_rows() -> list[str]:
    text = (repo_data_dir().parent / "CREDITS.md").read_text(encoding="utf-8")
    table = text.split("## Data", 1)[1].split("\n## ", 1)[0]
    rows = [ln for ln in table.splitlines() if ln.startswith("| ") and not ln.startswith("| Name") and not ln.startswith("|---")]
    return [" | ".join(r.split(" | ")[:2]) for r in rows]


def _key(pid: str) -> str | None:
    if pid in ROW_KEY:
        return ROW_KEY[pid]
    return next((v for k, v in ROW_KEY.items() if k.endswith("_") and pid.startswith(k)), None)


def test_every_manifest_product_has_exactly_one_credits_row():
    pids = {r["product_id"] for r in json.loads((repo_data_dir() / "manifest" / "manifest.json").read_text(encoding="utf-8"))["files"].values()}
    rows = _data_rows()
    unmapped = sorted(p for p in pids if _key(p) is None)
    assert not unmapped, unmapped
    for p in pids:
        hits = [r for r in rows if _key(p) in r]
        assert len(hits) == 1, (p, _key(p), len(hits))


def test_sldem_rows_state_the_kaguya_contribution_and_the_citation():
    text = (repo_data_dir().parent / "CREDITS.md").read_text(encoding="utf-8")
    for key in ("SLDEM2015_256", "SLDEM2015_512"):
        row = next(ln for ln in text.splitlines() if ln.startswith("| ") and key in ln.split(" | ")[0])
        assert "JAXA" in row and "Terrain Camera" in row and "10.1016/j.icarus.2015.07.039" in row
    assert re.search(r"SLDEM2015_512.*not approved", text)
