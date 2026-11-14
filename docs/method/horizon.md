# Terrain horizon: method, checks and limits

Code: `core/lsncore/horizon.py`. Tests: `core/tests/test_horizon.py`, `core/tests/test_pipeline.py`.
Status on 14 November 2026: checked against analytic cases and a gridded synthetic
raster. **Not yet run on LOLA data and not yet compared with an independent horizon
product**; every statement about real terrain below is marked as not measured.

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
of the LOLA products.

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
instead of two radii. Sample points are generated on the sphere from the site's
East/North/Up unit vectors, `p = cos g * up + sin g * (cos A * north + sin A * east)`,
which stays well conditioned at the poles and across the 180 degree meridian. At a pole
the azimuth zero is the meridian of the longitude that was given for the site.

## 3. Sampling

| Setting | Value | Reason |
|---|---|---|
| Azimuth step | 0.25 deg (1440 rays), configurable | Half the Sun's angular radius or less |
| First sample | one near-field pixel from the site | Closer samples would only measure interpolation noise at the site |
| Range step near the site | half a near-field pixel | Do not step over a crest of the bilinear surface |
| Range step far from the site | grows by the factor 1 + 0.25 deg in radians per step | Constant angular resolution; 1348 samples reach 300 km for 20 m pixels |
| Far terrain | read from the coarsest overview level whose pixel is not larger than the range step | The step never skips more than two pixels of the level being read |
| Interpolation | bilinear between pixel centres (in the data reader) | Continuous surface, never exceeds the pixel values |
| Refinement | the 3 best local maxima of each ray, 4 rounds of 9 samples between their neighbours | Removes the dependence on where the coarse samples fall (bracket shrinks 256 times) |
| Observer heights | all heights use the same terrain samples in one pass | Cost of an extra height is small; results equal separate runs |
| Arithmetic | 64-bit floats; arrays are stored as 32-bit floats in the package | 32-bit rounding of an angle near 10 deg is about 1e-6 deg |

Refinement only ever raises a ray's maximum to a higher value actually found on the
surface, so it cannot produce a horizon that is not there.

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

The test `test_far_field_bound_covers_terrain_beyond_the_search_radius` puts a mountain
outside a shortened search radius and checks, for every azimuth, that the bound is at
least the rise of the horizon when the radius is extended.

## 5. Acceptance tests and measured accuracy

Thresholds were written in the test file before the implementation and were not changed.
Expected values come from closed-form geometry written independently in the test file
(the unrearranged triangle formula, haversine distances, classic great-circle formulas).
Sites: latitude -85, the south pole itself, 110 m from the pole on the 180 degree
meridian, latitude -80 at longitude -179.5, latitude +12 and latitude +88.

| Case | Threshold (fixed first) | Measured |
|---|---|---|
| Smooth sphere, observer 1, 2, 10, 100 m up: depression `-acos(R/(R+m))`, 6 sites | 0.0005 deg | 9.2e-12 deg |
| Crater rim at a known distance and height (parabolic bowl 1500 m deep, rim at 20 km; observer 0, 2, 20 m), 6 sites | 0.001 deg | 1.2e-5 deg |
| ... reported distance to the rim | 10 m | 0.05 m |
| ... reported obstacle height | 1 m | below 1e-4 m |
| ... obstacle latitude and longitude against azimuth and distance | 1 m | 5e-10 m |
| Smooth hill 60 km away, 5 azimuths, against an independent dense 1-D solution | 0.002 deg | 3.2e-8 deg |
| Several heights in one pass against one run per height | 1e-9 deg | 0 |
| Data stream's gridded 100 m synthetic raster, through its reader (bowl, ring ridge at 12 km), smooth part | 0.02 deg | 0.0052 deg (mean -0.0026 deg) |
| Runtime, one site, 1440 azimuths, 300 km, 6 heights | 5 s | 0.9 to 1.3 s |

Notes on the table:

- Without the refinement step the crater-rim error is 0.0047 deg: the refinement is what
  brings it under the threshold.
