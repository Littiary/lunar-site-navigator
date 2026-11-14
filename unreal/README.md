# Unreal view scene

Unreal Engine 5.8.4 C++ project that shows one site package: the terrain horizon around the
site, the Sun as a directional light, and the Sun and Earth discs. It reads packages
(`docs/contract/SPEC.md`) and computes no Sun or Earth position, rise or set time, margin
or visible fraction of its own.

Only one machine compiles this project and writes its binary assets (`Content/`).

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

## What the scene draws

- **Horizon line of the terrain mesh**: one vertex per azimuth sample at the point given
  by `horizon.elevation_deg` and `horizon.distance_m`. This is package data.
- **Ground between the site and that line**: a placeholder surface with procedural craters
  that only lower it. It is not elevation data and the HUD says so. It will be replaced by
  real tiles when the data stream provides an export.
- **Reference sphere**, sunk near the site so that it stays out of sight from the observer.
- **Sun light, Sun disc, Earth disc** from the `timeline` series. A package without a
  timeline shows none of them.
- A package with `synthetic: true` is marked on screen at all times.

## Run

```
Scripts\build.ps1                      # compile the editor target
Scripts\run_tests.ps1                  # all automated tests, no window
python Scripts\compare_horizon.py      # horizon comparison repeated in Python
Scripts\capture.ps1 -Out <png> -Time 552 -Yaw 340 -Pitch 2 -HorizonLine
```

Interactive: `UnrealEditor.exe LunarSiteNavigator.uproject -game`. Mouse or arrow keys
look, `Q`/`E` step the time sample (Shift: 24 samples), `PageUp`/`PageDown` change the
observer height, `Z`/`X` zoom, `H` toggles the package horizon line. Command line:
`-LsnPackage=<site package dir>` or `-LsnPackageRoot=<root with index.json>`, `-LsnTime=`,
`-LsnHeight=`, `-LsnYaw=`, `-LsnPitch=`, `-LsnFov=`, `-LsnHorizonLine`, `-LsnShot=<png>`.

Without a package argument the scene uses `docs/contract/sample/packages` when present and
otherwise the pinned copy in `TestData/` (see `TestData/README.md`).

## Tests and thresholds

Thresholds are constants next to the tests, written before the first measurement.

| Test group | What it shows | Threshold |
|---|---|---|
| `Frame.*` | Known directions and points land at hand-written Unreal coordinates; the Moon centre is straight below the origin | 1e-12 (unit vectors), 1e-5 cm |
| `Package.LoadSample`, `RefusesBadPackages` | Reader follows the contract; another major version, a truncated array, the wrong package kind and a missing manifest are refused | exact |
| `Package.FrameAgreesWithCore` | `site.enu` and `site.position_km` equal the frame derived here from latitude and longitude | see test |
| `Package.BodyFrameAgreesWithSeries` | Direction-table positions mapped through the body-fixed frame give the series directions | 0.0002 deg |
| `Package.ObstaclePointsReproduceHorizon` | Obstacle points (arc distance, obstacle height) placed through the site frame give `horizon.elevation_deg`; these fields are independent of the elevation | 0.05 deg |
| `Mesh.*` | Winding matches the engine, sphere stays out of sight, craters only lower, silhouette measurement is exact on known shapes | see tests |
| `Acceptance.SunAndEarthFromPackage`, `SunFollowsThePackage` | Light direction, light source angle, disc positions and disc sizes of the spawned scene equal the package at every sample | 0.001 deg |
| `Acceptance.HorizonSilhouette` | Silhouette of the scene's terrain and sphere components, seen from the observer, equals `horizon.elevation_deg` for every height and azimuth | 0.001 deg |
| `Acceptance.HorizonExportForPython` + `compare_horizon.py` | The same comparison with the package read by Python | 0.001 deg |

Limits: all of this has run against the synthetic contract sample only. The silhouette test
compares mesh geometry, not rendered pixels; the rendered view is checked by eye with the
horizon line overlay. The terrain horizon is by construction the package horizon, so it
proves the frame, reader and mesh chain, not the science behind the package.
