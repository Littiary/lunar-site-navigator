"""Curated list of notable landing sites: data/sites/curated_sites.json (``python -m lsn_data.curated_sites``).

Sources:
* past landings: LROC "Anthropogenic Features on the Moon" (Wagner et al. 2017, Icarus 283, 92-103, updated
  2026-08-14), coordinates measured on LROC NAC images (retroreflector sites tied to laser ranging), PDS
  LRO-L-LROC-5-RDR-V1.0 extras, fetched by ``python -m lsn_data fetch LROC_ANTHROPOGENIC``;
* the three project candidate sites: data/sites/sites.json (unchanged);
* Artemis III regions: NASA published no coordinates; only a region named after an IAU feature gets a
  representative point (the IAU Gazetteer centre of that feature), marked as such.
Nothing is guessed; sites without a primary coordinate are listed under "omitted" with the reason.
"""

from __future__ import annotations

import json
import struct
import zipfile
from pathlib import Path

import numpy as np

from . import manifest as mf
from .paths import data_root, manifest_path, repo_data_dir

LROC_URL = "https://pds.lroc.im-ldi.com/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/EXTRAS/SHAPEFILE/ANTHROPOGENIC_OBJECTS/ANTHROPOGENIC_OBJECTS_360.ZIP"
LROC_CITATION = ("R. V. Wagner, D. M. Nelson, J. B. Plescia, M. S. Robinson, E. J. Speyerer, E. Mazarico (2017), Coordinates of "
                 "anthropogenic features on the Moon, Icarus 283, 92-103, doi:10.1016/j.icarus.2016.05.011; table updated 2026-08-14")
LROC_FRAME = ("Moon body-fixed, mean Earth/polar axis; planetocentric latitude, east longitude, sphere 1737.4 km (table .PRJ "
              "'GCS_Moon_2000', sphere 1737400 m). The LROC README does not name the body-fixed frame; its retroreflector "
              "entries equal the DE421/DE430 mean-Earth coordinates within 0.3 m and differ from the principal-axis ones by "
              "about 850 m, so the table is in the mean-Earth frame, the frame of our LOLA products")

# (site_id, LROC OBJECT_ID, category, display name)
LROC_SITES = [
    ("apollo_11", "A11_LM", "past_landing", "Apollo 11 (Lunar Module Eagle descent stage)"),
    ("apollo_12", "A12_LM", "past_landing", "Apollo 12 (Lunar Module Intrepid descent stage)"),
    ("apollo_14", "A14_LM", "past_landing", "Apollo 14 (Lunar Module Antares descent stage)"),
    ("apollo_15", "A15_LM", "past_landing", "Apollo 15 (Lunar Module Falcon descent stage)"),
    ("apollo_16", "A16_LM", "past_landing", "Apollo 16 (Lunar Module Orion descent stage)"),
    ("apollo_17", "A17_LM", "past_landing", "Apollo 17 (Lunar Module Challenger descent stage)"),
    ("surveyor_1", "Surveyor1", "past_landing", "Surveyor 1 lander"),
    ("change_3", "ChangE3", "past_landing", "Chang'e 3 lander"),
    ("change_4", "ChangE4", "past_landing", "Chang'e 4 lander"),
    ("change_5", "ChangE5", "past_landing", "Chang'e 5 lander"),
    ("change_6", "ChangE6", "past_landing", "Chang'e 6 lander"),
    ("chandrayaan_3", "Vikram2", "past_landing", "Chandrayaan-3 Vikram lander"),
    ("slim", "SLIM", "past_landing", "SLIM lander"),
    ("im_1_odysseus", "IM1", "past_landing", "IM-1 Odysseus lander (CLPS)"),
    ("blue_ghost_1", "BlueGhost1", "past_landing", "Blue Ghost Mission 1 lander (CLPS; LROC object: retroreflector on the lander)"),
    ("im_2_athena", "IM2", "past_landing", "IM-2 Athena lander (CLPS; south-polar, Mons Mouton)"),
]

ARTEMIS_RELEASE = "https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/"
ARTEMIS_LPSC = "https://ntrs.nasa.gov/citations/20250011660"
ARTEMIS_REGIONS = ["Peak near Cabeus B", "Haworth", "Malapert Massif", "Mons Mouton Plateau", "Mons Mouton",
                   "Nobile Rim 1", "Nobile Rim 2", "de Gerlache Rim 2", "Slater Plain"]


