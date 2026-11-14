# Package contract, version 0.1

This document defines the files the science core writes and every viewer reads. It is the
only interface between the core and the web pages, the Three.js view and the Unreal scene.

- Machine-checkable schema: [`schemas/lsn-contract.schema.json`](schemas/lsn-contract.schema.json) (JSON Schema 2020-12).
- Sample with invented values: [`sample/`](sample/README.md).
- Reference writer, reader and validator: `core/lsncore/contract/`.
- Owner: the core stream. Other streams request changes; they do not edit these files
  (CONTRIBUTING.md, rule 2).

The key words "must" and "may" are used in their plain sense: "must" is a requirement the
validator or a reader relies on.

## 1. What exists

| Thing | File | Purpose |
|---|---|---|
| Scenario | one JSON file, `kind: "scenario"` | The single input of the tool: sites, time window, observer heights, thresholds, data versions |
| Site package | directory, `kind: "site"` | Everything computed for one site: site geometry, 360° horizon, and (when computed) time series, events, windows, metrics |
| Direction-table package | directory, `kind: "direction_table"` | Sun and Earth positions over time, independent of any site |
| Index | `index.json`, `kind: "index"` | Lists the packages under a package root, so static pages need no directory listing |

A **package** is a directory that holds `manifest.json` and the binary arrays the manifest
refers to. Nothing else may be in the directory. The directory name is the package id.

```
<package root>/
  index.json
  direction_table/<package_id>/manifest.json, positions_km.f8
  site/<site_id>/<package_id>/manifest.json, horizon_*.f4|f8, series_*.f4
```

Readers find packages through `index.json` (`packages[].path` is relative to the package
root, with forward slashes). A feature that has not been computed is simply absent from
the package (for example `timeline`); a reader must then hide the corresponding view
instead of showing a placeholder number.

## 2. Conventions

| Topic | Rule |
|---|---|
| Text | JSON, UTF-8, ASCII keys in lower case, decimal point. No NaN or Infinity in JSON: an unknown number is `null` |
| Arrays | Raw binary, little-endian, C order (the last index varies fastest), no header. Unknown values are NaN |
| Time axis | TDB seconds past J2000 (the SPICE "ET" axis), 64-bit float. Field names end in `_et_s` |
| Display time | UTC as ISO 8601 with milliseconds and a `Z` suffix, `2026-11-14T09:00:00.000Z`, always written by the core. Readers never convert between TDB and UTC themselves |
| Body-fixed frame | Named in `site.frame` and in the direction table's `frame` (a SPICE frame name). Both must be equal for a site package and the table it was computed from |
| Sphere | The Moon is a sphere of radius `site.reference_radius_m`, the reference radius of the elevation model. Terrain height is measured from that sphere, along the radial direction |
| Latitude, longitude | Degrees, planetocentric, east-positive longitude, canonical range (-180, 180]. Scenarios may give 0 to 360; the core wraps and rounds to 1e-7 degree |
| Local frame | East, North, Up at the site. Up is the outward radial direction (the sphere normal), not the terrain normal. `site.enu` gives the three unit vectors in the body-fixed frame. At a pole, east and north follow from the longitude that was given |
| Azimuth | Degrees, clockwise from north seen from above: north 0, east 90, south 180, west 270. It is the initial bearing of the great circle leaving the site |
| Elevation | Degrees above the local horizontal plane (the plane perpendicular to Up). Negative values are normal: from a height, the horizon lies below the horizontal |
| Lengths | Vectors and body radii in kilometres (as in SPICE); heights and distances in metres. The unit is part of the field name and repeated in `unit` |
| Observer height | Metres above the terrain surface at the site, along Up |

## 3. Common parts

### 3.1 Array reference

Every array is described where it is used:

```json
{"file": "horizon_elevation_deg.f4", "dtype": "<f4", "shape": [6, 1440], "unit": "deg",
 "method": "horizon.elevation", "sha256": "…64 hex…", "nan_count": 0}
```

