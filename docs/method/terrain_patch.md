# Terrain patches: the ground a viewer draws

Code: `core/lsncore/terrain_patch.py`, terrain access in `core/lsncore/dem.py`, wiring in
`core/lsncore/pipeline.py`. Tests: `core/tests/test_terrain_patch.py`. Package fields:
contract 0.7, [`docs/contract/SPEC.md`](../contract/SPEC.md) section 5.9.

Status on 14 November 2026: the geometry is checked against closed forms, and on LOLA
terrain the patches are checked against the data reader and against the horizon of the
same package. **One criterion fixed beforehand was not met at two of three site records
(section 3).** A patch is for drawing; no number of the tool is computed from it.

## 1. What is written

For every site, square grids centred on it in its local East/North/Up frame (origin at
the ground point of the site, up along the outward radial of the reference sphere). The
value at a node is the **up coordinate of the surface point whose east and north
coordinates are those of the node**. A viewer places a vertex at (east, north, up) and
needs no projection and no curvature correction: on a smooth sphere the values fall off
as `-(east^2 + north^2) / (2 r)`, 0.3 m at 1 km, 18 m at 8 km and 295 m at 32 km, and
that is in the numbers.

How a node is computed: its surface point lies at distance `R + h` from the centre, `R`
being the reference radius and `h` the terrain height at the point's latitude and
longitude, which in turn depend on that distance. Starting from the radius of the site,
the point is recomputed until the radius changes by less than 0.1 mm (the place moves by
the height change times the sine of the angle from the site, at most 0.026 at 45 km, so
a few rounds are enough).

Which data: bilinear interpolation of the block-average level of the elevation product
whose pixel is the coarsest not larger than the grid spacing. A coarse patch therefore
shows averaged ground, not single samples of the fine grid. The manifest names product,
level, pixel size and the SHA-256 of the file read, and for a derived level the SHA-256
of the product it was derived from.

Default patches, chosen by the team (a scenario may state others):

| Id | Side | Spacing | Nodes | Bytes (float32) | Read from, at the three site records |
|---|---|---|---|---|---|
| `near` | 4 km | 20 m | 201 x 201 | 161 604 | `LDEM_80S_20M`, level 0 |
| `mid` | 16 km | 80 m | 201 x 201 | 161 604 | `LDEM_80S_20M`, level 2 (average of 4 x 4 pixels) |
| `far` | 64 km | 320 m | 201 x 201 | 161 604 | `LDEM_80S_20M`, level 4 (average of 16 x 16 pixels) |

484 812 bytes per site. Each patch is four times as wide and four times as coarse as the
one before, so the grid spacing is at most one twenty-fifth of the distance wherever a
patch is the finest one available (beyond 2 km and beyond 8 km). Computing the three
takes 0.1 to 0.6 s per site.

## 2. Checks

Thresholds were fixed in the test file before the first run.

| Case | Threshold | Measured |
|---|---|---|
| Smooth sphere, three sites (one 11 km from the pole, one next to the 180 degree meridian): values against `sqrt(r^2 - east^2 - north^2) - r` | 0.002 m | passes |
| Rolling analytic surface, two sites: every node turned back into latitude, longitude and height with frame vectors written out in the test, against the surface | 0.05 m | passes |
| A hill at a known bearing and distance appears at that place of the grid (three sites, one per patch) | one grid spacing | passes |
| A patch that reaches beyond the data holds NaN there and the package says so | exact | passes |
| LOLA, three site records: nodes of the near patch against the data reader at the finest level | 0.05 m | 0.0001 m |
| LOLA: nodes of the mid and far patch against the data reader at their level; product, level and checksums in the manifest against the reader's own record | 0.05 m; equal | 0.0002 m; equal |
| LOLA: near patch drawn between its nodes against the finest data at 2000 random places, largest difference | 5 m | 2.5, 1.5 and 1.8 m |
| ... and 95 % of the places | 0.5 m | **0.83, 0.55 and 0.49 m: not met at two records** |
| LOLA: horizon of the drawn surface against the package horizon (section 4), all patches: share of the azimuths inside the tolerance | 95 % | 99.9, 100 and 100 % |
| ... no azimuth off by more than the outer tolerance | all | holds |
| ... the same two for the far patch alone | 95 %; all | 99.9, 100 and 100 %; holds |
| Size of the default patches of one site | 500 000 bytes | 484 812 |

