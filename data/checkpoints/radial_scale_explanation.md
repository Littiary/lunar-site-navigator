# The radial scale of the crater-catalogue check: what it is and what it is not

Expectation written first: `radial_scale_expectation.md` (commit 7658127). Numbers below come from
`catalogue_report.json`, `radial_scale_diagnosis.json` (`python -m lsn_data.catalogue_diag`) and
`independent_report.json` (`python -m lsn_data.independent`, criterion `thresholds_independent.json`, commit 12fb030).

## Result

**The mapping is correct; the -3.6e-4 is not in our reading of the LOLA files.** Every horizon computed so far is
unaffected by it.

1. `lsn_data.georef` and `PolarGrid.from_label` reproduce the equations of the LOLA projection catalog
   (`DSMAP_POLAR.CAT`, revision 2022-01-15) and the label (corner -304 000 m / +304 000 m, also stated as
   `upperleft_corner_x/y` in the PDS4 label, R = 1737.4 km, true scale at the pole). Eighteen line/sample values
   derived by hand from those equations (pole, four meridians at 85 S and 80 S, a diagonal point, the three site
   records, five points of the 60 m product) agree to better than 0.001 pixel in both directions
   (`data/tests/test_mapping_by_hand.py`).
2. Against measurements that involve neither images nor a hand-made catalogue, our reading shows no radial scale:

   | our product | reference | radial scale | +- (block bootstrap) |
   |---|---|---|---|
   | LDEM_80S_20M | 21 294 LOLA RDR laser returns, 80.5-89.8 S | -2.7e-5 | 0.6e-5 |
   | LDEM_60S_60M | 235 876 LOLA RDR laser returns, 60.5-79.5 S | -0.03e-5 | 0.04e-5 |
   | LDEM_80S_20M | LDEM_16 cylindrical cells, 80.5-89.5 S (reported only) | -1.8e-5 | 1.7e-5 |
   | LDEM_60S_60M | LDEM_16 cylindrical cells, 60.5-79.5 S (reported only) | -0.2e-5 | 0.5e-5 |
   | LDEM_80S_20M, LDEM_60S_60M | LDEM_128 cylindrical cells (criterion A) | pending: LDEM_128 still downloading | |

   Against LDEM_16 both polar products show a rotation of +0.005 to +0.007 deg (8 sigma), which the laser returns do
   not show (-0.0004 +- 0.0002 deg and 0.00001 +- 0.00002 deg): it is a property of LDEM_16 (product V3.1, 2019,
   other data set and gridding), not of our reading. 0.007 deg is 18 m at 150 km.

   The catalogue value -3.6e-4 is excluded by more than 50 standard errors by the laser returns. -2.7e-5 is 4 m at
   150 km. East-west mirroring raises the RMS difference by a factor of 1000, so the orientation of longitude is
   confirmed with data, not only with the catalog text.
3. The projection's scale factor k = 1/cos^2(colatitude/2) (1.9e-3 at 85 S, 7.7e-3 at 80 S) cannot produce a radial
   scale of crater centres: catalogue centre and DEM rim are both mapped by the same conformal projection, and k only
   enters the rim search radius, where the check already applies it.

## Where the -3.6e-4 comes from

Part of it is a bias of the check's own rim detector, not of the mapping:

* The detector takes the highest point on each ray. On a regional slope that point moves uphill, and the fitted circle
  with it. Adding `beta * a * grad(h)` to the model gives beta = 0.83 +- 0.04 (a 20-sigma effect; it also explains
  most of the 230 m crater-to-crater scatter). Around these craters the terrain rises towards the pole on average
  (mean radial slope -0.010 +- 0.006), so the bias has a poleward mean and leaks into eps:
  with the slope term eps = **-2.6e-4 +- 0.4e-4**; with the rim fit repeated on the DEM after removing the regional
  plane, eps = -2.6e-4.

The remaining -2.6e-4 is **not fully explained**. What was tested:

| candidate (catalogue convention, not an error of ours) | predicted | measured |
|---|---|---|
| circle fit in the stereographic plane instead of on the sphere | < 1.3 m, outward | negligible by construction |
| circle fit in latitude/longitude space (centre moves poleward by D^2/(8 s)) | coefficient +0.125 on D^2/s | -0.09 +- 0.05: rejected (opposite sign) |
| catalogue sphere 1737.1513 km (Robbins 2019, section 3.6.4; FGDC metadata `semiaxis` 1737151.3) | affects diameters only (-1.4e-4 of D), not angular positions | consistent with no effect on eps |
| constant radial offset of the traced rims | b metres | b = +7 +- 29 m with eps -2.9e-4 +- 1.3e-4: the data cannot separate b from eps |
| radial offset proportional to diameter (tracing bias on WAC images and hillshades) | c * D | c = -0.008 +- 0.003 with eps -1.3e-4 +- 0.7e-4 |

With 192 craters the models "constant scale of -2.6e-4" and "a radial tracing bias of about 0.8 % of the diameter plus
a scale near -1.3e-4" fit equally well. Both describe the catalogue's positions relative to LOLA (it was traced on WAC
mosaics at 100 m/pixel and on hillshades, "best effort" horizontal accuracy according to its metadata), and the laser
returns show that neither is in our products or our mapping. We therefore state it as a limit of the catalogue
check: **the catalogue positions near the south pole differ from LOLA by a radial scale of about -2.6e-4 (about 40 m
at 150 km) or an equivalent size-dependent offset; cause not determined.**

## Published spot heights (criterion `thresholds_spot_heights.json`)

Smith et al. (2010) give the lowest point of the Moon as -9117 m at 187.5074 E, 70.360 S (Antoniadi). Our 60 m
south-polar product gives -9128.8 m at exactly that point, which is also the lowest point within 5 km: -11.8 m,
inside the 50 m criterion. LDEM_16 fails the criterion at both points (-103 m at the highest point, +138 m at the
lowest): its 1.9 km cells average the extremes away; its own maximum and minimum lie within 1 km of the published
positions. The criterion stays as written; LDEM_16 is not used for terrain.

## Corrections to earlier statements

* The previous session described -3.6e-4 as a property of the reading ("detected but small"). It is not a property of
  the reading: about a quarter of it is the rim detector's uphill bias, the rest is in the catalogue.
* `radial_scale_expectation.md` gives its writing time as 12:25Z; the commit time 12:22:40Z is the correct one.
  `thresholds_independent.json` says "written_utc 12:50Z"; it was committed at 12:33:24Z (commit 12fb030), before
  any of its comparisons was run. The files are not edited (rule 5); the commit times are authoritative.
