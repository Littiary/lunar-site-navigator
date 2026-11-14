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
| Ground, real packages | LOLA heights sampled once per site through the data stream's reader on 480 rings per azimuth from 1 m to 300 km (`Scripts/export_terrain.py`), as 64-bit heights (a 32-bit height of several kilometres is known to half a millimetre only, which is 0.006 deg at the 5 m where the horizon search of a near-field package starts). A cache for drawing: no number on screen comes from it. `--near-field auto` (the default) reads the reader's 5 m site model (`open_terrain(near_field=True)`) only when the package's own `horizon.terrain_source` names a product of 5 m or finer, so the drawn ground and the package horizon always rest on the same data; the published 0.9 packages name the 20 m product and are drawn from it. `-LsnTerrainRoot=<folder>` shows a cache from another folder, for comparison only (`docs/unreal/near_ground/wide_5m_data_preview.png` against `wide_20m_data.png`) |
| Ground, synthetic packages or without a terrain export | a placeholder surface with procedural craters; the read-out says so |
| Sun light direction and source angle, Sun and Earth discs | package: `timeline.series` at the selected time |
| Countdowns "sets in" / "rises in" | package: interval boundaries of the windows `sun_visible`, `earth_visible`. "at least" means the package has no such event in its computed range |
| Time strips (yellow Sun, blue Earth) | package: the same windows |
| Obstacle view: highlighted ridge, "hidden by terrain ... away", "this ridge costs N h" | package (contract 0.2, SPEC 5.5): `series.<BODY>.blocker_azimuth_index` at the sample, `horizon.obstacle_id` there, the run of `horizon.obstacles[k]`, `lost_s` of the matching `timeline.blockers` record. Hidden for packages without these fields |
| Dashed outline "Sun (behind terrain)" | package: direction and angular radius of the series, drawn over the terrain while the body is hidden |
| Panorama (top right): horizon all round, Sun and Earth marks, the highlighted obstacle | package: `horizon.elevation_deg`, the series at the selected time, the obstacle run |
| Summary numbers under the panorama | package: metrics `sun_visible_fraction_of_time`, `sun_longest_outage_s`, `earth_visible_fraction_of_time`, `earth_longest_outage_s`, with units converted; `sun_lost_to_terrain_s` and `sun_gained_from_terrain_s` as one sentence, "Terrain here costs N h of Sun and gives M h that a smooth sphere would not have" |
| "About N % of the ground within 20 m is drawn in shadow ..." | none (a statement about the drawing): where the elevation samples near the site rise towards the package's Sun direction by more than the Sun's height, the ground lies in its own shadow. Shown while the package gives the Sun as visible, so that the dark ground is not read as a contradiction: the package's horizon search starts 20 m out and its result is for the observer at the site |
| "Sun 121 deg to the right" at the lower right | package: direction of the body at the selected time, when it is outside the view |
| Calendar page | package (since 0.3, SPEC 5.6): `timeline.calendar`, `request.timeline.requirements`, `timeline.opportunities`. "Landing now meets the requirement; it can slip by ..." is the distance from the selected time to the end of the landing window it lies in; for the scenario's planned landing the package's own slip report is printed. The requirement is named and marked as an example chosen by the team |
| Pale edges of the time strips, "for a stated horizon error of ..." under a countdown | package (since 0.4, SPEC 5.7): windows `<body>_visible_certain` / `_possible`, `earliest_et_s` / `latest_et_s` of the event |
| Uncertainty page: ellipse map and its hours | package: `timeline.uncertainty.landing_ellipse` (points, statistics), `series.SUN.ellipse_visible_share` |
| Mast-height trade, site pairs | package (since 0.5, SPEC 5.8, 6a): `timeline.height_trade`; the `site_pairs` package of the root, shown only if it was computed from the very site package on screen |
| Reference sphere | package: `reference_radius_m`; sunk near the site so that it stays out of sight |
| Surface shading | none (a display model): the engine's cosine law times a regolith factor 2 / (mu0 + mu), limited to 4, which together give the Lommel-Seeliger law used as a first description of dark, dusty surfaces. The Sun's direction in it is the package's. No image texture |
| Roughness and small craters finer than the elevation data | none: **illustrative**. A procedural height field computed in the surface shader (weak roughness on three scales, each on its own turned grid; craters in three sizes of about 0.3 to 30 m, at most one cell in ten holding one and most of them small; a few per cent of grey variation) tilts the shading normal only. Strengths: `lsn.Look.CraterStrength`, `lsn.Look.NoiseStrength`. Vertex positions are untouched, so the outline of the terrain, its shadows and the horizon are those of the data, and the horizon test does not see it. It fades out with distance (45 m to 1.1 km). Stated on screen in the details; `-LsnNoDetail` switches it off |
| Star field | Yale Bright Star Catalogue (8404 stars to magnitude 6.5, `Content/LsnSky/stars.f4`), turned for the date by the orientation of the Moon that `Scripts/export_sky.py` takes from the SPICE kernels of the ephemeris stream (a cache tied to the package id, like the terrain samples). Decoration: no number comes from it. Checked on real data: SPICE's Sun direction turned by the same matrices equals the package's Sun series within 0.001 deg. Dimmed to a tenth while the package gives the Sun as wholly visible; brightness is a compressed scale, not photometry. `-LsnNoStars` |
| Lander, mast, boulders | none: scale objects of the team's own design, built in Blender by `Scripts/blender/make_scale_objects.py` (generic four-legged lander 3.85 m high, a mast whose head stands at the observer height of the package, boulders of 0.4 to 1.7 m). Since the pass of 14 November 2026 the lander has bevelled edges, smooth normals, dished footpads, a bell nozzle, tanks, a dish with its feed, panels of cells in a frame and small thrusters (22 424 triangles); the mast head is a camera on a yoke; there are four boulders. The models stay OBJ files read by the scene's own loader (`Mesh/LsnProps`), with the normals as Blender wrote them; no FBX and no static-mesh asset was made, so the size tests of the models still read the very files that are drawn. Their sides that face away from the Sun are lit by the sunlit ground, by the form factor of a lit plane (`UpdateLook` in `Scene/LsnSiteScene.cpp`, `lsn.Look.BounceScale`): the engine's Lumen was tried and does not see the terrain, which is a procedural mesh without a surface cache. They belong to no package, are separate from the terrain mesh and take no part in the horizon test. The lander stands 38 m from the site; it can stand between the observer and a low Sun, which no package number knows about. Button **Scale objects**, key `P`, `-LsnNoScaleObjects`. The mast is where the observer is, so it is drawn only for a camera that is not the observer (`-LsnCameraUp= -LsnCameraBack=`) |
| Camera positions (button **Camera**, key `V`, `-LsnView=hero` or `wide`) | none: choices of where the camera stands, composed about the package's Sun azimuth. The observer's own view; a camera 16 m behind the lander and 5.5 m up, looking towards the Sun; a wide view from 120 m away and 30 m up with the Sun 60 deg to the right, outside the picture, so that every shadow lies across it. The header, the chips and the countdowns stay those of the observer, and the screen says that the camera is not the observer. Values: `lsn.Cam.*` |
| Arrival view (button, key `A`, `-LsnDo=arrival`) | none: a camera move of 8 s from 9 km above and 26 km behind the site down to the camera position in use. Labelled on screen as a camera move; no descent, trajectory or engine is simulated |
| First lunar day (button, key `D`, `-LsnDo=first_day`) | package: the time jumps to the planned landing of `timeline.opportunities` and the timeline plays one calendar period in 25 s, with the countdowns of the package running. Nothing is computed; it is the playback of the package at a chosen speed |
| Exposure, contrast, glare | none: display choices, fixed (no automatic exposure), set for sunlit ground: `lsn.Look.ExposureBias`, `FilmSlope`, `FilmToe`, `SunLux`, `BloomIntensity`, `BloomThreshold`, `ObjectAmbient` (console variables, so that they can be tried while the scene runs or with `-dpcvars=`) |
| Line under a countdown: "measured pixel +/- 5.0 m: 8 d 15 h to 8 d 18 h" | package (since 0.10, SPEC 5.7): `terrain_quality` of the event that ends the countdown (`limiting_pixel` constrained = measured, interpolated, unknown; `height_error_m`) and the event's `earliest_et_s` / `latest_et_s`. Shown only where the event carries the field: in the published 0.11 set the three project sites do, the 17 curated sites do not, and there the line is absent |
| Custom coordinates, two steps | the science core, run as a separate program: step 1 `python -m lsncore site` (terrain horizon, a few seconds), step 2 `python -m lsncore custom --lat --lon --start <today, UTC> --name --out` (complete package of 30 days). The screen shows the core's own `progress k/n` lines, then which terrain product and class served the site. The engine computes nothing. Needs the Python environment, the elevation data and the SPICE kernels of the core on the machine (`LSN_PYTHON`, `LSN_KERNEL_DIR`, docs/setup.md); the core's own last line is shown if one is missing. Another command can be set with `-LsnCustomTimeline=` or `CustomTimelineCommand` in `Config/DefaultGame.ini` |
| Sites whose elevation data is not installed on the machine that made the terrain caches | the ground is a sheet up to the package horizon (no relief of its own, it throws no shadows); the Sun, the Earth and every number are those of the package as everywhere. The camera positions away from the observer and the arrival view are refused there with a line that says why. `Scripts/export_terrain.py` names the missing product for each such site |
| Brightness under a high Sun | none: the display intensity of the Sun falls to `lsn.Look.HighSunExposure` (0.35) between 5 and 45 deg of the package's Sun elevation, as a camera stops down; without it equatorial sites at noon are white |
| Glare of the Sun | none: the engine's bloom, limited to what is several times brighter than sunlit ground |
| Earth's disc | package: direction and angular size; a sphere lit by the scene's Sun, so its phase follows from the two package directions. Its map is NASA's Blue Marble (December 2004 composite, so its snow is that month's, not the date's; no clouds, no night lights, no atmosphere), turned by the `earth_view` of the direction table (since 0.8, SPEC 6.1: sub-lunar latitude and longitude and the position angle of the pole), with the geometry the contract writes down. Checked on the published table: the centre of the disc has the table's latitude and longitude within 1e-4 deg. A table without `earth_view` gives the plain sphere as before (`-LsnNoEarthMap`) |
| Shadows | the engine's virtual shadow maps from the terrain mesh, with the Sun's angular diameter (package) as the light's source angle: hard shadows with the penumbra of the solar disc |
| Fill light from the zenith, no shadows | none: a display aid so that the terrain stays readable while the Sun is down. It is on only while the package gives the Sun as wholly hidden at the selected sample; with the Sun up, shadows are black. Button **Night fill light**, key `L`, `-LsnNoFillLight` |

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
Scripts\test_build.ps1 -Build <folder>\Windows  # run the stand-alone program: every site, and two side by side
Scripts\bench.ps1 -Build <folder>\Windows       # frame time of the stand-alone program
Scripts\after_packages.ps1                      # all of the above in order, after new packages are on main
```

`after_packages.ps1` is the one command for the day the packages are regenerated: it merges
`origin/main`, samples the terrain for the new package ids, builds, runs the tests, makes
the pitch clip and stills, builds the stand-alone program, runs it and measures it. It
stops at the first failure and commits nothing. `pitch.ps1 -PackageRoot <root> -Out <folder
outside the repository>` rehearses the same views on other packages; such output is marked
as a rehearsal and is not for the repository.

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

**Interface pass of 14 November 2026.** One design system (`Scene/LsnUi.h`): the engine's Roboto
family (shipped with Unreal, no font was added) in four sizes at a window height of 1080 px
(40 site name and countdown, 24 chip state and panel titles, 18 text, 14 footnotes, group
labels and badges), scaled with the height of the window; Roboto's figures are tabular; the
units of a duration are one size smaller than its digits. Panels are dark at 75 % opacity with
the picture blurred behind them, a 1 px hairline and 8 px corners, on an 8 px grid inside a
48 px safe margin. Colour carries state only (amber Sun, blue Earth, green requirement met,
red not met). One quiet button style with hover, pressed, on and not-available states; the one
accent button is **Compute and show**. Fades and slides take 150 to 200 ms.

How it is built: the HUD of each view still decides what is on screen and reads every text
from the package; instead of drawing on the canvas it adds boxes, text and lines to a list
of the frame, and one Slate widget over the game view paints that list (rounded boxes,
`SBackgroundBlur` behind panels, Slate fonts). This keeps the layout in C++ where it is tested
(`Planner.ButtonsOnScreen`, `Planner.SitePicker` at 1280 x 720, 1920 x 1080 and 2560 x 1440);
no widget asset was made in the editor. Not done in this pass: a keyboard-focus ring, since
the keys are shortcuts and there is no focus that moves from button to button.

The sections below describe the pages; where they speak of a sheet over the view, the page is
now a tab of the drawer, and where they speak of three main buttons and a bar of grouped
buttons, read the control bar and the tab **Controls** (see `KEYS.md`).

One site fills the screen; with a second site the screen is split left and right. Both
halves show the same instant (matched by the TDB time of the packages), the same observer
height, zoom and elevation of the view. By default each half keeps its view on its own
Sun's azimuth, so that the same instant can be compared although the Sun stands in
another direction at each site; `F` switches to a common azimuth. If the instant lies
outside the time range of the right package, that half says so and keeps its nearest
sample.

The screen is laid out as a product screen with one type scale (site name, large; times and
countdowns, large; text; captions):

- **Header**: site name, selected time, and three chips: Sun, Earth (state and time to the
  next set or rise from the package windows, with the range for the stated horizon error)
  and whether a landing now meets the example requirement. A chip is filled in its colour
  while the state is good and dark with a coloured edge while it is not.
- **Three main actions**, the largest buttons on screen: compare two sites, jump to the next
  sunset (the package's next `set` event of the Sun), show what blocks the Sun.
- **What blocks the Sun or the Earth now**, under the main actions: distance, azimuth and
  cost of the obstacle as the package gives them.
- **Bar along the bottom** in labelled groups: time, observer, site, plan, view, info.
- **Site picker** (button **Sites ...**, key `S`): the sites of the package root in groups,
  each with the resolution class of its terrain where the package states it (contract
  0.9). Click a name to show the site; **Left** and **Right** pin any two for the
  comparison. Groups come from the optional index field `programme`; without it there is
  one group. The layout holds 20 sites in 7 groups at 1280 x 720 (tested).
- **Custom coordinates**, at the foot of the picker: type a latitude and an east longitude
  and press **Compute and show**. The view hands the two numbers, as typed, to the science
  core in two steps and computes nothing itself. Step 1 is `python -m lsncore site --lat
  ... --lon ... --name ... --out Saved/LsnCustom`: the terrain horizon, about three
  seconds; its package is shown at once, with the terrain product, resolution class and
  pixel size it states. Step 2 is the core's command for a complete package with a
  timeline (about half a minute); while it runs the view shows the seconds and a bar
  (time run over the time the core states, never full before it ends), then the package
  with Sun, Earth and countdowns takes the place of the first. If step 2 fails, the view
  says why and the horizon stays. The command of step 2 is given as a template with
  `{lat}`, `{lon}`, `{name}`, `{out}` (`-LsnCustomTimeline=` or `CustomTimelineCommand` in
  `[LunarSiteNavigator]` of DefaultGame.ini); until the core stream has published it there
  is none, and the view says that only the horizon is shown. Run from a checkout, the
  core and data reader of this repository are used (PYTHONPATH). The Python environment is looked for in `-LsnPython=`, `LSN_PYTHON`, `.venv`
  next to the repository and `C:/Projects/lsn-venv`; if none is there, the view says that
  custom coordinates cannot be computed on this machine.
- **Resolution class** of the terrain behind the result (`horizon.terrain_source`, since
  0.9): "terrain: fine, 20 m pixels" next to the site name; nothing for older packages.
- **Details** on demand (button, key `I`): package id, frame, contract version, the raw
  values of the sample and the validation status of every method behind a number on screen.
- **Planner pages** (calendar, uncertainty, mast and pairs) open as a sheet over the view.
- Side by side, each half has its own header and chips; the right half's **Next site >** is
  in its own header; the bar spans the window.

The pointer is visible: click a button, drag on a time strip to choose the time, hold the
right mouse button to look round, turn the wheel to zoom. Every button and its key carry
out the same named action (`ALsnObserverPawn::DoAction`). `KEYS.md` is the one-page list
for a first-time user (copied into the stand-alone program as `KEYS.txt`); it also names
what is on keys only.

| Keys | |
|---|---|
| `1` .. `9` | show that site of the package root (`Shift`: in the right half, side by side) |
| `C` | comparison of two sites on and off |
| `K` | calendar page: lunar-day calendar on one time axis for the site (side by side: for both sites), landing windows of the chosen requirement, slip of a landing at the selected time and of the scenario's planned landing |
| `U` | uncertainty page: the stated horizon error and the survey of the stated landing ellipse (small map of its sample points) |
| `M` | mast-height trade and site pairs |
| `R` | next requirement of the package |
| right mouse button held, arrow keys | look (while following the Sun: turn away from it) |
| mouse wheel | zoom |
| `Q` / `E` | one sample back / forward (`Shift`: 24 samples) |
| `,` / `.` | one day back / forward |
| `B` / `N` | previous / next rise or set of the Sun in the package (`Shift`: of the Earth) |
| `Home` / `End` | first / last sample |
| `Space`, `[`, `]` | play and pause, halve and double the playing speed |
| `Tab` | hide the pointer and look with the mouse alone |
| `G` | lower drawing quality |
| `I` | details panel |
| `P` | scale objects |
| `F1` | list of keys on screen |
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
`-LsnCameraUp=<m> -LsnCameraBack=<m>`, `-LsnNoHud`, `-LsnLowQuality`,
`-LsnDo=<action>,<action>` (named actions carried out at the start),
`-LsnBench=<txt> -LsnBenchSeconds=<s>` (measure the frame time, write it and quit),
`-LsnClickLog=<txt>` (write down every click and what it did), `-LsnPage=sites`,
`-LsnCustom=<lat>,<lon>` (as if typed into the picker and computed), `-LsnPython=<python.exe>`,
`-LsnShotFrames=<n>` (frames to wait before `-LsnShot`), `-LsnViewingAidFill` (fill light on
for an overview still, with a caption that says so).

### Frame time

Measured by the stand-alone program itself (`Scripts\bench.ps1`): 1920 x 1080 window, no
vertical sync, timeline playing so that the shadows move in every frame, 20 s after a
6 s warm-up, on an NVIDIA GeForce RTX 5090 (2026-11-14, real packages of contract 0.1):

| View | Quality | Mean | 99 % of frames under | GPU memory in use |
|---|---|---|---|---|
| one site | normal | 1.8 ms | 2.1 ms | 1.5 GB |
| one site | low | 1.5 ms | 1.9 ms | 1.3 GB |
| two sites side by side | normal | 2.8 ms | 3.9 ms | 1.6 GB |
| two sites side by side | low | 2.3 ms | 3.3 ms | 1.5 GB |

Low quality (`G`, button, or `-LsnLowQuality`) draws the scene at two thirds of the
resolution and the shadows with coarser pages and fewer rays; it changes how finely the
picture is drawn, not what is shown. On this machine it saves about a fifth of the frame time.

Not measured: any other graphics card. An estimate for a laptop card with 8 GB of memory,
by scaling only: such cards are roughly five to eight times slower than this one at this
resolution, which would put two sites side by side at 14 to 22 ms per frame (45 to 70
frames per second) at normal quality and one site at 9 to 15 ms. Memory is not the limit
(1.6 GB of 8). The estimate is weakest for the shadows: the virtual shadow maps reach to the
far terrain, and their cost may grow faster on a slower card than the factor assumes. Run
`bench.ps1` on the backup laptop before the demo; if side by side is slow there, start with
`-LsnLowQuality`, and if it still is, show one site at a time.

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
| `Acceptance.SecondSceneAwayFromOrigin` | A scene 20 000 km from the world origin is the same scene: eye, Sun disc, light and silhouette as the package says; the two scenes are lit on separate lighting channels | 0.001 deg; 1e-6 cm |
| `Planner.ButtonsOnScreen` | At four window sizes (1280 x 720 to 3840 x 2160), one view and side by side: every button in the window, at least 22 x 60 px, no overlap with another button or a time strip, strips between header and bar, every bar button in a labelled group, the three main actions at least twice as large as any other button, no button across the middle of a side-by-side window, the right view's control in the right half | exact |
| `Planner.SitePicker` | 20 sites in 7 groups at 1280 x 720 and 1920 x 1080, one view and side by side: one header per group in list order, one row per site with show, pin-left and pin-right boxes, rows at least 18 px high, nothing across the middle of a side-by-side window, custom-coordinate boxes clear of the rows | exact |
| `Planner.CustomCoordinatesGoToTheCore` | Latitude and longitude accepted only as plain numbers in range; the command is the core's own `python -m lsncore site` with the numbers as typed | exact |
| `Package.TerrainSourceOfThePackage` | Resolution class and pixel of `horizon.terrain_source` unchanged; nothing shown for a package without it | exact |
| `Terrain.NearGroundFacingAwayFromTheSun` | Share of near ground that rises towards the Sun more steeply than the Sun stands high, on hand-made planes | 1e-9 |
| `Planner.ButtonsDoWhatKeysDo` | Named actions step by one sample and one day exactly, stop at the ends, go round the observer heights, switch play, the obstacle view and the details; "next sunset" lands on the package's next `set` event of the Sun; an unknown name is refused | exact; 1e-6 s |
| `Props.ModelsHaveTheirSizes`, `Props.TerrainUntouched` | The scale objects load, stand on the ground, have the sizes they claim, the mast reaches the observer height; showing or hiding them leaves the terrain mesh unchanged | 0.15 m; 0.01 m; exact |
| `Sky.EarthTurnedAsTheTableSays` | The Earth's axes from the three angles of the table as SPEC 6.1 writes them: hand-made cases, the longitude taken the short way round between records, and on the published table the centre of the disc at the table's latitude and longitude | 1e-12; 1e-9 deg; 1e-4 deg |
| `Sky.StarsWhereTheyStand` | Hand-made orientation maps J2000 axes to east, north, up and interpolates by the shortest turn; Sirius is the brightest star at its catalogue position; on the published packages SPICE's Sun direction turned by the exported orientation equals the package's Sun series | 1e-9; 1e-6 deg; 0.01 deg |
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
  split between obstacles to the step of the series. At a site on a crest the terrain
  mostly lies below the smooth horizon and gives time instead, so such a package can have
  few blockers or none.
- An obstacle within 1 km is marked "depends on single pixels of the elevation model", as
  the contract asks.
- The obstacle view uses the values of the sample the time position belongs to; it does
  not interpolate which obstacle is the limiting one.
- A page whose fields the package lacks says so in one line and shows nothing else. The
  published packages decide what can be shown: `Real.PlanningFieldsOnlyWhenPublished`
  prints, per site, which fields they carry.
- The layout of the buttons and what each named action does are covered by tests
  (`Planner.ButtonsOnScreen`, `Planner.ButtonsDoWhatKeysDo`), and the actions were run in
  the stand-alone program through `-LsnDo`. That a click of the real mouse reaches a button
  has not been checked: the session that built this cannot move the pointer of the desktop.
  `Scripts\click_test.ps1`, run from an ordinary terminal, does it with real clicks and
  prints what the program received. Keys and split screen were checked on real captures.
- Side by side, the bar and the main buttons act on both halves; the right half has one
  control of its own (its next site).
- Dark ground near the site at a very low Sun (de Gerlache, Sun 2.5 deg high), measured on
  2026-11-14. Two things were mixed. The wedges that fanned out from the observer were a
  drawing fault: the mesh had no elevation sample between the site and its first ring at
  5 m, so the first five metres were a cone to the site point. The rings now start at 1 m
  and the wedges are gone. What remains is real for the elevation data: the site stands
  on a crest, the ground falls away by up to 8 deg, and where it rises towards the Sun by
  more than the Sun's height it lies in its own shadow (38 % of the ground within 20 m at
  that instant; the same appears with unsmoothed normals, and the share is the same when
  counted from the data alone). The view says so on screen at such a site and instant.
- The site picker groups by the index field `programme`, which the contract does not
  define yet: it is a request to the core stream; until it exists there is one group.
- That a click of the real mouse or typed keys reach the picker and the coordinate fields
  has not been checked by hand; the entry was run through `-LsnCustom=<lat>,<lon>`.
- The dark horizontal stripes that the side-by-side view showed were a different thing and
  are gone: the two scenes stood 20 000 km apart in one world, which broke the shadows of
  both (measured: not in the single view, not with shadows off, pattern changed with the
  distance). Both scenes now stand at the same place, kept apart by the views and the
  lighting channels.
- `-LsnCameraUp=<m> -LsnCameraBack=<m>` lifts the camera above the observer for overview
  stills; the read-out then says that this is not the observer's view, and the markers
  that only make sense from the site are not drawn. `-LsnNoHud` leaves a caption line
  (site, time, package) and, for a synthetic package, the synthetic marker.
- Normals near the site are not those of the raw mesh. Measured with
  `Scripts/measure_banding.py`: every LOLA height around the three sites is a multiple of
  0.5 m, so the slope between 20 m pixels moves in steps of 1.43 deg; under a Sun 0.5 to
  1.6 deg high that changes the grazing illumination along one line by a factor of 15 to
  105 and drew bands on the near ground. The bands stayed with shadows switched off
  (`-LsnNoShadows`), so they were shading, not shadow error. The normals within 3 km are
  now taken from heights averaged over 40 m; the positions of the mesh are bit for bit the
  same (`Terrain.SmoothedNormalsForDrawing`), so the silhouette and the test that no
  terrain sample rises above the package horizon are untouched. Relief smaller than about
  80 m no longer shows in the shading near the site. `-LsnRawNormals` shows the raw ones.
- Display values (light intensity, fixed exposure, albedo 0.13, fill light, the limit of
  the regolith factor) are not photometry. The exposure is fixed for a Sun a few degrees
  above the horizon; nothing adapts to the scene.
