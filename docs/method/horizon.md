# Terrain horizon: method, checks and limits

Code: `core/lsncore/horizon.py`, terrain interface `core/lsncore/dem.py`.
Tests: `core/tests/test_horizon.py`, `core/tests/test_pipeline.py`.

Status on 15 November 2026: checked against analytic cases, against exhaustive reference
scans on a gridded synthetic raster and on the LOLA south-polar products. **Not compared
with an independent horizon product** (another tool or a published horizon); `validation/`
compares what follows from the horizon, sunlight at a place and time, with published maps
and images. Errors of the elevation model are not in the horizon itself; a package can
carry a band for a stated error ([uncertainty.md](uncertainty.md), since contract 0.4 and
0.6). What is established below is that the code finds the horizon of the surface it is
given, from the site outward; how well that surface matches the Moon is a separate
question (section 8).

## 1. What is computed

For a site (latitude, east longitude) and each observer height `m` above the terrain, the
horizon elevation in azimuth `A` is the largest elevation angle, above the plane
perpendicular to the radial direction at the site, of the straight line from the observer
to any terrain point on the great circle that leaves the site at azimuth `A`, out to the
search radius. Azimuth is clockwise from north. The value is negative where the terrain
horizon lies below the horizontal, which is normal on ridges and at any height above a
plain. Together with the angle, the terrain point that sets it is stored: distance (arc
length on the reference sphere), height, latitude, longitude.

The Moon is a sphere with the reference radius of the elevation model; terrain heights
are radial offsets from it. Coordinates are in the body-fixed mean-Earth/polar-axis frame
of the LOLA products. The terrain surface is the bilinear interpolation between pixel
centres of the finest product that covers a point, exactly as the data stream's reader
returns it.

## 2. Geometry

Observer `P` at distance `r_o = R + h_ground + m` from the centre, terrain point `Q` at
`r_t = R + H`, central angle `g` between them. In the plane through `P`, `Q` and the centre:

```
tan e = (r_t cos g - r_o) / (r_t sin g)
```

No small-angle approximation and no separate curvature correction: curvature is in the
triangle. The code evaluates the algebraically equal form

```
tan e = ((H - h_ground - m) - 2 r_t sin^2(g/2)) / (r_t sin g)
```

whose numerator is a difference of two small numbers (height difference, curvature drop)
instead of two radii. Points are generated on the sphere from the site's East/North/Up
unit vectors, `p = cos g * up + sin g * (cos A * north + sin A * east)`, which stays well
conditioned at the poles and across the 180 degree meridian. At a pole the azimuth zero is
the meridian of the longitude that was given for the site.

## 3. Search along a ray

A ray of 300 km over 20 m pixels would need 30 000 evaluations to be walked completely,
43 million per site. Sampling it sparsely instead is fast but wrong: the first version of
this code read far terrain at growing steps from averaged overview levels, and the first
runs on LOLA data showed it stepping over narrow crests (0.19 deg at 14.5 km in one
azimuth, 0.13 deg for an obstacle 42 m away in another). The search was therefore
rebuilt so that nothing is skipped without proof:

1. **Lattice.** Points half a pixel apart cover the whole ray, starting one pixel from
   the site and never farther than 20 m (section 9) (10 m steps for the 20 m product; 2.5 m steps in the first 200 m, where the
   elevation angle is most sensitive to small relief).
2. **Near zone.** Every lattice point out to about 2.3 km is evaluated on the finest data
   (229 lattice steps: 0.6 km for a 5 m raster, 13.6 km for the 118 m global product).
   The ground in front of the first point is evaluated as well, for every observer
   height: at eighths of its distance and then at that distance halved down to about
   2 cm (section 8, item 6).
