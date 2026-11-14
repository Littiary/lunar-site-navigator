# End-to-end results: three south-polar candidate points

Generated 2026-11-14T15:36:34Z by `validation/sites/run.py`. Do not edit by hand.

- Window: 2026-11-14T00:00:00.000Z to 2028-11-14T00:00:00.000Z (UTC). Countdowns count from the planned landing time of the scenario, 2027-01-10T00:00:00.000Z.
- **Inputs chosen by the team, not properties of the data or of a mission**: the three example requirements on the landing time (`docs/contract/presets/requirements.json`; they are not requirements of NASA or of any mission), a horizon error of 0.05 deg, a terrain height error of 1 m, a landing circle of 100 m radius sampled at 13 points, and the planned landing time. The numbers that follow from them say what would hold if they were true.
- Terrain: `lola:LDEM_80S_20M@V2.0+LDEM_60S_60M@V2.0`, search radius 300 km, azimuth step 0.25 deg. Ephemeris: kernel set `bfe870fccfa5`, direction table `dirtab-fbc51d64e42ab803`.
- Sun visible = any part of the disc above the terrain horizon. Earth visible = centre of the disc above the terrain horizon.
- The points are project candidates derived from LOLA and IAU crater outlines by the data stream; **they are not official landing sites**.
- **Status.** The method behind these numbers reproduces the published LOLA illumination maps of NASA Goddard at 100 points on terrain of the same resolution (`validation/pgda`), and the ephemeris is validated (see the validation card). Of two dated LROC images, the shadowed state of the south pole agrees; the comparison along an image strip fails its registered criterion (89.3 % agreement against 90 %; the image rule reads dimly lit ground as shadow), see `validation/lro_images`. The numbers of these three sites themselves have no independent counterpart: they use the finer 20 m terrain, a 24-month window and several observer heights, and no source gives rise and set times for these points.

## Shackleton crater rim crest

89.80531 deg S, -154.23109 deg E, terrain height 1701.1 m above the 1737.4 km sphere. Package `site-a4d3f54375701349`, status `ok`. Terrain: the height at the site is read from LDEM_80S_20M (20 m pixels, resolution class fine); the horizon at the default observer height is set by LDEM_80S_20M (20 m) in 100.0 % of the azimuths. Sun centre elevation -1.72 to 1.71 deg; Earth centre elevation -7.28 to 6.44 deg.

| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |
|---|---|---|---|---|---|---|---|---|---|
| 0 m | 66.9 % | 276.2 h | 141 | 41 | 22.84 d | 52.4 % | 334.2 h | 13.78 d | 44 % |
| 1 m | 76.1 % | 198.7 h | 164 | 38 | 22.85 d | 52.4 % | 334.2 h | 13.78 d | 25 % |
| 2 m | 78.0 % | 188.3 h | 174 | 44 | 22.85 d | 52.4 % | 334.1 h | 13.78 d | 22 % |
| 5 m | 80.6 % | 167.8 h | 172 | 42 | 22.85 d | 52.5 % | 334.1 h | 13.78 d | 18 % |
| 10 m | 83.2 % | 134.0 h | 172 | 42 | 22.86 d | 52.5 % | 334.0 h | 13.78 d | 13 % |
| 20 m | 86.3 % | 126.4 h | 162 | 30 | 22.88 d | 52.5 % | 333.9 h | 13.78 d | 10 % |

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

**What the terrain costs (observer 2 m).** Over a smooth sphere through the site the Sun would be visible for 10056 h of the window; the terrain takes 1091 h and gives 4724 h (terrain below the smooth horizon), leaving 13690 h. Earth: 8625 h, minus 0 h, plus 576 h, leaving 9201 h.

