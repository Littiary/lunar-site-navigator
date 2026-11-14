# Known limit: one-pixel step in SLDEM2015 at 90.00 E, 48.13-48.18 S

SLDEM2015 has a straight north-south step along 90.00 E between 48.183 S and 48.128 S. It is 11 rows of 59 m, about
1.7 km long. Across it the terrain falls 144-358 m from one pixel to the next, a slope of up to 85 deg over the
39.5 m east-west pixel of SLDEM2015_512. The step lies exactly on the edge between the 512 tiles `60S_30S_045_090` and
`60S_30S_090_135`.

It is also in the approved SLDEM2015_256, inside a tile there: a 216 m step at 48.139 S, since 256 is the exact
2 x 2 mean of 512 at this place. LDEM_128 (LOLA only, 237 m) does not show it. There the surface is a continuous slope
of about 23 deg, steepest pair 38.8 deg within 1.35 x 1.5 deg. Over the same 316 m across 90 E, LDEM_128 drops 133 m
where 512 drops 307 m. Around the line, the 512 cell means differ from LDEM_128 by up to 347 m.

The surrounding window (2.7 x 3 deg) has 454 pixel pairs steeper than 60 deg in 512, against 0-112 in ten random
windows of the same size. No LOLA return held here (LRO_SM_06, LRO_NO_08) falls within 48.6-47.7 S, 89.4-90.6 E, so
the true surface is not settled.

None of the 20 published sites, the 3 project sites included, has its 300 km horizon search disc touching the step.
The nearest is chandrayaan_3 at 1050 km. Only a requested site within 300 km of 90.00 E, 48.15 S is affected:
58.05-38.26 S, and at 48 S about 75.2-104.8 E. Its horizon from SLDEM2015_256, which the whole-Moon terrain uses there,
can carry an obstacle of up to 240 m that LOLA alone does not show: 2.7 deg at 5 km, 0.69 deg at 20 km, 0.28 deg at
50 km and 0.05 deg at 300 km, before curvature.

Measured 2026-11-14 by the data stream. Method: `data/checkpoints/sldem512_candidate_note.md`.
