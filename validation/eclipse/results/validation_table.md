# Validation table: eclipse of the Sun by the Earth, 14 March 2025, at the Blue Ghost landing point

Generated 2026-11-14T11:24:09Z by `validation/eclipse/compare.py`. Do not edit by hand.

**8 of 8 pass/fail checks pass; 0 fail; 2 comparisons are reported without a verdict.**
Published values, sources and thresholds are in `cases.json` and `thresholds.json`, committed before the first run (commit a8bbc5a). The test is not blind: see the disclosure in `thresholds.json`.

Model: opaque Earth disc of the equatorial radius, no atmosphere; uniform Sun disc; angles seen from the site. Site: 18.5623 N, 61.8103 E, -3650 [m] (LROC).
Computed contacts (UTC): C1 2025-03-14T05:00:42.422Z, C2 2025-03-14T06:17:23.203Z, C3 2025-03-14T08:34:24.609Z, C4 2025-03-14T09:51:10.078Z.

| Quantity | Published | Computed | Difference | Threshold | Result |
|---|---|---|---|---|---|
| Partial eclipse begins at the site (C1) | 2025-03-14T05:00:00Z | 2025-03-14T05:00:42.422Z | +0.71 min | < 2.0 min | **PASS** |
| Totality begins at the site (C2) | 2025-03-14T06:18:00Z | 2025-03-14T06:17:23.203Z | -0.61 min | < 2.0 min | **PASS** |
| Partial eclipse ends at the site (C4) | 2025-03-14T09:52:00Z | 2025-03-14T09:51:10.078Z | -0.83 min | < 2.0 min | **PASS** |
| Duration of totality at the site (C3 - C2) | 136.000 | 137.023 | +1.02 min | < 3.5 min | **PASS** |
| C1 at the site is not before the Moon enters the penumbra (P1) | P1 = 2025-03-14T03:57:24Z | 2025-03-14T05:00:42.422Z | +63.31 min | inside the bounds, allowance 2 min | **PASS** |
| C2 at the site lies between U1 and U2 | U1 = 2025-03-14T05:09:33Z and U2 = 2025-03-14T06:25:59Z | 2025-03-14T06:17:23.203Z | +8.60 min | inside the bounds, allowance 2 min | **PASS** |
| C3 at the site lies between U3 and U4 | U3 = 2025-03-14T07:31:23Z and U4 = 2025-03-14T08:47:48Z | 2025-03-14T08:34:24.609Z | +13.39 min | inside the bounds, allowance 2 min | **PASS** |
| C4 at the site is not after the Moon leaves the penumbra (P4) | P4 = 2025-03-14T10:00:01Z | 2025-03-14T09:51:10.078Z | +8.85 min | inside the bounds, allowance 2 min | **PASS** |
| Fraction of the Sun hidden by the Earth at the times of the published images | see below | see below |  |  | reported |
| Eclipse-aware power line at the site (fraction of the Sun's disc that is lit) | none | see below |  |  | reported |

- *Duration of totality at the site (C3 - C2)*: totality ends (C3) at 2025-03-14T08:34:24.609Z.
- *C1 at the site is not before the Moon enters the penumbra (P1)*: difference: smallest margin to a bound, in minutes (positive = inside).
- *C2 at the site lies between U1 and U2*: difference: smallest margin to a bound, in minutes (positive = inside).
- *C3 at the site lies between U3 and U4*: difference: smallest margin to a bound, in minutes (positive = inside).
- *C4 at the site is not after the Moon leaves the penumbra (P4)*: difference: smallest margin to a bound, in minutes (positive = inside).
- *Fraction of the Sun hidden by the Earth at the times of the published images*: the diamond ring was photographed about 4 min before the computed end of totality.
- *Fraction of the Sun hidden by the Earth at the times of the published images*, published: first look 2025-03-14T05:30:00Z (about); red surface during totality 2025-03-14T07:30:00Z (about); diamond ring 2025-03-14T08:30:00Z (about)
- *Fraction of the Sun hidden by the Earth at the times of the published images*, computed:
  - first look: 0.342
  - red surface during totality: 1.000
  - diamond ring: 1.000
- *Eclipse-aware power line at the site (fraction of the Sun's disc that is lit)*, computed:
  - hours without any sunlight: 2.284
  - hours with reduced sunlight: 4.841
  - lit fraction every 10 min: [1.0, 1.0, 1.0, 1.0, 0.9265, 0.7996, 0.6469, 0.4822, 0.3172, 0.1649, 0.0434, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0412, 0.1617, 0.3135, 0.4784, 0.6433, 0.7964, 0.924, 0.9997, 1.0, 1.0, 1.0]
  - first sample utc: 2025-03-14T04:30:42.422Z
  - smallest separation deg: 0.370
  - time of smallest separation: 2025-03-14T07:25:55.070Z
  - sun elevation deg: 28.976
  - earth elevation deg: 28.885
  - earth azimuth deg: 258.768
  - sun angular radius deg: 0.267
  - earth angular radius deg: 0.912

Time zone of the operator's times: UTC-5. US daylight saving time began on 9 March 2025, so clocks in Texas showed Central Daylight Time on 13 and 14 March. Read as UTC-6, the eclipse at the landing site would end at 10:52 UTC, after the whole Moon has left the Earth's penumbra (P4 = 10:00:01 UT on the NASA chart), which is impossible. The UTC-5 reading is therefore fixed by the two publications alone.

## Sources

- `firefly_live`: Firefly Aerospace: Blue Ghost Mission 1 live updates (posts of 13 and 14 March 2025). https://fireflyspace.com/news/blue-ghost-mission-1-live-updates/ (retrieved 2026-11-14T11:07:59Z)
- `lroc_blue_ghost`: LROC: 'Blue Ghost Lunar Lander Seen From Above', 7 March 2025. https://lroc.im-ldi.com/images/1407 (retrieved 2026-11-14T11:08:00Z)
- `nasa_gsfc_chart`: F. Espenak, NASA's GSFC: chart 'Total Lunar Eclipse of 2025 Mar 14' (dated 2009 Apr 29). https://eclipse.gsfc.nasa.gov/LEplot/LEplot2001/LE2025Mar14T.pdf (retrieved 2026-11-14T11:19:45Z)
- `nasa_science_page`: NASA Science: 'What You Need To Know About the March 2025 Total Lunar Eclipse' (last updated 6 March 2025). https://science.nasa.gov/solar-system/moon/what-you-need-to-know-about-the-march-2025-total-lunar-eclipse/ (retrieved 2026-11-14T11:19:43Z)