| Obstacle of the Sun (largest cost first) | Costs | Share of the lost time | Highest point: azimuth, elevation, distance | Within 1 km |
|---|---|---|---|---|
| 1 | 384 h | 35 % | 349.5 deg, +2.81 deg, 0.7 km | yes: depends on single pixels of the elevation model |
| 2 | 240 h | 22 % | 344.0 deg, +3.07 deg, 0.6 km | yes: depends on single pixels of the elevation model |
| 3 | 214 h | 20 % | 337.5 deg, +3.02 deg, 0.4 km | yes: depends on single pixels of the elevation model |

**Lunar days.** 25 in the window, 23 of them complete. Per complete lunar day (least, median, most): Sun visible 357, 571, 657 h; longest stretch without the Sun 49, 66, 121 h; Earth visible 321, 377, 413 h.

| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |
|---|---|---|---|---|
| `example-standard`: Earth in view at landing and 10 Earth days of unbroken sunlight from landing | 15 | 19.8 % | 13.2 d, 10.9 d | 2027-01-10: not feasible; next window in 0.4 d |
| `example-strict`: Earth in view at landing, 14 Earth days of unbroken sunlight from landing, Earth in view for at least half of those 14 days | 14 | 10.3 % | 7.5 d, 6.0 d | 2027-01-10: not feasible; next window in 0.4 d |
| `example-loose`: Earth in view at landing and 5 Earth days of unbroken sunlight from landing | 22 | 27.9 % | 15.6 d, 12.0 d | 2027-01-10: not feasible; next window in 0.4 d |

**If the horizon were wrong by the stated amount** (0.05 deg everywhere plus what 1 m of terrain height error gives at the distance of the limiting terrain: 0.050 to 0.805 deg, median 0.052 deg): Sun visible for certain 13315 h, possibly 14022 h (707 h uncertain); Earth for certain 9160 h, possibly 9242 h (83 h uncertain).

**Inside the stated landing circle** (100 m radius, 13 points, each with its own terrain horizon): Sun visible 13690 h at the site; 8396 h least, 10050 h median, 13944 h most over the points. Earth: 9201 h at the site; 8981, 9199, 9201 h.

| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |
|---|---|---|---|---|
| 0 m | 11744 h | +0 h | 276.2 h | 295 h |
| 1 m | 13344 h | +1601 h | 198.7 h | 347 h |
| 2 m | 13690 h | +1946 h | 188.3 h | 357 h |
| 5 m | 14141 h | +2397 h | 167.8 h | 378 h |
| 10 m | 14588 h | +2844 h | 134.0 h | 413 h |
| 20 m | 15138 h | +3395 h | 126.4 h | 424 h |

## de Gerlache crater rim crest

88.66410 deg S, -68.41044 deg E, terrain height 1815.2 m above the 1737.4 km sphere. Package `site-f5debe0fd2f3cdf7`, status `ok`. Terrain: the height at the site is read from LDEM_80S_20M (20 m pixels, resolution class fine); the horizon at the default observer height is set by LDEM_80S_20M (20 m) in 100.0 % of the azimuths. Sun centre elevation -2.85 to 2.88 deg; Earth centre elevation -6.77 to 7.23 deg.

| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |
|---|---|---|---|---|---|---|---|---|---|
| 0 m | 82.1 % | 264.0 h | 70 | 16 | 30.39 d | 57.3 % | 304.6 h | 14.55 d | 24 % |
| 1 m | 83.7 % | 256.9 h | 68 | 7 | 30.40 d | 57.3 % | 304.6 h | 14.55 d | 18 % |
| 2 m | 84.7 % | 256.9 h | 74 | 9 | 30.40 d | 57.3 % | 304.6 h | 14.55 d | 15 % |
| 5 m | 86.3 % | 256.8 h | 80 | 7 | 30.41 d | 57.3 % | 304.5 h | 14.56 d | 9 % |
| 10 m | 88.2 % | 135.4 h | 94 | 10 | 30.44 d | 57.3 % | 304.4 h | 14.56 d | 5 % |
| 20 m | 88.5 % | 135.1 h | 88 | 0 | 30.48 d | 57.4 % | 304.3 h | 14.56 d | 0 % |