| dtype | Meaning | JavaScript | C++ |
|---|---|---|---|
| `<f4` | 32-bit float | `Float32Array` | `float` |
| `<f8` | 64-bit float | `Float64Array` | `double` |
| `<i4` | 32-bit signed integer | `Int32Array` | `int32_t` |
| `\|u1` | 8-bit unsigned integer | `Uint8Array` | `uint8_t` |

The file size must equal the product of `shape` times the item size. For a shape `[H, A]`
the value for height index `h` and azimuth index `a` is at flat index `h * A + a`.

### 3.2 Method card (decision 6)

Every number carries `"method": "<id>"`: array references, single quantities
(`{"value", "unit", "method"}`), events, windows and metrics. The manifest's `methods`
object holds one card per id:

| Field | Content |
|---|---|
| `title` | Short name |
| `definition` | What the number means, precisely enough to recompute it |
| `algorithm` | How it was computed |
| `frame` | Reference frame of the number |
| `time_scale` | `TDB`, `UTC` or `none` |
| `data` | Ids and versions of the datasets used |
| `parameters` | The parameters that influence the number (search radius, step sizes, tolerances) |
| `validation.status` | `synthetic`, `unverified`, `analytic-test-passed` or `externally-validated` |
| `validation.evidence` | Where the check can be found (test name, report, measured residual) |
| `limits` | Where the number must not be trusted |

A viewer that shows a number must be able to show its card. `unverified` must be visible
to the user as such. A card may only be listed if a number refers to it.

### 3.3 Package header

All packages start with the same fields:

| Field | Content |
|---|---|
| `contract` | `{"name": "lsn-package", "version": "0.1"}` |
| `kind` | `site` or `direction_table` |
| `package_id` | `site-` or `dirtab-` followed by 16 hex digits; see 3.4 |
| `content_sha256` | Digest of the package content; see 3.4 |
| `status` | `ok`; `partial` (something requested is missing, explained in `warnings`); `error` |
| `synthetic` | `true` if any value is invented. Then `synthetic_notice` is required and every method card has status `synthetic` |
| `warnings` | List of plain sentences |
| `request` | The canonical request: what was asked |
| `inputs` | What it was computed from: `science_version`, dataset ids and digests, the direction table used |
| `methods` | Method cards |
| `provenance` | When and with which software the package was written (`created_utc`, core version, git commit, whether the working copy had uncommitted changes, Python and library versions, timings). No host name, user name or absolute path |

**Readers must show a clear "synthetic data" marker whenever `synthetic` is `true`.**

### 3.4 Identity and reproducibility

- `package_id` is the SHA-256 (first 16 hex digits) of the canonical JSON of
  `{contract_major, kind, synthetic, request, inputs}`. The same request on the same data
  with the same `science_version` gets the same id on every machine and every day.
  `science_version` is increased whenever a code change can alter numbers.
- `content_sha256` is the SHA-256 of the canonical JSON of the manifest without
  `content_sha256` and `provenance`. Because every array reference contains the digest of
  its file, this one value covers every byte of the result. Two runs agree at byte level
  exactly when their `content_sha256` agree.
- Canonical JSON: keys sorted, no whitespace, ASCII, numbers as written by Python's
  `json` module. Readers do not need to recompute the digests; they compare the strings.

### 3.5 Time grid (decision 4)

One object describes every uniform time axis, in the direction table and in every site:

```json
{"scale": "TDB", "epoch": "J2000", "start_et_s": 847886400.0, "step_s": 3600.0, "count": 721,
 "start_utc": "2026-11-14T00:00:00.000Z", "end_utc": "2026-12-14T00:00:00.000Z",
 "leap_seconds_in_range": 0}
```

Sample `i` is at `start_et_s + i * step_s`. A reader may label sample `i` with
`start_utc + i * step_s` only if `leap_seconds_in_range` is 0; otherwise it must use the
UTC strings the package provides.

## 4. Scenario (decision 5)

The whole input of a run is one file. Running the same scenario on the same data gives the
same package ids.

