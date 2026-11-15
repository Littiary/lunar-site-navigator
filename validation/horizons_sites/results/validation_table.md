# Validation table: Sun and Earth directions at the three site records versus JPL Horizons

Generated 2026-11-15T06:20:51Z by `validation/horizons_sites/compare.py` from the stored raw responses. Do not edit by hand.

**12 of 12 queries inside the thresholds, 3840 rows.** Largest direction difference: 0.0039 arcsec with the observer at the site, 0.0972 arcsec through the direction table that the packages use.

- Thresholds: those of `validation/horizons/thresholds.json` (direction 1.0 arcsec, angular diameter 0.1 arcsec, range 1.0 km, TDB - UT 0.002 s), fixed before any Horizons response was fetched.
- Core: frame `MOON_ME_DE440_ME421`, correction `LT+S`, sphere 1737.4 km, kernel set `bfe870fccfa5`.
- An additional check: not a row of the validation card. Both sides use JPL ephemerides of the same family and neither has terrain.

| Query | Rows | Direction, observer at the site (arcsec) | Direction, through the table (arcsec) | Angular diameter (arcsec) | Range (km) | TDB - UT (s) | Result |
|---|---|---|---|---|---|---|---|
| `shackleton_rim_crest__sun__weekend` | 289 | 0.0025 | 0.0025 | 0.0005 | 0.0021 | 0.000022 | **PASS** |
| `shackleton_rim_crest__earth__weekend` | 289 | 0.0039 | 0.0866 | 0.0006 | 0.0036 | 0.000022 | **PASS** |
| `de_gerlache_rim_crest__sun__weekend` | 289 | 0.0024 | 0.0025 | 0.0005 | 0.0021 | 0.000022 | **PASS** |
| `de_gerlache_rim_crest__earth__weekend` | 289 | 0.0036 | 0.0870 | 0.0006 | 0.0036 | 0.000022 | **PASS** |
| `malapert_massif_summit__sun__weekend` | 289 | 0.0025 | 0.0025 | 0.0005 | 0.0021 | 0.000022 | **PASS** |
| `malapert_massif_summit__earth__weekend` | 289 | 0.0037 | 0.0871 | 0.0005 | 0.0036 | 0.000022 | **PASS** |
| `shackleton_rim_crest__sun__year` | 351 | 0.0024 | 0.0024 | 0.0005 | 0.0025 | 0.000022 | **PASS** |
| `shackleton_rim_crest__earth__year` | 351 | 0.0038 | 0.0971 | 0.0006 | 0.0041 | 0.000022 | **PASS** |
| `de_gerlache_rim_crest__sun__year` | 351 | 0.0025 | 0.0026 | 0.0005 | 0.0025 | 0.000022 | **PASS** |
| `de_gerlache_rim_crest__earth__year` | 351 | 0.0038 | 0.0972 | 0.0006 | 0.0041 | 0.000022 | **PASS** |
| `malapert_massif_summit__sun__year` | 351 | 0.0025 | 0.0026 | 0.0005 | 0.0025 | 0.000022 | **PASS** |
| `malapert_massif_summit__earth__year` | 351 | 0.0039 | 0.0971 | 0.0006 | 0.0041 | 0.000022 | **PASS** |
