# Validation table: long-term Sun and Earth visibility versus the published LOLA illumination maps

Generated 2026-11-15T04:57:48Z by `validation/pgda/compare.py`. Do not edit by hand.

**7 of 7 pre-registered checks pass, 0 fail** (run A, observer at 0 m; thresholds in `thresholds.json`, points in `points.json`, both committed before the maps were read: commit d044186).

| Check (run A: 60 m terrain, 0 m, 100 points) | Measured | Threshold | Result |
|---|---|---|---|
| sun correlation | +0.9965 | >= 0.9 | **PASS** |
| sun median absolute difference | +0.0006 | <= 0.05 | **PASS** |
| sun median signed difference | +0.0000 | abs <= 0.02 | **PASS** |
| earth correlation | +0.9992 | >= 0.9 | **PASS** |
| earth median absolute difference | +0.0003 | <= 0.05 | **PASS** |
| earth median signed difference | +0.0000 | abs <= 0.02 | **PASS** |
| sun permanent shadow agreement | +0.9898 | >= 0.95 | **PASS** |

## Distribution of the differences (our share minus the published value)

| Run | Height | Body | Stratum | Points | r | Median | Mean | 10th pct | 90th pct | Median abs | Max abs | > 0.05 | > 0.10 | > 0.20 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A: 60 m terrain | 0m | sun | all | 100 | 0.996 | +0.000 | +0.000 | -0.005 | +0.006 | 0.001 | 0.076 | 3 | 0 | 0 |
| A: 60 m terrain | 0m | sun | ridge or rim | 33 | 0.999 | -0.000 | -0.001 | -0.007 | +0.004 | 0.002 | 0.036 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | sun | plain or slope | 31 | 0.990 | +0.000 | -0.002 | -0.015 | +0.003 | 0.001 | 0.076 | 3 | 0 | 0 |
| A: 60 m terrain | 0m | sun | floor | 33 | 0.997 | +0.000 | +0.002 | -0.000 | +0.008 | 0.000 | 0.045 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | sun | site record | 3 | 1.000 | -0.001 | +0.009 | -0.001 | +0.023 | 0.001 | 0.029 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | earth | all | 100 | 0.999 | +0.000 | -0.001 | -0.002 | +0.001 | 0.000 | 0.049 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | earth | ridge or rim | 33 | 0.998 | +0.000 | -0.002 | -0.009 | +0.001 | 0.000 | 0.049 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | earth | plain or slope | 31 | 0.999 | +0.000 | -0.002 | -0.002 | +0.002 | 0.001 | 0.049 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | earth | floor | 33 | 1.000 | +0.000 | +0.001 | -0.001 | +0.000 | 0.000 | 0.029 | 0 | 0 | 0 |
| A: 60 m terrain | 0m | earth | site record | 3 | 1.000 | +0.001 | -0.000 | -0.001 | +0.001 | 0.001 | 0.002 | 0 | 0 | 0 |
| A: 60 m terrain | 2m | sun | all | 100 | 0.992 | +0.002 | +0.013 | +0.000 | +0.040 | 0.002 | 0.113 | 5 | 3 | 0 |
| A: 60 m terrain | 2m | sun | ridge or rim | 33 | 0.995 | +0.003 | +0.012 | +0.000 | +0.040 | 0.003 | 0.050 | 1 | 0 | 0 |
| A: 60 m terrain | 2m | sun | plain or slope | 31 | 0.979 | +0.005 | +0.018 | +0.000 | +0.048 | 0.005 | 0.113 | 3 | 2 | 0 |
| A: 60 m terrain | 2m | sun | floor | 33 | 0.997 | +0.001 | +0.005 | +0.000 | +0.014 | 0.001 | 0.049 | 0 | 0 | 0 |
| A: 60 m terrain | 2m | sun | site record | 3 | 1.000 | +0.037 | +0.054 | +0.025 | +0.089 | 0.037 | 0.102 | 1 | 1 | 0 |
| A: 60 m terrain | 2m | earth | all | 100 | 0.992 | +0.000 | +0.010 | -0.000 | +0.028 | 0.001 | 0.225 | 8 | 2 | 1 |
| A: 60 m terrain | 2m | earth | ridge or rim | 33 | 0.992 | +0.000 | +0.014 | -0.000 | +0.057 | 0.001 | 0.108 | 5 | 1 | 0 |
| A: 60 m terrain | 2m | earth | plain or slope | 31 | 0.981 | +0.000 | +0.013 | -0.000 | +0.022 | 0.001 | 0.225 | 2 | 1 | 1 |
| A: 60 m terrain | 2m | earth | floor | 33 | 0.999 | +0.000 | +0.002 | -0.000 | +0.007 | 0.000 | 0.031 | 0 | 0 | 0 |
| A: 60 m terrain | 2m | earth | site record | 3 | 0.999 | +0.001 | +0.032 | +0.001 | +0.075 | 0.001 | 0.094 | 1 | 0 | 0 |
| B: production terrain | 0m | sun | all | 100 | 0.979 | -0.000 | -0.013 | -0.043 | +0.001 | 0.002 | 0.180 | 10 | 4 | 0 |
| B: production terrain | 0m | sun | ridge or rim | 33 | 0.991 | -0.010 | -0.015 | -0.035 | +0.000 | 0.010 | 0.083 | 2 | 0 | 0 |
| B: production terrain | 0m | sun | plain or slope | 31 | 0.945 | -0.000 | -0.018 | -0.044 | +0.003 | 0.001 | 0.180 | 4 | 3 | 0 |
| B: production terrain | 0m | sun | floor | 33 | 0.995 | +0.000 | -0.000 | -0.003 | +0.003 | 0.000 | 0.054 | 1 | 0 | 0 |
| B: production terrain | 0m | sun | site record | 3 | 0.982 | -0.083 | -0.095 | -0.117 | -0.078 | 0.083 | 0.126 | 3 | 1 | 0 |
| B: production terrain | 0m | earth | all | 100 | 0.984 | +0.000 | -0.011 | -0.024 | +0.001 | 0.000 | 0.316 | 6 | 3 | 2 |
| B: production terrain | 0m | earth | ridge or rim | 33 | 0.955 | +0.000 | -0.027 | -0.073 | +0.001 | 0.001 | 0.316 | 5 | 3 | 2 |
| B: production terrain | 0m | earth | plain or slope | 31 | 0.998 | +0.000 | -0.004 | -0.017 | +0.001 | 0.001 | 0.058 | 1 | 0 | 0 |
| B: production terrain | 0m | earth | floor | 33 | 1.000 | +0.000 | -0.001 | -0.003 | +0.001 | 0.000 | 0.023 | 0 | 0 | 0 |
| B: production terrain | 0m | earth | site record | 3 | 1.000 | -0.001 | -0.009 | -0.022 | +0.000 | 0.001 | 0.027 | 0 | 0 | 0 |
| B: production terrain | 2m | sun | all | 100 | 0.990 | +0.001 | +0.007 | -0.001 | +0.025 | 0.002 | 0.141 | 5 | 1 | 0 |
| B: production terrain | 2m | sun | ridge or rim | 33 | 0.995 | +0.002 | +0.006 | -0.002 | +0.024 | 0.004 | 0.049 | 0 | 0 | 0 |
| B: production terrain | 2m | sun | plain or slope | 31 | 0.968 | +0.003 | +0.009 | +0.000 | +0.047 | 0.005 | 0.141 | 4 | 1 | 0 |
| B: production terrain | 2m | sun | floor | 33 | 0.997 | +0.000 | +0.004 | -0.000 | +0.015 | 0.001 | 0.048 | 0 | 0 | 0 |
| B: production terrain | 2m | sun | site record | 3 | 0.997 | +0.017 | +0.038 | +0.016 | +0.068 | 0.017 | 0.080 | 1 | 0 | 0 |
| B: production terrain | 2m | earth | all | 100 | 0.991 | +0.000 | +0.005 | -0.001 | +0.014 | 0.000 | 0.199 | 7 | 2 | 0 |
| B: production terrain | 2m | earth | ridge or rim | 33 | 0.982 | +0.000 | +0.001 | -0.002 | +0.044 | 0.001 | 0.199 | 4 | 1 | 0 |
| B: production terrain | 2m | earth | plain or slope | 31 | 0.987 | +0.000 | +0.010 | -0.001 | +0.013 | 0.001 | 0.174 | 2 | 1 | 0 |
| B: production terrain | 2m | earth | floor | 33 | 1.000 | +0.000 | +0.001 | -0.000 | +0.001 | 0.000 | 0.030 | 0 | 0 | 0 |
| B: production terrain | 2m | earth | site record | 3 | 1.000 | +0.001 | +0.026 | +0.001 | +0.062 | 0.001 | 0.077 | 1 | 0 | 0 |

