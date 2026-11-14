# Unreal view scene

Unreal Engine 5.8.4 C++ project that shows one site package: the terrain horizon around the
site, the Sun as a directional light, the Sun and Earth discs, a time slider and the
countdowns to the next sunset and the next loss of the Earth. It reads packages
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
| Reference sphere | package: `reference_radius_m`; sunk near the site so that it stays out of sight |
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
Scripts\import_packages.ps1 <package root>      # real packages -> Content\LsnPackages
python Scripts\export_terrain.py Content\LsnPackages   # real ground (needs the data stream's reader and the LOLA files)
Scripts\capture.ps1 -Out <png> -Time 2092 -Yaw 211 -Pitch -3 -Fov 40
Scripts\record.ps1 -Out <mp4> -Site <site_id> -From 2088 -To 2100 -Seconds 25   # needs ffmpeg
Scripts\package.ps1 -Out <folder>               # stand-alone Windows program
```

`Content\LsnPackages` and `Content\LsnTerrain` are not under version control. The real
packages are produced by the science core (`python -m validation.sites.run <sites.json>
--out <package root>` on the core branch, with the LOLA files of `python -m lsn_data
fetch`); the same command gives the same package ids on every machine.

The stand-alone program is the folder `<folder>\Windows`; start `LunarSiteNavigator.exe`.
It needs neither the editor nor a network connection: packages and terrain are staged
next to it as plain files. `-LsnSite=<site_id>` picks a site, `-windowed -ResX= -ResY=`
a window.

Keys: mouse or arrow keys look; `Q`/`E` step one sample (Shift: 24); `Space` plays and
pauses; `[` `]` change the playing speed; `Tab` shows the cursor to drag the time strips;
`PageUp`/`PageDown` observer height; `Z`/`X` zoom; `O` obstacle view; `H` package
horizon line; `L` fill light; `Esc` quits. Command line: `-LsnPackage=<site package dir>` or
`-LsnPackageRoot=<root with index.json>`, `-LsnSite=`, `-LsnTime=`, `-LsnHeight=`,
`-LsnYaw=`, `-LsnPitch=`, `-LsnFov=`, `-LsnHorizonLine`, `-LsnShot=<png>`,
`-LsnPlayFrom= -LsnPlayTo= -LsnPlaySeconds= -LsnMovieDir=`.

Without a package argument the scene uses `Content\LsnPackages`, then
`docs/contract/sample/packages`, then the pinned copy in `TestData/`.

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
| `Hud.TextAndSyntheticMarker` | Synthetic marker for synthetic packages only; countdown wording, "at least" for lower bounds; UTC labels | exact |
| `Real.ImportedPackages` | On every imported real package: not synthetic, countdown at the start equals the package's own metric, obstacle points, scene silhouette, direction table against series | 1e-3 s; 0.05; 0.001; 0.0002 deg |
| `Real.TerrainAgainstHorizon` | No LOLA sample (from the start of the package's horizon search outwards) stands above the package horizon of its azimuth; mesh silhouette with real ground | 0.001 deg |

The two `Real.*` tests report a warning ("NOT RUN") when no real packages or terrain are
imported, as on a machine without the data.

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
- Display values (light intensity, exposure, albedo, fill light) are not photometry.