Direct link with the Deep Space Network (three complexes; station mask 10 deg for a two-way link, 6 deg to receive; geometry only):

| Observer height | Two-way link possible | Receive possible | Goldstone | Canberra | Madrid | Longest time without a link | Longest time with every station behind lunar terrain | Relay need |
|---|---|---|---|---|---|---|---|---|
| 0 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 297.0 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 1 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 297.0 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 2 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 297.0 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 5 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 296.9 h | 282.8 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 10 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.2 % | 296.9 h | 282.7 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 20 m | 56.5 % | 57.0 % | 25.2 % | 22.7 % | 25.3 % | 296.9 h | 282.6 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |

Eclipses of the Sun by the Earth in the window: 3 (1 total at the site); largest covered fraction of the Sun 1.000; 2027-08-17T05:40:53.672Z to 2027-08-17T08:53:21.797Z; 2028-01-12T02:19:21.327Z to 2028-01-12T05:58:34.452Z; 2028-07-06T16:59:51.796Z to 2028-07-06T19:46:03.983Z.

**What the terrain costs (observer 2 m).** Over a smooth sphere through the site the Sun would be visible for 10929 h of the window; the terrain takes 0 h and gives 3925 h (terrain below the smooth horizon), leaving 14854 h. Earth: 9183 h, minus 0 h, plus 873 h, leaving 10056 h.

**Lunar days.** 25 in the window, 23 of them complete. Per complete lunar day (least, median, most): Sun visible 418, 663, 711 h; longest stretch without the Sun 0, 28, 257 h; Earth visible 347, 413, 443 h.

| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |
|---|---|---|---|---|
| `example-standard`: Earth in view at landing and 10 Earth days of unbroken sunlight from landing | 21 | 33.2 % | 16.7 d, 14.5 d | 2027-01-10: feasible; can slip 14.6 d |
| `example-strict`: Earth in view at landing, 14 Earth days of unbroken sunlight from landing, Earth in view for at least half of those 14 days | 17 | 17.0 % | 9.7 d, 8.5 d | 2027-01-10: feasible; can slip 7.6 d |
| `example-loose`: Earth in view at landing and 5 Earth days of unbroken sunlight from landing | 26 | 39.6 % | 16.7 d, 14.1 d | 2027-01-10: feasible; can slip 14.6 d |

**If the horizon were wrong by the stated amount** (0.05 deg everywhere plus what 1 m of terrain height error gives at the distance of the limiting terrain: 0.050 to 0.478 deg, median 0.051 deg): Sun visible for certain 14635 h, possibly 15092 h (457 h uncertain); Earth for certain 10012 h, possibly 10099 h (88 h uncertain).

**Inside the stated landing circle** (100 m radius, 13 points, each with its own terrain horizon): Sun visible 14854 h at the site; 0 h least, 10326 h median, 14967 h most over the points. Earth: 10056 h at the site; 0, 8959, 10056 h.

| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |
|---|---|---|---|---|
| 0 m | 14401 h | +0 h | 264.0 h | 411 h |
| 1 m | 14690 h | +289 h | 256.9 h | 418 h |
| 2 m | 14854 h | +453 h | 256.9 h | 418 h |
| 5 m | 15143 h | +742 h | 256.8 h | 418 h |
| 10 m | 15470 h | +1068 h | 135.4 h | 456 h |
| 20 m | 15523 h | +1122 h | 135.1 h | 474 h |

## Mons Malapert (Malapert massif) summit

85.98795 deg S, 2.05767 deg E, terrain height 5173.5 m above the 1737.4 km sphere. Package `site-29ad241e86f8307d`, status `ok`. Terrain: the height at the site is read from LDEM_80S_20M (20 m pixels, resolution class fine); the horizon at the default observer height is set by LDEM_80S_20M (20 m) in 100.0 % of the azimuths. Sun centre elevation -5.56 to 5.59 deg; Earth centre elevation -3.10 to 10.59 deg.

