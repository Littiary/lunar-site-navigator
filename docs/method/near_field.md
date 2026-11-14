# The 5 m near field, and the band fed by the products' own errors

Code: `NearFieldTerrain` and `LolaTerrain` in `core/lsncore/dem.py`, the two-zone search in
`core/lsncore/horizon.py`, the height-error model in `core/lsncore/uncertainty.py` and
`core/lsncore/pipeline.py`. Tests: `core/tests/test_near_field.py`. Model:
`docs/contract/presets/terrain_height_error.json`. Package fields: contract 0.10,
[`docs/contract/SPEC.md`](../contract/SPEC.md) sections 5.3, 5.4 and 5.7.

Status on 14 November 2026: the search is checked against exhaustive scans on synthetic
nested rasters and on the three site records with their 5 m rasters. The 5 m rasters
(Barker et al. 2021, through the data stream) are built from the same LOLA returns as
the 20 m product: they are independent of its gridding, not of LOLA. Nothing here has
been compared with an independent measurement of the Moon.

## 1. What changes when the near field is on

Off by default. With `--near-field` (or `open_lola(near_field=True)`) a site that lies on
a 5 m site raster is computed on this surface: the 5 m raster inside its extent (16 to
21 km squares around the three site records), the 20 m and 60 m products everywhere
else. The 5 m rasters of other sites, tens of kilometres away, are not used for it. A
site that lies on no 5 m raster is computed exactly as without the option.

The horizon is searched in two zones. Out to the farthest corner of the site's 5 m
raster (12 to 19 km from the three records) the lattice follows the 5 m pixel, 2.5 m
steps, and the proof for skipped stretches uses block maxima of the 5 m raster computed
when it is opened (it has no overview levels of its own). Beyond that distance the
search is the one of the 20 m product, with the same terrain height at the site. Per
azimuth and observer height the higher of the two is the horizon. A finer raster does
not shrink the search cells of the wide products.

## 2. Checks

Thresholds were fixed before the first run; the first is the one of
[horizon.md](horizon.md), section 5.

| Case | Threshold | Measured |
|---|---|---|
| Synthetic 5 m raster without overviews inside a rough 20 m raster, four sites (on it, at its edge, off it), 16 azimuths, three heights: one search with the fine lattice everywhere, and the two-zone search, against a scan in 1 m steps | 0.002 deg | nothing missed |
| The neighbourhood bound across the edge of the finer raster, 150 discs of 3 m to 1.2 km against 3000 sampled points each | never below | holds |
| The adapter's surface against the data reader's at 5000 points on both rasters | 1e-9 m | passes |
| Three site records on their 5 m rasters, 8 azimuths at 2 m, 300 km, against a 1 m scan of the same surface | 0.002 deg | nothing missed |
| Runtime of one site with the near field (six heights, 1440 azimuths, 300 km), best of three, on a machine that is doing nothing else | 15 s | 4.6 s (de Gerlache record) to 9.7 s (Malapert record) measured alone; passes |

What the runtime limit means: the time of one site on an otherwise idle machine, taken
as the best of three runs. The best of three removes a short disturbance; it does not
remove a loaded machine. In one of two runs of the whole test suite on 14 November the
laptop was slowed by the long run itself, and two sites took 15.5 s and 18.1 s (best
of three each); alone, minutes later, the same two took 4.6 s and 9.7 s, and the second
run of the whole suite passed. The limit was not changed. The Malapert record has the
least margin.

The runtime criterion was not met by the first design: one search with the 2.5 m lattice
along the whole 300 km took 38 s at the Shackleton record and 96 s at the Malapert
record. The threshold stayed; the search was split into the two zones. The comparison
surface of the real-data test was changed with that design (the site's own 5 m raster
instead of all three), as section 1 defines it; the tolerance was not touched.

## 3. The three site records on the 20 m product and with the 5 m near field

14 November to 14 December 2026 (720 h), observer at 2 m unless said otherwise. Sun: any
part of the disc; Earth: centre.