def read_lroc(zpath: Path) -> list[dict]:
    """Rows of the LROC table (.DBF inside the ZIP), as strings."""
    with zipfile.ZipFile(zpath) as z:
        b = z.read("ANTHROPOGENIC_OBJECTS_360.DBF")
    n, hl, rl = struct.unpack("<IHH", b[4:12])
    fields, o = [], 32
    while b[o] != 0x0D:
        fields.append((b[o : o + 11].split(b"\0")[0].decode(), b[o + 16]))
        o += 32
    rows = []
    for i in range(n):
        r, p, d = b[hl + i * rl : hl + (i + 1) * rl], 1, {}
        for name, ln in fields:
            d[name] = r[p : p + ln].decode("latin1").strip()
            p += ln
        rows.append(d)
    return rows


def _class(px: float) -> str:
    return "fine" if px <= 20 else "medium" if px <= 60 else "coarse"


def _terrain_entry(t, lon, lat) -> dict:
    ids, _ = t.source(lon, lat)
    pid = str(np.asarray(ids).ravel()[0])
    p = t.product(pid)
    px = p.pixel_m(0) if hasattr(p, "res_ppd") else p.grid0.pixel_m
    q = t.sample_quality(lon, lat)
    return {
        "product_id": pid,
        "pixel_m": float(px),
        "resolution_class": _class(px),
        "returns_in_pixel": int(np.asarray(q["returns_in_pixel"]).ravel()[0]),
        "height_rms_error_m": (None if np.isnan(np.asarray(q["height_rms_error_m"]).ravel()[0])
                               else float(np.asarray(q["height_rms_error_m"]).ravel()[0])),
        "height_m": float(np.asarray(t.height_m(lon, lat)).ravel()[0]),
    }


PROGRAMME = [("apollo_", "Apollo"), ("surveyor_", "Surveyor"), ("change_", "Chang'e"), ("chandrayaan_", "Chandrayaan"),
             ("slim", "SLIM"), ("im_1", "CLPS"), ("im_2", "CLPS"), ("blue_ghost", "CLPS"), ("artemis3_", "Artemis")]


def _programme(rec: dict) -> str:
    if rec["kind"] == "project_candidate":
        return "Project sites"
    for prefix, name in PROGRAMME:
        if rec["site_id"].startswith(prefix):
            return name
    raise ValueError(f"no programme for {rec['site_id']}")


