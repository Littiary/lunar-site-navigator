# Notes on the whole-Moon checkpoints (moon_report.json)

* **SLDEM2015_256 label minimum/maximum (checkpoint 3): failed as written for 5 of 6 tiles.** The criterion
  (`thresholds_moon.json`) asks the measured extremes to lie inside [MINIMUM, MAXIMUM] of each label. The SLDEM2015
  labels give these in km rounded to 0.001 km; every measured extreme lies within 0.45 m of its label value (field
  `max_abs_difference_to_label_m`). The criterion is not changed; the failure is due to the labels' rounding.
* **Outer edge of SLDEM2015_256 (seams):** the +-60 deg edge test is almost entirely inside the polar 60 m squares
  (they reach 59.996 deg on their edges and 48.5 deg at their corners), so both sides read the polar product and the
  jumps (median 0.05-0.07 m) say little. The real switch from polar to SLDEM is the edge of each 60 m square
  (`edge_of_LDEM_60S_60M`, `edge_of_LDEM_60N_60M`: median 4.3 / 5.0 m, p95 23.6 / 40.4 m, within 10 / 60 m).
* **LDEM_128 checkpoint 1: failed with the cause identified** (`ldem128_second_source_note.md`).
* **North-polar products** were checked against 2010 laser returns with the format's documented validity rule
  (deviation recorded in the report).
