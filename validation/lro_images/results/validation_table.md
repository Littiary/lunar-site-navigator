# Validation table: sunlit or shadowed state against dated LROC images

Generated 2026-11-15T01:42:50Z by `validation/lro_images/compare.py`. Do not edit by hand.

**3 of 4 registered checks pass, 1 fail, 0 not decided.** Cases, reading rule and criteria are in `cases.json`, committed before any computation and before the image was downloaded (commit fb05da0). Terrain: `lola:LDEM_80S_20M@V2.0+LDEM_60S_60M@V2.0`.

| Check | Published or read from the image | Computed | Result |
|---|---|---|---|
| South pole at 2022-05-18T14:40:49.000Z (NAC M1407524099) | shadow, as documented by the camera team | shadow: visible fraction of the Sun 0.000, upper limb -8.794 deg, centre -9.057 deg against the horizon | **PASS** |
| Sub-solar point for that image | 0.15 N, 327.22 E | 0.148 N, 327.222 E | **PASS** |
| Nadir strip of 2010-12-13 (NAC M146846913L): agreement of states at the judged points | 298 of 366 points readable (68 mixed or outside) | 89.3 % agree (266 of 298) | **FAIL** |
| Sub-solar point for that image | -0.35 N, 95.26 E | -0.349 N, 95.264 E | **PASS** |

South pole detail: Sun at azimuth 327.22 deg, elevation -0.149 deg; terrain horizon there +8.908 deg; limiting terrain 0.12 km away.

Nadir strip detail: image sunlit and ours sunlit 6; image sunlit, ours shadow 0; image shadow, ours sunlit 32; image shadow and ours shadow 260. Centre row agreement 86.5 %, side rows 90.6 %. Brightness threshold (Otsu) 69.5 of 255; 8.4 % of the reduced image is above it.

## What the failed strip check shows (looked at after the result; not a criterion)

All 32 disagreements go one way: the image rule reads shadow, our state is sunlit, with the centre of our Sun +0.02 to +0.46 deg above the terrain horizon. Two causes fit this pattern, and these data do not decide between them.

1. The image rule. It uses one brightness threshold for the whole image (Otsu, 69.5 of 255), which settles between the bright Sun-facing slopes and everything else, so ground lit at a grazing angle would be read as shadow. For this cause: the disputed points are brighter than agreed shadow in the median (23 against 3); with one threshold on the brightness of a point between 5.5 and 33.5 the agreement would be 90 % or more (at best 98.7 % at 14.5); and without any threshold, among the 298 judged points, a point our model calls sunlit is brighter in the image than a point it calls shadow with probability 0.996.
2. Our horizon. A terrain horizon that is 0.02 to 0.46 deg too low at these points gives the same one-sided pattern. For this cause: the brightness of the disputed points (6 to 37) overlaps that of the 83 points which both sides call shadow with our Sun less than 1 deg below the horizon (3 to 21); and among the disputed points the brightness follows the height of our Sun only weakly (rank correlation 0.25).

These numbers were computed after seeing the result. They are not a criterion; the registered check stays failed.