3. **Cells with a proof.** Beyond that the lattice is grouped into cells whose length
   grows with distance (0.5 deg in radians times the distance, up to 2.4 km). For each
   cell the terrain source returns an upper bound of the surface inside it, read from
   block-maximum overview levels. From that bound follows the highest elevation anything
   in the cell could have. A cell is skipped only if this is below the horizon already
   found for every observer height; all other cells are walked lattice point by lattice
   point on the finest data. The cells are walked in rounds, the most promising of each
   azimuth first: one cell per azimuth, then two, four and so on. What a round finds
   raises the horizon found so far, and the next round skips every cell whose bound no
   longer exceeds it. A cell is only ever skipped on that comparison, so the order
   changes how much is walked, not what is found (tested: elevation, distance and
   height of the limiting point identical to the last bit for three orders).
4. **Creases.** Between two lattice points a bilinear surface has creases where the ray
   crosses a line through pixel centres, and the highest point of a crest between
   lattice points usually lies on one. The terrain source reports these crossings and
   they are evaluated too, for every stretch of ray that was evaluated at all.
5. **Refinement.** The four best near-zone maxima and the best point of each azimuth are
   refined by nested sampling (four rounds of nine points; the bracket shrinks 256 times).

The bound in step 3 is rigorous for the surface as defined: the bilinear surface at a
point is a weighted mean of the four finest pixels around it, and the 3 x 3 neighbourhood
of the overview block that contains a point contains every finest pixel within one block
size of it. The map scale of the polar stereographic projection is taken into account
when the neighbourhood size is chosen.

On the LOLA products, 0.15 to 1.3 % of the lattice beyond the near zone has to be walked;
the rest is excluded by the bound (measured with one cell per azimuth first and then
all remaining cells at once; with the rounds of step 3, in use since 14 November 2026,
a quarter to a third fewer, [near_field.md](near_field.md), section 2). All observer heights share the same terrain
evaluations. The size of the cells changes the cost, not the result: a cell is either
proven irrelevant or walked completely.

| Setting | Value |
|---|---|
| Azimuth step | 0.25 deg (1440 rays), configurable |
| First point | the lattice starts one finest pixel from the site, at most 20 m. In front of it, for every observer height: 7 points at eighths of that distance, and more at that distance halved from 1/16 on as long as they are not closer than 1 cm (2 cm for 5 m and for 20 m pixels). Closer than that a point cannot be placed well enough: the slope of the ground at the site changes by 0.001 deg between 1 and 2 cm |
| Map convention | off. `ground_from_first_point` leaves the points in front of the first one out for the 0 m observer only, for comparisons with pixel-based illumination maps; the method card of a package says which was used |
| Lattice step | half a finest pixel; an eighth of a pixel within 10 pixels of the site |
| Cell length | 0.5 deg in radians times the distance, at most 256 lattice points, and never more than the overview levels can bound |
| Interpolation | bilinear between pixel centres (data reader), finest product that covers the point |
| Arithmetic | 64-bit floats; arrays are stored as 32-bit floats in the package (rounding of an angle near 10 deg: about 1e-6 deg) |

## 4. Search radius and what lies beyond it

The default search radius is 300 km. Whether that is enough is not assumed but bounded,
per azimuth and observer height. A terrain point of height `H` at central angle `g` is
seen at `atan2((R+H) cos g - r_o, (R+H) sin g)`; this grows with `H` and, beyond the
tangent point, falls with `g`. So if no terrain beyond the end of a ray is higher than a
ceiling `H_c`, it can raise the horizon found by at most

```
bound = max(0, elevation of a point of height H_c at the end of the ray - horizon found)
```

The package stores, in `horizon.error_bounds`:

| Name | Meaning |
|---|---|
| `far_field_max_deg` | Largest bound over all azimuths and heights. 0 means: proven complete under the ceiling assumption |
| `far_field_open_azimuth_fraction` | Share of azimuths whose bound is not zero |
| `ceiling_height_m` | The ceiling used: the highest terrain in the elevation products. If the terrain source cannot state that, the highest of what the search evaluated is used instead: the near zone, the limiting points found and the site (a warning says so). That is not the highest terrain inside the search radius, because cells that were skipped were never read; the bound is then weaker than its name suggests. No published package uses this fallback |
| `shortest_reach_m` | Shortest ray: the search radius, or less where the data ends earlier |