def build(root=None) -> dict:
    import lsn_data

    root = Path(root or data_root())
    moon = lsn_data.open_terrain(products="moon", root=root)
    near = lsn_data.open_terrain(products="moon", root=root, near_field=True)
    m = mf.load(manifest_path())["files"]
    zrec = m["raw/catalogs/LROC_ANTHROPOGENIC/ANTHROPOGENIC_OBJECTS_360.ZIP"]
    rows = {r["OBJECT_ID"]: r for r in read_lroc(root / zrec["path"])}
    sites = []

    def finish(rec):
        # descriptive fields for the viewers' site picker; the machine category is kept as "kind"
        rec["kind"] = rec.pop("category")
        rec["category"] = {"past_landing": "past landing", "project_candidate": "project site",
                           "artemis_iii_candidate_region_representative": "candidate"}[rec["kind"]]
        rec["programme"] = _programme(rec)
        lon, lat = rec["lon_deg_east"], rec["lat_deg"]
        d = _terrain_entry(moon, lon, lat)
        nf = _terrain_entry(near, lon, lat)
        rec["terrain"] = {
            "default": {k: v for k, v in d.items() if k != "height_m"},
            "near_field": ({k: v for k, v in nf.items() if k != "height_m"} if nf["product_id"] != d["product_id"] else None),
            "classes": "fine <= 20 m pixels, medium <= 60 m, coarse above (cylindrical global products: near terrain within a "
                       "few pixels is not resolved)",
            "served_by": "lsn_data.open_terrain(products='moon') (default) and with near_field=True",
        }
        h = nf["height_m"] if rec["terrain"]["near_field"] else d["height_m"]
        rec["ground_height_m_above_1737.4km_sphere"] = round(h, 2)
        rec["ground_radius_m"] = round(h + 1_737_400.0, 2)
        rec["ground_height_from"] = rec["terrain"]["near_field"]["product_id"] if rec["terrain"]["near_field"] else d["product_id"]
        sites.append(rec)

    # 1. the existing three project sites, unchanged coordinates
    old = json.loads((repo_data_dir() / "sites" / "sites.json").read_text(encoding="utf-8"))
    for s in old["sites"]:
        rec = {k: v for k, v in s.items() if k not in ("ground_height_m_above_1737.4km_sphere", "ground_radius_m")}
        rec["category"] = "project_candidate"
        rec["coordinate_source"] = {
            "source": "data/sites/sites.json: located on LDEM_80S_20M by the stated rule from the IAU Gazetteer feature",
            "url": s["anchor"]["url"], "retrieved_utc": s["anchor"]["retrieved_utc"],
            "stated_precision": "one 20 m DEM pixel (location rule in location_method)",
        }
        finish(rec)

    # 2. past landings from the LROC table
    for sid, oid, cat, name in LROC_SITES:
        r = rows[oid]
        unc = float(r["UNCERTAIN"])
        finish({
            "site_id": sid, "name": name, "category": cat, "mission": r["MISSION"],
            "lon_deg_east": float(r["LON_360"]), "lat_deg": float(r["LATITUDE"]),
            "reference_frame": LROC_FRAME,
            "coordinate_source": {
                "source": "LROC Anthropogenic Features on the Moon (PDS LRO-L-LROC-5-RDR-V1.0 extras)",
                "citation": LROC_CITATION, "url": LROC_URL, "retrieved_utc": zrec["retrieved_utc"],
                "file_sha256": zrec["sha256"], "object_id": oid, "object": r["OBJECT"],
                "method": r["COORD_SRC"], "measured_on_LRO_imagery": True,
                "stated_uncertainty_m": unc, "arrival_date_utc": r["DATE"],
            },
            "other_values": "none compared: the LROC table is the only source used; mission-team values were not fetched",
            "status": "past landing site (position of the lander as measured on LROC images)",
        })

    # 3. Artemis III: representative point only where the region is named after an IAU feature with a point inside it
    mm = json.loads((repo_data_dir() / "sites" / "gazetteer_mons_mouton.json").read_text(encoding="utf-8"))
    det = mm["determinations"][0]
    finish({
        "site_id": "artemis3_region_mons_mouton_representative",
        "name": "Artemis III candidate region 'Mons Mouton': representative point (IAU centre of Mons Mouton)",
        "category": "artemis_iii_candidate_region_representative",
        "lon_deg_east": det["center_lon_deg"] % 360.0, "lat_deg": det["center_lat_deg"],
        "reference_frame": "IAU Gazetteer: planetographic, +East (equal to planetocentric on the 1737.4 km sphere); frame of the "
                           "Gazetteer's LOLA-based determination, taken as mean Earth/polar axis",
        "coordinate_source": {
            "source": "IAU Gazetteer of Planetary Nomenclature (USGS), feature 16070 Mons Mouton",
            "url": mm["source_url"], "retrieved_utc": mm["retrieved_utc"],
            "stated_precision": f"centre given to 0.1 deg (about 3 km); the feature is {det['diameter_km']:.0f} km across",
            "iau_status": mm["iau_status"],
        },
        "status": "REPRESENTATIVE point of a NASA candidate region, not a selected or published landing site; NASA "
                  "published no coordinates (release of 2024-10-28 and LPSC 2026 abstract); whether this point lies inside "
                  "NASA's region outline is unverified",
        "nasa_sources": [ARTEMIS_RELEASE, ARTEMIS_LPSC],
    })

    omitted = [
        {"name": "Luna 9", "reason": "not in the LROC table (LROC has not located the lander in NAC images); no measured "
                                     "coordinate from a primary source, so no point is guessed"},
    ]
    for reg in ARTEMIS_REGIONS:
        if reg == "Mons Mouton":
            continue
        if reg == "Malapert Massif":
            omitted.append({"name": f"Artemis III region '{reg}'", "reason": "no separate record: NASA published no coordinates; "
                            "the project site malapert_massif_summit (IAU Mons Malapert) lies on the same massif and serves as "
                            "its representative; match by name only, unverified"})
            continue
        if reg == "Mons Mouton Plateau":
            omitted.append({"name": f"Artemis III region '{reg}'", "reason": "NASA published no coordinates; the plateau is on "
                            "Mons Mouton (see artemis3_region_mons_mouton_representative; IM-2 Athena landed on Mons Mouton), "
                            "but no source places a point on NASA's plateau region"})
            continue
        omitted.append({"name": f"Artemis III region '{reg}'", "reason": "NASA published no coordinates (release 2024-10-28, "
                        "LPSC 2026 abstract); the region is named after a crater or an unofficial name whose IAU centre is not "
                        "inside the region (a rim, a peak or a plain), so a representative point would be a guess"})
    omitted.append({"name": "Planned CLPS south-polar targets", "reason": "no published landing coordinates were found from a "
                    "primary source during this work; the flown south-polar CLPS landers (IM-1, IM-2) are listed as past landings"})
    return {
        "schema": "lunar-site-navigator site records v0 (curated list)",
        "generated_utc": mf.utc_now(),
        "sites": sites,
        "omitted": omitted,
        "counts": {c: sum(1 for s in sites if s["kind"] == c) for c in sorted({s["kind"] for s in sites})},
        "display_fields": "category ('past landing', 'candidate', 'project site') and programme are descriptive, for site pickers",
    }


def main() -> None:
    doc = build()
    out = repo_data_dir() / "sites" / "curated_sites.json"
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(doc["counts"]), len(doc["sites"]), "sites,", len(doc["omitted"]), "omitted")


if __name__ == "__main__":
    main()
