# Unreal planner view

Unreal Engine 5.8.4 C++ project that shows site packages as a planner sees a site: the
terrain horizon around it, the Sun as a directional light, the Sun and Earth discs, a time
slider, the countdowns to the next sunset and the next loss of the Earth, the ridge that
hides the Sun and the hours it costs, and two sites side by side at the same instant. It reads packages
(`docs/contract/SPEC.md`, contract 0.x) and computes no Sun or Earth position, rise or set
time, margin or visible fraction of its own.

Only one machine compiles this project and writes its binary assets (`Content/`, stored
with Git LFS: run `git lfs install` once per machine).

## Frames and world origin

| Frame | Handedness, unit | Origin | Axes |
|---|---|---|---|
| Moon body-fixed (named by the package, `site.frame`) | right-handed, km | centre of the Moon | +Z north pole, +X lat 0 / lon 0, +Y lat 0 / lon 90 E |
| Site frame | right-handed, m | ground point of the site | east, north, up; up is the normal of the reference sphere |
| Unreal world | left-handed, cm | ground point of the site | **+X north, +Y east, +Z up** |

- Azimuth is clockwise from north (north 0, east 90); elevation is above the plane
  perpendicular to up. A direction with azimuth `a` and elevation `e` is
  `(cos e cos a, cos e sin a, sin e)` in the Unreal world, so Unreal yaw equals azimuth and
  pitch equals elevation.
- Body-fixed to Unreal is a reflection (right-handed to left-handed). It is applied to
  coordinates in double precision in `Frame/LsnSiteFrame`, never as an actor rotation.
- The world origin is the site's ground point, so everything near the camera has small
  coordinates. The centre of the Moon lies one site radius straight below, about
  -1.7e8 cm. The terrain mesh has its origin at the site; the sphere mesh has its origin at
  the centre of the Moon and is placed by its component transform, which the engine keeps
  in double precision. Vertex buffers are 32-bit: at the farthest horizon points
  (some 1e7 cm) one step is about 1 cm. The tests measure meshes after rounding to 32-bit.
- The Sun and Earth discs are drawn at a fixed distance in the direction and with the
  angular radius the package gives; their true distances are not used.

## What the scene draws, and where each part comes from

| Part | Source |
|---|---|
| Horizon line of the terrain (the crest vertex of every azimuth) | package: `horizon.elevation_deg`, `horizon.distance_m` |
| Ground, real packages | LOLA heights sampled once per site through the data stream's reader on 320 rings per azimuth (`Scripts/export_terrain.py`). A cache for drawing: no number on screen comes from it |
| Ground, synthetic packages or without a terrain export | a placeholder surface with procedural craters; the read-out says so |
| Sun light direction and source angle, Sun and Earth discs | package: `timeline.series` at the selected time |
| Countdowns "sets in" / "rises in" | package: interval boundaries of the windows `sun_visible`, `earth_visible`. "at least" means the package has no such event in its computed range |
| Time strips (yellow Sun, blue Earth) | package: the same windows |
| Obstacle view: highlighted ridge, "hidden by terrain ... away", "this ridge costs N h" | package (contract 0.2, SPEC 5.5): `series.<BODY>.blocker_azimuth_index` at the sample, `horizon.obstacle_id` there, the run of `horizon.obstacles[k]`, `lost_s` of the matching `timeline.blockers` record. Hidden for packages without these fields |
| Dashed outline "Sun (behind terrain)" | package: direction and angular radius of the series, drawn over the terrain while the body is hidden |
| Panorama (top right): horizon all round, Sun and Earth marks, the highlighted obstacle | package: `horizon.elevation_deg`, the series at the selected time, the obstacle run |
| Summary numbers under the panorama | package: metrics `sun_visible_fraction_of_time`, `sun_longest_outage_s`, `earth_visible_fraction_of_time`, `earth_longest_outage_s`, `sun_lost_to_terrain_s`, `sun_gained_from_terrain_s`, with units converted |
| "Sun 121 deg to the right" at the lower right | package: direction of the body at the selected time, when it is outside the view |
| Calendar page | package (since 0.3, SPEC 5.6): `timeline.calendar`, `request.timeline.requirements`, `timeline.opportunities`. "Landing now meets the requirement; it can slip by ..." is the distance from the selected time to the end of the landing window it lies in; for the scenario's planned landing the package's own slip report is printed. The requirement is named and marked as an example chosen by the team |
| Pale edges of the time strips, "for a stated horizon error of ..." under a countdown | package (since 0.4, SPEC 5.7): windows `<body>_visible_certain` / `_possible`, `earliest_et_s` / `latest_et_s` of the event |
| Uncertainty page: ellipse map and its hours | package: `timeline.uncertainty.landing_ellipse` (points, statistics), `series.SUN.ellipse_visible_share` |
| Mast-height trade, site pairs | package (since 0.5, SPEC 5.8, 6a): `timeline.height_trade`; the `site_pairs` package of the root, shown only if it was computed from the very site package on screen |
| Reference sphere | package: `reference_radius_m`; sunk near the site so that it stays out of sight |
| Surface shading | none (a display model): the engine's cosine law times a regolith factor 2 / (mu0 + mu), limited to 4, which together give the Lommel-Seeliger law used as a first description of dark, dusty surfaces. The Sun's direction in it is the package's. Uniform grey, no texture, no invented relief |
| Earth's disc | package: direction and angular size; a plain sphere lit by the scene's Sun, so its phase follows from the two package directions. No map of the Earth: the package does not say which side faces the Moon |
| Shadows | the engine's virtual shadow maps from the terrain mesh, with the Sun's angular diameter (package) as the light's source angle: hard shadows with the penumbra of the solar disc |
| Weak fill light from the zenith, no shadows | none: a display aid so that unlit terrain is told apart from the sky (key `L`, `-LsnNoFillLight`) |

