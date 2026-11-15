# Validation table: science core versus JPL Horizons

Generated 2026-11-15T06:20:50Z by `validation/horizons/compare.py` from the stored raw responses. Do not edit by hand.

- Core: SPICE (CSPICE_N0067), frame `MOON_ME_DE440_ME421`, correction `LT+S`, sphere 1737.4 km, kernel set `bfe870fccfa5` (naif0012.tls, pck00011.tpc, de440s.bsp, moon_pa_de440_200625.bpc, moon_de440_250416.tf).
- Reference: NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/; API version 1.2; printed resolution: azimuth and elevation 0.000001 deg (0.0036 arcsec); angular diameter 0.001 arcsec.
- Thresholds (fixed before the comparison, `thresholds.json`): direction < 1.0″, angular diameter < 0.1″, range < 1.0 km, TDB−UT < 0.002 s.
- Cases: 28 compared, 28 pass, 95676 rows in total.

| Site (E lon°, lat°, h km) | Body | Span | Rows | Direction max ″ (exact) | Direction RMS ″ | Direction max ″ (table) | Ang. diam. max ″ | Range max km | TDB−UT max s | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| eq_near (0.0, 0.0, 0.0) | Sun | weekend | 289 | 0.002 | 0.001 | 0.004 | 0.0005 | 0.0021 | 0.000022 | PASS |
| eq_near (0.0, 0.0, 0.0) | Earth | weekend | 289 | 0.003 | 0.002 | 0.016 | 0.0005 | 0.0036 | 0.000022 | PASS |
| low_lat_east (23.47, 0.67, 0.0) | Sun | weekend | 289 | 0.002 | 0.001 | 0.003 | 0.0005 | 0.0021 | 0.000022 | PASS |
| low_lat_east (23.47, 0.67, 0.0) | Earth | weekend | 289 | 0.003 | 0.002 | 0.048 | 0.0005 | 0.0036 | 0.000022 | PASS |
| far_mid_north (-150.0, 45.0, 1.0) | Sun | weekend | 289 | 0.003 | 0.001 | 0.003 | 0.0005 | 0.0021 | 0.000022 | PASS |
| far_mid_north (-150.0, 45.0, 1.0) | Earth | weekend | 289 | 0.004 | 0.002 | 0.073 | 0.0005 | 0.0036 | 0.000022 | PASS |
| north_polar (30.0, 88.0, 0.0) | Sun | weekend | 289 | 0.002 | 0.001 | 0.002 | 0.0005 | 0.0021 | 0.000022 | PASS |
| north_polar (30.0, 88.0, 0.0) | Earth | weekend | 289 | 0.004 | 0.002 | 0.087 | 0.0005 | 0.0036 | 0.000022 | PASS |
| south_polar_a (-135.0, -89.5, 1.5) | Sun | weekend | 289 | 0.002 | 0.001 | 0.002 | 0.0005 | 0.0021 | 0.000022 | PASS |
| south_polar_a (-135.0, -89.5, 1.5) | Earth | weekend | 289 | 0.004 | 0.002 | 0.087 | 0.0005 | 0.0036 | 0.000022 | PASS |
| south_polar_b (45.0, -85.0, -2.0) | Sun | weekend | 289 | 0.002 | 0.001 | 0.003 | 0.0005 | 0.0021 | 0.000022 | PASS |
| south_polar_b (45.0, -85.0, -2.0) | Earth | weekend | 289 | 0.004 | 0.002 | 0.087 | 0.0006 | 0.0036 | 0.000022 | PASS |
| south_polar_c (0.0, -89.99, 0.0) | Sun | weekend | 289 | 0.002 | 0.001 | 0.002 | 0.0005 | 0.0021 | 0.000022 | PASS |
| south_polar_c (0.0, -89.99, 0.0) | Earth | weekend | 289 | 0.004 | 0.002 | 0.087 | 0.0006 | 0.0036 | 0.000022 | PASS |
| eq_near (0.0, 0.0, 0.0) | Sun | nodal_cycle | 6545 | 0.002 | 0.001 | 0.005 | 0.0005 | 0.0040 | 0.000038 | PASS |
| eq_near (0.0, 0.0, 0.0) | Earth | nodal_cycle | 6545 | 0.004 | 0.002 | 0.025 | 0.0006 | 0.0042 | 0.000038 | PASS |
| low_lat_east (23.47, 0.67, 0.0) | Sun | nodal_cycle | 6545 | 0.003 | 0.001 | 0.005 | 0.0005 | 0.0040 | 0.000038 | PASS |
| low_lat_east (23.47, 0.67, 0.0) | Earth | nodal_cycle | 6545 | 0.005 | 0.002 | 0.059 | 0.0006 | 0.0042 | 0.000038 | PASS |
| far_mid_north (-150.0, 45.0, 1.0) | Sun | nodal_cycle | 6545 | 0.003 | 0.001 | 0.004 | 0.0005 | 0.0040 | 0.000038 | PASS |
| far_mid_north (-150.0, 45.0, 1.0) | Earth | nodal_cycle | 6545 | 0.004 | 0.002 | 0.085 | 0.0006 | 0.0042 | 0.000038 | PASS |
| north_polar (30.0, 88.0, 0.0) | Sun | nodal_cycle | 6545 | 0.003 | 0.001 | 0.003 | 0.0005 | 0.0040 | 0.000038 | PASS |
| north_polar (30.0, 88.0, 0.0) | Earth | nodal_cycle | 6545 | 0.005 | 0.002 | 0.098 | 0.0006 | 0.0042 | 0.000038 | PASS |
| south_polar_a (-135.0, -89.5, 1.5) | Sun | nodal_cycle | 6545 | 0.003 | 0.001 | 0.003 | 0.0005 | 0.0040 | 0.000038 | PASS |
| south_polar_a (-135.0, -89.5, 1.5) | Earth | nodal_cycle | 6545 | 0.005 | 0.002 | 0.099 | 0.0006 | 0.0042 | 0.000038 | PASS |
| south_polar_b (45.0, -85.0, -2.0) | Sun | nodal_cycle | 6545 | 0.003 | 0.001 | 0.003 | 0.0005 | 0.0040 | 0.000038 | PASS |
| south_polar_b (45.0, -85.0, -2.0) | Earth | nodal_cycle | 6545 | 0.005 | 0.002 | 0.099 | 0.0006 | 0.0042 | 0.000038 | PASS |
| south_polar_c (0.0, -89.99, 0.0) | Sun | nodal_cycle | 6545 | 0.003 | 0.001 | 0.003 | 0.0005 | 0.0040 | 0.000038 | PASS |
| south_polar_c (0.0, -89.99, 0.0) | Earth | nodal_cycle | 6545 | 0.005 | 0.002 | 0.098 | 0.0006 | 0.0042 | 0.000038 | PASS |

Worst case over all rows: direction 0.005″ (exact path), 0.099″ (direction table).

Statements printed by Horizons in the response headers:

- `Center body name: Moon (301)                      {source: DE441}`
- `Center pole/equ : MEAN_ME (high precision)        {East-longitude positive}`
- `Center radii    : 1737.4, 1737.4, 1737.4 km       {Equator_a, b, pole_c}`
- `Rel. light bend : Sun, EARTH                      {source: DE441}`
- `Target body name: Earth (399)                     {source: DE441}`
- `Target body name: Sun (10)                        {source: DE441}`
- `Target pole/equ : IAU_SUN                         {East-longitude positive}`
- `Target pole/equ : ITRF93 (high precision)         {East-longitude positive}`
- `Target radii    : 6378.137, 6378.137, 6356.752 km {Equator_a, b, pole_c}`
- `Target radii    : 695700.0, 695700.0, 695700.0 km {Equator_a, b, pole_c}`
- `Vis. interferer : EARTH (R_eq= 6378.137) km       {source: DE441}`
