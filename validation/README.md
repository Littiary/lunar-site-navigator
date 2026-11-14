# Validation

Independent checks of the science core. Each check has a threshold file that is written and committed before the comparison is run and is not edited afterwards.

Setup from a fresh clone, where the downloaded inputs go (never into the repository) and what the tests do without them: [`docs/setup.md`](../docs/setup.md). All commands below are run from the repository root with the environment that `python scripts/bootstrap.py` creates.

## `card/` — the validation card

`card/validation_card.md` (for readers) and `card/validation_card.json` (for the web page and the Unreal scene) list every check of the ephemeris, time and event layer: what was compared, against which source, the threshold and where it was fixed, the measured difference, pass or fail, the main limit of the check in one sentence (`limit` in the JSON file), and what is **not** validated. `python -m validation.card.build` recomputes every number from the stored reference data and the code (the terrain and image rows are read from their stored result tables); `tests/test_card.py` fails if the committed card and a fresh build disagree.

The card has 32 checks; 31 pass and one fails: the comparison with an LROC image strip (`lro_images/`, below). The failed check stays on the card as `FAIL` with its cause; a viewer that shows the card must show it too.

## `sites/` — end-to-end results for the south-polar site records, and the published packages

`python -m validation.sites.run data/sites/sites.json --publish` runs the whole pipeline of the current contract over 24 months for the curated site list of the data stream (`data/sites/curated_sites.json`, 20 sites) in three scenarios:

* `sites/scenario.json`: the three project sites, with the 5 m near field, six observer heights, the uncertainty band of the sourced height-error model, the landing-circle survey, a planned landing, a fourth terrain patch read from the 5 m raster, and the site pairs;
* `sites/scenario_curated_polar.json`: the four other sites that a LOLA polar product serves (Chandrayaan-3, IM-1, IM-2 and one representative point of an Artemis III candidate region), without the near field, with three observer heights and the uncertainty band of the same model, which the data stream measured on those products;
* `sites/scenario_curated.json`: the 13 past landing sites that the latitude-longitude product serves, without the near field, with three observer heights and without a stated uncertainty. No terrain height error has been measured for that product, so their events carry neither a time range nor `terrain_quality`.

Every package holds the terrain horizon with its obstacles and terrain source, the direction series, events, windows, countdowns, eclipses and the lit fraction of the Sun, ground-station windows, what each obstacle costs, the lunar-day calendar, landing windows for the three example requirements, the mast-height trade and terrain patches for drawing. The command validates the packages against the contract and publishes them in [`packages/`](../packages/README.md) at the repository root, where the web pages and the Unreal scene read them. `packages/README.md` is written by the same command and names the commit, the terrain and kernel versions, every package id and, for every site, which elevation products served it, whether the near field was on and which options its package carries. `sites/results/site_summary.md` and `.json` summarise the project sites per observer height, put their 24-month numbers before and after the 5 m near field side by side (the run without the near field is computed for that purpose and not published) and list all 20 sites. `tests/test_published_packages.py` checks that the published packages pass the contract validator as they are and carry what the README says.

The published packages are regenerated, never edited by hand, and are republished whenever a change alters results (the code change is committed first, the regenerated packages in the commit that follows, so that their provenance names a clean commit). The method behind them reproduces the published LOLA illumination maps on terrain of the same resolution (`pgda/`), but the numbers of these three sites themselves have no independent counterpart; the summary says which events are set by terrain closer than 1 km, where the 20 m elevation grid limits the accuracy.

## `pgda/` — terrain-dependent results versus the published LOLA illumination maps

**What is compared.** The share of time, over one 18.6-year nodal cycle at hourly steps, during which any part of the Sun's disc, and any part of the Earth's disc, is above the terrain horizon. The reference is an independent computation by the LOLA Science Team at NASA Goddard (Mazarico et al. 2011), published as 60 m maps of the south pole through the Planetary Geodesy Data Archive: `AVGVISIB_85S_060M_201608`, `..._EARTH` and the permanent-shadow map `LPSR_85S_060M_201608`. Their labels define the values exactly as that share. This checks the whole terrain chain at once: reading the elevation model, the horizon, the ephemeris and the disc test.

