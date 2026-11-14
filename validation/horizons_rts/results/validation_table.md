# Validation table: event finder versus JPL Horizons rise and set times

Generated 2026-11-14T10:40:19Z by `validation/horizons_rts/compare.py` from the stored raw responses. Do not edit by hand.

- Event: Sun, upper limb on the true visual horizon of the 1737.4 km sphere (dip included for a site above the sphere), no refraction.
- Reference: NASA/JPL Horizons, rise/transit/set search, 1-minute step, TVH mode; a row is the first search step at which the condition holds, so it lies 0 to 60 s after the true instant; stated accuracy: twice the search step.
- Core: scan step 60 s, bisection to 0.5 s, frame `MOON_ME_DE440_ME421`, kernel set `bfe870fccfa5`.
- Threshold (fixed before the data was fetched): |difference| < 120 s, unmatched events ≤ 0.

| Site (E lon°, lat°, h km) | Event | Horizons row (UTC) | Core (UTC) | Horizons − core (s) |
|---|---|---|---|---|
| eq_near (0.0, 0.0, 0.0) | set | 2026-11-02T06:22:00 | 2026-11-02T06:21:44.297 | +15.7 |
| eq_near (0.0, 0.0, 0.0) | rise | 2026-11-16T23:38:00 | 2026-11-16T23:37:18.984 | +41.0 |
| eq_near (0.0, 0.0, 0.0) | set | 2026-12-01T20:24:00 | 2026-12-01T20:23:31.640 | +28.4 |
| eq_near (0.0, 0.0, 0.0) | rise | 2026-12-16T13:58:00 | 2026-12-16T13:57:32.577 | +27.4 |
| low_lat_east (23.47, 0.67, 0.0) | rise | 2026-11-15T01:24:00 | 2026-11-15T01:23:57.890 | +2.1 |
| low_lat_east (23.47, 0.67, 0.0) | set | 2026-11-29T22:02:00 | 2026-11-29T22:01:38.671 | +21.3 |
| low_lat_east (23.47, 0.67, 0.0) | rise | 2026-12-14T15:42:00 | 2026-12-14T15:41:51.327 | +8.7 |
| low_lat_east (23.47, 0.67, 0.0) | set | 2026-12-29T12:35:00 | 2026-12-29T12:34:32.108 | +27.9 |
| far_mid_north_1km (-150.0, 45.0, 1.0) | set | 2026-11-14T16:08:00 | 2026-11-14T16:07:38.672 | +21.3 |
| far_mid_north_1km (-150.0, 45.0, 1.0) | rise | 2026-11-29T05:23:00 | 2026-11-29T05:22:35.859 | +24.1 |
| far_mid_north_1km (-150.0, 45.0, 1.0) | set | 2026-12-14T06:47:00 | 2026-12-14T06:46:27.421 | +32.6 |
| far_mid_north_1km (-150.0, 45.0, 1.0) | rise | 2026-12-28T19:06:00 | 2026-12-28T19:05:57.421 | +2.6 |
| south_85 (45.0, -85.0, 0.0) | rise | 2026-11-11T13:32:00 | 2026-11-11T13:31:26.953 | +33.0 |
| south_85 (45.0, -85.0, 0.0) | set | 2026-11-29T19:21:00 | 2026-11-29T19:20:26.484 | +33.5 |
| south_85 (45.0, -85.0, 0.0) | rise | 2026-12-11T06:58:00 | 2026-12-11T06:57:28.827 | +31.2 |
| south_85 (45.0, -85.0, 0.0) | set | 2026-12-29T00:13:00 | 2026-12-29T00:12:03.514 | +56.5 |

- eq_near__sun__rts_60d: 4 events, largest |difference| 41.0 s, unmatched 0: **PASS**
- low_lat_east__sun__rts_60d: 4 events, largest |difference| 27.9 s, unmatched 0: **PASS**
- far_mid_north_1km__sun__rts_60d: 4 events, largest |difference| 32.6 s, unmatched 0: **PASS**
- south_85__sun__rts_60d: 4 events, largest |difference| 56.5 s, unmatched 0: **PASS**
