# SLDEM2015 512 as a candidate mosaic: result and decision

Written 2026-11-14 by the data stream, after measuring. The criteria are those of `thresholds_moon.json`, written and
committed before any measurement. They have not been edited.

Report: `moon_report_SLDEM2015_512.json`, from `python -m lsn_data.moon_check --candidate SLDEM2015_512`, run at
below-normal priority. It covers the same items as `moon_report.json`, with SLDEM2015_512 opened in addition to
SLDEM2015_256 and LDEM_128.

## Decision

**SLDEM2015_512 is not added to `data/manifest/approved_mosaics.json`.** One item that SLDEM2015_256 passed fails
as written: `seams.moon_terrain_continuity.tile_seams`. That item says "points 0.5 m either side of every tile edge;
the jump must not exceed 1 m". The largest jump measured is 5.36 m.

The approval rule was "everything that the 256 ppd product passed also passes". This item does not, so the mosaic stays
unapproved. Nothing uses it: `open_terrain` and `open_moon` without `candidates` do not open it.

## Results, 512 vs 256

| item | SLDEM2015_512 | SLDEM2015_256 |
|---|---|---|
| checkpoint 2: RDR laser returns, abs(lat) <= 59.5 (443 241 returns) | passed: mean d +0.03 m, median abs d 1.35 m, translation E +4.0 +-0.7 m, N -1.5 +-1.2 m, mirror ratio 526 | passed: mean +0.01 m, median abs 1.75 m, E +5.2 m, N -1.6 m, mirror ratio 504 |
| checkpoint 3: reference radius, all labels | passed (32 labels) | passed |
| checkpoint 3: label min/max | 5 of 32 strictly inside; all within 0.50 m (labels round to 0.001 km), the same reported-only rounding item as 256 (`moon_notes.md`) | same rounding item |
| checkpoint 3: published spot heights | passed (highest point: extreme -2.6 m) | passed (-3.4 m) |
| seam vs LDEM_128, abs(lat) <= 55, 20 000 cells | passed: mean +0.09 m, median abs 2.93 m, p95 24.1 m | passed: +0.10, 2.95, 23.6 m |
| continuity at the 60 m polar edges | passed: median abs jump 4.3 / 5.0 m, p95 24.2 / 40.6 m | passed (4.3 / 5.0, 23.6 / 40.4 m) |
| continuity at the +-60 deg outer edge | passed | passed |
| **tile seams inside the mosaic: max abs jump over 1 m <= 1 m** | **failed: 5.36 m; 11 of 64 000 points above 1 m** | passed: 0.90 m |
| checkpoint 1: second source (PDS) | still running when the report was written: 9 of 32 images matched, 0 differed (the manifest holds the final state) | passed |

## What the tile-seam failure is

The failure is a property of the terrain in the product, not an error in reading the tiles.

1. **The largest jump** is at 90 E, 48.14 S, on the edge between tiles `60S_30S_045_090` and `60S_30S_090_135`. Over
   at least 13 rows (about 0.8 km) the last pixel west of the edge and the first pixel east of it differ by 144-244 m.
   Neighbouring pixel pairs inside each tile differ by 5-30 m.
2. **SLDEM2015_256 shows the same step at the same place**: 335.0 m to 118.8 m across 90 E. Its tiles are 120 deg
   wide, so for 256 this is inside a tile and not on any seam. The 256 test therefore never sampled it.
3. **SLDEM2015_256 is exactly the 2 x 2 block mean of SLDEM2015_512 as we read it**, including the blocks that
   straddle 512 tile edges. The RMS difference is below 0.005 m for 4000 random rows or columns on each side of the
   seams at 45, 90, 225 and 315 E and at 30 S, 0 and 30 N. A column or row offset in our reading of any 512 tile would
   show up here as a large difference.
4. **The bilinear interpolation is continuous across tiles.** The 1 m jump at a seam equals the local slope times 1 m,
   from the two pixel centres on either side. At 59 m pixels a 240 m step over one pixel is a slope of about 80 deg
   in the product. The 1 m threshold assumed that continuity alone keeps the jump below 1 m. That holds for smooth
   terrain but not for one-pixel steps of this size.
5. **The seam pixels are slightly rougher than interior pixels** in the 512 tiles. The median absolute difference of
   the pixel pair across a seam is 1.0-1.25 times that of interior pairs (e.g. 3.6 vs 3.0 m at 45 E, 5.0 vs 4.1 m at
   225 E, 3.7 vs 3.0 m at 30 N; no excess at 0 and 135 E). This is in the product: the same pixels average exactly
   into 256.

## What would change the decision

The criterion stays as written. Approving SLDEM2015_512 would need a decision by the team lead, for example that this
item is replaced by the test above (256 equal to the 2 x 2 mean of 512 across seams), written down before it is run on
another product. The data stream does not make that choice itself.
