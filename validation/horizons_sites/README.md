# JPL Horizons reference data for the three south-polar site records

Raw JPL Horizons observer tables for the Sun and the Earth seen from the three site records of the data stream (`data/sites/sites.json`, data branch commit `f48b9c4`): Shackleton rim crest, de Gerlache rim crest and Mons Malapert summit. They are reference data for comparing the core's Sun and Earth directions at the real sites. This folder holds the data only; the comparison logic and its thresholds belong to the ephemeris stream (`validation/horizons/compare.py`, `validation/horizons/thresholds.json`).

## Cases

3 sites × 2 bodies × 2 time spans = 12 queries, defined in `cases.json`.

| Span | Start (UTC) | Stop (UTC) | Step | Rows per query |
|---|---|---|---|---|
| `weekend` | 2026-11-14 00:00 | 2026-11-16 00:00 | 10 min | 289 |
| `year` | 2026-11-14 00:00 | 2027-11-14 00:00 | 25 h | 351 |

The `year` span is the twelve-month window of `validation/sites/scenario.json`. The 25-hour step lets the hour of day drift.

Query parameters are identical to `validation/horizons/cases.json`: observer table, `CENTER=coord@301`, `COORD_TYPE=GEODETIC`, quantities 4, 13, 20, 30 (apparent azimuth and elevation, angular diameter, distance and range rate, TDB − UT), degrees, airless apparent positions.

Site coordinates are copied from the site records without change: east longitude, planetocentric latitude, and height above the 1737.4 km sphere (`ground_height_m_above_1737.4km_sphere` / 1000). No observer height above the ground is added, so a comparison with the core at a 2 m observer height has to account for the 2 m difference. Each response header confirms how Horizons read the site: the 1737.4 km sphere (`Center radii`), the `MEAN_ME` frame with east longitude positive, and the coordinates as given. The responses state ephemeris DE441.

## Retrieval

* Fetched on 2026-11-14 between 11:23:16Z and 11:23:52Z UTC, one request at a time with a 1.5 s pause.
* Fetch tool: `validation/horizons/fetch.py` of the ephemeris branch (commit `a8bbc5a`), unchanged, run as `python -I fetch.py --dir validation/horizons_sites`.
* Every query returned HTTP 200 with an ephemeris block. Horizons API version 1.2.

## Files

| File | Role |
|---|---|
| `cases.json` | Sites, time spans and query parameters |
| `raw/<site>__<body>__<span>.json` | Response body exactly as received. Never edited. |
| `raw/<site>__<body>__<span>.meta.json` | Full URL, parameters, retrieval time (UTC), HTTP status, byte count, SHA-256, API signature, user agent |
| `.gitattributes` | Keeps `raw/` byte for byte (no line-ending conversion) |

To check that a raw file is unchanged, compare its SHA-256 with the value in its `.meta.json`.

## Limits

* Horizons has no terrain. Elevations are relative to the horizontal plane of the 1737.4 km sphere at the site, not to the terrain horizon.
* The sites are project candidate points derived from LOLA and IAU outlines, not official landing sites.

Reference: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/, data retrieved 2026-Nov-14.