Where data ends before the search radius, the ray ends there: the flags
`truncated_at_data_edge` and `coverage_complete`, the `nodata_fraction` and a warning
record it, the package status becomes `partial`, and the bound is computed from the
actual end of each ray. A site without terrain data is an error, not a package.

300 km is not always enough. For a test point 6 km above the reference sphere (latitude
-85.3, longitude 31.2) the bound is 0.15 deg in 1.1 % of the azimuths: seen from that
height, terrain as high as the highest in the LOLA polar products could still appear
above the horizon from beyond 300 km. For the other five test points the bound is zero.

## 5. Acceptance tests and measured accuracy

Thresholds were written in the test file before the corresponding code was implemented
and measured; none was changed afterwards. Expected values come from geometry written
independently in the test file (the unrearranged triangle formula, haversine distances,
classic great-circle formulas).

### 5.1 Analytic surfaces

Sites: latitude -85, the south pole itself, 110 m from the pole on the 180 degree
meridian, latitude -80 at longitude -179.5, latitude +12 and latitude +88.

| Case | Threshold (fixed first) | Measured |
|---|---|---|
| Smooth sphere, observer 1, 2, 10, 100 m up: depression `-acos(R/(R+m))`, 6 sites | 0.0005 deg | 3.0e-12 deg |
| Crater rim at a known distance and height (parabolic bowl 1500 m deep, rim at 20 km; observer 0, 2, 20 m), 6 sites | 0.001 deg | 2e-13 deg |
| ... reported distance to the rim | 10 m | below 0.001 m |
| ... reported obstacle height | 1 m | below 1e-4 m |
| ... obstacle latitude and longitude against azimuth and distance | 1 m | 5e-10 m |
| Smooth hill 60 km away, 5 azimuths, against an independent dense 1-D solution | 0.002 deg | 3.4e-8 deg |
| Several heights in one pass against one run per height | 1e-9 deg | 0 |

In the final algorithm the rim of the crater case coincides with a lattice point, so that
case now tests the formula and the bookkeeping rather than the search between points; the
search between points is tested by the hill case and by section 5.2.

### 5.2 Gridded surfaces: nothing may be missed

Reference: an exhaustive walk along the ray on the finest data in 1 m steps with the
unrearranged formula. Both the code and the reference can only report elevations of
points that exist on the surface, so the test is one-sided: the code must not be lower
than the reference by more than the tolerance. In addition, the point the code reports
is recomputed independently from the data and must have the elevation the code states.

| Case | Threshold (fixed first) | Measured |
|---|---|---|
| Synthetic rough raster with single-pixel spikes of 40 to 200 m (20 m pixels, with overviews), 3 sites x 16 azimuths x 3 observer heights | never more than 0.002 deg below the reference | worst case 0.000000 deg below; up to 0.011 deg above |
| LOLA products (20 m and 60 m south-polar), 3 arbitrary test points x 12 azimuths, observer 2 m, 300 km (in the test suite; skipped where the data is absent) | same | 0.000000 deg below |
| LOLA products, 6 test points x 36 azimuths x 3 observer heights (measured once, by script) | same | worst case 0.000000 deg below; up to 0.1 deg above within 1 km, 0.008 deg above beyond |
| LOLA products, a site at latitude -82 whose rays leave the 20 m product (in the test suite) | same | 0.000000 deg below |
| Reported obstacle recomputed from the data | 1e-5 deg | passes |
| Data stream's gridded 100 m synthetic raster against its analytic surface (bowl, ring ridge at 12 km), smooth part | 0.02 deg | 0.0052 deg (mean -0.0026 deg) |

Where the code is above the reference, it found a crease or a peak between the
reference's 1 m steps; the recomputation confirms these points are real.

**The first pixel.** The reference above starts 20 m from the site, as the search did
until 15 November 2026, so neither could see what the ground closer than that does. Two
independent reviews scanned from 1 m and found the horizon of a 0 m observer too low: by
0.5 to 0.8 degrees at two places, and in the published packages by up to 0.49 degrees
at the Shackleton record (in 24 % of the azimuths by more than 0.1) and 0.16 degrees at
Apollo 15. Repeated here with a scan that starts 5 cm from the site, in 5 cm steps
(tolerance 0.002 deg, as above):