| Field | Content |
|---|---|
| `scenario_id`, `title`, `description` | Identification |
| `synthetic` | `true` for scenarios that run the synthetic generator |
| `sites[]` | `site_id` (lower-case slug), `name`, `lat_deg`, `lon_deg`; optional `landing_utc`, `notes` |
| `observer_heights_m` | Heights computed in one pass (decision 2). Default set: 0, 1, 2, 5, 10, 20 m |
| `default_height_m` | The height viewers show first |
| `horizon` | `azimuth_step_deg`, `max_range_m` (search radius) |
| `time_window` | `start_utc`, `end_utc`, `step_s`, or `null` for horizon only |
| `bodies` | `SUN`, `EARTH` |
| `thresholds` | Per body, the condition that defines "visible": `{"quantity": "visible_fraction" \| "margin_deg", "op": ">" \| ">=", "value": number}` |
| `mission_profile` | Reserved |
| `data` | `dem_set_id`, `kernel_set_id`, optional `direction_table_id`: the data versions the run must use |

## 5. Site package

### 5.1 `request` and `inputs`

`request` echoes, in canonical form, the part of the scenario that concerns this site:
`site` (`site_id`, `name`, `lat_deg`, `lon_deg`), `observer_heights_m`, `horizon`
(`azimuth_step_deg`, `max_range_m`) and `timeline` (`start_utc`, `end_utc`, `step_s`,
`bodies`, `thresholds`, or `null`).

`inputs` holds `science_version`, `dem` (`dem_set_id` and one entry per elevation layer:
`layer_id`, `product_id`, `version`, `source_url`, `sha256`, `pixel_m`, `projection`) and
`direction_table` (`package_id`, `content_sha256`, or `null`).

### 5.2 `site`

| Field | Content |
|---|---|
| `site_id`, `name`, `body` | `body` is `MOON` |
| `lat_deg`, `lon_deg` | Canonical coordinates |
| `frame` | Body-fixed frame of the coordinates |
| `reference_radius_m` | Radius of the reference sphere of the elevation data |
| `surface_height_m` | Terrain height above that sphere at the site |
| `radius_m` | Distance of the ground point from the centre of the Moon: the sum of the two |
| `position_km` | Ground point in the body-fixed frame. The observer at height `h` is at `position_km + up * h / 1000` |
| `enu` | Unit vectors `east`, `north`, `up` in the body-fixed frame |
| `dem_pixel` | Optional: layer, row and column of the site in the elevation grid |
| `slope_deg` | Optional |

### 5.3 `horizon` (decisions 1 and 2)

| Field | Shape | Content |
|---|---|---|
| `azimuth` | | `{"start_deg": 0, "step_deg", "count"}` with `count * step_deg = 360`. Azimuth of index `a` is `a * step_deg`. The profile is periodic |
| `observer_heights_m` | `[H]` | Strictly increasing |
| `default_height_index` | | Index of the height to show first |
| `max_range_m` | | Search radius actually used (quantity) |
| `elevation_deg` | `[H, A]` `<f4` | Elevation angle of the terrain horizon: the largest elevation angle, over all terrain points along the great circle of that azimuth out to `max_range_m`, of the straight line from the observer to the terrain point |
| `distance_m` | `[H, A]` `<f4` | Distance from the site to the terrain point that sets the horizon, measured as arc length along the reference sphere |
| `obstacle_height_m` | `[H, A]` `<f4` | Optional. Terrain height of that point above the reference sphere |
| `obstacle_lat_deg`, `obstacle_lon_deg` | `[H, A]` `<f8` | Optional. Coordinates of that point |
| `error_bounds` | | Optional named quantities, for example the bound on what terrain beyond `max_range_m` could add |
| `flags` | | `coverage_complete`, `truncated_at_data_edge`, `nodata_fraction` |

Between azimuth samples, readers interpolate linearly (periodically). The obstacle point,
its distance and its height can change abruptly from one azimuth to the next; they must
not be interpolated, only read at the nearest sample.

Reserved optional arrays, same shape: `obstacle_dem_layer` (`|u1`), `elevation_sigma_deg`,
`elevation_lower_deg`, `elevation_upper_deg` (uncertainty band).

### 5.4 `timeline` (decisions 3 and 4)

Present only when a time window was computed.