| | Shackleton rim crest | de Gerlache rim crest | Mons Malapert summit |
|---|---|---|---|
| Terrain height at the site, 20 m / 5 m | 1701.07 / 1701.02 m | 1815.19 / 1815.33 m | 5173.50 / 5172.89 m |
| Horizon, 5 m minus 20 m: median | 0.000 deg | 0.000 deg | +0.148 deg |
| ... 95 % of the azimuths within | 0.37 deg | 0.08 deg | 0.50 deg |
| ... largest lower / higher | 0.22 / 0.80 deg | 0.14 / 0.56 deg | 0.06 / 0.79 deg |
| ... at 10 m observer height, 95 % within | 0.07 deg | 0.01 deg | 0.14 deg |
| Horizon set within 1 km, share of azimuths | 22 % / 22 % | 15 % / 15 % | 70 % / 76 % |
| Obstacles of the profile (within 1 km) | 39 (9) / 45 (15) | 48 (4) / 51 (7) | 40 (26) / 40 (26) |
| Sun visible at 2 m | 667.7 / 667.7 h | 720.0 / 720.0 h | **701.2 / 619.1 h** |
| Sun visible at 5 m | 673.6 / 674.6 h | 720.0 / 720.0 h | 720.0 / 720.0 h |
| Sun visible at 10 m | 687.5 / 687.6 h | 720.0 / 720.0 h | 720.0 / 720.0 h |
| Sun time lost to terrain against a smooth sphere | 52.3 / 52.3 h | 0 / 0 | 0 / 0 (gained 236.4 / 154.4 h) |
| Earth visible at 2 m | 322.6 / 322.6 h | 352.5 / 352.5 h | 592.6 / 586.6 h |
| Earth visible at 10 m | 322.7 / 322.7 h | 352.7 / 352.7 h | 668.6 / 653.8 h |
| Circle of 100 m, 13 points, Sun: least, median | 424, 558 / 439, 516 h | 0, 531 / 0, 528 h | 477, 540 / 348, 547 h |

Each cell gives the 20 m product first, the 5 m near field second.

What the difference measures. At the Shackleton and de Gerlache records the hours do not
change, although single azimuths of the horizon differ by up to 0.8 degrees: the Sun's
path does not cross those azimuths at a critical height in this month. At the Malapert
summit the 5 m raster puts the ground 0.6 m lower and the surrounding summit relief
0.15 degrees higher in the median, and a 2 m observer loses 82 of 701 Sun hours; at 5 m
height nothing is left of the difference. So the 20 m interpolation mattered where the
horizon is set within a few hundred metres of a low observer, by an amount inside the
spread that one-pixel shifts had already shown on the 20 m product (578 to 720 h).

**Shackleton, the obstacles.** The 52 lost hours stand on both products, and they are
still caused by terrain 0.3 to 0.7 km away between azimuths 336 and 351 degrees, 2.7 to
3.2 degrees high. The split changes: 20.7, 17.0 and 14.5 h for three obstacles on the
20 m product; 19.4, 10.0, 7.0 and 4.0 h and smaller shares for more obstacles on the 5 m
raster. Moving the site by 5 m changes the Sun hours by up to 19 h on the 5 m raster
(648.8 to 668.7 h), by 20 m by up to 121 h (546.6 to 670.2 h; on the 20 m product 585.4
to 669.2 h). The earlier wording holds: an order of magnitude for this pixel, not a
prediction, and the obstacles are not named features.

**de Gerlache, the hollow.** The point with no Sun, 82 m from the record, is in the 5 m
raster too, 17.1 m below the record (16.1 m on the 20 m product), with a horizon of 5.0
to 14.3 degrees set 37 to 79 m away.

| Observer | 20 m product | 5 m near field |
|---|---|---|
| 2 m | 0 h | 0 h |
| 5 m | 12 h | 0 h |
| 10 m | 526 h | 370 h |
| 20 m | 720 h | 720 h |
| 2 m, moved 5 m (eight directions) | 0 | 0 |
| 2 m, moved 20 m | 0 to 162 h | 0 to 55 h |
| 2 m, moved 40 m | 149 to 612 h | 106 to 604 h |