| Observer | Before | Now |
|---|---|---|
| 0 m, LOLA 20 m product, five places, all 1440 azimuths | too low by up to 2.8, 0.7, 4.4, 0.03 and 2.7 deg; at the Shackleton record in 957 azimuths | nothing over the tolerance (five places in the test suite, 72 azimuths each) |
| 1 m to 20 m, LOLA, the same places | nothing over the tolerance | nothing over the tolerance |
| 0 m and 1 m, synthetic rough raster with single-pixel spikes | 1 m: too low by 1.69 deg at one site | nothing over the tolerance |

So the ground between the site and the first lattice point is terrain like any other,
and the search looks at it now, for every observer height. Two cases of the reviews are
tests:

- A point of an LRO image (`validation/lro_images`, `row+700_along11500`) that the image
  shows in shadow and the core had as sunlit. From 20 m outward the horizon towards the
  Sun is at 0.00 deg; the ground at the site rises 0.11 m within the first 20 m, 0.70 deg
  seen from the surface, and the Sun's upper limb stood at 0.62 deg. With the ground at
  the site the horizon is 0.71 deg and the point is in shadow. Two metres up the Sun is
  in view either way.
- A point of the comparison with a published illumination map (`validation/pgda`,
  `plain_or_slope_03`), a pixel centre in a shallow pit: on the 60 m product the ground
  at the site raises the 0 m horizon in 1332 of 1440 azimuths, by 0.38 deg in the median.
  A map of 60 m pixels has no such thing as the ground inside its pixel, so for that
  comparison the map convention below is the like-for-like setting.

What it changes (measured on the 20 curated sites, as published: two project sites on
their 5 m raster): nothing at 2 m, to the last bit, at all 20 sites; at 1 m and above no
horizon value by more than 1.5e-12 deg. At 0 m the horizon rises by up to 0.50 deg at
the Shackleton record (24 % of the azimuths by more than 0.1 deg), 9.2 deg at the de
Gerlache record (55 %), 3.0 deg at the Malapert record (63 %), 2.4 deg at Chang'e 5,
1.0 deg at Surveyor 1 and less than 0.5 deg elsewhere. In 30 days from 14 November 2026
the Sun is in view of the 0 m observer for 410.8 h instead of 421.0 h at the Shackleton
record, 387.0 instead of 544.0 h at de Gerlache (the Earth 129.4 instead of 286.7 h) and
440.0 instead of 516.6 h at Malapert.

**Map convention.** `HorizonSettings.ground_from_first_point` leaves the ground in front
of the first lattice point out for the 0 m observer, and for it only: the horizon of a
surface element as a pixel-based illumination map has it, from one sample outward.
Tested: every other height is untouched to the bit, the 0 m horizon agrees with the
default wherever the default's limiting point lies beyond the first lattice point (to
1e-5 deg; the two searches refine different candidates), and it is complete from the
first point outward. Together with `first_sample_max_m = inf` it gives the horizon the
core computed before 14 November, when the lattice started one pixel from the site on
every product. It is off by default and the method card of a package states it.

Self-convergence on LOLA data: repeating the six test points with a lattice four times
finer, 16 refined maxima and six refinement rounds changes no value by more than 0.0006
deg (51 840 values: 6 points x 6 heights x 1440 azimuths).

The 0.005 deg on the 100 m raster is the grid, not the algorithm: bilinear interpolation
between 100 m pixels cuts the top of a ridge whose crest is 1 km wide, so the gridded
horizon is lower than the analytic one. At the tip of that raster's cone, a point
feature, the grid is 0.18 deg lower than the analytic surface.

### 5.3 Conventions

A hill placed one degree east of a site on the equator appears at azimuth 90; from the
south pole (longitude 0 given), a hill at longitude 90 east appears at azimuth 90; through
the data reader, the cone of the synthetic raster at longitude 90 east appears at azimuth
90 and not at 270.

