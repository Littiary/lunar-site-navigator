"""What the download script fetches, and where from.

Primary source: the PDS Geosciences Node archive of the LRO LOLA RDR bundle.
Second source (same bytes, used for speed and for the cross-check): the LOLA
gridded-data mirror at MIT. Sizes, versions and projection parameters are NOT
stored here; they are read from the live archive and from the labels, and end
up in the manifest.
"""

from __future__ import annotations

from dataclasses import dataclass, field

PDS_ROOT = "https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx"
MIT_ROOT = "https://imbrium.mit.edu/DATA/LOLA_GDR"

# Archive-level identifiers read from the live bundle label (bundle_lola_rdr.xml).
PDS_BUNDLE_LID = "urn:nasa:pds:lro_lola_rdr"
PDS_DATASET_ID = "LRO-L-LOLA-4-GDR-V1.0"


@dataclass(frozen=True)
class FileSpec:
    role: str            # "data", "label", "label_xml", "doc"
    local_name: str      # file name under the product folder
    pds_path: str        # path under PDS_ROOT
    mit_path: str | None  # path under MIT_ROOT, if the mirror has the file


@dataclass(frozen=True)
class Product:
    product_id: str
    description: str
    files: tuple[FileSpec, ...] = field(default_factory=tuple)
    base: str = "raw/lola"  # folder under the data root that holds <product_id>/


def _polar_dem(product_id: str, desc: str) -> Product:
    low = product_id.lower()
    base = "data/lola_gdr/polar/img"
    return Product(
        product_id,
        desc,
        (
            FileSpec("data", f"{low}.img", f"{base}/{low}.img", f"POLAR/IMG/{product_id}.IMG"),
            FileSpec("label", f"{low}.lbl", f"{base}/{low}.lbl", f"POLAR/IMG/{product_id}.LBL"),
            FileSpec("label_xml", f"{low}.xml", f"{base}/{low}.xml", None),
        ),
    )


def _cyl_dem(product_id: str, desc: str) -> Product:
    low = product_id.lower()
    base = "data/lola_gdr/cylindrical/img"
    return Product(
        product_id,
        desc,
        (
            FileSpec("data", f"{low}.img", f"{base}/{low}.img", f"CYLINDRICAL/IMG/{product_id}.IMG"),
            FileSpec("label", f"{low}.lbl", f"{base}/{low}.lbl", f"CYLINDRICAL/IMG/{product_id}.LBL"),
            FileSpec("label_xml", f"{low}.xml", f"{base}/{low}.xml", None),
        ),
    )


DOCS = Product(
    "_docs",
    "Archive-level documents of the LOLA RDR bundle (bundle label, volume description, errata, "
    "projection catalog, interface specification)",
    tuple(
        FileSpec("doc", name, path, None)
        for name, path in (
            ("bundle_lola_rdr.xml", "bundle_lola_rdr.xml"),
            ("voldesc.cat", "voldesc.cat"),
            ("aareadme.txt", "aareadme.txt"),
            ("errata.txt", "errata.txt"),
            ("dsmap_polar.cat", "catalog/dsmap_polar.cat"),
            ("gdr_ds.cat", "catalog/gdr_ds.cat"),
            ("archsis.pdf", "document/archsis.pdf"),
        )
    ),
)

ROBBINS_URL = (
    "https://astrogeology.usgs.gov/ckan/dataset/f89f5478-b69a-486c-b9b5-30d7b0c5ad2b/resource/"
    "c4f25cc2-4f8a-4207-a845-5e176da3ac5a/download/lunar_crater_database_robbins_2018"
)

ROBBINS = Product(
    "ROBBINS_2018",
    "Robbins lunar crater database (USGS Astrogeology, 2018-08-15): hand-measured crater centres and diameters; "
    "used only as an independent position reference for the georeferencing check",
    (FileSpec("reference", "lunar_crater_database_robbins_2018.zip", ROBBINS_URL, None),),
    base="raw/catalogs",
)

MIT_RDR_ROOT = "https://imbrium.mit.edu/DATA/LOLA_RDR"


