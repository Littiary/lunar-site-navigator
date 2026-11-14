# Validation

Independent checks of the science core. Each check has a threshold file that is written and committed before the comparison is run and is not edited afterwards.

## `card/` — the validation card

`card/validation_card.md` (for readers) and `card/validation_card.json` (for the web page and the Unreal scene) list every check of the ephemeris, time and event layer: what was compared, against which source, the threshold and where it was fixed, the measured difference, pass or fail, and what is **not** validated. `python -m validation.card.build` recomputes every number from the stored reference data and the code; `tests/test_card.py` fails if the committed card and a fresh build disagree.

## `sites/` — end-to-end results for the south-polar site records, and the published packages

`python -m validation.sites.run data/sites/sites.json --publish` runs the whole pipeline (LOLA terrain horizon, direction table, events, windows, eclipses, ground-station windows, countdowns) for the site records of the data stream, validates the packages against the contract and publishes them in [`packages/`](../packages/README.md) at the repository root, where the web pages and the Unreal scene read them. `packages/README.md` is written by the same command and names the commit, the terrain and kernel versions and every package id. `sites/scenario.json` is the input; `sites/results/site_summary.md` and `.json` summarise the results per site and observer height. `tests/test_published_packages.py` checks that the published packages pass the contract validator as they are.

The published packages are regenerated, never edited by hand, and are republished in the same commit as any change that alters results. These results are **unverified** against any independent illumination product; the summary says which events are set by terrain closer than 1 km, where the 20 m elevation grid limits the accuracy.

## `landers/` — published records of real lunar landers

**What is compared.** Four missions, each with the published time and place of a real event and what the source says about the Sun or the Earth at that moment. Every published value is in `landers/cases.json` as printed, with its source URL, retrieval time, page checksum, printed precision and whether the source calls it approximate. `cases.json` and `thresholds.json` were committed before the core was run on these cases (commit eaf5634). The test is **not blind**: research before the hackathon had compared some of these values with Horizons, so the thresholds follow fixed rules derived from each source's printed precision and wording.

**Result** (`landers/results/validation_table.md`): 20 of 20 pass/fail checks pass; 5 further comparisons are reported without a verdict.

| Case | What the source published | Result |
|---|---|---|
| Apollo 11 landing, 20 July 1969 20:17:39 UT | Sun and Earth altitude, azimuth and sub-points (Apollo Lunar Surface Journal, computed from the Nautical Almanac, printed to 0.01°) | 8 angles agree within 0.035° (threshold 0.05°) |
| Apollo 16 landing, 21 April 1972 02:23:35 UT | The same eight angles; and the Sun angle the launch window was targeted for (NASA SP-4029: 11.9°) | 8 angles within 0.015°. At the planned landing time the core gives 11.88° (threshold 0.1°); the landing slipped by 5 h 45 min and the Sun was then at 14.76°: a change of 2.88°, while the NASA table still lists 11.9° |
| Blue Ghost Mission 1, end of the lunar day, 16 March 2025 | "lunar sunset on March 16"; 346 hours of daylight operations after the landing at 08:34 UTC on 2 March | Computed last light (smooth local sphere) 16 March 20:54:55 UTC: on the published day, and after the end of recorded daylight (18:34 UTC), as it must be. The 2.3 h between them is not explained: local terrain is not in the project's data for this site |
| Chandrayaan-3, lunar night, September 2023 | In sleep mode on 4 September; awakening awaited "around September 22" (ISRO) | With the LOLA terrain horizon: last light 4 September 07:14:41 UTC, first light 20 September 00:05:04 UTC, 66 h before the end of the expected wake-up day, as it must be. ISRO published no sunrise time; its wake-up date is 1.8 days after the computed sunrise |

**Limits.**

* The Apollo angles are another computation (a 1960s almanac), not a measurement; what the missions contribute is the real time and place. The comparison uses the source's own site coordinates and its definition without parallax; with parallax the Earth stands 0.21° lower at the Apollo 11 site, which is reported, not judged.
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
* The package does not yet carry the power line as a time series (a contract field is needed); it carries the eclipse windows and metrics.

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
