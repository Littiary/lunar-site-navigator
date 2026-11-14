# Package contract, version 0.11

This document defines the files the science core writes and every viewer reads. It is the
only interface between the core and the web pages, the Three.js view and the Unreal scene.

- Machine-checkable schema: [`schemas/lsn-contract.schema.json`](schemas/lsn-contract.schema.json) (JSON Schema 2020-12).
- Sample with invented values: [`sample/`](sample/README.md).
- What changed since earlier versions: [section 10](#10-changes).
- Reference writer, reader and validator: `core/lsncore/contract/`.
- Owner: the core stream. Other streams request changes; they do not edit these files
  (CONTRIBUTING.md, rule 2).

The key words "must" and "may" are used in their plain sense: "must" is a requirement the
validator or a reader relies on.

## 1. What exists

| Thing | File | Purpose |
|---|---|---|
| Scenario | one JSON file, `kind: "scenario"` | The single input of the tool: sites, time window, observer heights, thresholds, data versions |
| Site package | directory, `kind: "site"` | Everything computed for one site: site geometry, 360° horizon, (when computed) time series, events, windows, metrics, and since 0.7 the ground around the site for drawing |
| Direction-table package | directory, `kind: "direction_table"` | Sun and Earth positions over time, independent of any site |
| Site-pairs package | directory, `kind: "site_pairs"` | Since 0.5. What every two sites of a scenario achieve together; written when a scenario has two or more sites with a timeline |
| Index | `index.json`, `kind: "index"` | Lists the packages under a package root, so static pages need no directory listing |

A **package** is a directory that holds `manifest.json` and the binary arrays the manifest
refers to. Nothing else may be in the directory. The directory name is the package id.

```
<package root>/
  index.json
  direction_table/<package_id>/manifest.json, positions_km.f8, earth_*.f4
  site/<site_id>/<package_id>/manifest.json, horizon_*.f4|f8, series_*.f4, terrain_*_up_m.f4
  site_pairs/<package_id>/manifest.json
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
| `contract` | `{"name": "lsn-package", "version": "0.11"}` |
| `kind` | `site`, `direction_table` or `site_pairs` |
| `package_id` | `site-`, `dirtab-` or `pairs-` followed by 16 hex digits; see 3.4 |
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
| `sites[]` | `site_id` (lower-case slug), `name`, `lat_deg`, `lon_deg`; optional `landing_utc`, `notes`; since 0.11 optional `programme` and `category`, descriptive labels for a site list (5.2) |
| `observer_heights_m` | Heights computed in one pass (decision 2). Default set: 0, 1, 2, 5, 10, 20 m |
| `default_height_m` | The height viewers show first |
| `horizon` | `azimuth_step_deg`, `max_range_m` (search radius) |
| `time_window` | `start_utc`, `end_utc`, `step_s`, or `null` for horizon only |
| `bodies` | `SUN`, `EARTH` |
| `thresholds` | Per body, the condition that defines "visible": `{"quantity": "visible_fraction" \| "margin_deg", "op": ">" \| ">=", "value": number}` |
| `requirements[]` | Since 0.3, optional. Stated mission requirements on the landing time; see 5.6. `sites[].landing_utc` is the planned landing the slip tolerance refers to. Three example requirements are in [`presets/requirements.json`](presets/README.md) |
| `uncertainty` | Since 0.4, optional. Stated assumptions: `horizon_error_deg`, `dem_height_error_m` (since 0.6) or `dem_height_error_model` (since 0.10) and/or `landing_ellipse` (`semi_major_m`, `semi_minor_m`, `azimuth_deg` of the major axis, `points`); see 5.7 |
| `terrain_patches[]` | Since 0.7, optional. Terrain patches for drawing, each `{id, half_width_m, spacing_m}`; if absent the three default patches are written, an empty list writes none; see 5.9 |
| `mission_profile` | Reserved |
| `data` | `dem_set_id`, `kernel_set_id`, optional `direction_table_id`: the data versions the run must use. `dem_set_id: "any"` accepts the installed elevation products; a run on another set than the one named still happens and writes a warning. The package always records what was used |

## 5. Site package

### 5.1 `request` and `inputs`

`request` echoes, in canonical form, the part of the scenario that concerns this site:
`site` (`site_id`, `name`, `lat_deg`, `lon_deg`), `observer_heights_m`, `horizon`
(`azimuth_step_deg`, `max_range_m`) and `timeline` (`start_utc`, `end_utc`, `step_s`,
`bodies`, `thresholds`, since 0.3 `requirements` and the site's `landing_utc`, since 0.4 `uncertainty`; or `null`),
and since 0.7 `terrain_patches` (the patches that were written, in the canonical order of the core; absent if there are none).

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
| `programme` | Since 0.11, optional. Text: the programme the site belongs to, for grouping a site list (for example `Apollo`, `Chang'e`, `CLPS`, `Project sites`) |
| `category` | Since 0.11, optional. Text: what kind of entry the site is (for example `past landing`, `candidate`, `project site`) |
| `slope_deg` | Optional |

`programme` and `category` are **descriptive only**. They are copied word for word from
the site record through the scenario into the package and the index entry; the contract
fixes no list of values, and a reader shows them as they are and must cope with a site
that has neither. No number depends on them. They are not part of `request` and do not
enter the package id: the same site with another label keeps its id and gets another
`content_sha256`. A `category` says nothing about the status of a site with any agency.

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
| `error_bounds` | | Optional named quantities. The horizon core writes `far_field_max_deg` (largest amount by which terrain beyond the reach of the rays could still raise the horizon; 0 = search radius proven sufficient), `far_field_open_azimuth_fraction`, `ceiling_height_m` (the terrain ceiling that bound assumes) and `shortest_reach_m`; see [`../method/horizon.md`](../method/horizon.md) |
| `flags` | | `coverage_complete`, `truncated_at_data_edge`, `nodata_fraction` |
| `obstacle_id` | `[H, A]` `<i4` | Since 0.2. For each observer height and azimuth, the index into `obstacles` of the obstacle that this azimuth belongs to; -1 where the horizon has no data |
| `obstacles` | list | Since 0.2. One record per obstacle, see below. `obstacles[k].id` is `k` |
| `terrain_source` | | Since 0.9. Which elevation product served the site and the horizon, and its resolution class; see below |

Between azimuth samples, readers interpolate linearly (periodically). The obstacle point,
its distance and its height can change abruptly from one azimuth to the next; they must
not be interpolated, only read at the nearest sample.

**Obstacle** (since 0.2). An obstacle is a run of neighbouring azimuths whose horizon is
set by the same piece of terrain: the limiting points of neighbouring azimuths lie at
nearly the same distance (within 10 %, or within 50 m). Where the limiting point jumps
nearer or farther, a new obstacle begins. The grouping is done separately for each
observer height; ids are unique across heights.

| Field | Content |
|---|---|
| `id`, `height_index` | Position in the list; observer height the grouping belongs to |
| `azimuth_start_index`, `azimuth_count` | The run: azimuth indices `(azimuth_start_index + k) mod A` for `k = 0 … azimuth_count - 1`. A run may pass through azimuth 0 |
| `azimuth_start_deg`, `azimuth_end_deg` | First and last azimuth of the run in degrees (`end` is smaller than `start` when the run passes through 0) |
| `peak_azimuth_deg`, `peak_elevation_deg` | Where the obstacle stands highest in the profile, and how high |
| `peak_distance_m`, `peak_lat_deg`, `peak_lon_deg`, `peak_height_m` | The limiting terrain point at the peak azimuth |
| `distance_min_m`, `distance_max_m` | Range of the distances of the limiting points along the run |
| `near_field` | `true` if the peak is closer than 1 km: such an obstacle depends on single pixels of the elevation model and on the observer height |
| `method` | Method card |

The outline of an obstacle in 3-D is the sequence of limiting points
(`obstacle_lat_deg`, `obstacle_lon_deg`, `obstacle_height_m` at `[height_index, j]`) for
the azimuth indices `j` of its run. Obstacles are geometric runs of the profile; they
carry no names.

**Terrain source** (since 0.9). `terrain_source` says which elevation product served the
site, so that a viewer can tell the user how much detail the horizon can hold:

| Field | Content |
|---|---|
| `at_site` | `product_id`, `pixel_m`, `projection` of the product the terrain height at the site was read from |
| `resolution_class` | `fine` (pixel at the site up to 30 m), `medium` (up to 120 m) or `coarse` (larger). With the LOLA products: the 20 m polar products are fine, the 60 m polar products medium, the global 237 m product coarse |
| `classes` | The definition of the classes in words |
| `products[]` | Every product that set the horizon in at least one azimuth at the default observer height: `product_id`, `pixel_m`, `projection`, `azimuth_share` (share of the azimuths whose limiting terrain point was read from it) |
| `method` | Method card id |

The product is chosen per place by the data reader: a polar product where its square
covers the place, the finest installed latitude-longitude product elsewhere. For a
latitude-longitude product `pixel_m` is the north-south pixel. A package whose class is
not `fine` carries a warning that names the pixel; relief narrower than about two pixels
is not in its horizon, and obstacles of that size cannot be shown.

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
| `series.<BODY>.lit_fraction` | `[H, N]` optional, since 0.2. Fraction of the disc that is above the terrain horizon and not hidden by another body; for the Sun: `visible_fraction` reduced by an eclipse by the Earth. Use it for power; use `visible_fraction` for line of sight to the terrain |
| `series.<BODY>.ellipse_visible_share` | `[N]` optional, since 0.4. Share of the sample points of the stated landing ellipse at which the body is visible; see 5.7 |
| `series.<BODY>.blocker_azimuth_index` | `[H, N]` `<i4`, since 0.2. For every sample, the azimuth index of the horizon sample that limits the view of the disc; see 5.5 |
| `events[]` | Rise and set events, sorted by time |
| `windows[]` | Interval sets |
| `metrics[]` | Summary numbers |
| `blockers[]` | Since 0.2. The obstacles that cost visible time compared with a smooth sphere; see 5.5 |
| `uncertainty` | Since 0.4, only if the scenario states assumptions. What was assumed and what follows; see 5.7 |
| `calendar` | Since 0.3. Visible time per lunar day; see 5.6 |
| `height_trade` | Since 0.5. Visible time and longest outage per observer height; see 5.8 |
| `opportunities[]` | Since 0.3, only if the scenario states requirements. Landing windows and slip tolerance; see 5.6 |

**Countdown metrics** (`<body>_visible_at_reference`, `<body>_time_to_set_s`,
`<body>_time_to_rise_s` and the two `_is_lower_bound` flags) are counted from one
instant per site: the site's `landing_utc` if the scenario states one inside the time
window, otherwise the start of the window. Since 0.10 each of them carries that instant
as `reference`: `utc`, `et_s` (TDB seconds past J2000, `time_scale` says so) and `is`
(`planned landing of the site`, `start of the time window` or `stated reference time`).
A reader takes the instant from this field, not from the label. Packages before 0.10
have it in the label only; there the rule above applies, with `request.timeline.landing_utc`.

**Event:** `type` (`rise`, `set`), `body`, `height_index`, `et_s`, `utc`, `azimuth_deg`
(of the body at the event), `horizon_elevation_deg` and `obstacle_distance_m` (of the
terrain that hides or reveals it), `threshold` (the condition crossed), `method`.
Optional: `obstacle_lat_deg`, `obstacle_lon_deg`, `sigma_s` (1-sigma time uncertainty),
`closing_rate_deg_per_h`, `grazing`, and since 0.4 `earliest_et_s`, `latest_et_s`,
`earliest_utc`, `latest_utc` (range of the event time for the stated horizon error; 5.7).

**Window:** `id`, `subject` (`SUN`, `EARTH`, `COMBINED`), `height_index`, `definition`
(a sentence), optional `threshold`, `intervals_et_s` (`[[start, end], …]`, sorted,
disjoint), `intervals_utc` (the same instants as strings), `clipped_start` and
`clipped_end` (the first or last interval touches the end of the computed range, so its
true start or end is unknown), `method`.

**Metric:** `id`, `label`, `value`, `unit`, `height_index` (or `null`), `method`.

Window ids written by the core, each per observer height: `<body>_visible` (the
scenario's condition), `<body>_any_part_visible`, `<body>_full_disc_visible`,
`sun_and_earth_visible`, and since 0.2 `<body>_visible_smooth_sphere`,
`<body>_lost_to_terrain`, `<body>_gained_from_terrain` (5.5). `<body>` is `sun` or `earth`.

In Python, a window is a `lsncore.timeline.IntervalSet`. Union, intersection, complement,
`close_gaps` and `drop_short` are defined there once and used by every feature.

### 5.5 Showing the obstacle (since 0.2)

These fields answer three questions for a site: what is in the way of the Sun or the
Earth at a given time, where it is, and what it costs.

**The comparison.** For every body and observer height the core also evaluates the
scenario's visibility condition over a *smooth sphere through the site*: no terrain, the
horizon a circle below the horizontal by the dip angle of the observer height. Then

```
<body>_lost_to_terrain     = visible over the smooth sphere AND NOT visible over the terrain
<body>_gained_from_terrain = visible over the terrain AND NOT visible over the smooth sphere
visible over the terrain   = smooth sphere - lost + gained          (as sets of time)
```

Time is gained where the terrain lies below the smooth horizon, as it does around a site
on a summit. The three windows are in `windows[]`; their durations are the metrics
`<body>_visible_s`, `<body>_visible_smooth_sphere_s`, `<body>_lost_to_terrain_s` and
`<body>_gained_from_terrain_s` (seconds).

**Per sample.** `series.<BODY>.blocker_azimuth_index[h, i]` is the azimuth index `j` of
the horizon sample that limits the view of the disc at sample `i`. Which sample that is
depends on the scenario's condition for the body: for "any part visible" it is, among
the horizon samples under the disc, the one where the upper edge of the disc stands
highest above the horizon (for a hidden disc: where its first light will appear); for
the centre condition it is the sample nearest to the azimuth of the centre; for "whole
disc visible" the one where the horizon reaches highest above the lower edge. The index
is defined at every sample, also while the body is visible.

**Blocker** (one record per body, observer height and obstacle that costs time; sorted by
cost, largest first):

| Field | Content |
|---|---|
| `body`, `height_index` | What is hidden, for which observer height |
| `obstacle_id` | Index into `horizon.obstacles`; -1 if the limiting sample has no data |
| `lost_s` | Part of `<body>_lost_to_terrain` during which this obstacle is the limiting one, in seconds |
| `share_of_lost` | `lost_s` divided by the total lost time of that body and height |
| `intervals_et_s`, `intervals_utc` | When: sorted, disjoint intervals |
| `azimuth_start_deg`, `azimuth_end_deg`, `peak_azimuth_deg`, `peak_elevation_deg`, `peak_distance_m`, `peak_lat_deg`, `peak_lon_deg`, `peak_height_m`, `near_field` | Copied from the obstacle record, so that a label needs no second lookup |
| `method` | Method card |

The totals come from the visibility windows and have the accuracy of the event times.
The split between obstacles is resolved to the step of the series: each sample stands
for the half step before and after it.

**Recipe for a viewer** (height index `h`, body `B`, time-slider sample `i`):

1. `f = series.B.visible_fraction[h, i]`: 1 whole disc visible, 0 hidden, between: partly hidden.
2. `j = series.B.blocker_azimuth_index[h, i]`. The limiting terrain point is at azimuth
   `j * step_deg`, distance `horizon.distance_m[h, j]`, position
   `horizon.obstacle_lat_deg[h, j]`, `obstacle_lon_deg[h, j]`, `obstacle_height_m[h, j]`.
3. `k = horizon.obstacle_id[h, j]`; `horizon.obstacles[k]` gives the run of azimuths to
   highlight and the peak for a label.
4. The record in `timeline.blockers` with the same `body`, `height_index` and
   `obstacle_id` gives the hours this obstacle costs in the computed window
   (`lost_s / 3600`); there is none if it costs nothing.
5. Show the method card and, if `near_field` is true, say that the obstacle is within
   1 km and depends on single pixels of the elevation model.

### 5.6 Opportunity calendar and slip tolerance (since 0.3)

**Calendar.** `timeline.calendar` cuts the computed range into lunar days and gives the
visible time in each. A lunar day begins when the Sun crosses the 180 degree meridian
of the body-fixed frame (the middle of the far side, close to new Moon). The periods do
not depend on the site, so the rows of several sites line up.

| Field | Content |
|---|---|
| `period`, `definition`, `method` | `lunar_day`; the sentence above; method card |
| `periods[]` | `index`, `start_et_s`, `end_et_s`, `start_utc`, `end_utc`, `complete`. The periods follow each other without gaps and cover the range of the series. The first and the last are cut by the ends of the range and have `complete: false`: their totals are not totals of a full lunar day |
| `quantities[]` | `id`, `label`, `unit` (seconds), `window` (the window id it is taken from), `values[h][p]` for observer height `h` and period `p`, `method` |

Quantity ids: `sun_visible_s`, `earth_visible_s`, `sun_and_earth_visible_s` (time for
which the window holds inside the lunar day), `sun_longest_outage_s`,
`earth_longest_outage_s` (longest stretch inside the lunar day without the body; a
stretch that continues across a boundary is cut there), and `sun_lit_s` when the package
has the eclipse-aware window `sun_lit`.

**Requirement.** A scenario may state requirements on the landing time:

```json
{"id": "example-surface-stay", "label": "…", "mission_duration_s": 432000,
 "conditions": [
   {"window": "earth_visible", "kind": "visible_at_landing"},
   {"window": "sun_visible", "kind": "continuous_from_landing", "min_s": 172800},
   {"window": "earth_visible", "kind": "total_in_mission", "min_s": 216000}]}
```

A requirement is always an input of the scenario. Three examples, chosen by the team and
labelled as such (they are not requirements of NASA or of any mission), are shipped in
[`presets/requirements.json`](presets/requirements.json): `example-standard` (Earth in
view at landing, 10 Earth days of unbroken sunlight), `example-strict` and
`example-loose`. Viewers read that file to offer presets and must show the `label` of
the requirement with every number derived from it.

`window` is the id of any window of the timeline. `visible_at_landing`: the window's
condition holds at the landing time. `continuous_from_landing`: it holds without
interruption for `min_s` from landing. `total_in_mission`: it holds for at least `min_s`
in total between landing and landing + `mission_duration_s`. All conditions must hold.

**Opportunity** (one record per requirement and observer height):

| Field | Content |
|---|---|
| `requirement_id`, `height_index` | Which requirement (in `request.timeline.requirements`), which observer height |
| `landing_windows_et_s`, `landing_windows_utc` | The landing times for which the requirement holds: sorted, disjoint intervals |
| `latest_landing_et_s`, `latest_landing_utc` | Last landing time that can be judged: the end of the computed range minus the mission duration. Later landings are not in the windows, whatever the truth |
| `clipped_start`, `clipped_end` | The first window starts at the start of the range, or the last one ends at `latest_landing`: its true extent is unknown |
| `feasible_fraction` | Total length of the windows divided by the time from the start of the range to `latest_landing` |
| `window_count`, `longest_window_s`, `median_window_s` | Summary of the windows |
| `feasible_s_per_period` | Feasible landing time inside each period of the calendar |
| `planned_landing` | `null`, or the slip report for the site's `landing_utc` (below) |
| `method` | Method card |

**Slip report** (`planned_landing`): `utc`, `et_s`; `feasible` (the requirement holds for
a landing at the planned time); `slip_tolerance_s` (the landing can be delayed by up to
this much and the requirement still holds; 0 if not feasible); `early_tolerance_s` (or
advanced by this much); `slip_tolerance_is_lower_bound` (the window is cut by the end of
what can be judged); `wait_s` (0 if feasible, otherwise the time to the next landing
window, `null` if there is none in the range); `wait_after_window_s` (from the end of the
current window to the next one); `next_window_start_utc`, `next_window_length_s`.

The landing windows are computed from the edges of the visibility windows by interval
arithmetic, not by trying dates, so they have the accuracy of the event times. The
requirement is the scenario's; the package cannot tell whether it is the right one.

### 5.7 Uncertainty band and landing ellipse (since 0.4)

Both are answers to "what if" questions with a stated assumption. Neither is an error
estimate of the result, and they are not combined.

**Stated horizon error.** Two assumptions can be stated, alone or together (they are
added): `uncertainty.horizon_error_deg`, a shift of the whole profile by the same angle
at every azimuth; and, since 0.6, `uncertainty.dem_height_error_m`, a height error of
the terrain point that sets the horizon, which moves the horizon in that azimuth by
`atan(height error / distance)`: much for near terrain, little for far terrain. The
profile is raised and lowered by the resulting error. Per body and observer height:

| Window id | Meaning |
|---|---|
| `<body>_visible_certain` | Visible even if the horizon is higher than computed by the stated angle |
| `<body>_visible_possible` | Visible if the horizon is lower by that angle |
| `<body>_visible_uncertain` | Possible and not certain: the band |

Always: certain is inside `<body>_visible`, which is inside possible. Metrics
`<body>_visible_certain_s`, `<body>_visible_possible_s`, `<body>_visible_uncertain_s`.
Every event gets `earliest_et_s`, `latest_et_s` (and the UTC strings): the interval of
the band that contains it; equal to the event time if the band is empty there. A
requirement (5.6) may name `sun_visible_certain` instead of `sun_visible` to get landing
windows that hold under the stated error.

**Height-error model** (since 0.10). Instead of one number, `uncertainty.dem_height_error_model`
states the height error per elevation product: `id`, `label`, `source`, and either
`constant_m` or `rules`, a map from product id (with `*` as wildcard; the most specific
pattern applies) to `{"rms_map_factor", "flat_m"}` (that factor times the product's own
error map at the pixel, `flat_m` where the map is empty) or `{"slope_classes": [{"up_to_deg",
"error_m"}]}` (by the slope of the terrain at the limiting point). `dem_height_error_m` and
the model exclude each other. The models shipped with the contract are in
[`presets/terrain_height_error.json`](presets/README.md); its default is measured by the
data stream and names its source, the constants are illustrative.

With a model or a constant, the package says what fed the band:

| Where | Field | Content |
|---|---|---|
| `horizon` | `obstacle_height_error_m` | `[H, A]` `<f4`: stated height error of the terrain point that sets the horizon; NaN where there is none |
| `horizon` | `obstacle_constrained` | `[H, A]` `<i4`: 1 if the pixel of that point holds a laser return, 0 if it was filled by interpolation, -1 if unknown |
| `timeline.uncertainty.horizon_error` | `dem_height_error_model` | `id`, `label`, `source` of the model; a viewer shows the label with the band |
| | `applied_height_error_m`, `applied_error_deg` | Least, median and largest error at the default observer height, in metres and as an angle |
| | `sources[]` | `source` (`rms_map`, `flat`, `slope_class`, `constant`) with its `azimuth_share` |
| | `limiting_pixels` | Shares of the azimuths whose limiting pixel is `constrained`, `interpolated`, `unknown` |
| every event | `terrain_quality` | `band_source`, `height_error_m`, `limiting_pixel` (`constrained`, `interpolated`, `unknown`) and `product_id` of the horizon sample at the azimuth of the body at the event. A viewer can say "this time rests on an interpolated pixel" |

**Stated landing ellipse** (`uncertainty.landing_ellipse`). The site is the centre.
Sample points fill the ellipse evenly in area; each has its own terrain horizon and its
own local vertical. Computed for the default observer height only.

| Field | Content |
|---|---|
| windows `<body>_visible_all_points`, `<body>_visible_any_point` | Visible at every sample point; at one point at least. The site's own window lies between them |
| `series.<BODY>.ellipse_visible_share` | `[N]`: share of the points at which the body is visible at each sample of the series (1 = everywhere in the ellipse, 0 = nowhere) |
| `uncertainty.landing_ellipse.points[]` | `lat_deg`, `lon_deg`, `surface_height_m`, `visible_s` per body (`null` if the point has no complete horizon). The first point is the site |
| `uncertainty.landing_ellipse.visible_s.<BODY>` | `centre_s`, `min_s`, `median_s`, `max_s` over the points |

`timeline.uncertainty.horizon_error` (`error_deg` and/or `dem_height_error_m`, and since
0.6 `applied_error_deg` with the least, median and largest error used at the default
observer height) and `.landing_ellipse` repeat the stated numbers and carry an
`assumption` sentence that a viewer must show with the band. The share of
points is a survey of the ellipse, not a probability.

### 5.8 Mast-height trade (since 0.5)

`timeline.height_trade` puts the observer heights of the package side by side:

| Field | Content |
|---|---|
| `observer_heights_m` | The heights of the package, lowest first |
| `quantities[]` | `id`, `label`, `unit` (seconds), `window` (the window id it is read from), `values[h]`, `change_s[h]` (value minus the value at the lowest height), `method` |

Quantity ids: `sun_visible_s`, `earth_visible_s`, `sun_and_earth_visible_s` (total time
the window holds in the computed range), `sun_longest_outage_s`,
`earth_longest_outage_s` (longest continuous time it does not), `sun_lit_s` when the
eclipse-aware window exists, and `sun_least_lunar_day_s` (Sun-visible time in the least
sunlit complete lunar day of the calendar). Only the listed heights are computed; a
viewer must not interpolate between them. For more heights, list them in the
scenario's `observer_heights_m` (up to 16).

### 5.9 Terrain patches for drawing (since 0.7)

`terrain` holds the ground around the site on regular grids, so that a viewer draws the
surface the horizon was computed from. **It is for drawing only.** Whether a body is
visible, and when it rises or sets, always comes from `timeline`, which was computed on
the finest elevation data. A viewer must not decide visibility by casting rays against a
patch, and where the drawn surface and the horizon profile disagree, the profile is
right.

| Field | Content |
|---|---|
| `use` | Always `"drawing"` |
| `notice` | The rule above in one sentence |
| `frame` | The frame in words: local East/North/Up of the site (`site.enu`), origin at the ground point of the site (`site.position_km`), metres |
| `method` | Method card id |
| `patches[]` | The patches. A reader selects a patch by its `id`, never by its position in the list (see below) |

A patch is a square grid centred on the site:

| Field | Content |
|---|---|
| `id` | `near`, `mid`, `far` for the default patches |
| `spacing_m`, `half_width_m` | Grid spacing, and half the side of the square |
| `count_east`, `count_north` | Nodes per axis, `2 * half_width_m / spacing_m + 1` |
| `east_min_m`, `north_min_m` | Coordinates of element `[0][0]`; both are `-half_width_m` |
| `up_m` | Array reference: float32, shape `[count_north, count_east]`, metres. NaN where the elevation data ends; such nodes must be left out of the mesh |
| `up_min_m`, `up_max_m` | Range of the values (`null` if there is none) |
| `sources[]` | Where the heights were read: `product_id`, `level` (0 is the elevation product itself, level k its block average over 2^k x 2^k pixels), `pixel_m`, `statistic`, `sha256` of the file read, `derived_from_sha256` (the product's data file, for a derived level), `node_share`. The products are listed in `inputs.dem.layers[]` with their source address. Empty in a synthetic package |

**Patches are selected by `id`; the order of the list is not part of the contract.** A
reader looks a patch up by its `id` and must not take the first, second or third entry
for `near`, `mid` or `far`, nor assume that there are three: a scenario may state other
patches, for example a 5 m patch `site` around the site, and the package then holds
that one as well. (The core writes the list with the smallest spacing first. Until
0.11 this section stated that order; a reader must not rely on it.)

Placing a vertex needs no projection and no correction for the curvature of the Moon,
which is already in the values (on a smooth sphere `up` falls off as
`-(east^2 + north^2) / (2 r)`: 0.3 m at 1 km, 18 m at 8 km, 295 m at 32 km):

```
east  = east_min_m  + j * spacing_m          j = 0 .. count_east - 1
north = north_min_m + i * spacing_m          i = 0 .. count_north - 1
up    = up_m[i][j]

vertex, local, metres      (east, north, up)
vertex, body-fixed, km     site.position_km + (east * enu.east + north * enu.north + up * enu.up) / 1000
observer at height m       (0, 0, m)
direction of azimuth A and elevation E (horizon, series)
                           (sin A cos E, cos A cos E, sin E)
```

The default patches (a scenario may state others in `terrain_patches`: at most 8, at most
1025 nodes per axis, `half_width_m` a multiple of `spacing_m`; an empty list writes none):

| `id` | Side | Spacing | Nodes | Bytes | Read from |
|---|---|---|---|---|---|
| `near` | 4 km | 20 m | 201 x 201 | 161 604 | the finest product |
| `mid` | 16 km | 80 m | 201 x 201 | 161 604 | its block average over 4 x 4 pixels |
| `far` | 64 km | 320 m | 201 x 201 | 161 604 | its block average over 16 x 16 pixels |

That is 0.49 MB per site, raw. Where patches overlap, draw the one with the smallest
`spacing_m`. Terrain beyond the
largest patch is not in the package as a surface; its silhouette is
`horizon.elevation_deg`, with `horizon.distance_m` saying how far away it is.

How well the drawn surface matches the package horizon (measured on three site records,
[method note](../method/terrain_patch.md)): its silhouette differs from
`horizon.elevation_deg` by 0.03 to 0.04 degrees in the median, by 0.09 to 0.33 degrees at
95 % of the azimuths and by 0.46 degrees at most, the largest differences being where
terrain within 500 m of the site sets the horizon; it stands above the package horizon by
0.02 degrees at most. The far patch alone matches to 0.22 degrees where the horizon is
set by terrain beyond 8 km and is off by up to 3.3 degrees for nearer terrain. The Sun's
disc is 0.53 degrees across: hence the rule at the top of this section.

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
| `earth_view` | Since 0.8, optional. The orientation of the Earth per record, for drawing it; see 6.1 |
| `inputs.kernels[]` | `name`, `bytes`, `sha256`, `source_url`, `load_order` |
| `inputs.earth_orientation_kernels[]` | Since 0.8, when `earth_view` is present: the kernels the Earth's orientation was read from, same fields |

Reserved: `earth_rotation` (for ground-station windows).

Direction from a site, as the core computes it:

```
d  = positions_km[t, body] - site.position_km - up * h / 1000      (all body-fixed, km)
az = atan2(d · east, d · north)      el = asin((d · up) / |d|)
```

Viewers use this only to place the Sun and the Earth in a scene. Rise and set times,
margins and visible fractions are read from the site package, never recomputed.

### 6.1 Orientation of the Earth (since 0.8)

`earth_view` lets a viewer turn a textured Earth the right way. It is present when the
Earth-orientation kernels were installed (`request.earth_view` is then `true`);
otherwise the table carries a warning and a viewer draws the Earth without detail. It is
for drawing only.

| Field | Content |
|---|---|
| `sub_lunar_lat_deg` | `[N]` `<f4`: latitude of the point of the Earth's surface at the centre of the disc seen from the centre of the Moon, as on a map (perpendicular to the reference ellipsoid) |
| `sub_lunar_lon_deg` | `[N]` `<f4`: its east longitude, in (-180, 180] |
| `north_pole_angle_deg` | `[N]` `<f4`: position angle of the Earth's north pole in the sky of that observer, counted from the Moon's north pole (+Z of `frame`, projected on the plane of the sky) counter-clockwise, towards east = +Z x (direction to the Earth) |
| `earth_frame` | Earth-fixed frame of latitude and longitude (`ITRF93`) |
| `flattening` | Flattening of the reference ellipsoid of the latitude |
| `method` | Method card id |

Between records: latitude and position angle linearly; longitude linearly **the short
way round** (it wraps at 180 degrees and moves west by about 14.5 degrees per hour).

From the three angles to the Earth's axes in the frame of the table (`g` is the unit
vector from the centre of the Moon to the Earth, `positions_km[t, EARTH]` normalised):

```
east     = normalise(Z x g)              Z = (0, 0, 1)
north    = g x east
phi      = atan(tan(sub_lunar_lat) * (1 - flattening)^2)      (0.19 deg at most from sub_lunar_lat)
pole     = sin(phi) * (-g) + cos(phi) * (cos(angle) * north + sin(angle) * east)
meridian = normalise(-g - sin(phi) * pole)
x_axis   = cos(lon) * meridian - sin(lon) * (pole x meridian)
y_axis   = pole x x_axis
```

`pole` is the Earth's north pole and `x_axis` the direction of latitude 0, longitude 0;
a texture in the usual latitude-longitude layout is mapped with these axes. In a site's
local frame the same vectors are obtained by projecting on `site.enu`. Measured against
JPL Horizons: latitude and longitude within 0.007 degrees, pole angle within 0.0002
degrees ([method note](../method/earth_view.md)).

## 6a. Site-pairs package (since 0.5)

Written at `site_pairs/<package_id>/` when a scenario has at least two sites with a
timeline. It holds no arrays. Each site is taken at its default observer height; all
sites share the time range of the scenario.

| Field | Content |
|---|---|
| `request` | `site_package_ids` (in the order of `sites`), `windows` (the window ids compared) |
| `inputs.site_packages[]` | `site_id`, `package_id`, `content_sha256` of each site package used |
| `time` | The common time grid |
| `sites[]` | `site_id`, `name`, `lat_deg`, `lon_deg`, `package_id`, `observer_height_m` |
| `pairs[]` | One entry for every two sites: `site_a`, `site_b`, `distance_m` (great circle on the reference sphere), `windows[]` |

A row of `pairs[].windows[]`, for one compared window (`sun_visible`, `earth_visible`,
`sun_and_earth_visible`):

| Field | Content |
|---|---|
| `window` | The window id |
| `a_s`, `b_s` | Time the window holds at site A, at site B |
| `either_s`, `both_s`, `neither_s` | At one of them at least; at both; at neither. `either_s + neither_s` is the length of the range |
| `either_fraction` | `either_s` divided by the length of the range |
| `longest_neither_s`, `neither_intervals_et_s`, `neither_intervals_utc` | The joint outages |
| `gain_over_better_s` | `either_s` minus the larger of `a_s` and `b_s`: what the second site adds |
| `covered_share_of_better_outage` | That gain divided by the time the better site lacks; `null` if it lacks none |
| `method` | Method card |

The package says when at least one site sees the body. It does not say that power or
data can be moved between the sites.

## 7. Index

`packages[]`: `kind`, `package_id`, `path`, `synthetic`, `status`; for sites also
`site_id`, `name`, `lat_deg`, `lon_deg`, `has_timeline` and, since 0.11 and only where
the site states them, `programme` and `category` (5.2); for site pairs `site_ids`.

## 8. Versioning

The version is `major.minor`. Adding an optional field raises the minor number; readers
must ignore fields they do not know and keep working. Changing the meaning, unit or layout
of an existing field raises the major number; a reader must refuse a package with another
major number and say why. A reader written for 0.2 reads 0.1 packages (it finds the 0.2
fields absent); the validator accepts every minor version up to its own. While the major number is 0 the format may still change, but
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

## 10. Changes

### 0.11 (14 November 2026)

Additive; nothing that existed in 0.10 changed its meaning, name, unit or layout.

- Optional descriptive labels `programme` and `category` in `sites[]` of a scenario, in `site` of a site package and in the site entries of the index (5.2, 7). They are not part of `request`: package ids do not depend on them.
- No change to any number. A reader written for 0.10 reads 0.11 packages unchanged and finds two fields it does not know.
- Clarification, no change to any file: terrain patches are selected by `id`; the order and the number of `terrain.patches[]` are not part of the contract (5.9). Section 5.9 said "finest first" since 0.7. The core still writes them that way, but a reader must not rely on it: a package may hold a patch finer than `near`. The validator no longer requires an order; it checks that the patches written are those the request states.

### 0.10 (14 November 2026)

Additive; nothing that existed in 0.9 changed its meaning, name, unit or layout. The version number is compared part by part: 0.10 is newer than 0.9.

- Scenario and site request: `uncertainty.dem_height_error_model`.
- Site package: `horizon.obstacle_height_error_m`, `horizon.obstacle_constrained`; `terrain_quality` in every event; `dem_height_error_model`, `applied_height_error_m`, `sources`, `limiting_pixels` in `timeline.uncertainty.horizon_error`.
- Presets: `docs/contract/presets/terrain_height_error.json`.
- Countdown metrics carry `reference` (the instant they are counted from); section 5.4. Their values and ids are unchanged.
- `inputs.dem.layers[]` can name a 5 m site raster when the run used the near field ([method note](../method/near_field.md)).

### 0.9 (14 November 2026)

Additive; nothing that existed in 0.8 changed its meaning, name, unit or layout.

- Site package: `horizon.terrain_source`; method card `horizon.terrain_source`.
- A site anywhere on the Moon gets a package when an elevation product covers it; `inputs.dem.layers[]` then lists the latitude-longitude products as well.
- Packages of sites served by the polar products are unchanged apart from the new field.

### 0.8 (14 November 2026)

Additive; nothing that existed in 0.7 changed its meaning, name, unit or layout.

- Direction table: `earth_view` with three arrays `earth_*.f4`, `request.earth_view`, method card `dirtab.earth_view`; section 6.1.
- `inputs.earth_orientation_kernels[]` of a table with `earth_view` lists the kernels the Earth's orientation was read from. Such a table has a new package id, and so have the site packages computed from it.
- The sample table holds an invented `earth_view`; the sample was regenerated (new ids).

### 0.7 (14 November 2026)

Additive; nothing that existed in 0.6 changed its meaning, name, unit or layout.

- Site package: `terrain` with its patches and the arrays `terrain_<id>_up_m.f4`; method card `terrain.patch`; section 5.9.
- Scenario: `terrain_patches`. Site request: `terrain_patches`.
- The default patches are written for every site unless the scenario says otherwise. Because the request names them, a site computed again has a new package id.
- The sample holds three small invented patches per site; it was regenerated (new ids).

### 0.6 (14 November 2026)

Additive, with one relaxation; nothing that existed in 0.5 changed its meaning, name,
unit or layout, and a scenario that states only what 0.5 knew gives a package with every
field of 0.5.

- Scenario and site request: `uncertainty.dem_height_error_m`.
- `timeline.uncertainty.horizon_error`: `dem_height_error_m`, `applied_error_deg`.
- Relaxation: `timeline.uncertainty.horizon_error.error_deg` is present only if a common shift was stated. In 0.5 it was always present, because a common shift was the only horizon error that could be stated. A reader must not assume it when `dem_height_error_m` is there.
- Requirement presets in `docs/contract/presets/requirements.json` (a documented file next to the contract; not part of a package).
- The sample scenario states an invented terrain height error in addition; the sample was regenerated (new ids).

### 0.5 (14 November 2026)

Additive; nothing that existed in 0.4 changed its meaning, name, unit or layout.

- `timeline.height_trade` (5.8).
- New package kind `site_pairs` with id prefix `pairs-` (6a); the index lists it with `site_ids`. Readers that only know `site` and `direction_table` must skip index entries of other kinds.
- New method card ids: `timeline.height_trade`, `pairs.complementarity`.
- The sample scenario has a second invented site, so the sample holds two site packages and one site-pairs package; it was regenerated (new ids).

### 0.4 (14 November 2026)

Additive; nothing that existed in 0.3 changed its meaning, name, unit or layout.

- Scenario and site request: `uncertainty` (`horizon_error_deg`, `landing_ellipse`).
- Windows `<body>_visible_certain`, `_possible`, `_uncertain`, `_all_points`, `_any_point` and the matching metrics (5.7).
- Events: `earliest_et_s`, `latest_et_s`, `earliest_utc`, `latest_utc`.
- `timeline.series.<BODY>.ellipse_visible_share`, `timeline.uncertainty`.
- New method card ids: `timeline.horizon_error`, `timeline.landing_ellipse`.
- The sample scenario states an invented horizon error and an invented ellipse; the sample was regenerated (new site package id).

### 0.3 (14 November 2026)

Additive; nothing that existed in 0.2 changed its meaning, name, unit or layout.

- Scenario: `requirements[]`; `sites[].landing_utc` is now used as the planned landing.
- Site request: `request.timeline.requirements`, `request.timeline.landing_utc` (so that the package id depends on them).
- `timeline.calendar`, `timeline.opportunities[]` (5.6).
- New method card ids: `timeline.calendar`, `timeline.opportunity`.
- The sample scenario states an invented example requirement and a planned landing; the sample was regenerated (new site package id).

### 0.2 (14 November 2026)

Additive; nothing that existed in 0.1 changed its meaning, name, unit or layout.

- `horizon.obstacle_id`, `horizon.obstacles[]`: the profile grouped into obstacles (5.3).
- `timeline.series.<BODY>.blocker_azimuth_index`, `timeline.blockers[]` (5.5).
- New window ids `<body>_visible_smooth_sphere`, `<body>_lost_to_terrain`, `<body>_gained_from_terrain` and metrics `<body>_visible_s`, `<body>_visible_smooth_sphere_s`, `<body>_lost_to_terrain_s`, `<body>_gained_from_terrain_s` (5.5).
- `timeline.series.<BODY>.lit_fraction` (5.4), optional.
- New method card ids: `horizon.obstacles`, `timeline.smooth_sphere`, `timeline.blocking`, `timeline.lit_fraction`.
- The validator accepts packages of older minor versions.
- The sample was regenerated: its package ids changed (new directories), and its invented horizon now has a far ridge and a near rock field so that it falls into several obstacles. Find the packages through `index.json`.