def _rdr(phase: str, name: str) -> Product:
    """One LOLA RDR file (individual laser returns of about one orbit), used as an independent reference."""
    low = name.lower()
    return Product(
        name,
        f"LOLA RDR {phase}: geolocated laser returns of one orbit (independent check of the gridded products)",
        (
            FileSpec("data", f"{low}.dat", f"data/lola_rdr/{phase.lower()}/{low}.dat", f"{MIT_RDR_ROOT}/{phase}/{name}.DAT"),
            FileSpec("label", f"{low}.lbl", f"data/lola_rdr/{phase.lower()}/{low}.lbl", f"{MIT_RDR_ROOT}/{phase}/{name}.LBL"),
        ),
        base="raw/lola_rdr",
    )


# 13 orbits spread over mission phase LRO_SM_06 (every 26th file of the phase), so that all longitudes are crossed.
RDR_SAMPLE = tuple(
    f"LOLARDR_{t}"
    for t in (
        "110320314", "110340414", "110360514", "110380613", "110400713", "110420812", "110440912",
        "110461013", "110481113", "110501213", "110521312", "110561318", "110581419",
    )
)

# 14 orbits spread over mission phase LRO_ES_100 (Jan-Feb 2021, every 27th file). The 20 m and 60 m polar products
# use data through LRO_ES_54 (Feb 2017), so these returns are NOT in them: an independent sample of the DEM error.
RDR_INDEPENDENT = tuple(
    f"LOLARDR_{t}"
    for t in (
        "210261356", "210281841", "210302326", "210330411", "210350855", "210371339", "210391823",
        "210412308", "210440353", "210460837", "210481322", "210501806", "210522250", "210550335",
    )
)

# 14 orbits of mission phase LRO_NO_08 (Apr-May 2010, near-circular 50 km orbit, GRGM900C orbits as stated in each
# label): the LRO_SM_06 files have no valid returns north of 80.5 N (high altitude over the north pole in 2011).
RDR_NORTH = tuple(
    f"LOLARDR_{t}"
    for t in (
        "100951948", "100972243", "101000137", "101020431", "101040726", "101061019", "101081314",
        "101101608", "101121901", "101142154", "101170047", "101190339", "101210632", "101230925",
    )
)

RDR_FORMAT = Product(
    "_rdr_docs",
    "LOLA RDR record structure (LOLARDR.FMT)",
    (FileSpec("doc", "lolardr.fmt", "label/lolardr.fmt", None),),
    base="raw/lola_rdr",
)

PRODUCTS: dict[str, Product] = {
    p.product_id: p
    for p in (
        _polar_dem(
            "LDEM_80S_20M",
            "LOLA south-polar DEM, 80S to pole, 20 m/pixel, polar stereographic (primary terrain)",
        ),
        _polar_dem(
            "LDEM_60S_60M",
            "LOLA south-polar DEM, 60S to pole, 60 m/pixel, polar stereographic (far terrain)",
        ),
        _cyl_dem(
            "LDEM_16",
            "LOLA global DEM, 16 pixel/degree, simple cylindrical (independent check of the polar products)",
        ),
        _polar_dem(
            "LDEM_80N_20M",
            "LOLA north-polar DEM, 80N to pole, 20 m/pixel, polar stereographic (whole-Moon coverage)",
        ),
        _polar_dem(
            "LDEM_60N_60M",
            "LOLA north-polar DEM, 60N to pole, 60 m/pixel, polar stereographic (whole-Moon coverage)",
        ),
        _cyl_dem(
            "LDEM_128",
            "LOLA global DEM, 128 pixel/degree, simple cylindrical (global fallback and independent check)",
        ),
        DOCS,
        ROBBINS,
        RDR_FORMAT,
        *(_rdr("LRO_SM_06", n) for n in RDR_SAMPLE),
        *(_rdr("LRO_ES_100", n) for n in RDR_INDEPENDENT),
        *(_rdr("LRO_NO_08", n) for n in RDR_NORTH),
    )
}