The three site records are the Shackleton rim crest, the de Gerlache rim crest and the
Mons Malapert summit of the data stream, in that order wherever three numbers are given.

One expectation in the test file was wrong and was corrected before the LOLA tests ran:
the check of a patch that reaches beyond the data assumed a straight data edge, while a
circle of latitude bends towards the site away from its meridian. The comparison was
restricted to a strip around the meridian. No tolerance was touched.

## 3. The criterion that was not met

Between its nodes a viewer draws a patch as a bilinear surface. The test asked that this
surface stay within 0.5 m of the finest elevation data at 95 % of 2000 random places of
the near patch. Measured: 0.83 m at the Shackleton record, 0.55 m at the de Gerlache
record, 0.49 m at the Malapert record. The criterion stands as written; the two cases are
marked in the test file as known failures, and nothing was changed to make them pass.

What it means. At its nodes the near patch equals the elevation model to 0.1 mm, so the
difference is not an error of position or of height. The patch is a 20 m grid in the
site's east-north orientation; the elevation model is a 20 m grid in the orientation of
its map projection. Between nodes the two are different surfaces through the same
terrain. Looked at afterwards (not a criterion): near the Shackleton record a node of the
near patch differs from the mean of its two neighbours by 0.5 m in the median and by
2.2 m at 95 %, with a median slope of 0.36. The 0.5 m was an assumption about how smooth the 20 m
model is, and on rim terrain it is rougher than that. For drawing, 0.8 m in 20 m is not
visible; what matters for a viewer is the silhouette, which is section 4.

## 4. How close the drawn silhouette is to the package horizon

The horizon of the drawn surface was computed the way a renderer sees it: straight rays
from the observer (default height, 2 m) over the bilinear surface, the finest patch
winning where several overlap, every 0.25 degrees. It was compared with
`horizon.elevation_deg` of the same package.

**Tolerance, fixed beforehand.** What a grid allows is a height error at the terrain that
sets the horizon: a ridge with side slopes of 0.6 loses 0.15 of the grid spacing when
averaged over one cell. So the tolerance is the angle that 15 % of the grid spacing
(3 m, 12 m, 48 m) subtends at the distance of that terrain, plus 0.02 degrees: 0.11
degrees at 2 km for the near patch, 0.36 degrees at 2 km and 0.11 degrees at 8 km for the
mid patch, 0.36 degrees at 8 km and 0.11 degrees at 32 km for the far patch. It must hold
at 95 % of the azimuths, and no azimuth may be off by more than the same with 50 % of the
spacing. Where the package horizon is set by terrain beyond the patches, the drawn
surface only has to stay below it.

**Measured, all three patches**

| Site record | Azimuths whose limiting terrain lies on the patches | Difference there: median, 95 %, largest | Drawn surface above the package horizon, any azimuth |
|---|---|---|---|
| Shackleton rim crest | 699 of 1440 | 0.04, 0.33, 0.46 deg | at most 0.015 deg |
| de Gerlache rim crest | 408 of 1440 | 0.04, 0.11, 0.16 deg | never |
| Mons Malapert summit | 1187 of 1440 | 0.03, 0.09, 0.21 deg | at most 0.023 deg |

By distance of the terrain that sets the horizon (95 % and largest difference):

| Distance | Patch | Shackleton | de Gerlache | Malapert |
|---|---|---|---|---|
| up to 500 m | near | 0.41, 0.46 deg | 0.11, 0.16 deg | 0.10, 0.21 deg |
| 500 m to 2 km | near | 0.05, 0.11 deg | no azimuth | 0.04, 0.06 deg |
| 2 to 8 km | mid | 0.02, 0.02 deg | 0.09, 0.13 deg | 0.04, 0.05 deg |
| 8 to 32 km | far | 0.09, 0.22 deg | 0.10, 0.12 deg | 0.09, 0.09 deg |

The largest differences are where terrain within 500 m sets the horizon: a metre of
height is half a degree at 100 m, and there the drawn 20 m grid and the bilinear model
differ by up to 2.5 m (section 3).

