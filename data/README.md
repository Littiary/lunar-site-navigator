# data/ : LOLA terrain data (stream C)

Downloads NASA LOLA elevation products, records every file in a committed manifest,
and reads them with correct georeferencing. No raw data is in git.

## Data root (outside git)

Default `C:\lsn-data` (Windows) or `~/lsn-data`; override with the environment variable `LSN_DATA_ROOT`.

```
<root>/raw/lola/<PRODUCT_ID>/...        files exactly as fetched
<root>/raw/lola/_docs/...               archive documents (bundle label, errata, SIS)
<root>/derived/<PRODUCT_ID>/...         pyramids (mean_L<k>.npy, max_L<k>.npy, pyramid.json)
```

## Commands

```
pip install -e data[test]
python -m lsn_data where                 # data root and manifest path
python -m lsn_data fetch                 # download, hash, write data/manifest/manifest.json
python -m lsn_data verify                # checkpoint 1: every file equals its manifest record
python -m lsn_data cross-check           # re-hash each file from its other source
python -m lsn_data pyramid               # build overview levels (polar and cylindrical)
python -m pytest data/tests              # tests; those that need the real data skip if it is absent
```

## Products

| Product ID | Role | Grid |
|---|---|---|
| `LDEM_80S_20M` | primary terrain, 80S to the pole | 30400 x 30400, 20 m, polar stereographic |
| `LDEM_60S_60M` | far terrain, 60S to the pole | 31040 x 31040, 60 m, polar stereographic |
| `LDEM_16` | global, 16 px/deg; independent check only | 5760 x 2880, simple cylindrical |
| `LDEM_80N_20M`, `LDEM_60N_60M` | north-polar mirror of the two south products (whole-Moon terrain) | as the south products |
| `LDEM_128` | global fallback of the whole-Moon terrain, independent check | 46080 x 23040, 128 px/deg (237 m), simple cylindrical |
| `SLDEM2015_256_*` / `SLDEM2015_512_*` | 60S-60N, LOLA + Kaguya TC (only if downloaded) | 6 tiles of 118 m / 32 tiles of 59 m, float km |
| `LOLARDR_*` (13 files of LRO_SM_06, 14 of LRO_NO_08; 14 labels of LRO_ES_100, unused) | individual laser returns: independent check of mapping and products (LRO_NO_08 for the north-polar products, where LRO_SM_06 has no valid returns) | binary table, LOLARDR.FMT |

Version, reference radius, scaling and projection parameters are read from the PDS labels; the manifest
records the product version and SHA-256 of each file.

## Interface for the horizon code (stream A)

```python
from lsn_data import open_terrain
terrain = open_terrain()                         # real LOLA products under the data root
terrain = open_terrain(label_paths=[...])        # or any list of PDS3 labels, e.g. the synthetic DEM

terrain.reference_radius_m                       # 1_737_400.0, from the labels
h = terrain.height_m(lon_deg, lat_deg, max_pixel_m=None)   # metres above the reference sphere
r = terrain.radius_m(lon_deg, lat_deg, max_pixel_m=None)   # distance from the Moon's centre, m
terrain.provenance(manifest=None)                # per product: ids, version and, for EVERY file behind it, name, role,
                                                 # size_bytes, sha256, source_url, manifest_path, retrieved_utc, read (bool)
```

* `lon_deg` east positive, planetocentric `lat_deg`; scalars or arrays (they broadcast). Result is `float64`, **NaN where no product covers the point**.
* `max_pixel_m`: scalar or array. Reads the coarsest overview level whose pixel size is not larger than this, so far terrain is cheap
  (e.g. `max_pixel_m = distance / 500`). `None` means the finest data. Products are combined automatically: the 20 m product inside its square (+-304 km of the pole), the 60 m product beyond.
* Bilinear interpolation between pixel centres (`method="nearest"` is also available).
* `statistic="max"` reads block-maximum overviews: a conservative horizon (never misses a ridge). Default `"mean"`.
* Blocks for tight loops: `PolarDEM.window_xy(x0, y0, x1, y1, level)` and `window_around(lon, lat, half_width_m, level)` return a `Window`
  (float32 heights in metres plus a `PolarGrid` with the georeferencing).

Projection (`lsn_data.georef`): spherical polar stereographic, true at the pole, `rho = 2 R tan(colatitude / 2)`; south pole:
`x = rho sin(lon)`, `y = rho cos(lon)`; area pixels, row 0 at the top; the pole is a pixel corner.

### Synthetic DEM for tests

`data/fixtures/synth_s90_100m.lbl` + `.dat` (400 x 400 pixels of 100 m, 40 km wide, 320 kB). Same file layout and label keys as the real
products, analytic surface in `lsn_data/synthetic.py` (`height_m(x, y)` gives the exact value): a cone of 1500 m apex at 8 km towards 90 degrees east,
a ring ridge of 800 m at 12 km from the pole and a 400 m bowl at the pole. It is **not LOLA data**. Regenerate with `python -m lsn_data.synthetic`; a test
checks the committed bytes equal the generator output.

```python
from lsn_data import open_terrain
t = open_terrain(label_paths=["data/fixtures/synth_s90_100m.lbl"])
```

### Pyramid levels and blocks (many samples at once)