Between two time samples the Sun and the Earth are drawn at the linear interpolation of
the package series over that one step, for a smooth display; at a whole sample the
package values are shown unchanged, and the numbers in the read-out are always those of a
sample. A package with `synthetic: true` is marked "SYNTHETIC DATA" at all times; a real
package never is (both directions are tested).

## Run

```
Scripts\build.ps1                               # compile the editor target
Scripts\run_tests.ps1                           # all automated tests, no window
python Scripts\compare_horizon.py               # horizon comparison repeated in Python
python Scripts\export_terrain.py ..\packages     # real ground (needs the data stream's reader and the LOLA files)
Scripts\capture.ps1 -Out <png> -Time 2092 -Yaw 211 -Pitch -3 -Fov 40
Scripts\record.ps1 -Out <mp4> -Site <site_id> -From 2088 -To 2100 -Seconds 25   # needs ffmpeg
Scripts\package.ps1 -Out <folder>               # stand-alone Windows program
Scripts\pitch.ps1                               # pitch clip and six stills -> docs\unreal\pitch (needs ffmpeg)
```

The scene reads the published packages from `packages/` at the root of the repository,
which the science core regenerates; it keeps no copy of its own. Any contract version
0.x is read, and a panel whose fields a package lacks is hidden. `Content\LsnTerrain`
(the terrain samples for drawing) is not under version control; it is tied to the package
ids, so run `export_terrain.py` again after the packages have been regenerated, or the
placeholder ground is drawn.

The stand-alone program is the folder `<folder>\Windows`; start `LunarSiteNavigator.exe`.
It needs neither the editor nor a network connection: `package.ps1` copies `packages/`
and the terrain samples into it as plain files when it is built. `-LsnSite=<site_id>` picks a site, `-windowed -ResX= -ResY=`
a window.

## Planner interface

One site fills the screen; with a second site the screen is split left and right. Both
halves show the same instant (matched by the TDB time of the packages), the same observer
height, zoom and elevation of the view. By default each half keeps its view on its own
Sun's azimuth, so that the same instant can be compared although the Sun stands in
another direction at each site; `F` switches to a common azimuth. If the instant lies
outside the time range of the right package, that half says so and keeps its nearest
sample.

| Keys | |
|---|---|
| `1` .. `9` | show that site of the package root (`Shift`: in the right half, side by side) |
| `C` | comparison of two sites on and off |
| `K` | calendar page: lunar-day calendar on one time axis for the site (side by side: for both sites), landing windows of the chosen requirement, slip of a landing at the selected time and of the scenario's planned landing |
| `U` | uncertainty page: the stated horizon error and the survey of the stated landing ellipse (small map of its sample points) |
| `M` | mast-height trade and site pairs |
| `R` | next requirement of the package |
| mouse, arrow keys | look (while following the Sun: turn away from it) |
| `Q` / `E` | one sample back / forward (`Shift`: 24 samples) |
| `,` / `.` | one day back / forward |
| `B` / `N` | previous / next rise or set of the Sun in the package (`Shift`: of the Earth) |
| `Home` / `End` | first / last sample |
| `Space`, `[`, `]` | play and pause, halve and double the playing speed |
| `Tab` | mouse cursor, to drag the two time strips |
| `F` | keep the view on the Sun's azimuth |
| `PageUp` / `PageDown` | observer height |
| `Z` / `X` | zoom |
| `O`, `H`, `L` | obstacle view, package horizon line, fill light |
| `Esc` | quit |