- The 0.005 deg on the gridded raster is the grid, not the algorithm: bilinear
  interpolation between 100 m pixels cuts the top of a ridge whose crest is 1 km wide, so
  the gridded horizon is lower than the analytic one (negative mean). At the tip of that
  raster's cone, a point feature, the grid is 0.18 deg lower than the analytic surface.
  A raster cannot hold what is narrower than its pixels; see section 7.
- Direction conventions are tested separately: a hill placed one degree east of a site on
  the equator appears at azimuth 90; from the south pole (longitude 0 given), a hill at
  longitude 90 east appears at azimuth 90; through the data reader, the cone at longitude
  90 east appears at azimuth 90 and not at 270.
- One test scenario was changed after its first run: the mountain of the far-field test
  was too low to raise the horizon by more than the 0.1 deg the test demands as proof that
  the case is not trivial. The mountain was made higher and closer. No tolerance and no
  inequality under test was changed.

## 6. Runtime

Measured on the team laptop (Windows 11, Python 3.14.7, NumPy 2.5.4), single process,
default settings (0.25 deg, 300 km, six observer heights):

| Terrain source | Time per site |
|---|---|
| Analytic function (no file access) | 0.9 to 1.3 s |
| Data stream's reader on synthetic rasters of realistic size (20 m, 8192 x 8192 pixels; 60 m, 10240 x 10240 pixels; six overview levels each) | 1.3 to 1.8 s |
| LOLA products | not measured yet (download in progress) |

An azimuth step of 0.05 deg takes 7 to 9 s on the synthetic rasters.

## 7. Sensitivities measured on synthetic terrain

These numbers come from an invented rough surface (relief of about 2 km with a 300 m
ripple of 1 to 2 km wavelength), read through the data stream's reader. They show the
size of the effects, not their size on the Moon. They will be repeated on LOLA data.

| Question | Result |
|---|---|
| Halving the range step everywhere | horizon changes by at most 0.007 deg (95 % of azimuths below 0.002 deg) |
| Linear interpolation of the 0.25 deg profile against a 0.05 deg profile | 95 % of azimuths within 0.0012 deg; largest difference 0.026 deg at a narrow feature |
| Far terrain from block-maximum instead of block-average overviews | horizon higher by at most 0.059 deg (95 % of azimuths below 0.014 deg) |

The last row is the price of reading far terrain from averaged overview levels. The
block-maximum run is an upper bound of the horizon of the full-resolution surface; the
package format reserves `elevation_upper_deg` for it.

## 8. Limits: where the result must not be trusted

1. **Sub-pixel relief and the first kilometre.** The terrain is the bilinear surface
   through the DEM pixels. Rocks, small craters and crests narrower than a pixel are not
   in it. An obstacle 100 m away needs only 1.7 m of unmodelled height to change the
   horizon by 1 deg. `distance_m` shows, per azimuth, how near the limiting terrain is;
   azimuths limited by terrain closer than about 1 km depend on DEM detail and on the
   exact observer height.
2. **Elevation model errors are not included.** Height and position errors of the DEM
   translate directly into horizon errors (height error divided by distance). No
   uncertainty band is computed yet.
3. **Narrow obstacles between rays.** With a 0.25 deg step an obstacle narrower than the
   step can be missed or cut; near and far alike.
4. **Averaged far terrain.** Beyond the distance where the range step exceeds the finest
   pixel, terrain is read from block-averaged overviews: narrow distant peaks are lowered.
5. **Beyond the data or the search radius.** Nothing is seen there. The far-field bound
   states what could be missed, under the assumption that no unseen terrain exceeds the
   stated ceiling. With the LOLA polar products, sites far from the pole have rays that
   leave the data; they are flagged `partial`.
6. **Sphere.** Distances, the local vertical and the horizontal plane refer to a sphere of
   the DEM reference radius. The local vertical is the radial direction, not the plumb
   line; the Moon's flattening and gravity anomalies are ignored.
7. **Observer.** A point at height `m` above the DEM surface. The lander's own structure
   and the terrain within the first pixel are not modelled. Height 0 means the terrain
   surface itself and is the most sensitive to the first samples.
8. **No physics beyond geometry.** No refraction (there is none to speak of), no
   scattering, no multiple reflection; this is line of sight to bare terrain.