```python
terrain.levels()                                 # [{product_id, level, statistic, pixel_m, n_rows, n_cols, x_ul_m, y_ul_m}, ...]
dem = terrain.product("LDEM_80S_20M")            # a PolarDEM
v = dem.level_view(level=3, statistic="max")     # LevelView: dn (read-only memmap int16, zero copy), grid, scale, ...; v.heights_m() -> float32 m
w = dem.level_window(level=2, statistic="mean", rows=(100, 900), cols=(0, 500))   # Window: float32 metres + georeferenced grid
w = terrain.window_around(lon, lat, half_width_m, max_pixel_m=None, statistic="mean")  # level chosen automatically
w.heights_m, w.grid.rowcol_to_xy(r, c), w.grid.lonlat_to_rowcol(lon, lat), w.radius_m()
dem.height_xy(x_m, y_m, level=3, statistic="max")  # vectorised sampling of one level
```

`rows`/`cols` are `(start, stop)` or slices in the level's own pixel indices; `None` is the whole level (level 0 of the 20 m product is 3.7 GB as float32).
Level `k` has `2**k` times larger pixels and the same upper-left corner, so `grid.x_ul_m`/`y_ul_m` are shared by all levels.

### Whole-Moon terrain (opt-in)

```python
t = open_terrain(products="moon")                # MoonTerrain over everything downloaded (see t.coverage())
h = t.height_m(lon, lat, max_pixel_m=None)       # any latitude and longitude
ids, levels = t.source(lon, lat, max_pixel_m=None)   # which product and level each point is read from
```

Rule: a south or north polar product that covers the point decides exactly as `Terrain` does (so every point of the
default terrain gets the same value); elsewhere the finest cylindrical mosaic that is complete on disk and listed in
`data/manifest/approved_mosaics.json` (now `SLDEM2015_256`, then `LDEM_128`). `SLDEM2015_512` is complete on disk
but not approved (data/checkpoints/sldem512_candidate_note.md), so it is reported as "present but not approved" and
not used. Cylindrical tiles are read on the global grid of their resolution, so bilinear
interpolation is continuous across tile edges and the 0/360 meridian. `open_terrain()` without arguments still
returns the south-polar `Terrain`, because the core adapter (`lsncore.dem.LolaTerrain`) reads polar-grid internals.
`Terrain.source()` (same signature) reports the product and level for the polar terrain.

Downloads: `python -m lsn_data fetch LDEM_128 LDEM_80N_20M LDEM_60N_60M --segments 4` (parallel byte ranges per file;
the mirror limits each connection). Pyramids: `python -m lsn_data pyramid <product ids>` works for cylindrical files too.

## Independent checks of the mapping (item 1 and 2 of the data stream's review)

* `data/tests/test_mapping_by_hand.py`: 18 line/sample values derived by hand from `DSMAP_POLAR.CAT` and the labels.
* `python -m lsn_data.independent` -> `data/checkpoints/independent_report.json` (criterion `thresholds_independent.json`):
  our polar products against LOLA RDR laser returns and against the cylindrical LDEM_128 / LDEM_16 grids
  (displacement fit: translation, rotation, radial scale; east-west mirror test).
* Published spot heights (Smith et al. 2010): criterion `thresholds_spot_heights.json`, results in the reports.
* The catalogue's radial scale: `data/checkpoints/radial_scale_explanation.md` (`python -m lsn_data.catalogue_diag`).
* Whole-Moon checkpoints and seams: `python -m lsn_data.moon_check` -> `moon_report.json` (criterion `thresholds_moon.json`).

## Checkpoints (status is in `data/checkpoints/report.json`, produced by `python -m lsn_data checkpoints`)

Thresholds are in `data/checkpoints/thresholds.json`, committed before the first measurement and not edited since.
Post-hoc diagnostics (not pass/fail rules) are in `data/checkpoints/diagnostics.json`.

## Site records

`data/sites/sites.json`: three south-polar sites (Shackleton rim crest, de Gerlache rim crest, Mons Malapert summit), each anchored on an
IAU Gazetteer feature with URL and retrieval time (`data/sites/gazetteer_records.json`), located on the 20 m DEM by a stated rule, with reference
frame and terrain product checksum. They are the project's own candidate sites, not NASA landing sites.

### Supplementary georeferencing check (checkpoint 2)

Criterion `data/checkpoints/thresholds_supplementary.json` (committed before measuring), result `data/checkpoints/supplementary_report.json`.
Best-fit translation of each IAU outline onto its rim crest: no common translation (mean 936 m, standard error 658 m); the rotation rule is flagged
(-0.87 deg +- 0.35 deg), driven by Cabeus alone. Checkpoint 2 itself is unchanged: 2 of 6.

### Crater-catalogue georeferencing check

Criterion `data/checkpoints/thresholds_catalogue.json` (committed before measuring), result `data/checkpoints/catalogue_report.json`. 192 rim fits against the Robbins
catalogue: translation (-21, +24) m, rotation -0.013 deg, radial scale -3.6e-4, all below the levels that matter for horizons (100 m).
The radial scale is not in our reading (laser returns: -2.7e-5 +- 0.6e-5); about a quarter of it is the check's rim
detector moving uphill, the rest is in the catalogue positions, cause not determined (`radial_scale_explanation.md`). The catalogue
was measured on LROC, LOLA and Kaguya TC products in a LOLA control net, so this tests our reading of the files against LOLA-controlled products, not the absolute frame.
