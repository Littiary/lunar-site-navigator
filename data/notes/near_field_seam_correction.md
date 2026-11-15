# Correction: the 5 m -> 20 m seam check sampled the wrong points; Site23 fails it

Written 2026-11-15 by the data stream after an independent data audit. The criterion
(`data/checkpoints/thresholds_near_field.json`, `seam`: median abs jump <= 3.0 m, p95 <= 15 m) is unchanged.

## What was wrong

`lsn_data.moon_check._square_edge_points` drew one random number per point and used it both as the x of the points on
the top and bottom edges and as the y of the points on the left and right edges. For the polar squares, which are
centred on the pole, x and y share the same range, so this was correct there. The 5 m site DEMs are not centred on the
pole: Site11 spans y 7-23 km and Site23 y 111-132 km, while the draw covered their x range.

So on the left and right edges the points fell outside the raster. In both 0.5 m offsets they were read from the 20 m
product, and `inside_sources` listed `LDEM_80S_20M`. Only 82 % (Site04), 49 % (Site11) and 49 % (Site23) of the
"inside" points lay in the 5 m raster.

Commit bf942fb reported "all criteria passed" from these samples. That statement is withdrawn for the seam.

## Fix and new result

The position along the left and right edges is now drawn from the y range.
`data/tests/test_edge_points.py` checks that every point lies on the edge and that 0.5 m inside is inside, for the
three site extents and a polar square. With the fix, every inside point is read from the 5 m raster.

`data/checkpoints/near_field_report.json` was regenerated with nothing else changed:

| site | median abs jump | p95 abs jump | seam |
|---|---|---|---|
| Site04 (Shackleton rim) | 2.42 m | 11.52 m | passed |
| Site11 (de Gerlache rim) | 2.14 m | 6.55 m | passed |
| Site23 (Malapert massif) | 3.42 m | 11.47 m | **failed** (median above 3.0 m) |

`all_passed` is now false. The other near-field items (the 5 m vs 20 m comparison at each site) are unchanged and passed.

The whole-Moon continuity check at the edges of the polar squares used the same function, but there x and y share
the same range, so `moon_report.json` is not affected.

## Effect on the Malapert record (2 m observer, 0.25 deg azimuths, 300 km)

Measured with the repository's horizon search (`core/`, read-only use), comparing near field on (5 m inside Site23,
20 m beyond) with the 20 m product only.

* The site (85.988 S, 2.058 E) is 5.63 km from the nearest Site23 edge (east). Along the 1440 azimuths the ray leaves
  the 5 m extent at 5.6-18.7 km, with a median of 10.9 km.
* At 1217 of 1440 azimuths the horizon point lies inside the 5 m extent. At no azimuth does it lie within 500 m of
  the extent's edge.
* Bound from the seam: a jump J at the edge changes the elevation of a ray to that point by at most atan(J/d). At the
  nearest edge this is 0.035 deg for the median jump (3.42 m) and 0.117 deg for the p95 jump (11.47 m). Over all
  azimuths the medians are 0.018 and 0.060 deg. Because no horizon point lies near the edge, the actual effect on the
  horizon is below these bounds.
* For comparison, the whole effect of the 5 m layer on the horizon (near field minus 20 m only) has a median of
  0.148 deg, 95 % of azimuths within 0.50 deg, and a largest value of 0.79 deg (at 153.25 deg).
* Runtime: 8.7 s with the near field, 2.6 s with 20 m only (one search, cold start).

## Decision (team lead, 2026-11-15): option B, Malapert on the 20 m product

A layer that fails its checkpoint is not used. This is the same rule as for SLDEM2015_512.

* **What A would have risked:** keeping the 5 m layer at Malapert. The seam would change its horizon by at most
  0.12 deg (the p95 bound above).
* **What B gives up:** the whole effect of the 5 m layer at Malapert (median 0.148 deg, p95 0.50 deg, largest
  0.79 deg) and the 1 m error band inside the 5 m extent. Malapert returns to the 20 m band of 5 m / 7 m (2-sigma, by
  slope).

**How it is enforced.** `data/manifest/approved_near_field.json` lists the near-field layers that may be used: Site04
and Site11. The reader (`lsn_data.near_field_usable`) opens a 5 m layer only if it is listed there and
`near_field_report.json` records both its comparison and its seam as passed. Site23 is not special-cased. It fails
the rule and so is not opened.

* `open_terrain(near_field=True)` and `open_terrain(products="moon", near_field=True)` read the Malapert record
  from `LDEM_80S_20M`; the moon terrain reports Site23 as "present but not approved".
* Only the near-field checkpoints themselves open every layer (`site_dems(include_unapproved=True)`).
* Test: `data/tests/test_near_field_gate.py`.

**Effect on the published site list.** `data/sites/curated_sites.json` was regenerated. Only the Malapert record
changed:

* `terrain.near_field` is now null.
* The ground height is now from `LDEM_80S_20M`: 5173.50 m instead of 5172.89 m (ground radius 1742573.50 m).
