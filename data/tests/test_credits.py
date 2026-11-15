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


def _all_rows() -> list[list[str]]:
    """Rows of the Data, Software libraries and Images tables (the AI-tools table lists one person per row)."""
    text = (repo_data_dir().parent / "CREDITS.md").read_text(encoding="utf-8").split("## Use of AI tools", 1)[0]
    return [[c.strip() for c in ln.strip().strip("|").split(" | ")] for ln in text.splitlines()
            if ln.startswith("| ") and not ln.startswith("|---") and not ln.startswith("| Name") and not ln.startswith("| Team member")]


def _same_item_key(row: list[str]) -> tuple:
    """Name without its parenthetical details, second column and source column: two rows with the same key credit the
    same item (it catches a row copied again with a longer list in brackets, e.g. the Gazetteer feature list)."""
    name = re.sub(r"\s+", " ", re.sub(r"\([^()]*\)", "", row[0])).strip(" ,;")
    return name, row[1], row[-2]


def test_no_row_appears_twice():
    keys = [_same_item_key(r) for r in _all_rows()]
    dup = sorted({k[0] for k in keys if keys.count(k) > 1})
    assert not dup, dup


def _urls(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, str) and v.startswith("https://") and k in ("url", "source_url"):
                yield v
            else:
                yield from _urls(v)
    elif isinstance(obj, list):
        for v in obj:
            if isinstance(v, str) and v.startswith("https://"):
                yield v
            else:
                yield from _urls(v)


def test_every_cited_source_of_the_checkpoints_and_site_list_is_credited():
    """Reference values in the threshold files and the sources of the published site list each have a credit row."""
    text = (repo_data_dir().parent / "CREDITS.md").read_text(encoding="utf-8")
    credited = re.findall(r"https://[^\s|)\]]+", text)
    cp = repo_data_dir() / "checkpoints"
    missing = []
    for f in sorted(cp.glob("thresholds*.json")):
        for u in _urls(json.loads(f.read_text(encoding="utf-8"))):
            if not any(u.startswith(c) for c in credited):  # the row may name the directory that holds the file
                missing.append((f.name, u))
    sites = json.loads((repo_data_dir() / "sites" / "curated_sites.json").read_text(encoding="utf-8"))
    for s in sites["sites"]:
        for u in s.get("nasa_sources", []):
            if u not in text:
                missing.append((s["site_id"], u))
        host = s["coordinate_source"]["url"].split("/")[2]
        if host not in text:
            missing.append((s["site_id"], host))
    assert not missing, missing
