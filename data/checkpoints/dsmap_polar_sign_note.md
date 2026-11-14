# A sign inconsistency in the LOLA polar projection catalog DSMAP_POLAR.CAT (south pole, sample axis)

## The document

* File: `catalog/dsmap_polar.cat` of the LRO LOLA RDR bundle (data set LRO-L-LOLA-4-GDR-V1.0),
  https://pds-geosciences.wustl.edu/lro/lro-l-lola-3-rdr-v1/lrolol_1xxx/catalog/dsmap_polar.cat
* Version: last entry of its `LABEL_REVISION_NOTE` is "2022-01-15 gan:corrected transformation and inverse for both
  hemispheres using factors for sign and absolute value of latitude." Server `Last-Modified: Thu, 30 Nov 2023 18:43:35 GMT`.
* SHA-256 `e5f345f60f75f8fef00f7b59b806306616bf195079c537195e6413b8a6501ca9` (4312 bytes), fetched 2026-11-14T10:13:18Z
  and fetched again at 2026-11-14T13:59Z with the same hash (`data/manifest/manifest.json`).

## What it says (quoted exactly; line numbers of the file)

Text, lines 26-29:

```
circles around the center. In the north, Longitude 0 extends straight
down from the center and Longitude 90 East extends to the right.
In the south, Longitude 0 extends straight up from the center, and
Longitude 90 East extends to the right.
```

Line/sample to latitude/longitude, lines 41-46 (blank line and the LAT lines 47-48 left out):

```
   X = (I - N/2 - 0.5)*MAP_SCALE
   Y = (J - N/2 - 0.5)*MAP_SCALE*NS
   R = SQRT(X^2 + Y^2)
   LON = ATAN2(X,Y) * 180/PI
```

with (lines 52-58, 62) `I = sample coordinate`, `J = line coordinate`, `NS=-1 in the southern hemisphere`,
`LON = east longitude of pixel I,J in degrees`.

Latitude/longitude to line/sample, lines 71-75:

```
   R = 2*1737400*TAN((90-ABS(LAT)) * PI/360) * SIGN(LAT)
   X = R*SIN(LON*PI/180)
   Y = R*COS(LON*PI/180)
   I = NINT(X/MAP_SCALE + N/2 + 0.5)
   J = NINT(Y/MAP_SCALE + N/2 + 0.5)
```

with (line 79 onwards) `SIGN(LAT) =-1 (southern hemisphere)`.

## The inconsistency

Write rho = 2 * 1737400 * tan((90 - |LAT|)/2) > 0. In the south SIGN(LAT) = -1, so the printed forward equations give
X = -rho sin(LON) and Y = -rho cos(LON), hence

    I - N/2 - 0.5 = -rho sin(LON) / MAP_SCALE         (forward, as printed)

For LON = 90 E this puts the point at I < N/2, i.e. to the LEFT of the centre. The text (lines 28-29) says 90 East is
to the RIGHT. Feeding the printed forward result into the printed inverse gives X = -rho sin(LON), Y = +rho cos(LON)
(the NS = -1 factor undoes the sign on Y only), so LON_back = atan2(-rho sin(LON), rho cos(LON)) = -LON: the document's
two directions do not invert each other in the south. In the north (SIGN = NS = +1) all three statements agree.

The forward mapping implied by the document's own inverse equations and text is

    I = +rho sin(LON) / MAP_SCALE + N/2 + 0.5
    J = -rho cos(LON) / MAP_SCALE + N/2 + 0.5        (south; i.e. SIGN(LAT) applied to Y only)

which is what `lsn_data.georef` implements (x = rho sin(lon), y = rho cos(lon), row 0 at the top).

## Measured consequence

Comparing our south-polar products with independent LOLA measurements, once with the implied mapping and once with
longitude mirrored (lon -> -lon, which is exactly what the printed forward equations do to the sample axis):

| product | reference | RMS, implied mapping | RMS, printed forward formula | ratio |
|---|---|---|---|---|
| LDEM_80S_20M | 21 294 LOLA RDR returns, 80.5-89.8 S | 1.80 m | 1 851 m | 1028 |
| LDEM_60S_60M | 235 876 LOLA RDR returns, 60.5-79.5 S | 1.62 m | 2 721 m | 1676 |
| LDEM_80S_20M | LDEM_16 cylindrical cells (another projection) | 30.4 m | 2 423 m | 80 |
| LDEM_60S_60M | LDEM_16 cylindrical cells | 34.5 m | 2 502 m | 73 |

Source: `data/checkpoints/independent_report.json` (`mirror_rms_m`, `stats.rms_d_m`), produced by
`python -m lsn_data.independent`. The data agree with the text and the inverse equations; the printed forward
formula would put every point on the wrong side of the 0-180 meridian.

## Is there a reading under which it is not an error?

Only by giving a symbol a meaning the document does not give it: if LON in lines 72-73 meant WEST longitude in the
south, or if sample I were counted from the right in the south. The document defines LON as east longitude (line 62)
and the sample direction by its inverse equations and its text, and the products' bytes follow those definitions (table
above). Under the document's own definitions the printed lat/lon -> line/sample equations are wrong in the southern
hemisphere for the sample (X) axis; the line (Y) axis and the whole northern hemisphere are right. We have not
contacted the PDS Geosciences Node or the LOLA team; until they confirm, call it "an inconsistency in DSMAP_POLAR.CAT
(2022-01-15 revision) that we found and checked against the data", not "an error in the LOLA data": the data products
themselves are consistent with the text.