Command line: `-LsnPackage=<site package dir>` or `-LsnPackageRoot=<root with index.json>`,
`-LsnSite=<site_id>`, `-LsnCompare=<site_id>,<site_id>`, `-LsnTime=`, `-LsnUtc=<2027-07-28T18:00:00Z>`,
`-LsnHeight=`, `-LsnPage=calendar|uncertainty|trade`, `-LsnRequirement=<index>`,
`-LsnYaw=` (while following the Sun: the offset from its azimuth), `-LsnPitch=`, `-LsnFov=`,
`-LsnFollowSun`, `-LsnHorizonLine`, `-LsnNoFillLight`, `-LsnNoObstacle`, `-LsnShot=<png>`,
`-LsnPlayFrom= -LsnPlayTo=` (or `-LsnPlayFromUtc= -LsnPlayToUtc=`) `-LsnPlaySeconds= -LsnMovieDir=`,
`-LsnCameraUp=<m> -LsnCameraBack=<m>`, `-LsnNoHud`.

`Scripts\pitch.ps1` makes everything under `docs/unreal/pitch/` from the published
packages and writes `README.txt` there: which package, site and time each file shows. A
view whose data the published packages lack is not produced, and the text file says so;
run the script again when `packages/` has been regenerated.

Without a package argument the scene uses `packages/` of the repository (in the
stand-alone program: its copy of that folder), then `docs/contract/sample/packages`, then
the pinned copy in `TestData/`.

## Tests and thresholds

Thresholds are constants next to the tests, written before the first measurement.