## Permanent shadow

98 points compared (2 left out because their 3 x 3 neighbourhood in the published flag map is mixed): agreement 99.0 %. Published as permanent shadow and never lit in our period: 14. Published as permanent shadow but lit in ours: 0. Published as lit but never lit in ours: 1.

## Effect of the period

For 10 points the share was also computed over a second nodal cycle starting 2000-01-01: the largest change is 0.0010 for the Sun and 0.0046 for the Earth.

## Sources

- sun: `AVGVISIB_85S_060M_201608.IMG`, sha256 `82dadf321dee28f1947c1fed81858d4cf50fe8eb2aa405aae114e8ab21c1efe1`, http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608.IMG (retrieved 2026-11-14T12:27:00Z)
- earth: `AVGVISIB_85S_060M_201608_EARTH.IMG`, sha256 `0958313069d6039b2474c875ff662f28dbcba2bd853d9ea458aa807b7948c11f`, http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/AVGVISIB_85S_060M_201608_EARTH.IMG (retrieved 2026-11-14T12:27:03Z)
- permanent shadow: `LPSR_85S_060M_201608.IMG`, sha256 `f8203cab342c817fc7851431e264def3cc64a3b8c30f032d61e0a44f1e4ef761`, http://imbrium.mit.edu/EXTRAS/ILLUMINATION/IMG/LPSR_85S_060M_201608.IMG (retrieved 2026-11-14T12:27:19Z)
