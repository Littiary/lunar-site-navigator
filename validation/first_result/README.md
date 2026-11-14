# First end-to-end result (one south-polar site, real terrain)

`python -m validation.first_result.run <sites.json> <site_id> <output folder>` builds a one-site scenario from a site record of the data stream, runs the core pipeline (LOLA terrain horizon → SPICE direction table → events, windows, countdown) and validates the packages against the contract. Packages are written to the output folder, not to the repository.

## Run of 14 November 2026

| Item | Value |
|---|---|
| Site | "Shackleton crater rim crest", record `shackleton_rim_crest` of the data stream: 89.80531° S, 205.76891° E (−154.23109°), terrain height 1701.1 m above the 1737.4 km sphere. A project candidate point derived from LOLA and the IAU crater outline; **not an official landing site** |
| Terrain | `lola:LDEM_80S_20M@V2.0+LDEM_60S_60M@V2.0`, search radius 300 km, azimuth step 0.25° |
| Ephemeris | kernel set `bfe870fccfa5` (DE440), frame `MOON_ME_DE440_ME421`, `LT+S` |
| Window | 2026-11-14 00:00 UTC to 2027-01-13 00:00 UTC (60 days) |
| Thresholds | Sun: any part of the disc above the terrain horizon. Earth: centre of the disc above the terrain horizon |
| Packages | site `site-b13dc4bc0d138132`, direction table `dirtab-a7dbf225e60426e6`; both pass `lsncore validate` |
| Run time | 6.6 s (horizon 1.0 s, timeline 4.9 s) on the team laptop |

Result per observer height (reference instant for the countdowns: start of the window):

| Observer height | Sun visible (share of window) | Longest interval without Sun | Time until the Sun next sets | Earth visible (share of window) | Time until the Earth next sets |
|---|---|---|---|---|---|
| 0 m | 78.7 % | 164.8 h | 21.52 d | 49.1 % | 16.43 d |
| 1 m | 90.1 % | 87.7 h | 23.06 d | 49.1 % | 16.43 d |
| 2 m | 92.0 % | 63.0 h | 23.12 d | 49.1 % | 16.43 d |
| 5 m | 92.9 % | 56.5 h | 23.27 d | 49.2 % | 16.43 d |
| 10 m | 94.4 % | 47.5 h | 23.63 d | 49.2 % | 16.43 d |
| 20 m | 99.9 % | 2.2 h | 54.17 d | 49.2 % | 16.44 d |

At the start of the window the Earth is below the horizon; it rises 2.98 d later, and "time until the Earth next sets" is counted to the set that follows that rise.

Events at 2 m: the Sun sets on 2026-12-07 02:46:57 UTC behind terrain 0.68 km away (horizon +1.91°, azimuth 359.8°) and reappears on 2026-12-09 07:02:42 UTC; it sets again on 2027-01-05 11:40:31 UTC and reappears on 2027-01-08 02:39:04 UTC. The Earth rises and sets over terrain 125 to 131 km away at azimuths 149° to 161°.

## What this result is and is not

* **Unverified against an independent source.** The ephemeris part is validated against JPL Horizons (`validation/horizons`, `validation/horizons_rts`); the terrain horizon has passed analytic tests only (core stream). No published illumination product or mission record has been compared with these numbers yet.
* The Sun outages at this site are set by terrain 0.2 to 0.7 km from the observer, where the 20 m elevation grid, not the method, limits the accuracy; 22 % of the horizon at 2 m is set by terrain closer than 1 km. The strong dependence on observer height (79 % at the ground, 99.9 % at 20 m) is the visible consequence. Event times that depend on such near terrain can be off by hours.
* 60 days in southern summer; the shares are not annual averages.
* Event times are numerically exact to 0.25 s for the given horizon profile; that is not their physical accuracy.
* Eclipses of the Sun by the Earth are not included.