| Field | Content |
|---|---|
| `direction_table_id` | The table the series was computed from; equal to `inputs.direction_table.package_id` |
| `time` | Time grid (3.5), `N` samples |
| `bodies` | Bodies present, in order |
| `series.<BODY>.azimuth_deg` | `[N]` azimuth of the centre of the disc |
| `series.<BODY>.elevation_deg` | `[N]` elevation of the centre of the disc (geometric, no terrain) |
| `series.<BODY>.angular_radius_deg` | `[N]` optional |
| `series.<BODY>.margin_deg` | `[H, N]` elevation of the disc centre minus the terrain horizon at the same azimuth, for each observer height |
| `series.<BODY>.visible_fraction` | `[H, N]` fraction of the disc area above the terrain horizon, 0 to 1 |
| `events[]` | Rise and set events, sorted by time |
| `windows[]` | Interval sets |
| `metrics[]` | Summary numbers |

**Event:** `type` (`rise`, `set`), `body`, `height_index`, `et_s`, `utc`, `azimuth_deg`
(of the body at the event), `horizon_elevation_deg` and `obstacle_distance_m` (of the
terrain that hides or reveals it), `threshold` (the condition crossed), `method`.
Optional: `obstacle_lat_deg`, `obstacle_lon_deg`, `sigma_s` (1-sigma time uncertainty),
`closing_rate_deg_per_h`, `grazing`.

**Window:** `id`, `subject` (`SUN`, `EARTH`, `COMBINED`), `height_index`, `definition`
(a sentence), optional `threshold`, `intervals_et_s` (`[[start, end], …]`, sorted,
disjoint), `intervals_utc` (the same instants as strings), `clipped_start` and
`clipped_end` (the first or last interval touches the end of the computed range, so its
true start or end is unknown), `method`.

**Metric:** `id`, `label`, `value`, `unit`, `height_index` (or `null`), `method`.

In Python, a window is a `lsncore.timeline.IntervalSet`. Union, intersection, complement,
`close_gaps` and `drop_short` are defined there once and used by every feature.

## 6. Direction-table package (decision 3)

One table serves every site. It stores positions relative to the **centre of the Moon**.

| Field | Content |
|---|---|
| `frame` | SPICE name of the body-fixed frame of the vectors |
| `center` | `MOON` |
| `aberration_correction` | SPICE correction string that was used, observer at the centre of the Moon |
| `bodies` | Order of the second array axis, for example `["SUN", "EARTH"]` |
| `time` | Time grid (3.5), `N` records |
| `positions_km` | `[N, B, 3]` `<f8`: time, body, x-y-z |
| `body_radii_km` | Radius of each body used for its disc (quantity with method card) |
| `interpolation` | `recommended` method between records, and the measured `max_error_km` and `max_error_arcsec` of that method (`null` if not measured) |
| `inputs.kernels[]` | `name`, `bytes`, `sha256`, `source_url`, `load_order` |

Reserved: `earth_rotation` (for ground-station windows).

Direction from a site, as the core computes it:

```
d  = positions_km[t, body] - site.position_km - up * h / 1000      (all body-fixed, km)
az = atan2(d · east, d · north)      el = asin((d · up) / |d|)
```

Viewers use this only to place the Sun and the Earth in a scene. Rise and set times,
margins and visible fractions are read from the site package, never recomputed.

## 7. Index

`packages[]`: `kind`, `package_id`, `path`, `synthetic`, `status`; for sites also
`site_id`, `name`, `lat_deg`, `lon_deg`, `has_timeline`.

## 8. Versioning

The version is `major.minor`. Adding an optional field raises the minor number; readers
must ignore fields they do not know and keep working. Changing the meaning, unit or layout
of an existing field raises the major number; a reader must refuse a package with another
major number and say why. While the major number is 0 the format may still change, but
only in announced batches, and every change updates this document, the schema and the
sample in the same commit.

## 9. Checking a package

```
pip install -e core[dev]
python -m lsncore validate <package directory | scenario.json | index.json> …
```

The validator applies the schema and then checks what a schema cannot: array files exist
with the stated size, digest and NaN count; every `method` has a card and every card is
used; array shapes agree with the axes; events are sorted and inside the time grid;
intervals are sorted and disjoint; the package id and the content digest can be
recomputed; synthetic data is labelled as such.
