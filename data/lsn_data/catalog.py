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
    (FileSpec("data", "lunar_crater_database_robbins_2018.zip", ROBBINS_URL, None),),
    base="raw/catalogs",
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
        DOCS,
        ROBBINS,
    )
}

# What a plain `fetch` downloads (the order is the order of work).
DEFAULT_SET = ("_docs", "LDEM_80S_20M", "LDEM_60S_60M", "LDEM_16")
