# Validation table: core versus published records of real lunar landers

Generated 2026-11-14T12:30:06Z by `validation/landers/compare.py`. Do not edit by hand.

**52 of 52 pass/fail checks pass; 0 fail; 13 comparisons are reported without a verdict.**
Published values, sources, precision and thresholds are in `cases.json` and `thresholds.json`, committed before the first run (commit eaf5634); the second batch of four Apollo landings is in `cases_second_batch.json` (commit af10faa), under the same rules. The test is not blind: see the disclosure in `thresholds.json`.

## Apollo 11 lunar module landing, 20 July 1969

Terrain: none (smooth sphere); the Sun is more than 10 degrees above the horizon, so terrain does not matter for these angles.

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sun altitude at landing (source's site coordinates) | 10.650 | 10.664 | +0.014 | < 0.05 deg | **PASS** |
| Sun azimuth at landing (difference on the sky) | 88.810 | 88.808 | -0.002 | < 0.05 deg | **PASS** |
| East longitude of the sub-solar point | 102.800 | 102.781 | -0.019 | < 0.05 deg | **PASS** |
| Latitude of the sub-solar point | 1.300 | 1.299 | -0.001 | < 0.05 deg | **PASS** |
| Earth altitude at landing (source's site coordinates) | 59.430 | 59.395 | -0.035 | < 0.05 deg | **PASS** |
| Earth azimuth at landing (difference on the sky) | 272.160 | 272.175 | +0.008 | < 0.05 deg | **PASS** |
| East longitude of the sub-earth point | -7.130 | -7.162 | -0.032 | < 0.05 deg | **PASS** |
| Latitude of the sub-earth point | 1.690 | 1.699 | +0.009 | < 0.05 deg | **PASS** |
| Sun elevation at the actual landing site and time, against the launch-window target | 10.800 | 10.703 | -0.097 |  | reported |
| Earth elevation seen from the actual site (with parallax) against the source's value (without parallax) | 59.430 | 59.224 | -0.206 |  | reported |

- *Sun azimuth at landing (difference on the sky)*: azimuth difference -0.002 deg at altitude 10.7 deg.
- *Earth azimuth at landing (difference on the sky)*: azimuth difference +0.015 deg at altitude 59.4 deg.
- *Sun elevation at the actual landing site and time, against the launch-window target*: The published value is a planned angle; it is not judged..
- *Earth elevation seen from the actual site (with parallax) against the source's value (without parallax)*: Shows the size of the parallax the source leaves out..

## Apollo 16 lunar module landing, 21 April 1972 (landing delayed by about six hours)

Terrain: none (smooth sphere).

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sun altitude at landing (source's site coordinates) | 14.760 | 14.773 | +0.013 | < 0.05 deg | **PASS** |
| Sun azimuth at landing (difference on the sky) | 86.010 | 85.997 | -0.013 | < 0.05 deg | **PASS** |
| East longitude of the sub-solar point | 90.310 | 90.296 | -0.014 | < 0.05 deg | **PASS** |
| Latitude of the sub-solar point | 1.530 | 1.537 | +0.007 | < 0.05 deg | **PASS** |
| Earth altitude at landing (source's site coordinates) | 77.160 | 77.163 | +0.003 | < 0.05 deg | **PASS** |
| Earth azimuth at landing (difference on the sky) | 319.700 | 319.685 | -0.003 | < 0.05 deg | **PASS** |
| East longitude of the sub-earth point | 7.250 | 7.248 | -0.002 | < 0.05 deg | **PASS** |
| Latitude of the sub-earth point | 0.860 | 0.857 | -0.003 | < 0.05 deg | **PASS** |
| Sun elevation at the planned landing time against the targeted angle of the launch window | 11.900 | 11.883 | -0.017 | < 0.1 deg | **PASS** |
| Change of the Sun elevation caused by the landing delay | 2.860 | 2.877 | +0.017 |  | reported |

- *Sun azimuth at landing (difference on the sky)*: azimuth difference -0.013 deg at altitude 14.8 deg.
- *Earth azimuth at landing (difference on the sky)*: azimuth difference -0.015 deg at altitude 77.2 deg.
- *Sun elevation at the planned landing time against the targeted angle of the launch window*: planned landing 1972-04-20 20:39:00 UTC, 5 h 44 min 35 s before the actual landing.
- *Change of the Sun elevation caused by the landing delay*: Sun elevation at the actual landing time and site: 14.76 deg; the table of SP-4029 still lists the targeted 11.9 deg..

## Firefly Blue Ghost Mission 1, Mare Crisium, landed 2 March 2025; end of the lunar day on 16 March 2025

Terrain: none: no elevation data for this latitude in the project's terrain set. Smooth local sphere through the landing point (1737.4 km minus 3.65 km), observer 2 m above it.

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Day of the lunar sunset (last light on the smooth local sphere) | 2025-03-16 (US Central Daylight Time) | 2025-03-16T20:54:54.609Z |  | inside 2025-03-16T05:00Z to 2025-03-17T05:00Z | **PASS** |
| Recorded daylight must end before geometric last light | 2025-03-16T18:34:00.000Z (landing + 346 h) | 2025-03-16T20:54:54.609Z | +2.849 | last light not earlier than landing + 346 h - 0.5 h | **PASS** |
| End of recorded daylight against smooth-sphere sunset | see below | see below | +2.349 |  | reported |

- *Recorded daylight must end before geometric last light*: difference: hours by which the inequality is satisfied.
- *End of recorded daylight against smooth-sphere sunset*: difference: hours from the end of recorded daylight to geometric last light; a local horizon as high as the Sun's upper limb at that moment, or the operator's definition of night, would account for it.
- *End of recorded daylight against smooth-sphere sunset*, published:
  - landing plus 346h: 2025-03-16T18:34:00.000Z
  - final data minus 5h: 2025-03-16T18:15:00.000Z or earlier ('just over 5 hours')
- *End of recorded daylight against smooth-sphere sunset*, computed:
  - lower limb touches horizon: 2025-03-16T19:48:05.391Z
  - centre on horizon: 2025-03-16T20:21:29.766Z
  - last light: 2025-03-16T20:54:54.609Z
  - sun upper limb elevation at landing plus 346h deg: 1.040
  - sun centre elevation at landing deg: 3.425
  - sun azimuth at landing plus 346h deg: 269.724

## ISRO Chandrayaan-3 lander and rover, 69.4 degrees south, landed 23 August 2023; lunar night and expected awakening

Terrain: LOLA elevation model of the project (60 m grid at this latitude), terrain horizon out to 300 km, observer 2 m above the surface.

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sunrise over the terrain horizon must precede the end of the expected wake-up day | 2023-09-22 (Indian Standard Time), 'around' | 2023-09-20T00:05:04.453Z | +66.415 | not later than 2023-09-22T18:30:00Z | **PASS** |
| Lunar night at the landing site | see below | see below | +1.767 |  | reported |

- *Sunrise over the terrain horizon must precede the end of the expected wake-up day*: difference: hours by which the inequality is satisfied.
- *Lunar night at the landing site*: difference: days from computed sunrise to the start of 22 September 2023 (IST).
- *Lunar night at the landing site*, published:
  - sleep status date: 2023-09-04 (IST)
  - expected awakening: around 2023-09-22 (IST)
- *Lunar night at the landing site*, computed:
  - sunset last light terrain: 2023-09-04T07:14:41.485Z, 2023-10-03T23:25:14.297Z
  - sunrise first light terrain: 2023-09-20T00:05:04.453Z
  - sunrise azimuth deg: 85.475
  - sunrise horizon elevation deg: 1.118
  - sunrise obstacle distance km: 0.502
  - sunset last light smooth sphere: 2023-09-04T18:05:25.547Z, 2023-10-04T10:02:04.454Z
  - sunrise first light smooth sphere: 2023-09-19T17:23:30.703Z
  - terrain delay of sunrise h: 6.693
  - sun centre elevation on 2023-09-22 IST deg: 8.212, 11.925
  - all sun events terrain: set, 2023-09-04T07:14:41.485Z, rise, 2023-09-20T00:05:04.453Z, set, 2023-10-03T23:25:14.297Z
  - dem surface height m: 529.110
  - lroc elevation m: 532.000
  - dem set: lola:LDEM_80S_20M@V2.0+LDEM_60S_60M@V2.0
  - horizon coverage complete: True

## Apollo 12 lunar module landing, 19 November 1969

Terrain: none (smooth sphere).

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sun altitude at landing (source's site coordinates) | 5.190 | 5.189 | -0.001 | < 0.05 deg | **PASS** |
| Sun azimuth at landing (difference on the sky) | 91.160 | 91.163 | +0.003 | < 0.05 deg | **PASS** |
| East longitude of the sub-solar point | 61.500 | 61.497 | -0.003 | < 0.05 deg | **PASS** |
| Latitude of the sub-solar point | -1.440 | -1.446 | -0.006 | < 0.05 deg | **PASS** |
| Earth altitude at landing (source's site coordinates) | 61.560 | 61.548 | -0.012 | < 0.05 deg | **PASS** |
| Earth azimuth at landing (difference on the sky) | 86.950 | 86.960 | +0.005 | < 0.05 deg | **PASS** |
| East longitude of the sub-earth point | 5.020 | 5.032 | +0.012 | < 0.05 deg | **PASS** |
| Latitude of the sub-earth point | -1.360 | -1.365 | -0.005 | < 0.05 deg | **PASS** |
| Sun elevation at the actual landing site and time, against the launch-window target | 5.100 | 5.149 | +0.049 |  | reported |
| Earth elevation seen from the actual site (with parallax) against the source's value (without parallax) | 61.560 | 61.396 | -0.164 |  | reported |

- *Sun azimuth at landing (difference on the sky)*: azimuth difference +0.003 deg at altitude 5.2 deg.
- *Earth azimuth at landing (difference on the sky)*: azimuth difference +0.010 deg at altitude 61.5 deg.
- *Sun elevation at the actual landing site and time, against the launch-window target*: The published value is a planned angle; it is not judged..
- *Earth elevation seen from the actual site (with parallax) against the source's value (without parallax)*: Shows the size of the parallax the source leaves out..

## Apollo 14 lunar module landing, 5 February 1971

Terrain: none (smooth sphere).

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sun altitude at landing (source's site coordinates) | 10.360 | 10.356 | -0.004 | < 0.05 deg | **PASS** |
| Sun azimuth at landing (difference on the sky) | 89.540 | 89.550 | +0.010 | < 0.05 deg | **PASS** |
| East longitude of the sub-solar point | 62.170 | 62.171 | +0.001 | < 0.05 deg | **PASS** |
| Latitude of the sub-solar point | -0.210 | -0.218 | -0.008 | < 0.05 deg | **PASS** |
| Earth altitude at landing (source's site coordinates) | 66.100 | 66.065 | -0.035 | < 0.05 deg | **PASS** |
| Earth azimuth at landing (difference on the sky) | 96.700 | 96.809 | +0.044 | < 0.05 deg | **PASS** |
| East longitude of the sub-earth point | 6.400 | 6.435 | +0.035 | < 0.05 deg | **PASS** |
| Latitude of the sub-earth point | -6.070 | -6.117 | -0.047 | < 0.05 deg | **PASS** |
| Sun elevation at the actual landing site and time, against the launch-window target | 10.300 | 10.349 | +0.049 |  | reported |
| Earth elevation seen from the actual site (with parallax) against the source's value (without parallax) | 66.100 | 65.952 | -0.148 |  | reported |

- *Sun azimuth at landing (difference on the sky)*: azimuth difference +0.010 deg at altitude 10.4 deg.
- *Earth azimuth at landing (difference on the sky)*: azimuth difference +0.109 deg at altitude 66.1 deg.
- *Sun elevation at the actual landing site and time, against the launch-window target*: The published value is a planned angle; it is not judged..
- *Earth elevation seen from the actual site (with parallax) against the source's value (without parallax)*: Shows the size of the parallax the source leaves out..

## Apollo 15 lunar module landing, 30 July 1971

Terrain: none (smooth sphere).

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sun altitude at landing (source's site coordinates) | 12.050 | 12.045 | -0.005 | < 0.05 deg | **PASS** |
| Sun azimuth at landing (difference on the sky) | 95.730 | 95.722 | -0.008 | < 0.05 deg | **PASS** |
| East longitude of the sub-solar point | 80.330 | 80.338 | +0.008 | < 0.05 deg | **PASS** |
| Latitude of the sub-solar point | 0.240 | 0.244 | +0.004 | < 0.05 deg | **PASS** |
| Earth altitude at landing (source's site coordinates) | 69.280 | 69.290 | +0.010 | < 0.05 deg | **PASS** |
| Earth azimuth at landing (difference on the sky) | 203.000 | 203.001 | +0.000 | < 0.05 deg | **PASS** |
| East longitude of the sub-earth point | -4.350 | -4.347 | +0.003 | < 0.05 deg | **PASS** |
| Latitude of the sub-earth point | 6.840 | 6.846 | +0.006 | < 0.05 deg | **PASS** |
| Sun elevation at the actual landing site and time, against the launch-window target | 12.200 | 12.025 | -0.175 |  | reported |
| Earth elevation seen from the actual site (with parallax) against the source's value (without parallax) | 69.280 | 69.180 | -0.100 |  | reported |

- *Sun azimuth at landing (difference on the sky)*: azimuth difference -0.008 deg at altitude 12.0 deg.
- *Earth azimuth at landing (difference on the sky)*: azimuth difference +0.001 deg at altitude 69.3 deg.
- *Sun elevation at the actual landing site and time, against the launch-window target*: The published value is a planned angle; it is not judged..
- *Earth elevation seen from the actual site (with parallax) against the source's value (without parallax)*: Shows the size of the parallax the source leaves out..

## Apollo 17 lunar module landing, 11 December 1972

Terrain: none (smooth sphere).

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Sun altitude at landing (source's site coordinates) | 13.330 | 13.347 | +0.017 | < 0.05 deg | **PASS** |
| Sun azimuth at landing (difference on the sky) | 95.830 | 95.845 | +0.014 | < 0.05 deg | **PASS** |
| East longitude of the sub-solar point | 106.260 | 106.236 | -0.024 | < 0.05 deg | **PASS** |
| Latitude of the sub-solar point | -0.760 | -0.769 | -0.009 | < 0.05 deg | **PASS** |
| Earth altitude at landing (source's site coordinates) | 45.520 | 45.479 | -0.041 | < 0.05 deg | **PASS** |
| Earth azimuth at landing (difference on the sky) | 240.880 | 240.894 | +0.010 | < 0.05 deg | **PASS** |
| East longitude of the sub-earth point | -7.100 | -7.138 | -0.038 | < 0.05 deg | **PASS** |
| Latitude of the sub-earth point | -4.250 | -4.265 | -0.015 | < 0.05 deg | **PASS** |
| Sun elevation at the actual landing site and time, against the launch-window target | 13.000 | 13.350 | +0.350 |  | reported |
| Earth elevation seen from the actual site (with parallax) against the source's value (without parallax) | 45.520 | 45.282 | -0.238 |  | reported |

- *Sun azimuth at landing (difference on the sky)*: azimuth difference +0.015 deg at altitude 13.3 deg.
- *Earth azimuth at landing (difference on the sky)*: azimuth difference +0.014 deg at altitude 45.5 deg.
- *Sun elevation at the actual landing site and time, against the launch-window target*: The published value is a planned angle; it is not judged..
- *Earth elevation seen from the actual site (with parallax) against the source's value (without parallax)*: Shows the size of the parallax the source leaves out..

## Sources

- `sp4029_landing`: NASA SP-2000-4029, Apollo by the Numbers: table 'LM Lunar Landing'. https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_18-27_LM_Lunar_Landing.htm (retrieved 2026-11-14T11:07:54Z)
- `sp4029_windows`: NASA SP-2000-4029, Apollo by the Numbers: table 'Launch Windows'. https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_18-14_Launch_Windows.htm (retrieved 2026-11-14T11:07:55Z)
- `sp4029_apollo16`: NASA SP-2000-4029, Apollo by the Numbers: Apollo 16 summary. https://www.nasa.gov/wp-content/uploads/static/history/SP-4029/Apollo_16a_Summary.htm (retrieved 2026-11-14T11:07:56Z)
- `alsj_altaz`: Apollo Lunar Surface Journal: Sun and Earth altitude and azimuth table (Scotti_AltAz.txt). https://www.nasa.gov/wp-content/uploads/static/history/alsj/Scotti_AltAz.txt (retrieved 2026-11-14T11:07:56Z)
- `alsj_sunangles`: Apollo Lunar Surface Journal: 'Sun Angles', compiled by Brian W. Lawrence, last revised 8 February 1999. https://apollojournals.org/alsj/sunangles.html (retrieved 2026-11-14T11:07:57Z)
- `firefly_release`: Firefly Aerospace press release, 17 March 2025: completion of 14 days of surface operations. https://fireflyspace.com/news/firefly-aerospace-successfully-completes-14-days-of-surface-operations-on-the-moon (retrieved 2026-11-14T11:07:58Z)
- `firefly_live`: Firefly Aerospace: Blue Ghost Mission 1 live updates. https://fireflyspace.com/news/blue-ghost-mission-1-live-updates/ (retrieved 2026-11-14T11:07:59Z)
- `lroc_blue_ghost`: LROC: 'Blue Ghost Lunar Lander Seen From Above', 7 March 2025. https://lroc.im-ldi.com/images/1407 (retrieved 2026-11-14T11:08:00Z)
- `lroc_chandrayaan3`: LROC: 'Chandrayaan-3 Landing Site', 5 September 2023. https://lroc.im-ldi.com/images/1314 (retrieved 2026-11-14T11:08:01Z)
- `isro_updates`: ISRO: Chandrayaan-3 mission updates. https://www.isro.gov.in/Chandrayaan3.html (retrieved 2026-11-14T11:08:02Z)
