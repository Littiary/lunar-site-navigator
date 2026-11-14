# Credits

Every third-party item used in this project gets one row here before it is merged.

## Data

| Name | Provider | Version or product ID | Licence or terms | Source URL | Retrieved (UTC) |
|---|---|---|---|---|---|
| Lunar crater database v1 (Robbins), 1,296,796 craters; used only as an analysis reference for the georeferencing check, not redistributed | Stuart J. Robbins (SwRI), published by USGS Astrogeology Science Center | v1, publication date 2018-08-15, PDS4 bundle; cite Robbins (2019), J. Geophys. Res. Planets 124, 871-892, doi:10.1029/2018JE005592 | **Unverified: no licence or terms of use exist in any authoritative place we could find.** Checked 2026-11-14: (1) the publisher's record page https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins (retrieved 12:28Z) states no licence; (2) its FGDC metadata https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins.xml (retrieved 12:28:35Z) has empty `accconst` and `useconst` (access and use constraints) elements; (3) the PDS4 bundle labels and README contain citation information only, no licence; (4) the paper's acknowledgments (https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2018JE005592, read 12:31Z) say only "The database itself is available through the NASA PDS"; the record page gives its PDS status as "In Review" and it is hosted in the PDS Imaging Annex, whose USGS page (https://www.usgs.gov/centers/astrogeo-sc/science/pds-img-annex) states no terms either. So the PDS public-domain statement cannot be assumed to cover it. Freely downloadable; not committed to git. | https://astrogeology.usgs.gov/search/map/moon_crater_database_v1_robbins | 2026-11-14 (manifest) |
| LOLA gridded elevation LDEM_80S_20M (20 m/pixel, 80S to pole) | NASA LRO LOLA team (D. E. Smith, G. A. Neumann, NASA GSFC), PDS Geosciences Node; fetched from the MIT LOLA mirror and cross-checked against PDS | Product V2.0, data set LRO-L-LOLA-4-GDR-V1.0, bundle urn:nasa:pds:lro_lola_rdr 1.0, DOI 10.17189/tnyt-7007 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ldem_80s_20m.img | 2026-11-14 (exact time and SHA-256 in data/manifest/manifest.json) |
| LOLA gridded elevation LDEM_60S_60M (60 m/pixel, 60S to pole) | same as above | Product V2.0, data set LRO-L-LOLA-4-GDR-V1.0 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ldem_60s_60m.img | 2026-11-14 (manifest) |
| LOLA gridded elevation LDEM_16 (16 pixel/degree, global; used only as an independent check) | same as above | Product V3.1, data set LRO-L-LOLA-4-GDR-V1.0 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_16.img | 2026-11-14 (manifest) |
| LOLA gridded elevation LDEM_80N_20M and LDEM_60N_60M (north-polar mirror of the south products; whole-Moon coverage) | same as above | data set LRO-L-LOLA-4-GDR-V1.0; product version per file in data/manifest/manifest.json | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ | 2026-11-14 (manifest) |
| LOLA gridded elevation LDEM_128 (128 pixel/degree, global; global fallback and independent check) | same as above | data set LRO-L-LOLA-4-GDR-V1.0; product version in data/manifest/manifest.json | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_128.img | 2026-11-14 (manifest) |
| LOLA RDR laser returns, 13 files of mission phase LRO_SM_06 and the record structure LOLARDR.FMT (independent check of the gridded products) | same as above | data set LRO-L-LOLA-3-RDR-V1.0, product version V1.04 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_rdr/lro_sm_06/ | 2026-11-14 (manifest) |
| LOLA RDR bundle documents (bundle label, volume description, errata, projection catalog, interface specification) | NASA PDS Geosciences Node | urn:nasa:pds:lro_lola_rdr 1.0 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/ | 2026-11-14 (manifest) |
| Gazetteer of Planetary Nomenclature: crater and massif names, centres and outlines (Shackleton, Shoemaker, Faustini, Cabeus, de Gerlache, Haworth, Mons Malapert) | IAU Working Group for Planetary System Nomenclature, hosted by USGS Astrogeology | Feature pages 5450, 5494, 1919, 953, 1439, 14502, 16338 | Public domain ("Everything in the Gazetteer of Planetary Nomenclature is in the public domain", https://planetarynames.wr.usgs.gov/Page/FAQ); cite the IAU WGPSN Gazetteer | https://planetarynames.wr.usgs.gov/ | 2026-11-14 (per feature in data/checkpoints/features.json and data/sites/gazetteer_records.json) |
| Shackleton crater parameters (centre of rim, floor radius 1734.63 km, mean rim height 1.3 km, depth 4.1 km) used as published reference values | M. T. Zuber et al., Nature 486, 378-381 (2012), Table 1, NASA NTRS 20120013758 | Paper, 2012 | Published research results, quoted as numbers with citation (no text or figures reproduced) | https://ntrs.nasa.gov/citations/20120013758 | 2026-11-14 |

## Software libraries

| Name | Version | Licence | Source URL | Used in |
|---|---|---|---|---|
| NumPy | 2.5.4 | BSD-3-Clause (the wheel also bundles 0BSD, MIT, Zlib and CC0-1.0 parts) | https://numpy.org | data/ (reader, pyramids) |
| pytest | 9.2.0 | MIT | https://docs.pytest.org | data/tests |

## Images, fonts and other assets

| Name | Author or provider | Licence | Source URL | Used in |
|---|---|---|---|---|

## Use of AI tools

| Team member | Tool and model | Used for |
|---|---|---|
