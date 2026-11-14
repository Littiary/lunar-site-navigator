# Terrain horizon: method, checks and limits

Code: `core/lsncore/horizon.py`, terrain interface `core/lsncore/dem.py`.
Tests: `core/tests/test_horizon.py`, `core/tests/test_pipeline.py`.

Status on 14 November 2026: checked against analytic cases, against exhaustive reference
scans on a gridded synthetic raster and on the LOLA south-polar products. **Not yet
compared with an independent horizon product** (another tool or a published horizon), and
elevation-model errors are not yet propagated. What is established below is that the code
finds the horizon of the surface it is given; how well that surface matches the Moon is a
separate question (section 8).

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
   the site (10 m steps for the 20 m product; 2.5 m steps in the first 200 m, where the
   elevation angle is most sensitive to small relief).
2. **Near zone.** Every lattice point out to about 4.6 km is evaluated on the finest data.
3. **Cells with a proof.** Beyond that the lattice is grouped into cells whose length
   grows with distance (0.25 deg in radians times the distance, 1.3 km at 300 km). For each
   cell the terrain source returns an upper bound of the surface inside it, read from
   block-maximum overview levels. From that bound follows the highest elevation anything
   in the cell could have. A cell is skipped only if this is below the horizon already
   found for every observer height; all other cells are walked lattice point by lattice
   point on the finest data. The most promising cell of each azimuth is walked first, so
   that the following comparison is as sharp as possible.
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

On the LOLA products, 0.1 to 0.7 % of the lattice beyond the near zone has to be walked;
the rest is excluded by the bound. All observer heights share the same terrain
evaluations.

| Setting | Value |
|---|---|
| Azimuth step | 0.25 deg (1440 rays), configurable |
| First point | one finest pixel from the site |
| Lattice step | half a finest pixel; an eighth of a pixel within 10 pixels of the site |
| Cell length | 0.25 deg in radians times the distance, at most 256 lattice points, and never more than the overview levels can bound |
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
| `ceiling_height_m` | The ceiling used: the highest terrain in the elevation products, or, if that is not available, the highest terrain met inside the search radius (then a warning says so) |
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
| Reported obstacle recomputed from the data | 1e-5 deg | passes |
| Data stream's gridded 100 m synthetic raster against its analytic surface (bowl, ring ridge at 12 km), smooth part | 0.02 deg | 0.0052 deg (mean -0.0026 deg) |

Where the code is above the reference, it found a crease or a peak between the
reference's 1 m steps; the recomputation confirms these points are real.

Self-convergence on LOLA data: repeating the six test points with a lattice four times
finer, 16 refined maxima and six refinement rounds changes no value by more than 0.0005
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
- Completeness tests: the first version also demanded that the code be no more than 0.002
  deg *above* the 1 m reference for obstacles beyond 1 km. The code turned out to be
  above it (0.0022 deg on LOLA data, 0.011 deg on the spiked raster) because the
  reference misses creases between its steps. That comparison was replaced by the
  independent recomputation of the reported point. The 0.002 deg tolerance on misses was
  not changed.

## 6. Runtime

Measured on the team laptop (Windows 11, Python 3.14.7, NumPy 2.5.4), single process,
default settings (0.25 deg, 300 km, six observer heights), while other work was running
on the machine:

| Terrain source | Time per site |
|---|---|
| LOLA 20 m and 60 m south-polar products with six overview levels, six test points | 1.9 to 2.5 s (3.9 s on the first read of a region not yet in the file cache) |
| Analytic function | 1.1 to 3.6 s |

Target: under 5 s. The LOLA runtime is asserted in the test suite when the data is present.

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
2. **Elevation model errors are not included.** Height and position errors of the DEM
   translate directly into horizon errors (height error divided by distance). Single
   high pixels are taken at face value, whether they are terrain or noise. No uncertainty
   band is computed yet.
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
6. **Observer.** A point at height `m` above the DEM surface. The lander's own structure
   and the terrain within the first pixel are not modelled. Height 0 means the terrain
   surface itself and is the most sensitive to the first points.
7. **Geometry only.** No refraction (there is none to speak of), no scattering, no
   reflected light; this is line of sight to bare terrain.
8. **Products without overviews.** The proof in section 3 needs block-maximum overview
   levels. Without them every cell is one lattice point and the whole ray is walked: the
   result is the same, the runtime is not.
