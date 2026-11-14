# Radial scale of the crater-catalogue check: expectation written before reading the mapping code

Written 2026-11-14T12:25Z, before `lsn_data/georef.py`, `lsn_data/dem.py` and `lsn_data/catalogue_check.py` were re-read.
Only `data/checkpoints/thresholds_catalogue.json` (the definition of the measured quantity) and
`data/checkpoints/catalogue_report.json` (the result, eps = -3.62e-4 +- 0.61e-4) were read.

## What is measured

For each crater i the offset `t_i = (centre of the circle fitted to the 20 m DEM rim crest) - (catalogue centre)`,
both in the polar stereographic plane, and the fit `t_i = T + delta (z x r_i) + eps r_i`, `r_i` the catalogue centre
relative to the pole in the plane. The catalogue centre reaches the plane through our forward mapping
`lonlat_to_xy`; the DEM rim reaches the plane through our reading of the raster (line/sample to x/y from the
label). eps therefore compares the two halves of our own mapping, and the catalogue's positions.

## Projection facts (spherical polar stereographic, true at the pole, R = 1 737 400 m)

`rho = 2 R tan(c / 2)`, c the colatitude; the projection is conformal with scale `k = 1 / cos^2(c / 2)` in every
direction. Arc distance from the pole `s = R c`; `rho / s - 1 = c^2 / 12 + O(c^4)`.

| latitude | k - 1 | rho (m) | s (m) | rho/s - 1 |
|---|---|---|---|---|
| 89 S | 7.6e-5 | 30 324 | 30 323 | 2.5e-5 |
| 87 S | 6.9e-4 | 90 991 | 90 970 | 2.3e-4 |
| 85 S | 1.91e-3 | 151 713 | 151 617 | 6.4e-4 |
| 82.5 S | 4.30e-3 | 227 750 | 227 425 | 1.43e-3 |
| 80.5 S | 6.91e-3 | 288 734 | 288 072 | 2.30e-3 |

## Expected eps for a correct reading

**eps = 0**, independent of latitude. Both the catalogue centre and the DEM rim are mapped by the same projection;
the scale factor k changes plane lengths (it matters for the rim search radius `a = (D/2) k`, which the criterion
already includes) but it cannot move a crater centre relative to the image of its own latitude and longitude.
A correct reader must show no radial scale at any latitude.

## What a non-zero eps would mean, with the predicted signature of each cause

Not errors of ours (catalogue conventions):

1. Circle fitted in the stereographic plane instead of on the sphere: stereographic maps circles to circles, but the
   plane centre is displaced outward by `R tan(c/2) sec^2(c/2) a^2 / 2`, a = D / (2R). At most 1.3 m (D = 16 km at
   250 km). Negligible.
2. Circle fitted in latitude/longitude space (equirectangular with a cos(latitude) factor): the rim is egg-shaped there,
   widest at colatitude `c' = arccos(cos c / cos a) < c`, so the fitted centre moves POLEWARD by about
   `R a^2 / (2 tan c)`: 3 m (D = 2 km, 150 km), 53 m (8 km, 150 km), 640 m (16 km, 50 km). Signature: offset
   proportional to `D^2 / s`, so eps per crater is proportional to `D^2 / s^2`. A poleward catalogue bias gives a
   POSITIVE eps (DEM minus catalogue points away from the pole).
3. Positions measured on images under low Sun, or on mosaics georeferenced with another sphere radius or another
   true-scale latitude: a sphere radius R' instead of R gives a constant `eps = R'/R - 1` (1737.4 vs 1738.0 km:
   -3.45e-4); a true-scale latitude phi_c instead of the pole gives a constant `eps = -(1 - cos^2(c_c/2))` (-3.6e-4
   needs phi_c = 87.8 S). Signature: constant eps, no dependence on D or s.
4. A bias of the rim-crest detector that moves every crest the same distance b along the radial direction (for example
   a regional slope towards or away from the pole): offset constant in metres, so eps per crater `= b / s`, larger
   for craters nearer the pole.

Errors of ours (would be a bug):

5. Treating an azimuthal-equidistant raster as stereographic, or the reverse: `eps(s) = -+ c^2/12`, zero at the pole,
   6.4e-4 at 150 km, 2.3e-3 at 290 km: strongly growing with distance.
6. Wrong reference radius or wrong map scale in one half of the mapping: constant eps equal to the relative error.
7. Using arc distance s where plane distance rho is needed (or k at the wrong latitude): eps of order (k - 1) or
   c^2/12, i.e. 1e-4 to 7e-3, growing with distance.
8. Half-pixel error in the line/sample convention: a translation of 10 m (20 m product), no eps.

## Test to discriminate

Per-crater radial offsets `t_i . r_i/|r_i|` after removing T, regressed on `s`, on `1` (constant metres) and on
`D^2 / s`. Causes 5 and 7 predict growth with s; 3 and 6 predict constant eps; 4 predicts constant metres;
2 predicts dependence on D. The measured subsets (nearer than median -5.3e-4, farther -2.9e-4) already point away
from 5 and 7, but that is to be tested, not assumed.
