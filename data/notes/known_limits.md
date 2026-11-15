# Known limits of the terrain data

Each entry gives the measurement behind it. Entries are added as limits are found.

* **Radial scale of LDEM_80S_20M.** Against LOLA RDR laser returns the 20 m product has a radial scale of
  -2.7e-5 +- 0.57e-5 (SHOT_FLAG = 0; -1.6e-5 +- 0.20e-5 with the validity rule of LOLARDR.FMT). This is inside the
  criterion (abs <= 5e-5), but it is significantly different from zero. At the 304 km edge of the 20 m square it
  corresponds to a horizontal shift of about 8 m toward the pole. LDEM_60S_60M shows none (-0.03e-5 +- 0.04e-5).
  Source: `data/checkpoints/independent_report.json`, part B.
* **Polar products beyond the 60 deg latitude of their labels.** The square of LDEM_60S_60M (and LDEM_60N_60M)
  reaches to about 48.5 deg latitude at its corners, and the terrain uses it wherever its square covers a point.
  The georeferencing checks against independent laser returns covered 60.5-79.5 deg and 80.5-89.8 deg, so the
  corner pixels beyond 60 deg have not been checked against independent returns. Only the seam with LDEM_128 in
  55-60 deg was checked (`moon_report.json`, seams).
* **One-pixel step in SLDEM2015 at 90.00 E, 48.13-48.18 S:** see `known_limit_sldem_step_90e_48s.md`.
* **5 m -> 20 m seam at Site23 (Malapert massif) fails its criterion** (median 3.42 m against 3.0 m): see
  `near_field_seam_correction.md`.
