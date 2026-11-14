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
python -m lsn_data pyramid               # build overview levels
python -m pytest data/tests              # tests; those that need the real data skip if it is absent
```

## Products

| Product ID | Role | Grid |
|---|---|---|
| `LDEM_80S_20M` | primary terrain, 80S to the pole | 30400 x 30400, 20 m, polar stereographic |
| `LDEM_60S_60M` | far terrain, 60S to the pole | 31040 x 31040, 60 m, polar stereographic |
| `LDEM_16` | global, 16 px/deg; independent check only | 5760 x 2880, simple cylindrical |

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
terrain.provenance()                             # product ids, versions, file names used
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