The hollow is therefore not produced by the gridding of the 20 m product: a raster
gridded separately at 5 m from the same returns shows it, slightly deeper. It is a
feature of the LOLA data about 100 m across, most likely a small crater. What was said
before stays true and gets sharper: the lighting within 100 m of this record ranges
from none to continuous, the result at a point depends on where it is within 40 m and
on a few metres of observer height, and nothing follows from it for the rim as a site.
What changes: this is a statement about small relief that the data resolve, not about
the resolution limit of the 20 m product.

## 4. The band, fed by the errors of the products

The stated height error is now a model (`uncertainty.dem_height_error_model`). The one
shipped as default, with its source in the file:

- on a 5 m site raster: twice the producers' RMS error map at the pixel of the terrain
  point that sets the horizon (0.2 to 1.6 m at the three records), 1 m where the map is
  empty;
- on every other product: 5 m where that point lies on a slope of up to 30 degrees, 7 m
  above (the data stream's two-sigma figures from the 20 m product against the 5 m
  rasters).

The constants 0.5, 1 and 2 m of the first version remain selectable; they have no
source. Per azimuth the horizon is raised and lowered by `atan(height error /
distance)`, as before. The package writes the error of every limiting point, whether its
pixel holds a laser return, and for every event what fed its band.

Sun band at 2 m (possible minus certain), and the spread of the Sun's rise and set times:

| Site record | 20 m product, 5 m / 7 m by slope | 5 m near field, error map | Events on the 20 m product | Events with the near field |
|---|---|---|---|---|
| Shackleton rim crest | 85.9 h (592.8 to 678.8 h) | 13.9 h (655.3 to 669.2 h) | set 11.8 h, rise 74.1 h | set 1.1 h, rise 1.8 h |
| de Gerlache rim crest | 18.2 h (701.8 to 720.0 h) | 0 h | none | none |
| Mons Malapert summit | 217.6 h (502.4 to 720.0 h) | 94.9 h (590.3 to 685.3 h) | 208 h, the events merge | 20.6 and 27.8 h |

Earth band at 2 m: 0.1 h, 0.3 h and 73.0 h on the 20 m product; 0.1 h, 0.3 h and 7.3 h
with the near field. Where the horizon is set within a kilometre, a 5 m error is degrees
of horizon (3.8 degrees at the nearest azimuth of the Shackleton record) and the band is
wide: on the 20 m product alone the Sun's return at the Shackleton record is known to
three days, and at the Malapert summit the band is a third of the month. With the 5 m
rasters the same events are known to one or two hours at Shackleton and to about a day
at Malapert.

Which pixels the events rest on, near field on: at the Shackleton record the Sun's set
on a pixel with a laser return (0.31 m), its rise on an interpolated one (0.37 m); at the
Malapert summit three of four events on interpolated pixels. Over the whole profile 30,
37 and 59 % of the limiting points lie on interpolated pixels (19, 29 and 21 % on the
20 m product).

## 5. Limits

1. **One instrument.** Every product is LOLA. The 5 m rasters check the gridding of the
   20 m product, not the returns. The RMS maps are the producers' model estimate, not a
   test against independent data, and errors common to all LOLA products are in no band.
2. **Interpolated pixels.** A third to a half of the limiting points near the sites lie on
   pixels without a return. Their error-map values are the producers' estimate for
   interpolated ground; the package marks the events that rest on them.
3. **The band is still one-sided reasoning.** The same sign at every azimuth, and the
   lowered profile ignores the terrain behind the limiting point
   ([uncertainty.md](uncertainty.md), section 5).
4. **Three records.** The 5 m rasters exist for these sites only; elsewhere the 5 m and
   7 m figures apply and the bands are as wide as shown for the 20 m product.
5. **Patches.** The terrain patches for drawing are read at 20 m and coarser as before;
   with the near field on, the drawn ground and the 5 m surface of the science differ by
   about a metre near the site.
6. **Offsets between the products.** The data stream measured a horizontal offset of
   6.6 m between the 5 m and the 20 m product at Malapert; where the search changes zone
   the surface changes product without blending.
