# Validation card: ephemeris, time and event finding

Generated 2026-11-14T11:01:49Z by `validation/card/build.py`; every measured value is recomputed from the stored reference data and the code. Do not edit by hand.

**14 of 14 checks pass.** Core: SPICE, frame `MOON_ME_DE440_ME421`, correction `LT+S`, sphere 1737.4 km, kernel set `bfe870fccfa5`.

| What was compared | Against | Cases | Threshold | Measured | Result |
|---|---|---|---|---|---|
| Direction of the Sun and the Earth from a lunar surface point (observer at the site) | JPL Horizons observer tables, DE441 (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 28 queries, 95676 rows: 7 lunar surface points (3 south-polar), Sun and Earth, 14-16 Nov 2026 at 10 min and 2026-11-01 to 2045-07-01 at 25 h | < 1 arcsec | 0.0049 arcsec | **PASS** |
| Same direction through the site-independent direction table that viewers read | JPL Horizons observer tables, DE441 (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 28 queries, 95676 rows: 7 lunar surface points (3 south-polar), Sun and Earth, 14-16 Nov 2026 at 10 min and 2026-11-01 to 2045-07-01 at 25 h | < 1 arcsec | 0.0988 arcsec | **PASS** |
| Apparent angular diameter of the Sun and the Earth | JPL Horizons observer tables, DE441 (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 28 queries, 95676 rows: 7 lunar surface points (3 south-polar), Sun and Earth, 14-16 Nov 2026 at 10 min and 2026-11-01 to 2045-07-01 at 25 h | < 0.1 arcsec | 0.00057 arcsec | **PASS** |
| Distance from the site to the Sun and to the Earth | JPL Horizons observer tables, DE441 (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 28 queries, 95676 rows: 7 lunar surface points (3 south-polar), Sun and Earth, 14-16 Nov 2026 at 10 min and 2026-11-01 to 2045-07-01 at 25 h | < 1 km | 0.0042 km | **PASS** |
| Time scales: TDB minus UTC | JPL Horizons observer tables, DE441 (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 28 queries, 95676 rows: 7 lunar surface points (3 south-polar), Sun and Earth, 14-16 Nov 2026 at 10 min and 2026-11-01 to 2045-07-01 at 25 h | < 0.002 s | 3.8e-05 s | **PASS** |
| Sunrise and sunset times on a smooth sphere (upper limb, with the dip of the horizon) | JPL Horizons rise/transit/set search, 1-minute step (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 16 sunrise and sunset events: 4 lunar surface points (one 1 km above the sphere), 2026-11-01 to 2026-12-31 | < 120 s | 56.5 s | **PASS** |
| Sunrise and sunset events without a counterpart on the other side | JPL Horizons rise/transit/set search, 1-minute step (https://ssd.jpl.nasa.gov/horizons/), retrieved 2026-11-14 | 16 sunrise and sunset events: 4 lunar surface points (one 1 km above the sphere), 2026-11-01 to 2026-12-31 | ≤ 0 events | 0 events | **PASS** |
| East-North-Up projection of the core against the SPICE routine azlcpo (same kernels, separate code) | NAIF SPICE Toolkit N0067, routine azlcpo | 3668 rows: 7 points, Sun and Earth, 60 days | < 1e-06 deg | 1e-13 deg | **PASS** |
| Direction table (observer at the Moon's centre, site vector subtracted) against the observer at the site | the core's own exact path (SPICE spkcpo) | 3668 rows: 7 points, Sun and Earth, 60 days | < 0.2 arcsec | 0.0964 arcsec | **PASS** |
| Hourly direction table, 4-point interpolation, against direct SPICE at random times | direct SPICE evaluation | 20000 vectors over 90 days | < 0.01 arcsec | 1.4e-05 arcsec | **PASS** |
| Visible fraction of a disc cut by a straight horizon | area of a circular segment (closed form) | 481 disc positions from fully hidden to fully visible | < 0.002 fraction of the disc | 5.7e-05 fraction of the disc | **PASS** |
| Rise and set times in cases with a known answer (linear motion, diurnal arc, terrain ramp, short occultation) | closed-form event times | 14 events in 4 cases | < 1 s | 0.234 s | **PASS** |
| Sun events on a smooth sphere from the interpolated table against the zero crossing of the exact SPICE elevation | direct SPICE evaluation at the site | 11 events, three thresholds, 45 days | < 1 s | 0.234 s | **PASS** |
| Events found by a 5 s scan but not by the default 60 s scan, other than pairs of opposite crossings closer than 60 s (the stated limit) | the same finder with a 5 s scan step | 171 events on an invented rough polar horizon, 30 days; 1 pair(s) closer than 60 s were not reported by the default scan | ≤ 0 events | 0 events | **PASS** |

## Where each threshold was fixed

- validation/horizons/thresholds.json (commit f25145f): committed on its own before the reference data was fetched or compared.
- validation/horizons_rts/thresholds.json (commit 48afcd5): committed on its own before the reference data was fetched or compared.
- core/tests/ephem/test_directions.py (commit aa86a5a): written in the acceptance test before the implementation was run; committed together with it.
- core/tests/events/test_events.py (commit 5a14bcb): written in the acceptance test before the implementation was run; committed together with it.
- core/lsncore/events/finder.py (commit 5a14bcb); test added in commit d93504e: stated limit of the finder (two crossings closer than the scan step can be missed), written in the module before the test.

## Not validated

- **Event times and visibility shares on real terrain** (unverified). No independent illumination product or mission record has been compared yet. The terrain horizon has passed analytic tests of the core stream only (docs/method/horizon.md).
- **Published event times of real landers** (not done yet). Planned as the next validation step.
- **Earth rise and set against an independent source** (not done). Horizons does not state which point of the Earth's disc its rise and set refer to; only the Earth's direction and size are validated.
- **Eclipses of the Sun by the Earth** (not modelled). The visible fraction of the Sun does not include occultation by the Earth.

## Limits

- Every check on this card is terrain-free. Near the lunar poles the terrain horizon, not the ephemeris, sets the accuracy of an event time: a horizon error of 0.01 deg can move an event by many minutes.
- The external reference (Horizons) and the core use JPL ephemerides of the same family; an error common to both would not show.
- Thresholds marked as written in the acceptance test were committed in the same commit as the code they test; only the Horizons thresholds have a commit of their own that predates the data.

Reference: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/, data retrieved 2026-Nov-14.