### 5.4 Changes to tests after their first run

Recorded here because thresholds and reference files must not be bent to make a test pass.

- Far-field test: the mountain placed outside the search radius was too low to raise the
  horizon by the 0.1 deg the test demands as proof that the case is not trivial. The
  mountain was made higher and closer. No tolerance and no inequality was changed.
- Runtime tests: a single timed run was replaced by the shortest of three runs, after
  single runs failed while the laptop's processor was slowed down (section 6). The 5 s
  limit was not changed.
- Completeness tests: the first version also demanded that the code be no more than 0.002
  deg *above* the 1 m reference for obstacles beyond 1 km. The code turned out to be
  above it (0.0022 deg on LOLA data, 0.011 deg on the spiked raster) because the
  reference misses creases between its steps. That comparison was replaced by the
  independent recomputation of the reported point. The 0.002 deg tolerance on misses was
  not changed.
- Recomputation of the reported point (15 November): since the ground at the site is
  searched, the point that sets a 0 m horizon can lie two centimetres from the site. The
  test placed the reported point with the classic great-circle formulas, which take an
  arcsine of a number close to 1 near a pole and are good to about 1e-7 m; at a
  centimetre that moved a steep line of sight by 0.001 deg and the check failed at one
  synthetic site. The test now places that point from the unit vectors of the site,
  written out in the test. The 1e-5 deg tolerance was not changed. For the same reason
  the search does not go closer than 1 cm (it had gone to 2.4 mm on a 5 m raster, where
  the check missed the tolerance by 1.4e-6 deg).
- First-pixel tests (15 November): written first with the 0 m case as a stated limit and
  an expected failure; rewritten the same day when the ground at the site was made part
  of the search for 0 m as well. The 0.002 deg tolerance is the same in both versions.

## 6. Runtime

Measured on the team laptop (Windows 11, Python 3.14.7, NumPy 2.5.4), single process,
default settings (0.25 deg, 300 km, six observer heights):

| Terrain source | Time per site |
|---|---|
| LOLA 20 m and 60 m south-polar products with six overview levels, six test points, three runs each | 1.0 to 1.5 s (median 1.2 s) |
| Analytic function | about 1 to 2 s |

Target: under 5 s. The LOLA runtime is asserted in the test suite when the data is present.

The same call can take three to four times longer on this laptop: after a few seconds of
sustained load the processor lowers its clock, and every NumPy operation slows down by the
same factor (measured: 2.0 s, then 5.8 s, 7.8 s, 7.8 s for four identical calls in a row,
with identical call counts; processor time, not waiting). The search was made cheaper
after that observation (one exact bound per cell for the ground observer and a cheap
valid one for the other heights; larger cells), which brought the time at full clock
speed from about 2 s down to the figures above. The test takes the shortest of three runs.

A defect found by a measurement run, not by the tests: with the larger cells, sample
points beyond the corner of the 20 m raster asked that raster for a neighbourhood it
cannot bound, and the search stopped with an error for a site at latitude -82. Points
whose neighbourhood cannot touch a raster now get nothing from it, and that site is in
the test suite.

## 7. What was learned from the first version

The first version (sparse far sampling on block-averaged overviews, refinement of three
maxima) passed all analytic tests and still missed real obstacles on LOLA data: at three
test points, 4 to 125 of the 1440 azimuths changed by more than 0.01 deg when its range
step was halved, the largest change being 0.19 deg. Smooth analytic surfaces do
not exercise what real terrain does: single-pixel peaks, and creases next to the site.
The completeness tests of section 5.2 were added for that reason, before the search was
rebuilt.

## 8. Limits: where the result must not be trusted

1. **Sub-pixel relief and the first kilometre.** The terrain is the bilinear surface
   through the DEM pixels. Rocks, small craters and crests narrower than a pixel are not
   in it. An obstacle 100 m away needs only 1.7 m of unmodelled height to change the
   horizon by 1 deg. On the six LOLA test points the horizon was set by terrain closer
   than 1 km in 14 to 66 % of the azimuths (observer at 2 m). `distance_m` shows, per
   azimuth, how near the limiting terrain is; such azimuths depend on DEM detail and on
   the exact observer height.