**Points.** 100 pixel centres of the published grid, chosen from the elevation model alone by a seeded rule before any map value was read (`points.json`): 33 ridges and rims, 33 floors, 31 plains and slopes, and the three site records. Thresholds in `thresholds.json` (commit d044186).

**Result** (`pgda/results/validation_table.md`), run A, the like-for-like run on the 60 m LOLA product, observer on the surface:

| Quantity | Threshold | Sun | Earth |
|---|---|---|---|
| Correlation over the 100 points | at least 0.90 | 0.9973 | 0.9993 |
| Median absolute difference | at most 0.05 | 0.0006 | 0.0004 |
| Median signed difference | within 0.02 | +0.0000 | +0.0000 |
| 10th to 90th percentile of the difference | reported | -0.004 to +0.007 | -0.002 to +0.001 |
| Largest absolute difference | reported | 0.079 | 0.044 |
| Points beyond 0.05 / 0.10 / 0.20 | reported | 2 / 0 / 0 | 0 / 0 / 0 |

Permanent shadow: 98 points compared (2 on a boundary left out), agreement 100 %; all 14 points published as permanently shadowed are never lit in our period, and no other point is.

**How comparable the two are.**

| Aspect | Published maps | Our run A | Effect |
|---|---|---|---|
| Quantity | share of timesteps lit "by any fraction" of the disc | the same (upper limb above the horizon) | none |
| Light source | finite disc | finite disc | none |
| Time step | hourly | hourly | none |
| Period | one nodal cycle of about 18.6 years; dates not stated | 2020-01-01 plus 6798.38 days | a second cycle starting 2000-01-01 changes the share by at most 0.001 (Sun) and 0.005 (Earth) at the 10 points tried |
| Observer height | not stated | 0 m | at 2 m our Sun shares are higher by +0.013 on average, at 0 m by +0.002: the maps behave like a surface-level product |
| Elevation model | LDEM_85S_060M of 2016, 60 m | LDEM_60S_60M V2.0, 60 m | not separable from the method; part of the 0.08 largest difference |
| Location | value of a 60 m pixel | horizon computed at the pixel centre | none at this resolution |

**Where the differences are.** Six of the 100 points differ by more than 0.02 in the Sun share (largest 0.079). Their cause was not traced: terrain closer than 1 km sets a somewhat larger part of their horizon (median 50 % of the azimuths against 34 % for the other points), which fits a difference between the two 60 m elevation models, but the model of 2016 that the reference used is not available to test this.

**Resolution effect (run B, reported, not judged).** With the terrain the tool actually uses (20 m near the pole) the median difference stays at -0.000 (Sun) and +0.000 (Earth), but the mean drops to -0.012 and -0.011, 4 Sun points and 3 Earth points differ by more than 0.10, and the largest differences are 0.18 and 0.32. At the three site records, which sit on crests, the 20 m terrain gives a Sun share lower by 0.075 in the median. Finer terrain resolves small obstacles that a 60 m grid smooths away, so crests come out less lit; this is a property of the data, not a disagreement between the methods.

**Limits.**

* The like-for-like run shows that the method reproduces an independent computation on terrain of the same resolution. It does not show that 60 m, or 20 m, terrain is the truth: both sides rest on LOLA elevation data.
* 100 points; with that number a correlation is known to about ±0.04, and the many points in permanent shadow raise it. It is therefore also given per stratum in the table of results.
* The published maps are long-term shares. They do not test individual rise and set times.
* The period, observer height, disc sampling and horizon settings of the reference are not stated by its sources.

## `lro_images/` — sunlit or shadowed state against dated LROC images

