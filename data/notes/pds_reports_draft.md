# Draft reports to the PDS Geosciences Node / LOLA team (for the team lead; not sent)

Draft written 2026-11-14 by the data stream. Facts and reproduction steps only. Nothing here has been sent.

---

## 1. LDEM_128.IMG: the PDS copy and the MIT LOLA mirror copy differ in bytes 56-4095

**Files**

| copy | URL | Last-Modified (HTTP) | size (bytes) | SHA-256 |
|---|---|---|---|---|
| PDS Geosciences Node | https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/data/lola_gdr/cylindrical/img/ldem_128.img | Wed, 06 Sep 2017 15:55:04 GMT | 2 123 366 400 | 0e4fea9b863e3255f58de15ccbd2bb8b1e248cb09217fd55d23ed37489f764b4 |
| MIT LOLA mirror | https://imbrium.mit.edu/DATA/LOLA_GDR/CYLINDRICAL/IMG/LDEM_128.IMG | Wed, 30 Aug 2017 18:30:15 GMT | 2 123 366 400 | 0ab81a3e8d20e5528a21bc6c994974726cb486198013085f4c423c86fbd1154b |

Both copies were fetched in full on 2026-11-14 and hashed. The labels (`ldem_128.lbl`) are identical.

**Observation**

* The two files differ only in bytes 56-4095 (0-based, inclusive): samples 29-2048 (1-based) of line 1, i.e.
  latitude 89.996 N, longitudes 0.22-16.00 E.
* In the PDS copy these 2020 samples are all 0. In the MIT copy they are 15-65 DN (7.5-32.5 m); neighbouring line 2
  in both copies holds 28-30 m there.
* Setting bytes 56-4095 of the MIT copy to zero gives exactly the SHA-256 of the PDS copy, so there is no other
  difference.

**Reproduce**

```
curl -sI <PDS url>; curl -sI <MIT url>                     # same size, Last-Modified 2017-09-06 vs 2017-08-30
curl -s -r 56-4095 <PDS url> | python -c "import sys,struct; v=struct.unpack('<2020h', sys.stdin.buffer.read()); print(sum(x==0 for x in v), min(v), max(v))"
                                                           # PDS: 2020 0 0     (MIT url: 0 15 65)
curl -s <PDS url> | sha256sum; curl -s <MIT url> | sha256sum
```

---

## 2. DSMAP_POLAR.CAT: the latitude/longitude -> line/sample equations disagree with the inverse equations and the text in the southern hemisphere

**File**: https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/catalog/dsmap_polar.cat, last
`LABEL_REVISION_NOTE` entry "2022-01-15 gan:corrected transformation and inverse for both hemispheres using factors for
sign and absolute value of latitude.", HTTP Last-Modified Thu, 30 Nov 2023 18:43:35 GMT, 4312 bytes, SHA-256
e5f345f60f75f8fef00f7b59b806306616bf195079c537195e6413b8a6501ca9 (fetched 2026-11-14).

**As printed**

* Text, lines 28-29: "In the south, Longitude 0 extends straight up from the center, and Longitude 90 East extends to the right."
* Line/sample -> lat/lon, lines 41-46: `X = (I - N/2 - 0.5)*MAP_SCALE`, `Y = (J - N/2 - 0.5)*MAP_SCALE*NS`,
  `LON = ATAN2(X,Y) * 180/PI`, with NS = -1 in the south.
* Lat/lon -> line/sample, lines 71-75: `R = 2*1737400*TAN((90-ABS(LAT)) * PI/360) * SIGN(LAT)`, `X = R*SIN(LON*PI/180)`,
  `Y = R*COS(LON*PI/180)`, `I = NINT(X/MAP_SCALE + N/2 + 0.5)`, `J = NINT(Y/MAP_SCALE + N/2 + 0.5)`, with SIGN(LAT) = -1 in the south.

**Observation**

In the south the lines 71-75 give X = -rho sin(LON), which places 90 E to the left of the centre (I < N/2). Applying
lines 41-46 to that result returns LON = -LON. In the north the two sets of equations and the text agree. Equations
consistent with lines 28-29 and 41-46 in the south would be `I = rho sin(LON)/MAP_SCALE + N/2 + 0.5`,
`J = -rho cos(LON)/MAP_SCALE + N/2 + 0.5`.

Against LOLA RDR laser returns, the south-polar products LDEM_80S_20M and LDEM_60S_60M agree with lines 28-29 and 41-46
(RMS height difference 1.8 m and 1.6 m); with longitude mirrored as lines 71-75 imply, the RMS is 1851 m and 2721 m.

**Reproduce**

```
curl -s -o dsmap_polar.cat <url>; sed -n '26,29p;41,46p;71,75p' dsmap_polar.cat
python -c "import math; R=1737400; S=20; N=30400; r=-2*R*math.tan(5*math.pi/360); X=r*math.sin(math.pi/2); Y=r*math.cos(math.pi/2); I=X/S+N/2+0.5; J=Y/S+N/2+0.5; print(I, math.degrees(math.atan2((I-N/2-0.5)*S, (J-N/2-0.5)*S*-1)))"
                                                           # 85 S, 90 E -> I = 7614.8 (< N/2) and LON back = -90.0
```

The evidence and measured RMS are in data/checkpoints/dsmap_polar_sign_note.md and data/checkpoints/independent_report.json.
