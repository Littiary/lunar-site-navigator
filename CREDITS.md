# Credits

Every third-party item used in this project gets one row here before it is merged.

## Data

| Name | Provider | Version or product ID | Licence or terms | Source URL | Retrieved (UTC) |
|---|---|---|---|---|---|
| LOLA gridded elevation LDEM_80S_20M (20 m/pixel, 80S to pole) | NASA LRO LOLA team (D. E. Smith, G. A. Neumann, NASA GSFC), PDS Geosciences Node; fetched from the MIT LOLA mirror and cross-checked against PDS | Product V2.0, data set LRO-L-LOLA-4-GDR-V1.0, bundle urn:nasa:pds:lro_lola_rdr 1.0, DOI 10.17189/tnyt-7007 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ldem_80s_20m.img | 2026-11-14 (exact time and SHA-256 in data/manifest/manifest.json) |
| LOLA gridded elevation LDEM_60S_60M (60 m/pixel, 60S to pole) | same as above | Product V2.0, data set LRO-L-LOLA-4-GDR-V1.0 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/polar/img/ldem_60s_60m.img | 2026-11-14 (manifest) |
| LOLA gridded elevation LDEM_16 (16 pixel/degree, global; used only as an independent check) | same as above | Product V3.1, data set LRO-L-LOLA-4-GDR-V1.0 | Public domain: "Data sets archived in the PDS are in the public domain" (PDS Geosciences Node FAQ, https://pds-geosciences.wustl.edu/faq.html); cite as published research | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_16.img | 2026-11-14 (manifest) |
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