2. **Elevation model errors are not in the horizon.** Height and position errors of the
   DEM translate directly into horizon errors (height error divided by distance). Single
   high pixels are taken at face value, whether they are terrain or noise. A package can
   carry a band for a stated error; what that band is and is not is in
   [uncertainty.md](uncertainty.md), section 5.
3. **Narrow obstacles between rays.** Each ray is searched completely, but rays are 0.25
   deg apart. On a synthetic rough surface, linear interpolation of the 0.25 deg profile
   differed from a 0.05 deg profile by less than 0.0012 deg in 95 % of the azimuths and
   by 0.026 deg at the worst narrow feature. Not yet measured on LOLA data.
4. **Beyond the data or the search radius.** Nothing is seen there. The far-field bound
   states what could be missed, under the assumption that no unseen terrain exceeds the
   stated ceiling. With the LOLA polar products, rays of sites far from the pole leave
   the data; such packages are flagged `partial`.
5. **Sphere.** Distances, the local vertical and the horizontal plane refer to a sphere of
   the DEM reference radius. The local vertical is the radial direction, not the plumb
   line; the Moon's flattening and gravity anomalies are ignored.
6. **Observer, and the ground at its feet.** A point at height `m` above the DEM surface.
   The lander's own structure is not modelled. The ground between the site and the first
   lattice point is searched like all other terrain, for every height. **Height 0 is the
   surface point itself, and the slope of the ground at the site is part of its horizon:**
   uphill, the horizon of a 0 m observer is at least that slope (5 deg at the Shackleton
   record, 9 deg at de Gerlache). The elevation model does not resolve the ground below
   its pixel; that slope is the slope of the interpolated surface between posts 5 m or
   20 m apart, and where the site sits inside its cell decides it. A 0 m row is therefore
   the lighting of a point lying on the modelled ground, it depends on interpolation far
   more than any row above it, and it is not what a pixel-based illumination map shows
   (section 5.2, map convention). For an instrument on a lander, use a height above 0:
   from 1 m up the ground at the site reached no horizon on LOLA data.
7. **Geometry only.** No refraction (there is none to speak of), no scattering, no
   reflected light; this is line of sight to bare terrain.
8. **Products without overviews.** The proof in section 3 needs block-maximum overview
   levels. Without them every cell is one lattice point and the whole ray is walked: the
   result is the same, the runtime is not.

## 9. Sites away from the poles

Code: `MoonTerrainAdapter` in `core/lsncore/dem.py`; tests `core/tests/test_moon_terrain.py`.
Package field: `horizon.terrain_source`, contract 0.9.

The data stream's whole-Moon reader serves any latitude and longitude: a polar product
where its square covers the place, a latitude-longitude (simple-cylindrical) product
elsewhere (LDEM_128 with 237 m pixels, finer mosaics where installed). The horizon core
uses it through one adapter:

- **Near a pole nothing changes.** If the whole search disc of a site lies inside one
  pole's products, the site is handed to the adapter of those products as if no other
  product existed. The package of the Shackleton record is identical, id and content,
  with and without the whole-Moon terrain (test).
- **Elsewhere** the same search runs on the latitude-longitude grid. Its cells are
  `pixel` wide north-south and `pixel * cos(latitude)` east-west; the lattice follows the
  smaller of the two down to latitude 75 degrees. Beyond that the columns get narrower
  than a lattice step: the lattice keeps its width there and every column line a step
  crosses is evaluated, so the search stays complete at a higher cost per ray.
- **The proof for skipped stretches** needs an upper bound of the surface in a
  neighbourhood. A disc of angular radius `rho` around a point at latitude `phi` spans
  `rho` in latitude and `asin(sin rho / cos phi)` in longitude. The 3 x 3 blocks of an
  overview level around the block of the point bound it if the block is at least the
  wider span plus one pixel; where no level is wide enough (close to a pole, or very
  wide discs) the highest terrain of the product stands in.