| Observer height | Sun visible | Longest time without Sun | Sun rise/set events | of which set by terrain < 1 km away | Time to next Sun set | Earth visible | Longest time without Earth | Time to next Earth set | Horizon set by terrain < 1 km |
|---|---|---|---|---|---|---|---|---|---|
| 0 m | 60.8 % | 369.6 h | 50 | 50 | 22.33 d | 78.9 % | 158.7 h | 17.16 d | 97 % |
| 1 m | 67.6 % | 343.9 h | 54 | 35 | 22.86 d | 80.6 % | 147.4 h | 17.29 d | 78 % |
| 2 m | 72.5 % | 329.8 h | 66 | 43 | 23.14 d | 81.6 % | 141.6 h | 17.40 d | 70 % |
| 5 m | 79.7 % | 306.5 h | 44 | 22 | 25.23 d | 84.5 % | 122.8 h | 17.79 d | 65 % |
| 10 m | 84.8 % | 267.6 h | 58 | 15 | 26.87 d | 91.2 % | 83.8 h | 18.58 d | 40 % |
| 20 m | 86.2 % | 260.6 h | 64 | 5 | 26.87 d | 100.0 % | 0.0 h | at least 674.00 d | 8 % |

Direct link with the Deep Space Network (three complexes; station mask 10 deg for a two-way link, 6 deg to receive; geometry only):

| Observer height | Two-way link possible | Receive possible | Goldstone | Canberra | Madrid | Longest time without a link | Longest time with every station behind lunar terrain | Relay need |
|---|---|---|---|---|---|---|---|---|
| 0 m | 77.3 % | 78.5 % | 32.7 % | 33.2 % | 32.4 % | 144.1 h | 132.7 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 1 m | 78.9 % | 80.2 % | 33.3 % | 34.1 % | 32.9 % | 129.0 h | 111.9 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 2 m | 79.7 % | 81.0 % | 33.5 % | 34.6 % | 33.1 % | 118.9 h | 109.2 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 5 m | 82.8 % | 84.3 % | 34.3 % | 36.6 % | 33.9 % | 96.5 h | 85.5 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 10 m | 89.1 % | 90.9 % | 35.8 % | 40.8 % | 35.2 % | 22.5 h | 12.1 h | 2: interrupted by lunar terrain: relay or waiting needed during those outages |
| 20 m | 94.5 % | 96.5 % | 38.7 % | 42.2 % | 37.8 % | 12.7 h | 0.0 h | 1: interrupted only by station gaps on the Earth |

Eclipses of the Sun by the Earth in the window: 3 (1 total at the site); largest covered fraction of the Sun 1.000; 2027-08-17T05:41:50.859Z to 2027-08-17T08:54:02.578Z; 2028-01-12T02:20:03.045Z to 2028-01-12T05:59:24.608Z; 2028-07-06T17:00:20.858Z to 2028-07-06T19:46:48.046Z.

**What the terrain costs (observer 2 m).** Over a smooth sphere through the site the Sun would be visible for 9499 h of the window; the terrain takes 0 h and gives 3213 h (terrain below the smooth horizon), leaving 12713 h. Earth: 12340 h, minus 0 h, plus 1972 h, leaving 14312 h.

**Lunar days.** 25 in the window, 23 of them complete. Per complete lunar day (least, median, most): Sun visible 379, 457, 686 h; longest stretch without the Sun 23, 122, 187 h; Earth visible 537, 581, 603 h.

| Example requirement (not a requirement of NASA or of any mission) | Landing windows | Share of the judged range that is a feasible landing time | Longest, median window | Planned landing |
|---|---|---|---|---|
| `example-standard`: Earth in view at landing and 10 Earth days of unbroken sunlight from landing | 27 | 32.0 % | 22.4 d, 8.0 d | 2027-01-10: not feasible; next window in 0.8 d |
| `example-strict`: Earth in view at landing, 14 Earth days of unbroken sunlight from landing, Earth in view for at least half of those 14 days | 24 | 21.2 % | 22.4 d, 4.6 d | 2027-01-10: not feasible; next window in 0.8 d |
| `example-loose`: Earth in view at landing and 5 Earth days of unbroken sunlight from landing | 31 | 45.0 % | 22.4 d, 9.2 d | 2027-01-10: not feasible; next window in 0.8 d |