**Measured, far patch alone.** Where the horizon is set by terrain beyond 8 km: median
0.04, 0.03 and 0.07 degrees; 95 % 0.09, 0.10 and 0.09 degrees; largest 0.22, 0.13 and
0.13 degrees. Nearer terrain is averaged away by 320 m cells: there the far patch alone
is off by up to 3.3 degrees, which is what the near and mid patches are for.

For comparison, the Sun's disc is 0.53 degrees across. A renderer that decides by itself
whether the Sun is behind the drawn ground can therefore be wrong by a large part of the
disc near the site; that is the reason for the rule in section 5.

What averaging costs in height (nodes against the finest data): mid patch median 0.7 to
0.9 m, 95 % 2.3 to 3.4 m, largest 12 to 27 m; far patch median 2.3 to 2.5 m, 95 % 8.9 to
9.3 m, largest 69 to 75 m.

**With the 5 m near field** (`core/tests/test_near_field.py`, measured on 14 November
2026 at the three site records). Since the data stream built overview levels for the 5 m
site rasters, a patch is read from the raster the science used wherever that raster has
a level with the pixel of the patch; the package names raster and level in `sources`.
Tested: every such node within 0.05 m of that level (threshold fixed beforehand).

| Patch | Shackleton record | de Gerlache record | Malapert record (on Site23, measured 14 November; that raster is no longer used, see [near_field.md](near_field.md)) |
|---|---|---|---|
| near, 20 m | 5 m raster, 20 m block average, all nodes | the same | the same |
| mid, 80 m | 5 m raster 80 %, 20 m product 20 % | 86 % and 14 % | 20 m product only: this raster has levels to 40 m |
| far, 320 m | 5 m raster 6 %, 20 m product 94 % | the same | 20 m product only |
| Centre node of the near patch against the ground point of the science | -0.20 m | -0.79 m | 0.00 m |
| Near patch drawn between its nodes against the 5 m surface, 2000 places: median, 95 %, largest | 0.18, 0.85, 2.3 m | 0.14, 0.69, 3.3 m | 0.16, 0.76, 2.5 m |
| ... within 100 m of the site | 0.17, 0.79, 1.8 m | 0.22, 1.42, 4.9 m | 0.09, 0.51, 1.2 m |

So the drawn ground follows the surface of the science to a few decimetres in the
median. It cannot follow it exactly: a 20 m grid of block averages does not hold 5 m
relief. At the de Gerlache record, a crest with a hollow beside it, the drawn ground at
the observer's feet is 0.8 m low and up to 4.9 m off within 100 m.

A scenario can state a finer patch for that, and the core serves it today without any
change: `{"id": "site", "half_width_m": 500, "spacing_m": 5}` in `terrain_patches`, next
to the three defaults. Measured at the three records: read from the 5 m raster itself
(level 0), centre node 0.000 m, drawn between nodes within 100 m of the site median
0.003 to 0.006 m, 95 % 0.04 to 0.08 m, largest 0.4 to 0.8 m; 201 x 201 nodes, 161 604
bytes. It is not written by default: the default set stays the three patches the
viewers were written for.

## 5. Limits

1. **For drawing only.** The horizon, the windows and the event times of a package are
   computed on the finest data with a search that proves it misses nothing
   ([horizon.md](horizon.md)). A viewer takes "visible" or "hidden" from the timeline and
   never from rays against the patch. Where the drawn surface and the horizon profile
   disagree, the profile is right; drawing the profile as a line on top makes that
   visible instead of hiding it.
2. **Averaged ground.** The mid and far patches are block averages: crests are lower,
   narrow gaps are filled, by the amounts in section 4.
3. **The elevation model's own limits remain.** A patch reproduces the model, not the
   Moon: relief narrower than two 20 m pixels is in neither
   ([uncertainty.md](uncertainty.md), section 5).
4. **Nothing beyond 32 km.** Terrain farther than the largest patch is in the package
   only as the horizon profile with the distance of the limiting terrain; a viewer can
   draw that as a backdrop, not as a surface.
5. **A height field in the tangent plane.** One value per (east, north): no overhangs.
   32 km from the site a cell covers 0.02 % more ground than at the site.
6. **Edge of the data.** Nodes outside the elevation products are NaN and must be left
   out of the mesh; the package carries a warning with their share.
7. **Three site records.** The measured values are for three rim and summit points of
   the LOLA south-polar products; other terrain can differ.