- **The first sample.** The search used to start one pixel from the site. On a 20 m
  grid that is 20 m; on a 237 m grid it skipped the ground next to the site, and the
  first run of the completeness test on a coarse synthetic grid failed for that reason
  (0.27 degrees in the uphill azimuths). The first sample is now one pixel away but
  never farther than 20 m. Nothing changes for the 20 m products.

**Checks** (thresholds of section 5: 0.002 degrees against an exhaustive scan in 1 m
steps, 1e-5 degrees for the reported point, 5 s per site).

| Case | Measured |
|---|---|
| Rough synthetic latitude-longitude grid (1.9 km pixels, single-pixel spikes), four sites: at the 0/360 meridian, 300 km search with skipped stretches, latitude 84 where a step crosses several columns; 16 azimuths, three heights each | nothing missed |
| The neighbourhood bound against 4000 sampled points in each of 180 discs (100 m to 200 km; mid latitude, across the 0/360 meridian, next to and over the pole) | never below a sampled point |
| South-polar site through the whole-Moon terrain against the polar adapter alone | same package id and content checksum |
| LDEM_128, five sites (26.1 N; 0.5 N on the far side; 43.3 S; 62 S at the edge of the polar square; 85 N without a polar product), 8 azimuths at 2 m, 300 km | nothing missed |
| Runtime on LDEM_128, six heights, 1440 azimuths, 300 km | 2.6 to 2.9 s at the three mid-latitude sites; 1.4 s at 62 S (60 m polar product); 8.7 s at 85 N on the latitude-longitude grid |

The LDEM_128 rows were measured on 14 November 2026 with overview levels built in a
scratch folder, before the data stream had built its own. Since then every product has
them, and between 60 degrees south and north the reader serves the finer SLDEM2015
mosaic (118 m pixels) instead of LDEM_128. The test now runs on it, and at 26.1 N
nothing is missed. Its first runs took 7.0 and 7.7 s and failed the 5 s limit. The cause
was the finer product together with two wastes in the terrain adapter, not the load on
the machine alone: the search for cell boundaries took consecutive points of different
rays for one long step and looked through up to 64 columns for each, and every tile of
a mosaic was asked about coverage more often than needed. Both were removed; the search
step, the overview levels and the limit were not touched. The data stream then made the
coverage query itself cheap, and the adapter's own shortcut for it was taken out again.

| Core | SLDEM2015 256, 118 m (served at 26.1 N) | LDEM_128, 237 m, alone |
|---|---|---|
| before (commit 595c9a4) | 9.10, 6.17, 5.52 s: best 5.52 s | 2.36, 2.29, 2.27 s: best 2.27 s |
| after (commit bc5a1e6) | 2.65, 2.43, 2.39 s: best 2.39 s | 1.31, 1.30, 1.41 s: best 1.30 s |
| with the data stream's faster coverage query (its commit 05f0fcd) | 1.77, 1.78, 1.62 s: best 1.62 s | 1.16, 1.15, 1.16 s: best 1.15 s |

Six heights, 1440 azimuths, 300 km, three runs each after one run to read the files,
measured on 14 November 2026 with the processors at 26 % load from other work. The
finer product has 8.7 million lattice points beyond the near zone instead of 4.2
million and walks 79 thousand of them instead of 16 thousand. Between 0.4 and 5.5 % of the lattice
points beyond the near zone had to be walked.

**Limits.**

1. A 237 m grid holds no obstacle narrower than about 0.5 km. At the three mid-latitude
   test sites the median distance of the limiting terrain was 1.9 to 19 km; what is
   nearer than a few pixels is a slope of the grid, not an obstacle. Packages say so
   (`resolution_class`, warning).
2. Near a pole without the polar products the latitude-longitude grid is slow (8.7 s)
   and adds nothing; the package carries a warning.
3. Where a polar square ends, the surface changes product. The two products differ by
   metres there; no blending is done.
4. LDEM_128 has not been compared with an independent horizon by this stream.