**If the horizon were wrong by the stated amount** (0.05 deg everywhere plus what 1 m of terrain height error gives at the distance of the limiting terrain: 0.050 to 0.759 deg, median 0.235 deg): Sun visible for certain 11810 h, possibly 13537 h (1727 h uncertain); Earth for certain 14088 h, possibly 14552 h (465 h uncertain).

**Inside the stated landing circle** (100 m radius, 13 points, each with its own terrain horizon): Sun visible 12713 h at the site; 9596 h least, 11067 h median, 13510 h most over the points. Earth: 14312 h at the site; 12279, 14028, 14324 h.

| Observer height | Sun visible in the window | Change against the surface | Longest time without the Sun | Sun visible in the least sunlit complete lunar day |
|---|---|---|---|---|
| 0 m | 10662 h | +0 h | 369.6 h | 339 h |
| 1 m | 11853 h | +1191 h | 343.9 h | 364 h |
| 2 m | 12713 h | +2051 h | 329.8 h | 379 h |
| 5 m | 13983 h | +3321 h | 306.5 h | 402 h |
| 10 m | 14871 h | +4209 h | 267.6 h | 441 h |
| 20 m | 15122 h | +4460 h | 260.6 h | 448 h |

## Two sites together

Package `pairs-fa4b9bc4663c9738`. Each site at its default observer height. 'Either' is the share of the window in which at least one of the two sites sees the body.

| Sites | Distance | Sun: each alone | Sun: either | Longest time with the Sun at neither | What the second site adds | Earth: either | Longest time with the Earth at neither |
|---|---|---|---|---|---|---|---|
| Shackleton crater rim crest and de Gerlache crater rim crest | 41 km | 78.0 %, 84.7 % | 97.0 % | 43 h | 2169 h (81 % of the better site's dark time) | 57.3 % | 305 h |
| Shackleton crater rim crest and Mons Malapert (Malapert massif) summit | 127 km | 78.0 %, 72.5 % | 84.4 % | 188 h | 1123 h (29 % of the better site's dark time) | 81.6 % | 142 h |
| de Gerlache crater rim crest and Mons Malapert (Malapert massif) summit | 115 km | 84.7 %, 72.5 % | 90.8 % | 163 h | 1071 h (40 % of the better site's dark time) | 81.6 % | 142 h |

## Limits

- Shares and longest outages describe this 24-month window only; they are not multi-year averages.
- Landing windows hold for the stated example requirements only; the tool reports when a stated requirement holds, it does not know what a mission needs. Landings later than the end of the window minus the mission duration cannot be judged.
- The uncertainty band and the landing-circle survey show what follows from the stated horizon error, height error and circle. The stated numbers are not measured errors of the elevation model, and the survey over 13 points is not a probability.
- The site pairs say when at least one of two sites sees the body; they do not say that power or data can be moved between the sites.
- Where an event is set by terrain closer than about 1 km, the 20 m elevation grid, not the method, limits the accuracy, and the event time can be off by hours. The column on near terrain counts those events.
- Event times are numerically exact to 0.25 s for the given horizon profile; that is not their physical accuracy.
- The direct-link figures are geometric: a station above the lunar terrain horizon and the site above the station's elevation limit. No link budget, no azimuth-dependent station masks, no scheduling, no multipath near the lunar horizon. A relay need of 2 means that for part of the time no ground station at all can be reached.
- A countdown marked 'at least' has no set inside the computed window.
- The shares of time above are cut by the terrain only. Eclipses of the Sun by the Earth are listed per site (opaque Earth, no atmosphere) and are in the package as the windows 'sun_eclipsed_by_earth', 'sun_totally_eclipsed_by_earth' and 'sun_lit'.
