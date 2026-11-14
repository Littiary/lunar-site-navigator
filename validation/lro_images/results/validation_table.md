# Validation table: sunlit or shadowed state against dated LROC images

Generated 2026-11-14T12:53:09Z by `validation/lro_images/compare.py`. Do not edit by hand.

**3 of 4 registered checks pass, 1 fail, 0 not decided.** Cases, reading rule and criteria are in `cases.json`, committed before any computation and before the image was downloaded (commit fb05da0). Terrain: `lola:LDEM_80S_20M@V2.0+LDEM_60S_60M@V2.0`.

| Check | Published or read from the image | Computed | Result |
|---|---|---|---|
| South pole at 2022-05-18T14:40:49.000Z (NAC M1407524099) | shadow, as documented by the camera team | shadow: visible fraction of the Sun 0.000, upper limb -8.794 deg, centre -9.057 deg against the horizon | **PASS** |
| Sub-solar point for that image | 0.15 N, 327.22 E | 0.148 N, 327.222 E | **PASS** |
| Nadir strip of 2010-12-13 (NAC M146846913L): agreement of states at the judged points | 298 of 366 points readable (68 mixed or outside) | 89.3 % agree (266 of 298) | **FAIL** |
| Sub-solar point for that image | -0.35 N, 95.26 E | -0.349 N, 95.264 E | **PASS** |

South pole detail: Sun at azimuth 327.22 deg, elevation -0.149 deg; terrain horizon there +8.908 deg; limiting terrain 0.12 km away.

Nadir strip detail: image sunlit and ours sunlit 6; image sunlit, ours shadow 0; image shadow, ours sunlit 32; image shadow and ours shadow 260. Centre row agreement 86.5 %, side rows 90.6 %. Brightness threshold (Otsu) 69.5 of 255; 8.4 % of the reduced image is above it.

## Why the strip check failed (looked at after the result; not a criterion)

All 32 disagreements go one way: the image rule reads shadow, our state is sunlit. At those points the image is not black: its brightness is 6 to 37 (median 23) of 255, against a median of 3 where both sides say shadow, and our Sun stands only +0.02 to +0.46 deg above the terrain horizon. Ground lit at such a grazing angle is dim. The registered rule uses one brightness threshold for the whole image (Otsu), and that threshold (69.5) settles between the bright Sun-facing slopes and everything else, so dimly lit ground is counted as shadow. The rule, not the horizon, is the likely cause.

Without any threshold: among the 298 judged points, a point our model calls sunlit is brighter in the image than a point it calls shadow with probability 0.996 (median brightness 25 against 3). This supports the explanation but was computed after seeing the result; the registered check stays failed.
