# End-to-end results: the three project sites, and the curated list

Generated 2026-11-14T17:42:17Z by `validation/sites/run.py`. Do not edit by hand.

- Window: 2026-11-14T00:00:00.000Z to 2028-11-14T00:00:00.000Z (UTC). Countdowns count from the planned landing time of the scenario, 2027-01-10T00:00:00.000Z.
- **Inputs chosen by the team, not properties of the data or of a mission**: the three example requirements on the landing time (`docs/contract/presets/requirements.json`; they are not requirements of NASA or of any mission), a landing circle of 100 m radius sampled at 13 points, and the planned landing time. The numbers that follow from them say what would hold if they were true.
- **Stated terrain height error**: the model `lola-two-sigma-2026-11` shipped with the contract (Two sigma for the LOLA products: on the 5 m site rasters twice the producers' RMS error map at the pixel (1 m where the map is empty); on every other product 5 m up to 30 degrees of slope and 7 m above). It is the data stream's measurement of the elevation products against each other and the producers' own error maps, not a test against independent data.
- The three sites are computed **with the 5 m near field**: inside the 5 m site rasters of the data stream the terrain is read from them, elsewhere from the 20 m and 60 m products. The section 'Before and after the 5 m near field' puts the 24-month numbers of both side by side.
- Terrain: `lola:LOLA5MPP_SITE04@None+LDEM_80S_20M@V2.0+LDEM_60S_60M@V2.0`, search radius 300 km, azimuth step 0.25 deg. Ephemeris: kernel set `bfe870fccfa5`, direction table `dirtab-fbc51d64e42ab803`.
- Sun visible = any part of the disc above the terrain horizon. Earth visible = centre of the disc above the terrain horizon.
- The points are project candidates derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**.
- **Status.** The method behind these numbers reproduces the published LOLA illumination maps of NASA Goddard at 100 points on terrain of the same resolution (`validation/pgda`), and the ephemeris is validated (see the validation card). Of two dated LROC images, the shadowed state of the south pole agrees; the comparison along an image strip fails its registered criterion (89.3 % agreement against 90 %; the image rule reads dimly lit ground as shadow), see `validation/lro_images`. The numbers of these three sites themselves have no independent counterpart: they use the finer 20 m terrain, a 24-month window and several observer heights, and no source gives rise and set times for these points.

## Shackleton crater rim crest

89.80531 deg S, -154.23109 deg E, terrain height 1701.0 m above the 1737.4 km sphere. Package `site-e3810b35dcfa4777`, status `ok`. Terrain: the height at the site is read from LOLA5MPP_SITE04 (5 m pixels, resolution class fine); the horizon at the default observer height is set by LDEM_80S_20M (20 m) in 78.1 % of the azimuths, LOLA5MPP_SITE04 (5 m) in 21.9 % of the azimuths. Sun centre elevation -1.72 to 1.71 deg; Earth centre elevation -7.28 to 6.44 deg.

| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |
|---|---|---|---|---|---|---|---|---|---|
| 0 m | 47.7 % | 420.1 h | 130 | 47 | 22.01 d | 52.4 % | 334.2 h | 13.78 d | 57 % |
| 1 m | 72.0 % | 281.1 h | 164 | 49 | 22.85 d | 52.4 % | 334.2 h | 13.78 d | 33 % |
| 2 m | 76.9 % | 191.6 h | 178 | 49 | 22.85 d | 52.4 % | 334.1 h | 13.78 d | 22 % |
| 5 m | 80.2 % | 177.3 h | 176 | 46 | 22.85 d | 52.5 % | 334.1 h | 13.78 d | 20 % |
| 10 m | 83.1 % | 136.4 h | 172 | 42 | 22.86 d | 52.5 % | 334.0 h | 13.78 d | 13 % |
| 20 m | 86.3 % | 125.5 h | 170 | 38 | 22.88 d | 52.5 % | 333.9 h | 13.78 d | 10 % |

Direct link with the Deep Space Network (three complexes; station mask 10 deg for a two-way link, 6 deg to receive; geometry only):

| Observer height | Two-way link possible | Receive possible | Goldstone | Canberra | Madrid | Longest time without a link | Longest time with every station behind lunar terrain | Relay need |
|---|---|---|---|---|---|---|---|---|
| 0 m | 51.8 % | 52.3 % | 23.5 % | 20.6 % | 23.4 % | 322.9 h | 321.0 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 1 m | 51.8 % | 52.3 % | 23.5 % | 20.6 % | 23.4 % | 322.9 h | 321.0 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 2 m | 51.8 % | 52.3 % | 23.5 % | 20.6 % | 23.4 % | 322.9 h | 321.0 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 5 m | 51.8 % | 52.3 % | 23.5 % | 20.6 % | 23.4 % | 322.9 h | 321.0 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 10 m | 51.8 % | 52.3 % | 23.5 % | 20.6 % | 23.4 % | 322.8 h | 320.9 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 20 m | 51.8 % | 52.3 % | 23.5 % | 20.6 % | 23.4 % | 322.8 h | 320.9 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |

Eclipses of the Sun by the Earth in the window: 3 (1 total at the site); largest covered fraction of the Sun 1.000; 2027-08-17T05:41:37.734Z to 2027-08-17T08:53:54.609Z; 2028-01-12T02:19:51.795Z to 2028-01-12T05:59:10.545Z; 2028-07-06T17:00:24.139Z to 2028-07-06T19:46:49.921Z.

**What the terrain costs (observer 2 m).** Over a smooth sphere through the site the Sun would be visible for 10056 h of the window; the terrain takes 1212 h and gives 4653 h (terrain below the smooth horizon), leaving 13496 h. Earth: 8625 h, minus 0 h, plus 576 h, leaving 9201 h.

| Obstacle of the Sun (largest cost first) | Costs | Share of the lost time | Highest point: azimuth, elevation, distance | Within 1 km |
|---|---|---|---|---|
| 1 | 373 h | 31 % | 350.5 deg, +2.84 deg, 0.7 km | yes: depends on single pixels of the elevation model |
| 2 | 165 h | 14 % | 330.5 deg, +1.85 deg, 0.1 km | yes: depends on single pixels of the elevation model |
| 3 | 143 h | 12 % | 344.8 deg, +3.12 deg, 0.6 km | yes: depends on single pixels of the elevation model |

**Lunar days.** 25 in the window, 23 of them complete. Per complete lunar day (least, median, most): Sun visible 353, 555, 657 h; longest stretch without the Sun 50, 68, 121 h; Earth visible 321, 377, 413 h.

| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |
|---|---|---|---|---|
| `example-standard`: Earth in view at landing and 10 Earth days of unbroken sunlight from landing | 15 | 19.6 % | 13.2 d, 10.6 d | 2027-01-10: not feasible; next window in 0.4 d |
| `example-strict`: Earth in view at landing, 14 Earth days of unbroken sunlight from landing, Earth in view for at least half of those 14 days | 14 | 10.1 % | 7.5 d, 6.0 d | 2027-01-10: not feasible; next window in 0.4 d |
| `example-loose`: Earth in view at landing and 5 Earth days of unbroken sunlight from landing | 22 | 27.7 % | 15.6 d, 11.5 d | 2027-01-10: not feasible; next window in 0.4 d |

**If the terrain were wrong by the stated height-error model** (`lola-two-sigma-2026-11`: at the terrain points that set the horizon 0.23 to 5.00 m, median 5.00 m, which seen from the site is 0.001 to 1.316 deg, median 0.009 deg; 70 % of those points lie on a pixel with a laser return, 30 % on interpolated ground): Sun visible for certain 13322 h, possibly 13690 h (368 h uncertain); Earth for certain 9199 h, possibly 9203 h (4 h uncertain).

**Inside the stated landing circle** (100 m radius, 13 points, each with its own terrain horizon): Sun visible 13496 h at the site; 8631 h least, 10810 h median, 14059 h most over the points. Earth: 9201 h at the site; 9194, 9199, 9202 h.

| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |
|---|---|---|---|---|
| 0 m | 8374 h | +0 h | 420.1 h | 173 h |
| 1 m | 12634 h | +4260 h | 281.1 h | 290 h |
| 2 m | 13496 h | +5122 h | 191.6 h | 353 h |
| 5 m | 14064 h | +5689 h | 177.3 h | 369 h |
| 10 m | 14585 h | +6211 h | 136.4 h | 413 h |
| 20 m | 15133 h | +6759 h | 125.5 h | 425 h |

## de Gerlache crater rim crest

88.66410 deg S, -68.41044 deg E, terrain height 1815.3 m above the 1737.4 km sphere. Package `site-66887386ea4fc6ea`, status `ok`. Terrain: the height at the site is read from LOLA5MPP_SITE11 (5 m pixels, resolution class fine); the horizon at the default observer height is set by LDEM_80S_20M (20 m) in 79.1 % of the azimuths, LOLA5MPP_SITE11 (5 m) in 20.9 % of the azimuths. Sun centre elevation -2.85 to 2.88 deg; Earth centre elevation -6.77 to 7.23 deg.

| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |
|---|---|---|---|---|---|---|---|---|---|
| 0 m | 62.9 % | 340.3 h | 82 | 53 | 3.47 d | 47.9 % | 366.5 h | 12.88 d | 43 % |
| 1 m | 83.8 % | 256.9 h | 70 | 9 | 30.40 d | 57.3 % | 304.6 h | 14.53 d | 19 % |
| 2 m | 84.7 % | 256.8 h | 74 | 10 | 30.40 d | 57.3 % | 304.6 h | 14.56 d | 15 % |
| 5 m | 86.2 % | 256.8 h | 80 | 7 | 30.41 d | 57.3 % | 304.5 h | 14.56 d | 9 % |
| 10 m | 88.1 % | 135.4 h | 94 | 10 | 30.44 d | 57.3 % | 304.4 h | 14.56 d | 5 % |
| 20 m | 88.5 % | 135.1 h | 88 | 0 | 30.48 d | 57.4 % | 304.3 h | 14.56 d | 0 % |

Direct link with the Deep Space Network (three complexes; station mask 10 deg for a two-way link, 6 deg to receive; geometry only):

| Observer height | Two-way link possible | Receive possible | Goldstone | Canberra | Madrid | Longest time without a link | Longest time with every station behind lunar terrain | Relay need |
|---|---|---|---|---|---|---|---|---|
| 0 m | 47.3 % | 47.7 % | 21.9 % | 18.3 % | 21.8 % | 364.4 h | 350.7 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 1 m | 56.4 % | 56.9 % | 25.2 % | 22.7 % | 25.2 % | 297.0 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 2 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 297.0 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 5 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 296.9 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 10 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 296.9 h | 282.7 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 20 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.3 % | 296.9 h | 282.6 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |

Eclipses of the Sun by the Earth in the window: 3 (1 total at the site); largest covered fraction of the Sun 1.000; 2027-08-17T05:40:53.672Z to 2027-08-17T08:53:21.797Z; 2028-01-12T02:19:21.327Z to 2028-01-12T05:58:34.452Z; 2028-07-06T16:59:51.796Z to 2028-07-06T19:46:03.983Z.

**What the terrain costs (observer 2 m).** Over a smooth sphere through the site the Sun would be visible for 10929 h of the window; the terrain takes 0 h and gives 3923 h (terrain below the smooth horizon), leaving 14852 h. Earth: 9183 h, minus 0 h, plus 873 h, leaving 10056 h.

**Lunar days.** 25 in the window, 23 of them complete. Per complete lunar day (least, median, most): Sun visible 418, 663, 711 h; longest stretch without the Sun 0, 28, 257 h; Earth visible 347, 413, 443 h.

| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |
|---|---|---|---|---|
| `example-standard`: Earth in view at landing and 10 Earth days of unbroken sunlight from landing | 21 | 33.2 % | 16.7 d, 14.5 d | 2027-01-10: feasible; can slip 14.6 d |
| `example-strict`: Earth in view at landing, 14 Earth days of unbroken sunlight from landing, Earth in view for at least half of those 14 days | 17 | 17.0 % | 9.7 d, 8.5 d | 2027-01-10: feasible; can slip 7.6 d |
| `example-loose`: Earth in view at landing and 5 Earth days of unbroken sunlight from landing | 26 | 39.6 % | 16.7 d, 14.1 d | 2027-01-10: feasible; can slip 14.6 d |

**If the terrain were wrong by the stated height-error model** (`lola-two-sigma-2026-11`: at the terrain points that set the horizon 0.21 to 5.00 m, median 5.00 m, which seen from the site is 0.002 to 0.308 deg, median 0.004 deg; 63 % of those points lie on a pixel with a laser return, 37 % on interpolated ground): Sun visible for certain 14797 h, possibly 14937 h (140 h uncertain); Earth for certain 10053 h, possibly 10059 h (6 h uncertain).

**Inside the stated landing circle** (100 m radius, 13 points, each with its own terrain horizon): Sun visible 14852 h at the site; 0 h least, 10124 h median, 14889 h most over the points. Earth: 10056 h at the site; 0, 8536, 10056 h.

| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |
|---|---|---|---|---|
| 0 m | 11043 h | +0 h | 340.3 h | 367 h |
| 1 m | 14698 h | +3655 h | 256.9 h | 418 h |
| 2 m | 14852 h | +3809 h | 256.8 h | 418 h |
| 5 m | 15130 h | +4087 h | 256.8 h | 418 h |
| 10 m | 15464 h | +4422 h | 135.4 h | 455 h |
| 20 m | 15523 h | +4480 h | 135.1 h | 474 h |

## Mons Malapert (Malapert massif) summit

85.98795 deg S, 2.05767 deg E, terrain height 5172.9 m above the 1737.4 km sphere. Package `site-3c901dfc80efc5b8`, status `ok`. Terrain: the height at the site is read from LOLA5MPP_SITE23 (5 m pixels, resolution class fine); the horizon at the default observer height is set by LOLA5MPP_SITE23 (5 m) in 84.5 % of the azimuths, LDEM_80S_20M (20 m) in 15.5 % of the azimuths. Sun centre elevation -5.56 to 5.59 deg; Earth centre elevation -3.10 to 10.59 deg.

| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |
|---|---|---|---|---|---|---|---|---|---|
| 0 m | 49.5 % | 473.7 h | 50 | 50 | 20.69 d | 69.5 % | 221.3 h | 15.97 d | 100 % |
| 1 m | 64.2 % | 356.2 h | 53 | 41 | 22.57 d | 78.7 % | 163.1 h | 17.23 d | 91 % |
| 2 m | 68.7 % | 340.2 h | 62 | 43 | 23.06 d | 80.9 % | 146.0 h | 17.34 d | 76 % |
| 5 m | 78.4 % | 312.1 h | 62 | 38 | 24.60 d | 83.8 % | 128.2 h | 17.69 d | 67 % |
| 10 m | 84.1 % | 270.4 h | 68 | 32 | 26.86 d | 89.5 % | 92.4 h | 18.40 d | 48 % |
| 20 m | 86.1 % | 260.6 h | 64 | 3 | 26.87 d | 100.0 % | 0.0 h | at least 674.00 d | 9 % |

Direct link with the Deep Space Network (three complexes; station mask 10 deg for a two-way link, 6 deg to receive; geometry only):

| Observer height | Two-way link possible | Receive possible | Goldstone | Canberra | Madrid | Longest time without a link | Longest time with every station behind lunar terrain | Relay need |
|---|---|---|---|---|---|---|---|---|
| 0 m | 68.3 % | 69.1 % | 29.7 % | 28.3 % | 29.5 % | 213.6 h | 202.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 1 m | 77.1 % | 78.4 % | 32.6 % | 33.1 % | 32.3 % | 143.6 h | 133.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 2 m | 79.2 % | 80.5 % | 33.3 % | 34.3 % | 33.0 % | 128.4 h | 111.2 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 5 m | 81.9 % | 83.4 % | 34.1 % | 36.0 % | 33.7 % | 97.5 h | 87.4 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 10 m | 87.7 % | 89.5 % | 35.5 % | 39.9 % | 35.0 % | 23.7 h | 14.4 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 20 m | 94.5 % | 96.5 % | 38.7 % | 42.2 % | 37.8 % | 12.7 h | 0.0 h | 1: interrupted only by station gaps on the Earth |

Eclipses of the Sun by the Earth in the window: 3 (1 total at the site); largest covered fraction of the Sun 1.000; 2027-08-17T05:41:50.859Z to 2027-08-17T08:54:02.578Z; 2028-01-12T02:20:03.045Z to 2028-01-12T05:59:24.608Z; 2028-07-06T17:00:20.858Z to 2028-07-06T19:46:48.046Z.

**What the terrain costs (observer 2 m).** Over a smooth sphere through the site the Sun would be visible for 9499 h of the window; the terrain takes 0 h and gives 2546 h (terrain below the smooth horizon), leaving 12045 h. Earth: 12340 h, minus 0 h, plus 1854 h, leaving 14194 h.

**Lunar days.** 25 in the window, 23 of them complete. Per complete lunar day (least, median, most): Sun visible 368, 445, 625 h; longest stretch without the Sun 40, 136, 187 h; Earth visible 532, 577, 598 h.

| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |
|---|---|---|---|---|
| `example-standard`: Earth in view at landing and 10 Earth days of unbroken sunlight from landing | 27 | 28.6 % | 15.3 d, 7.1 d | 2027-01-10: not feasible; next window in 1.7 d |
| `example-strict`: Earth in view at landing, 14 Earth days of unbroken sunlight from landing, Earth in view for at least half of those 14 days | 23 | 17.1 % | 11.3 d, 4.6 d | 2027-01-10: not feasible; next window in 1.7 d |
| `example-loose`: Earth in view at landing and 5 Earth days of unbroken sunlight from landing | 30 | 42.2 % | 20.3 d, 10.0 d | 2027-01-10: not feasible; next window in 1.7 d |

**If the terrain were wrong by the stated height-error model** (`lola-two-sigma-2026-11`: at the terrain points that set the horizon 0.19 to 5.00 m, median 0.60 m, which seen from the site is 0.001 to 0.779 deg, median 0.112 deg; 41 % of those points lie on a pixel with a laser return, 59 % on interpolated ground): Sun visible for certain 11602 h, possibly 12728 h (1126 h uncertain); Earth for certain 14102 h, possibly 14290 h (188 h uncertain).

**Inside the stated landing circle** (100 m radius, 13 points, each with its own terrain horizon): Sun visible 12045 h at the site; 7277 h least, 11354 h median, 13489 h most over the points. Earth: 14194 h at the site; 11718, 13897, 14494 h.

| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |
|---|---|---|---|---|
| 0 m | 8683 h | +0 h | 473.7 h | 235 h |
| 1 m | 11256 h | +2573 h | 356.2 h | 352 h |
| 2 m | 12045 h | +3362 h | 340.2 h | 368 h |
| 5 m | 13762 h | +5079 h | 312.1 h | 396 h |
| 10 m | 14760 h | +6077 h | 270.4 h | 438 h |
| 20 m | 15101 h | +6418 h | 260.6 h | 448 h |

## Two sites together

Package `pairs-c6ab3aaa46a3aa80`. Each site at its default observer height. 'Either' is the share of the window in which at least one of the two sites sees the body.

| Sites | Distance | Sun: each alone | Sun: either | Longest time with the Sun at neither | What the second site adds | Earth: either | Longest time with the Earth at neither |
|---|---|---|---|---|---|---|---|
| Shackleton crater rim crest and de Gerlache crater rim crest | 41 km | 76.9 %, 84.7 % | 96.8 % | 47 h | 2124 h (79 % of the better site's dark time) | 57.3 % | 305 h |
| Shackleton crater rim crest and Mons Malapert (Malapert massif) summit | 127 km | 76.9 %, 68.7 % | 82.2 % | 192 h | 931 h (23 % of the better site's dark time) | 80.9 % | 146 h |
| de Gerlache crater rim crest and Mons Malapert (Malapert massif) summit | 115 km | 84.7 %, 68.7 % | 90.7 % | 163 h | 1053 h (39 % of the better site's dark time) | 80.9 % | 146 h |

## Before and after the 5 m near field

The three project sites over the same time range, with everything else the same: first on the 20 m product (not published), second with the 5 m site rasters inside it (the published packages). Sun: any part of the disc; Earth: centre. The band uses the same height-error model in both; without the near field it has no error map to read and applies 5 m or 7 m by slope.

| 20 m product / with the 5 m near field | Shackleton crater rim crest | de Gerlache crater rim crest | Mons Malapert (Malapert massif) summit |
|---|---|---|---|
| Height at the site read from | LDEM_80S_20M / LOLA5MPP_SITE04 | LDEM_80S_20M / LOLA5MPP_SITE11 | LDEM_80S_20M / LOLA5MPP_SITE23 |
| Terrain height at the site | 1701.07 m / 1701.02 m | 1815.19 m / 1815.33 m | 5173.50 m / 5172.89 m |
| Horizon at 2 m set within 1 km, share of azimuths | 22 % / 22 % | 15 % / 15 % | 70 % / 76 % |
| Sun visible on the surface | 66.9 % / 47.7 % | 82.1 % / 62.9 % | 60.8 % / 49.5 % |
| Sun visible at 2 m | 78.0 % / 76.9 % | 84.7 % / 84.7 % | 72.5 % / 68.7 % |
| Sun visible at 10 m | 83.2 % / 83.1 % | 88.2 % / 88.1 % | 84.8 % / 84.1 % |
| Longest time without the Sun at 2 m | 188 h / 192 h | 257 h / 257 h | 330 h / 340 h |
| Sun-visible hours per complete lunar day at 2 m: least, median, most | 357, 571, 657 / 353, 555, 657 | 418, 663, 711 / 418, 663, 711 | 379, 457, 686 / 368, 445, 625 |
| Sun time the terrain takes at 2 m, against a smooth sphere | 1091 h / 1212 h | 0 h / 0 h | 0 h / 0 h |
| Sun time the terrain gives at 2 m | 4724 h / 4653 h | 3925 h / 3923 h | 3213 h / 2546 h |
| Earth visible at 2 m | 52.4 % / 52.4 % | 57.3 % / 57.3 % | 81.6 % / 80.9 % |
| Earth visible at 10 m | 52.5 % / 52.5 % | 57.3 % / 57.3 % | 91.2 % / 89.5 % |
| Landing windows for `example-standard` at 2 m: number, share of the judged range | 15, 19.8 % / 15, 19.6 % | 21, 33.2 % / 21, 33.2 % | 27, 32.0 % / 27, 28.6 % |
| Planned landing feasible for `example-standard` | no / no | yes / yes | no / no |
| Band at 2 m: Sun visible for certain, possibly | 12560, 14418 h / 13322, 13690 h | 14045, 15786 h / 14797, 14937 h | 10627, 15588 h / 11602, 12728 h |
| Horizon error the model gives, median over the azimuths | 0.009 deg / 0.009 deg | 0.004 deg / 0.004 deg | 0.924 deg / 0.112 deg |
| Landing circle of 100 m, 13 points, Sun: least, median | 8396, 10050 h / 8631, 10810 h | 0, 10326 h / 0, 10124 h | 9596, 11067 h / 7277, 11354 h |

A difference is not an error of one side that the other corrects: the two elevation products are built from the same laser returns and differ in gridding and in a measured horizontal offset (6.6 m at the Malapert record, data stream). Where the horizon is set by terrain within a few hundred metres, as on the Malapert summit, a few pixels decide; the numbers of such a site at low observer heights are as uncertain as the difference shown here.

## All published sites

20 site packages, 106.8 MB with the direction table and the site pairs. Every package holds the horizon with its obstacles and terrain source, events, windows, countdowns, eclipses and the lit fraction of the Sun, ground-station windows, what the terrain costs, the lunar-day calendar, landing windows for the three example requirements, the height trade over its observer heights and three terrain patches. The columns say what differs.

| Site | Kind | Height at the site read from | Class | Horizon at 2 m set by | Near field | Observer heights | Uncertainty band | Landing-circle survey | Planned landing | Size |
|---|---|---|---|---|---|---|---|---|---|---|
| Shackleton crater rim crest (`shackleton-rim-crest`) | Project sites: project site | LOLA5MPP_SITE04 (5 m) | fine | LDEM_80S_20M (20 m) 78 %, LOLA5MPP_SITE04 (5 m) 22 % | on | 0, 1, 2, 5, 10, 20 m | `lola-two-sigma-2026-11` | yes | 2027-01-10 | 9.6 MB |
| de Gerlache crater rim crest (`de-gerlache-rim-crest`) | Project sites: project site | LOLA5MPP_SITE11 (5 m) | fine | LDEM_80S_20M (20 m) 79 %, LOLA5MPP_SITE11 (5 m) 21 % | on | 0, 1, 2, 5, 10, 20 m | `lola-two-sigma-2026-11` | yes | 2027-01-10 | 8.6 MB |
| Mons Malapert (Malapert massif) summit (`malapert-massif-summit`) | Project sites: project site | LOLA5MPP_SITE23 (5 m) | fine | LOLA5MPP_SITE23 (5 m) 85 %, LDEM_80S_20M (20 m) 15 % | on | 0, 1, 2, 5, 10, 20 m | `lola-two-sigma-2026-11` | yes | 2027-01-10 | 9.5 MB |
| Apollo 11 (Lunar Module Eagle descent stage) (`apollo-11`) | Apollo: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Apollo 12 (Lunar Module Intrepid descent stage) (`apollo-12`) | Apollo: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Apollo 14 (Lunar Module Antares descent stage) (`apollo-14`) | Apollo: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Apollo 15 (Lunar Module Falcon descent stage) (`apollo-15`) | Apollo: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.7 MB |
| Apollo 16 (Lunar Module Orion descent stage) (`apollo-16`) | Apollo: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Apollo 17 (Lunar Module Challenger descent stage) (`apollo-17`) | Apollo: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Surveyor 1 lander (`surveyor-1`) | Surveyor: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Chang'e 3 lander (`change-3`) | Chang'e: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.9 MB |
| Chang'e 4 lander (`change-4`) | Chang'e: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 3.0 MB |
| Chang'e 5 lander (`change-5`) | Chang'e: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.9 MB |
| Chang'e 6 lander (`change-6`) | Chang'e: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 3.1 MB |
| Chandrayaan-3 Vikram lander (`chandrayaan-3`) | Chandrayaan: past landing | LDEM_60S_60M (60 m) | medium | LDEM_60S_60M (60 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| SLIM lander (`slim`) | SLIM: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.7 MB |
| IM-1 Odysseus lander (CLPS) (`im-1-odysseus`) | CLPS: past landing | LDEM_80S_20M (20 m) | fine | LDEM_80S_20M (20 m) 93 %, LDEM_60S_60M (60 m) 7 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| Blue Ghost Mission 1 lander (CLPS; LROC object: retroreflector on the lander) (`blue-ghost-1`) | CLPS: past landing | SLDEM2015_256 (118 m) | medium | SLDEM2015_256 (118 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.8 MB |
| IM-2 Athena lander (CLPS; south-polar, Mons Mouton) (`im-2-athena`) | CLPS: past landing | LDEM_80S_20M (20 m) | fine | LDEM_80S_20M (20 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.9 MB |
| Artemis III candidate region 'Mons Mouton': representative point (IAU centre of Mons Mouton) (`artemis3-region-mons-mouton-representative`) | Artemis: candidate | LDEM_80S_20M (20 m) | fine | LDEM_80S_20M (20 m) 100 % | off | 0, 2, 10 m | none | no | none | 4.5 MB |

| Site | Sun visible at 2 m | Longest time without the Sun | Sun-visible hours per complete lunar day: least, median, most | Earth visible at 2 m | Landing windows for `example-standard`: number, share of the judged range | Warnings in the package |
|---|---|---|---|---|---|---|
| Shackleton crater rim crest | 76.9 % | 192 h | 353, 555, 657 h | 52.4 % | 15, 19.6 % | none |
| de Gerlache crater rim crest | 84.7 % | 257 h | 418, 663, 711 h | 57.3 % | 21, 33.2 % | none |
| Mons Malapert (Malapert massif) summit | 68.7 % | 340 h | 368, 445, 625 h | 80.9 % | 27, 28.6 % | none |
| Apollo 11 (Lunar Module Eagle descent stage) | 50.5 % | 355 h | 353, 354, 355 h | 100.0 % | 25, 16.3 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Apollo 12 (Lunar Module Intrepid descent stage) | 50.7 % | 354 h | 355, 356, 357 h | 100.0 % | 25, 16.5 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Apollo 14 (Lunar Module Antares descent stage) | 49.8 % | 360 h | 348, 349, 351 h | 100.0 % | 25, 15.6 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Apollo 15 (Lunar Module Falcon descent stage) | 48.1 % | 375 h | 334, 338, 341 h | 100.0 % | 25, 13.9 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Apollo 16 (Lunar Module Orion descent stage) | 50.4 % | 357 h | 351, 353, 355 h | 100.0 % | 25, 16.2 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Apollo 17 (Lunar Module Challenger descent stage) | 48.5 % | 370 h | 339, 341, 342 h | 100.0 % | 25, 14.3 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Surveyor 1 lander | 50.5 % | 355 h | 353, 354, 356 h | 100.0 % | 25, 16.3 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Chang'e 3 lander | 50.8 % | 358 h | 351, 357, 362 h | 100.0 % | 25, 16.6 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Chang'e 4 lander | 49.0 % | 364 h | 344, 350, 357 h | 0.0 % | 0, 0.0 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Chang'e 5 lander | 50.7 % | 359 h | 351, 357, 362 h | 100.0 % | 25, 16.5 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Chang'e 6 lander | 49.5 % | 360 h | 348, 353, 360 h | 0.0 % | 0, 0.0 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| Chandrayaan-3 Vikram lander | 48.8 % | 382 h | 326, 340, 357 h | 100.0 % | 25, 14.6 % | terrain: the site is served by LDEM_60S_60M with 60 m pixels (resolution class medium); relief narrower than about 120 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| SLIM lander | 48.4 % | 370 h | 338, 339, 342 h | 100.0 % | 25, 14.2 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| IM-1 Odysseus lander (CLPS) | 40.5 % | 450 h | 258, 278, 309 h | 100.0 % | 25, 6.3 % | none |
| Blue Ghost Mission 1 lander (CLPS; LROC object: retroreflector on the lander) | 50.2 % | 357 h | 352, 354, 356 h | 100.0 % | 25, 16.0 % | terrain: the site is served by SLDEM2015_256 with 118 m pixels (resolution class medium); relief narrower than about 237 m is not in the horizon, and nearby obstacles of that size cannot be shown |
| IM-2 Athena lander (CLPS; south-polar, Mons Mouton) | 47.7 % | 412 h | 272, 328, 380 h | 82.1 % | 23, 10.7 % | none |
| Artemis III candidate region 'Mons Mouton': representative point (IAU centre of Mons Mouton) | 34.0 % | 549 h | 110, 257, 298 h | 58.5 % | 12, 2.9 % | none |

## Limits

- Shares and longest outages describe this 24-month window only; they are not multi-year averages.
- Landing windows hold for the stated example requirements only; the tool reports when a stated requirement holds, it does not know what a mission needs. Landings later than the end of the window minus the mission duration cannot be judged.
- The uncertainty band shows what follows from the stated height-error model: per azimuth the horizon is raised and lowered by the angle that height error spans at the distance of the limiting terrain. Every elevation product is built from LOLA returns, so an error common to all of them is in no band. The landing-circle survey over 13 points is not a probability.
- The sites of the curated list other than the project sites carry no uncertainty band: the height-error model was measured on the polar products, and where a site is served by the 118 m product it is unresolved relief, not height error, that limits the horizon. Their packages carry the core's resolution warning.
- The site pairs say when at least one of two sites sees the body; they do not say that power or data can be moved between the sites.
- Where an event is set by terrain closer than about 1 km, the 20 m elevation grid, not the method, limits the accuracy, and the event time can be off by hours. The column on near terrain counts those events.
- Event times are numerically exact to 0.25 s for the given horizon profile; that is not their physical accuracy.
- The direct-link figures are geometric: a station above the lunar terrain horizon and the site above the station's elevation limit. No link budget, no azimuth-dependent station masks, no scheduling, no multipath near the lunar horizon. A relay need of 2 means that for part of the time no ground station at all can be reached.
- A countdown marked 'at least' has no set inside the computed window.
- The shares of time above are cut by the terrain only. Eclipses of the Sun by the Earth are listed per site (opaque Earth, no atmosphere) and are in the package as the windows 'sun_eclipsed_by_earth', 'sun_totally_eclipsed_by_earth' and 'sun_lit'.