| Test group | What it shows | Threshold |
|---|---|---|
| `Frame.*` | Known directions and points land at hand-written Unreal coordinates; the Moon centre is straight below the origin | 1e-12 (unit vectors), 1e-5 cm |
| `Package.LoadSample`, `RefusesBadPackages` | Reader follows the contract; another major version, a truncated array, the wrong package kind and a missing manifest are refused | exact |
| `Package.FrameAgreesWithCore` | `site.enu` and `site.position_km` equal the frame derived here from latitude and longitude | see test |
| `Package.BodyFrameAgreesWithSeries` | Direction-table positions mapped through the body-fixed frame give the series directions | 0.0002 deg |
| `Package.ObstaclePointsReproduceHorizon` | Obstacle points (arc distance, obstacle height) placed through the site frame give `horizon.elevation_deg` | 0.05 deg |
| `Package.CountdownFromWindows`, `WindowsOfTheSample` | Countdowns are distances to interval boundaries of the package windows; windows and series agree at every sample | 1e-9 s; 0 disagreements |
| `Mesh.*`, `Terrain.GridMesh` | Winding matches the engine, sphere stays out of sight, craters only lower, silhouette measurement is exact on known shapes, terrain-grid vertices lie at their ring, azimuth and height | see tests |
| `Acceptance.SunAndEarthFromPackage`, `SunFollowsThePackage` | Light direction, source angle, disc positions and sizes of the spawned scene equal the package at every sample | 0.001 deg |
| `Acceptance.SliderFollowsThePackage` | Whole positions equal the samples; between samples light and discs show the interpolated package series | 0.001 deg |
| `Acceptance.HorizonSilhouette` (+ `HorizonExportForPython`, `compare_horizon.py`) | Silhouette of the scene's terrain and sphere, seen from the observer, equals `horizon.elevation_deg` for every height and azimuth; repeated with the package read by Python | 0.001 deg |
| `Package.BlockerRecipe`, `ObstaclesOfTheSample` | The viewer recipe of SPEC 5.5 on a hand-made package and on the sample: limiting azimuth, obstacle, cost; runs carry their obstacle id; blockers are sorted and name existing obstacles; wording of the sentences | exact; shares <= 1 + 1e-6 |
| `Acceptance.ObstacleHighlight` | While a body is hidden the highlight lies on the azimuths of the obstacle's run and its lower edge is the package horizon; no highlight while the body is clear | 0.001 deg |
| `Acceptance.SecondSceneAwayFromOrigin` | The second scene of a comparison stands 20 000 km from the world origin and is the same scene: eye, Sun disc, light and silhouette as the package says; the two scenes are lit on separate lighting channels | 0.001 deg; 1e-6 cm |
| `Planner.LinkedTimeEventsAndMetrics` | Both halves show the same TDB instant or say that they cannot; jumps go to package events only; the summary numbers are the package metrics with units converted; site list; panorama mapping | 1e-9 samples; exact |
| `Planner.LandingSlipAndPanels`, `Package.PlanningFieldsOfTheSample` | Slip of a selected landing time from the landing windows (hand-made: exact; at the planned landing: equal to the package's slip report); calendar periods without gaps; certain inside visible inside possible at every sample; event bands contain their event; ellipse points inside the stated ellipse; mast and pair tables; nothing is shown without the fields | 1e-9 s; 1e-3 s; 0 violations |
| `Real.PlanningFieldsOnlyWhenPublished` | States for every published site package which planning fields it carries, and checks its slip reports where it has them | 1e-3 s |
| `Hud.TextAndSyntheticMarker` | Synthetic marker for synthetic packages only; countdown wording, "at least" for lower bounds; UTC labels | exact |
| `Real.ImportedPackages` | On every imported real package: not synthetic, countdown at the start equals the package's own metric, obstacle points, scene silhouette, direction table against series | 1e-3 s; 0.05; 0.001; 0.0002 deg |
| `Real.TerrainAgainstHorizon` | No LOLA sample (from the start of the package's horizon search outwards) stands above the package horizon of its azimuth; mesh silhouette with real ground | 0.001 deg |

The two `Real.*` tests run on the published packages in `packages/`. The terrain test
reports a warning ("NOT RUN") for a site without exported terrain samples, as on a machine
without the LOLA files.

## Limits

- The silhouette tests compare mesh geometry, not rendered pixels; the rendered view is
  checked by eye (horizon line overlay, captures under `docs/unreal/`).
- The crest of the terrain is by construction the package horizon. That proves the frame,
  reader and mesh chain. The independent part is `Real.TerrainAgainstHorizon`: heights read
  here through the data stream's reader never rise above the core's horizon.
- The package horizon starts 20 m from the site (`first_point_m` of its method card). For
  the 0 m observer the ground nearer than that rises up to 4.8 deg above the package
  horizon at the de Gerlache site; from 1 m up it does not. The test reports this with
  every run without a verdict.
- The ground is sampled on rings 2.8 % apart and at the 0.25 deg azimuth step: relief
  between samples is not drawn. Shadows on the ground are those of this sampled mesh, so
  a shadow edge is not a computed quantity; the package's `visible_fraction` is.
- "This ridge costs N h" is the package's `lost_s`: time the body would be visible over a
  smooth sphere through the site but is not over the terrain, in the computed window
  (here twelve months), split between obstacles to the step of the series. At a site on a
  crest the terrain mostly lies below the smooth horizon and gives time instead: the
  de Gerlache and Malapert packages have almost no blockers, the Shackleton rim has 38.
- An obstacle within 1 km is marked "depends on single pixels of the elevation model", as
  the contract asks. Four of the five costliest Sun obstacles of the Shackleton rim site
  at 2 m are of that kind (191 h, 120 h, 107 h, 61 h); the far ridge shown in
  `docs/unreal/obstacle_shackleton_ridge_2027-07-28.mp4` (52 h, 10.4 km away) is not.
- The obstacle view uses the values of the sample the time position belongs to; it does
  not interpolate which obstacle is the limiting one.
- A page whose fields the package lacks says so in one line and shows nothing else. The
  published packages decide what can be shown: `Real.PlanningFieldsOnlyWhenPublished`
  prints, per site, which fields they carry.
- The split screen, the keys and the mouse are not covered by automated tests; they were
  checked on real captures (`docs/unreal/planner_*.png`, `compare_*.mp4`). Sites are
  selected with the number keys; there is no mouse menu.
- `-LsnCameraUp=<m> -LsnCameraBack=<m>` lifts the camera above the observer for overview
  stills; the read-out then says that this is not the observer's view, and the markers
  that only make sense from the site are not drawn. `-LsnNoHud` leaves a caption line
  (site, time, package) and, for a synthetic package, the synthetic marker.
- Display values (light intensity, fixed exposure, albedo 0.13, fill light, the limit of
  the regolith factor) are not photometry. The exposure is fixed for a Sun a few degrees
  above the horizon; nothing adapts to the scene.