**What is compared.** Whether a point is sunlit or in shadow at the moment a Lunar Reconnaissance Orbiter Camera image was taken: the state the terrain horizon gives (sunlit if at least half of the Sun's disc is above the horizon at the surface) against the image. Two cases, with the reading rule and the criteria committed before any computation and before the image was downloaded (`lro_images/cases.json`, commit fb05da0). `python -m validation.lro_images.fetch` downloads the image to the data root, outside the repository; `files.json` records its URL, checksum and retrieval time, and a download that differs from that record is refused.

**Result** (`lro_images/results/validation_table.md`): 3 of 4 registered checks pass, 1 fail, 0 not decided.

* **South pole, 18 May 2022, 14:40:49 UTC (NAC M1407524099).** The camera team marks the pole, just inside the rim of Shackleton crater, as "now in shadows". Our state: shadow (visible fraction of the Sun 0.000; upper limb -8.794°, centre -9.057° against a horizon set by terrain 0.12 km away): **PASS**.
* **Nadir strip across the pole, 13 December 2010, 02:34:25 UTC (NAC M146846913L).** State read from the calibrated browse image by a fixed rule (averaged to 20 m, Otsu threshold, every pixel within 300 m must agree) at points every 500 m along three rows: 298 of 366 points could be read (68 lie within 300 m of a shadow edge or outside the image); our state agrees with the image at 266 of them (89.3 %; criterion 90 %): **FAIL**. Image sunlit and ours sunlit 6, image shadow and ours shadow 260, image sunlit but ours shadow 0, image shadow but ours sunlit 32.
  Cause, looked for after the result: all 32 disagreements are points the image rule reads as shadow and we call sunlit. There the image is dim, not black (brightness 6 to 37 of 255, median 23, against 3 in agreed shadow), and our Sun is only +0.02° to +0.46° above the terrain horizon: ground lit at a grazing angle. One brightness threshold for the whole image (69.5) cannot tell that from shadow. Threshold-free, a point we call sunlit is brighter in the image than a point we call shadow with probability 0.996. That number was computed after the fact and does not turn the failed check into a pass.
* **Sub-solar point at both image times** against the values printed on the LROC data pages (0.01° printed): largest difference 0.004° (criterion 0.02°).

**Limits.**

* The first case rests on the camera team's own reading of its image. The pole lies just inside the crater rim and the terrain that hides the Sun is only 0.12 km away, so the result depends on where the pole falls on the 20 m elevation grid to about that distance.
* The second case reads a lossy browse product, georeferenced from four corners that the data page prints to 0.01° (300 m in latitude), without a camera model. It can test broad sunlit and shadowed areas, not where a shadow edge lies; that is why points near an edge are not judged.
* Two images, both near Shackleton crater, both with the Sun within half a degree of the horizon.

## `landers/` — published records of real lunar landers

**What is compared.** Eight cases from eight missions (six Apollo landings, Blue Ghost Mission 1, Chandrayaan-3), each with the published time and place of a real event and what the source says about the Sun or the Earth at that moment. Every published value is in `landers/cases.json` and `landers/cases_second_batch.json` as printed, with its source URL, retrieval time, page checksum, printed precision and whether the source calls it approximate. `cases.json` and `thresholds.json` were committed before the core was run on these cases (commit eaf5634); the second batch of four Apollo landings was committed before it was computed (commit af10faa) and is judged by the same, unchanged rules. The test is **not blind**: research before the hackathon had compared some of these values with Horizons, so the thresholds follow fixed rules derived from each source's printed precision and wording.

**Result** (`landers/results/validation_table.md`): 52 of 52 pass/fail checks pass; 13 further comparisons are reported without a verdict.

| Case | What the source published | Result |
|---|---|---|
| Apollo 11 landing, 20 July 1969 20:17:39 UT | Sun and Earth altitude, azimuth and sub-points (Apollo Lunar Surface Journal, computed from the Nautical Almanac, printed to 0.01°) | 8 angles agree within 0.035° (threshold 0.05°) |
| Apollo 16 landing, 21 April 1972 02:23:35 UT | The same eight angles; and the Sun angle the launch window was targeted for (NASA SP-4029: 11.9°) | 8 angles within 0.015°. At the planned landing time the core gives 11.88° (threshold 0.1°); the landing slipped by 5 h 45 min and the Sun was then at 14.76°: a change of 2.88°, while the NASA table still lists 11.9° |
| Apollo 12, 14, 15 and 17 landings (19 November 1969 06:54:36, 5 February 1971 09:18:13, 30 July 1971 22:16:29, 11 December 1972 19:54:58 UT; times from NASA SP-4029, printed to 1 s) | The same eight angles for each landing (Apollo Lunar Surface Journal, printed to 0.01°) | All 32 angles within the 0.05° threshold; largest differences 0.012°, 0.047°, 0.010° and 0.041° (the largest is the latitude of the sub-Earth point at the Apollo 14 landing) |
| Blue Ghost Mission 1, end of the lunar day, 16 March 2025 | "lunar sunset on March 16"; 346 hours of daylight operations after the landing at 08:34 UTC on 2 March | Computed last light (smooth local sphere) 16 March 20:54:55 UTC: on the published day, and after the end of recorded daylight (18:34 UTC), as it must be. The 2.3 h between them is not explained: local terrain is not in the project's data for this site |
| Chandrayaan-3, lunar night, September 2023 | In sleep mode on 4 September; awakening awaited "around September 22" (ISRO) | With the LOLA terrain horizon: last light 4 September 07:14:41 UTC, first light 20 September 00:05:04 UTC, 66 h before the end of the expected wake-up day, as it must be. ISRO published no sunrise time; its wake-up date is 1.8 days after the computed sunrise |

**Limits.**

* The Apollo angles are another computation (a 1960s almanac), not a measurement; what the missions contribute is the real time and place. The comparison uses the source's own site coordinates and its definition without parallax; with parallax the Earth stands 0.21° lower at the Apollo 11 site, which is reported, not judged.
* Six of the eight cases are Apollo landings checked against one source computed with one almanac; they test Sun and Earth directions at a known time and place, not event times and not terrain.
* No operator published a sunrise or sunset clock time for its site. Operational records only bound the computed events from one side: they can show the core wrong, they cannot confirm an event time.
* Only the Chandrayaan-3 case uses terrain (60 m grid). Its sunrise is set by terrain 0.5 km from the lander, where the grid limits the accuracy.
* The reference frame of the LROC coordinates is not stated on the two LROC pages (unverified; assumed mean-Earth/polar-axis).
* UTC before 1972 is handled by the leap-second kernel with a constant offset; the error is about one second, far below the thresholds.

## `eclipse/` — eclipse of the Sun by the Earth, 14 March 2025

**What is compared.** What the Earth sees as a lunar eclipse is, at a lunar site, an eclipse of the Sun by the Earth: solar power drops or stops although the Sun is high above the terrain. `core/lsncore/events/eclipse.py` computes the contacts at a site and the eclipse-aware power line (the fraction of the Sun's disc that is above the terrain horizon and not hidden by the Earth). It is checked on the eclipse of 14 March 2025 at the Blue Ghost Mission 1 landing point against (a) the contact times the operator predicted for its site, printed to the minute, and (b) the whole-Moon contacts of the NASA GSFC chart, which every point of the Moon must respect. Cases and thresholds were committed before the first run (commit a8bbc5a); the test is not blind (see `eclipse/thresholds.json`).

**Result** (`eclipse/results/validation_table.md`): 8 of 8 pass/fail checks pass.

| Contact at the site | Operator's prediction (UTC) | Core (UTC) | Difference |
|---|---|---|---|
| Partial eclipse begins (C1) | 05:00 | 05:00:42 | +0.7 min |
| Totality begins (C2) | 06:18 | 06:17:23 | −0.6 min |
| Totality ends (C3) | "approximately 2 hours and 16 minutes" later | 08:34:25 (137.0 min of totality) | +1.0 min in duration |
| Partial eclipse ends (C4) | 09:52 | 09:51:10 | −0.8 min |

Threshold 2 min per contact and 3.5 min for the duration. The site contacts lie inside NASA's whole-Moon contacts with margins of 9 to 63 min. At the site the Sun is completely hidden for 2.28 h and partly hidden for 4.84 h; from the Earth, totality of the same eclipse lasts 65 min: the loss of sunlight depends on where on the Moon the lander stands.

**Limits.**

* The Earth is an opaque disc of its equatorial radius. Its atmosphere is not modelled: the real edge of the shadow is soft over about a minute, and during totality some red light still reaches the surface. The power line is therefore 0 in totality, where a real panel would see a very small, non-zero flux.
* The operator's times are predictions; its images of the eclipse are timed to about half an hour, which is too coarse to test contacts. No measured power curve was found.
* The operator labels its predicted times "CST". They are read as local Texas time on that date (UTC−5); read as UTC−6 the eclipse would end after the Moon has left the Earth's penumbra, which the NASA chart excludes.
* One eclipse, one site.
* The package carries the power line as the series `lit_fraction` of the Sun, sampled at the step of the series (one hour in the published packages), next to the eclipse windows and metrics. Between the Sun and the Earth the lit fraction is computed in the plane tangent to the sky at the Sun; an earlier version took differences of azimuth and elevation instead, which was wrong by up to 0.011 of the disc with the Sun 60° high and by less than 0.001 at the polar sites.

## `stations/` — ground-station geometry versus JPL Horizons

**What is compared.** The two conditions of a direct link between a lunar site and a ground station: how high the lunar site stands above the station's horizon (Earth end), and where the station appears in the sky of the lunar site (Moon end). The core computes them from the NAIF station and Earth orientation kernels (`core/lsncore/ephem/stations.py`); Horizons computes them with a Deep Space Network station as observer, and with the station's coordinates as a target seen from the Moon. Thresholds and queries were committed before any response was fetched (commit 6f74153).

**Result** (`stations/results/validation_table.md`): 12 of 12 cases pass, 3468 rows (three stations, a south-polar and an equatorial lunar site, 14 to 16 November 2026 at 10 minutes).

| Quantity | Threshold | Largest difference found |
|---|---|---|
| Earth end, observer at the station | 1″ | 0.42″ |
| Moon end, observer at the lunar site | 1″ | 0.19″ |
| Earth end through the fast path of the link windows (elevation) | 0.012° | 0.00009° |
| Moon end through the fast path | 1″ | 0.21″ |

The remaining 0.2″ to 0.4″ are larger than for the Sun and the Earth's centre (0.005″) and were not traced further; they are consistent with small differences in Earth orientation data and in how the two programs treat the Earth's rotation during the light time.

**What is built on it** (`core/lsncore/events/links.py`): per-station windows (station above the lunar terrain horizon, and the site at least 10° above the station's horizon; 6° to receive: the generic elevation limits of DSN 810-005 module 301), the network window of the three complexes, and a relay-need level that separates outages a second station would close from outages caused by lunar terrain.

**Limits.**

* Only the geometry is validated against an external source. The windows themselves are tested on cases with a known answer, not against a mission's contact schedule.
* Station masks are single elevation limits: azimuth-dependent horizon masks of the stations, the 13.5° limit for high-power transmit, the keyhole near the zenith, weather and scheduling are not modelled.
* No link budget, antenna pattern or frequency; near the lunar horizon a real link suffers from multipath, and the lunar-end mask is 0° here.
* Three Deep Space Network complexes only.
* Dates after 8 February 2027 use the long-term Earth orientation kernel, whose rotation angle is a prediction; the effect on a station rise or set is of the order of a second.

## `horizons/` — Sun and Earth directions versus JPL Horizons

**What is compared.** The apparent azimuth, elevation, angular diameter and distance of the Sun and of the Earth, seen from seven points on the lunar reference sphere, computed by the core (`core/lsncore/ephem/`) and by the JPL Horizons system (observer table, user-defined site on body 301).

**Why this is an independent check.** Horizons is separate software run by the JPL Solar System Dynamics group. It uses the DE441 ephemeris and its own implementation of the lunar mean-Earth frame, light time, stellar aberration and light bending. The core uses SPICE with DE440 and NAIF frame kernels. Agreement tests the whole chain apart from terrain: ephemeris, body-fixed frame, time scales, aberration correction, site vector and local East-North-Up projection.

**Cases.** 7 sites × 2 bodies × 2 time spans = 28 queries, 95 676 rows: the hackathon weekend at a 10-minute step and one 18.6-year nodal cycle (2026-11-01 to 2045-07-01) at a 25-hour step. Definitions in `cases.json`.

**Result** (`results/validation_table.md`, regenerated by `python -m validation.horizons.compare`):

| Quantity | Threshold | Largest difference found |
|---|---|---|
| Direction, exact per-site path | 1″ | 0.005″ |
| Direction, site-independent direction table | 1″ | 0.099″ |
| Angular diameter | 0.1″ | 0.0006″ |
| Distance | 1 km | 0.0042 km |
| TDB − UTC | 0.002 s | 0.000038 s |

The exact path agrees with Horizons at the level of Horizons' printed resolution (0.0036″). The direction table differs by up to 0.1″ for the Earth because it applies light time and stellar aberration for an observer at the Moon's centre instead of at the site; this is the measured price of keeping the table independent of the site.

**Files.**

| File | Role |
|---|---|
| `thresholds.json` | Acceptance thresholds, fixed before the comparison |
| `cases.json` | Sites, time spans and query parameters |
| `fetch.py` | Sends the queries one at a time; stores each response once |
| `raw/*.json` | Response bodies exactly as received (never edited) |
| `raw/*.meta.json` | Full URL, parameters, retrieval time (UTC), HTTP status, SHA-256, API version |
| `compare.py` | Recomputes every row with the core and writes `results/` |
| `../tests/test_horizons.py` | The same comparison as a test; also checks that the raw files are unchanged |

**Limits of this check.**

* It says nothing about terrain: Horizons has no terrain, and elevation here is relative to the horizontal plane of the 1737.4 km sphere.
* Both sides use JPL ephemerides of the same family (DE440, DE441), so an error common to that family would not show.
* UTC time tags for dates after the last announced leap second assume no further leap seconds, on both sides.
* The Earth's angular diameter is the equatorial width; the flattening of the disc (0.3 %) is not modelled.
* The sites are test points, not catalogued landing sites.

## `horizons_rts/` — rise and set times versus JPL Horizons

**What is compared.** Sunrise and sunset times on a smooth sphere (no terrain) from four points, found by the event finder (`core/lsncore/events/`), against the rise/transit/set search of Horizons (1-minute search step, "true visual horizon" mode). The event is the Sun's upper limb crossing the horizon of the 1737.4 km sphere; one site is 1 km above the sphere, where the horizon dips by 1.94°.

**Result** (`horizons_rts/results/validation_table.md`): 16 events over 60 days, none unmatched. Horizons minus core lies between +2 s and +57 s for every event. A Horizons row is the first one-minute search step at which the condition holds, so a difference between 0 and 60 s is what exact agreement looks like. Threshold, fixed before the data was fetched: 120 s (the accuracy Horizons states for this mode).

**Limits.** Smooth sphere only; the Sun only (Horizons does not state which point of the Earth's disc its rise and set refer to); the reference resolves one minute, so this check cannot confirm the finder's own 0.25 s numerical accuracy, which is covered by the analytic tests in `core/tests/events/`.

Reference: Giorgini, JD and JPL Solar System Dynamics Group, NASA/JPL Horizons On-Line Ephemeris System, https://ssd.jpl.nasa.gov/horizons/, data retrieved 2026-Nov-14.
