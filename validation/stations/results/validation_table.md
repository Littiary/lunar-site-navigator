# Validation table: ground-station geometry versus JPL Horizons

Generated 2026-11-14T11:41:00Z by `validation/stations/compare.py` from the stored raw responses. Do not edit by hand.

- Core: frame `MOON_ME_DE440_ME421`, correction `LT+S`, kernel set `bfe870fccfa5`, station group `bacdf4d6169a` (earth_1962_260806_2126_combined.bpc, earth_000101_270208_261113.bpc, earthstns_itrf93_260814.bsp, earth_topo_260814.tf).
- Thresholds (fixed before the data was fetched, commit 6f74153): exact path < 1.0 arcsec at both ends; fast path < 0.012 deg in elevation at the station and < 1.0 arcsec at the lunar site.
- 12 of 12 cases pass, 3468 rows, 14 to 16 November 2026 at 10 minutes.

| End | Station | Lunar site | Rows | Exact path, direction max (arcsec) | Fast path max | Elevation range (deg) | Status |
|---|---|---|---|---|---|---|---|
| Earth end: lunar site seen from the station | DSS-14 | polar | 289 | 0.375 | 0.00009 deg in elevation | -79.9 to 32.5 | PASS |
| Earth end: lunar site seen from the station | DSS-43 | polar | 289 | 0.342 | 0.00009 deg in elevation | -34.3 to 80.2 | PASS |
| Earth end: lunar site seen from the station | DSS-63 | polar | 289 | 0.424 | 0.00007 deg in elevation | -75.8 to 27.4 | PASS |
| Earth end: lunar site seen from the station | DSS-14 | equator | 289 | 0.404 | 0.00007 deg in elevation | -79.7 to 32.7 | PASS |
| Earth end: lunar site seen from the station | DSS-43 | equator | 289 | 0.341 | 0.00007 deg in elevation | -34.5 to 80.0 | PASS |
| Earth end: lunar site seen from the station | DSS-63 | equator | 289 | 0.416 | 0.00005 deg in elevation | -75.5 to 27.7 | PASS |
| Moon end: station seen from the lunar site | DSS-14 | polar | 289 | 0.179 | 0.200 arcsec | -5.6 to -3.2 | PASS |
| Moon end: station seen from the lunar site | DSS-43 | polar | 289 | 0.193 | 0.200 arcsec | -4.5 to -2.0 | PASS |
| Moon end: station seen from the lunar site | DSS-63 | polar | 289 | 0.192 | 0.210 arcsec | -5.1 to -2.8 | PASS |
| Moon end: station seen from the lunar site | DSS-14 | equator | 289 | 0.178 | 0.189 arcsec | 84.6 to 85.8 | PASS |
| Moon end: station seen from the lunar site | DSS-43 | equator | 289 | 0.193 | 0.185 arcsec | 85.5 to 86.6 | PASS |
| Moon end: station seen from the lunar site | DSS-63 | equator | 289 | 0.191 | 0.200 arcsec | 84.6 to 85.7 | PASS |

Site and target lines printed by Horizons (first query of each station):

- `earth_end__dss14__polar`: Target body name: Moon (301) {source: DE441} | Center body name: Earth (399) {source: DE441} | Center-site name: DSS-14 (70-m) | Target geodetic : 205.76891, -89.80531, 1.7011 {E-lon(deg),Lat(deg),Alt(km)} | Target pole/equ : MEAN_ME (high precision) {East-longitude positive} | Center geodetic : 243.1104618,35.4259009,1.00139 {E-lon(deg),Lat(deg),Alt(km)} | Center pole/equ : ITRF93 {East-longitude positive}
- `earth_end__dss43__polar`: Target body name: Moon (301) {source: DE441} | Center body name: Earth (399) {source: DE441} | Center-site name: DSS-43 (70-m) | Target geodetic : 205.76891, -89.80531, 1.7011 {E-lon(deg),Lat(deg),Alt(km)} | Target pole/equ : MEAN_ME (high precision) {East-longitude positive} | Center geodetic : 148.9812673,-35.4024242,.688867 {E-lon(deg),Lat(deg),Alt(km)} | Center pole/equ : ITRF93 {East-longitude positive}
- `earth_end__dss63__polar`: Target body name: Moon (301) {source: DE441} | Center body name: Earth (399) {source: DE441} | Center-site name: DSS-63 (70-m) | Target geodetic : 205.76891, -89.80531, 1.7011 {E-lon(deg),Lat(deg),Alt(km)} | Target pole/equ : MEAN_ME (high precision) {East-longitude positive} | Center geodetic : 355.7519915, 40.4312097, .86482 {E-lon(deg),Lat(deg),Alt(km)} | Center pole/equ : ITRF93 {East-longitude positive}