# What a plain `fetch` downloads (the order is the order of work).
DEFAULT_SET = ("_docs", "LDEM_80S_20M", "LDEM_60S_60M", "LDEM_16")


MIT_SLDEM_ROOT = "https://imbrium.mit.edu/DATA/SLDEM2015/TILES/FLOAT_IMG"


def _sldem_tile(name: str) -> Product:
    low = name.lower()
    base = "data/sldem2015/tiles/float_img"
    return Product(
        name,
        "SLDEM2015 tile: LOLA altimetry co-registered with SELENE (Kaguya) Terrain Camera stereo, 60S-60N, simple cylindrical, float km",
        (
            FileSpec("data", f"{low}.img", f"{base}/{low}.img", f"{MIT_SLDEM_ROOT}/{name}.IMG"),
            FileSpec("label", f"{low}.lbl", f"{base}/{low}.lbl", f"{MIT_SLDEM_ROOT}/{name}.LBL"),
            FileSpec("label_xml", f"{low}.xml", f"{base}/{low}.xml", None),
        ),
    )


SLDEM_256_TILES = tuple(
    f"SLDEM2015_256_{lat}_{lon}_FLOAT" for lat in ("60S_0S", "0N_60N") for lon in ("000_120", "120_240", "240_360")
)
SLDEM_512_TILES = tuple(
    f"SLDEM2015_512_{lat}_{lon:03d}_{lon + 45:03d}_FLOAT"
    for lat in ("60S_30S", "30S_00S", "00N_30N", "30N_60N")
    for lon in range(0, 360, 45)
)
for _t in SLDEM_256_TILES + SLDEM_512_TILES:
    PRODUCTS[_t] = _sldem_tile(_t)

# Cylindrical mosaics of the whole-Moon terrain, as (mosaic id, tile product ids); used when all tiles are present.
MOON_CYLINDRICAL: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("SLDEM2015_512", SLDEM_512_TILES),
    ("SLDEM2015_256", SLDEM_256_TILES),
    ("LDEM_128", ("LDEM_128",)),
)


# 5 m/pixel LOLA site DEMs of Barker, Mazarico, Neumann (2021), PGDA product 78 (single source, no mirror).
PGDA_5MPP_ROOT = "https://pgda.gsfc.nasa.gov/data/LOLA_5mpp"
SITE_DEM_SITES = {"Site04": "Shackleton rim", "Site11": "de Gerlache rim", "Site23": "Malapert massif"}


def _site_dem(site: str) -> Product:
    files = [
        FileSpec("data", f"{site}_final_adj_5mpp_surf.tif", f"{PGDA_5MPP_ROOT}/{site}/{site}_final_adj_5mpp_surf.tif", None),
        FileSpec("count", f"{site}_final_adj_5mpp_ldec.tif", f"{PGDA_5MPP_ROOT}/{site}/{site}_final_adj_5mpp_ldec.tif", None),
        FileSpec("uncertainty", f"{site}_final_adj_5mpp_toterr.tif", f"{PGDA_5MPP_ROOT}/{site}/{site}_final_adj_5mpp_toterr.tif", None),
    ]
    return Product(
        f"LOLA5MPP_{site.upper()}",
        f"LOLA 5 m/pixel site DEM {site} ({SITE_DEM_SITES[site]}), Barker et al. 2021, polar stereographic GeoTIFF",
        tuple(files),
        base="raw/lola_5mpp",
    )


PGDA_DOCS = Product("_pgda_docs", "README of the PGDA 5 m/pixel site DEMs",
                    (FileSpec("doc", "README", f"{PGDA_5MPP_ROOT}/README", None),), base="raw/lola_5mpp")
PRODUCTS[PGDA_DOCS.product_id] = PGDA_DOCS
for _s in SITE_DEM_SITES:
    PRODUCTS[f"LOLA5MPP_{_s.upper()}"] = _site_dem(_s)
SITE_DEM_PRODUCTS = tuple(f"LOLA5MPP_{_s.upper()}" for _s in SITE_DEM_SITES)
