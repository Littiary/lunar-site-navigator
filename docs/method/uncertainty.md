# Uncertainty band and landing-ellipse survey

Code: `core/lsncore/uncertainty.py`, wiring in `core/lsncore/pipeline.py`. Tests:
`core/tests/test_uncertainty.py`, `core/tests/test_contract_v04.py`. Package fields:
contract 0.4 and 0.6, [`docs/contract/SPEC.md`](../contract/SPEC.md) section 5.7. Brute-force
recomputation of two results: `core/tests/test_brute_force_lola.py`.

Status on 14 November 2026: the mechanics are checked against closed forms and a
brute-force scan. **The stated horizon error and the stated ellipse are inputs; neither
has been derived from the accuracy of the elevation model or of a lander.** The outputs
for real sites below are therefore "what if" numbers, not error bars of the tool.

## 1. What is asked, and what is assumed

**Stated horizon error.** *If the terrain horizon were higher or lower than computed by a
given angle, when would the body be visible?*

- Assumption, common shift (`horizon_error_deg`): the whole profile moves by the stated
  angle, the same at every azimuth and for every observer height.
- Assumption, terrain height error (`dem_height_error_m`, since contract 0.6): the
  terrain point that sets the horizon in an azimuth may be higher or lower than the
  elevation model says by the stated height. Seen from the site that is
  `atan(height error / distance)`: 0.57 deg for 1 m at 100 m, 0.057 deg at 1 km, 0.006 deg
  at 10 km. Near terrain gets a wide band, far terrain a narrow one; the same sign is
  assumed at every azimuth. This is the assumption that fits near-field obstacles.
  If both are stated they are added.
- Result: three window sets per body and observer height. `certain` holds even with the
  horizon that much higher; `possible` needs it that much lower; `uncertain` is the
  difference. Raising a horizon can only hide and lowering it can only reveal, so
  certain lies inside the nominal window and the nominal window inside possible. Every
  rise and set gets the interval of the band that contains it as its earliest and latest
  time.
- To first order an event moves by the stated angle divided by the rate at which the body
  climbs relative to the horizon. Near the poles that rate is small, and where the body
  runs along the horizon it goes to zero: the band then covers many hours, and events can
  appear or vanish inside it.

**Stated landing ellipse.** *If the lander came down somewhere else inside a given ellipse,
what would the windows be?*

- Assumption: any point of the ellipse is possible. Sample points fill it evenly in area
  (a sunflower pattern, the centre first; the same request always gives the same
  points). No landing-dispersion distribution is assumed.
- Each point gets its own terrain horizon (same settings as the site) and its own local
  vertical: moving 1 km on the Moon tilts the vertical by 0.033 deg, which matters at
  grazing incidence.
- Result: the windows that hold at every point and at one point at least; for every
  sample of the series the share of points at which the body is visible; the visible time
  at the centre and its least, median and largest value over the points. Default observer
  height only.

The two are separate. They are not combined, and neither includes ephemeris error,
elevation-model error that varies along the horizon, or the observer height.

## 2. Checks

Thresholds were fixed in the test file before the code was written.

| Case | Threshold | Measured |
|---|---|---|
| Band of a body rising at a constant rate over a flat horizon, against `delta / rate` (one hour) | 2 s | 0.23 s |
| Horizon error from a terrain height error against `atan(error / distance)`; band with an error that depends on azimuth | 1e-12 deg; 2 s | passes |
| Nesting certain, nominal, possible; band equals possible minus certain; zero error gives an empty band | exact | passes |
| Sample points of an ellipse against the ellipse on the sphere, three sites incl. 11 km from the pole on the 180 degree meridian | 0.5 m | passes |
| ... even in area: share of points inside the half-size ellipse | 0.25 +- 0.02 | passes |
| Windows at nine displaced points for a body circling the pole over a smooth sphere, against a scan in 1 s steps with each point's own vertical | 2 s | passes |
| Summary over points (all, any, share, least, median, most) | 1e-6 s | exact |

## 3. First outputs on LOLA terrain

Three site records of the data stream, terrain `LDEM_80S_20M` and `LDEM_60S_60M` version
2.0, 14 November to 14 December 2026 (720 h), observer 2 m. Stated for the run: horizon
error 0.05 deg; a circle of 100 m radius with 13 sample points. Both numbers were chosen
to exercise the tool. Three sites took 67 s.

**Horizon error 0.05 deg**

| Site record | Sun visible | Certain | Possible | Band | Range of a Sun event time | Earth band | Range of an Earth event time |
|---|---|---|---|---|---|---|---|
| Shackleton crater rim crest | 667.7 h | 666.7 h | 668.8 h | 2.1 h | 1.1 to 1.5 h | 3.2 h | 1.6 to 1.7 h |
| de Gerlache crater rim crest | 720.0 h | 720.0 h | 720.0 h | 0 | no event | 4.5 h | about 1.5 h |
| Mons Malapert summit | 701.2 h | 687.2 h | 713.2 h | 25.9 h | median 6.3 h, up to 15.1 h | 6.0 h | about 3.0 h |

An event time that is known to a fraction of a second for the computed horizon is known
to one to fifteen hours once 0.05 deg of horizon error is allowed.

**Terrain height error, Sun, observer 2 m** (band = possible minus certain)

| Site record | Horizon set within 1 km (share of azimuths) | 0.5 m | 1 m | 2 m | For comparison: common shift 0.05 deg |
|---|---|---|---|---|---|
| Shackleton crater rim crest | 22 % | 2.0 h | 4.7 h | 18.0 h | 2.1 h |
| de Gerlache crater rim crest | 15 % | 0 | 0 | 0 | 0 |
| Mons Malapert summit | 70 % | 88.5 h | 106.3 h | 154.6 h | 25.9 h |

With 1 m the horizon error per azimuth runs from 0.0003 deg to 0.75 deg at the
Shackleton record (median 0.002 deg) and has a median of 0.18 deg at the Malapert record,
where most of the horizon is near terrain. The heights 0.5, 1 and 2 m were chosen to
show the dependence; the accuracy of the LOLA products was not looked up for this note.

**Circle of 100 m radius, 13 points**

| Site record | Sun visible at the site | Least, median, most over the points | Earth visible at the site | Least, median, most |
|---|---|---|---|---|
| Shackleton crater rim crest | 667.7 h | 423.8, 557.8, 667.7 h | 322.6 h | 306.0, 322.6, 322.7 h |
| de Gerlache crater rim crest | 720.0 h | 0.0, 531.2, 720.0 h | 352.5 h | 0.0, 304.8, 352.5 h |
| Mons Malapert summit | 701.2 h | 476.5, 540.1, 720.0 h | 592.6 h | 494.2, 579.1, 592.6 h |

The site records are the highest DEM points of their neighbourhood, so nearly every
other point is worse: the centre is the best case by construction, not a typical one.
The spread at the de Gerlache record (0 to 720 h within 100 m) was examined separately.

## 4. The two extreme points at the de Gerlache record

The survey found the site record with the Sun for all 720 h and, 82 m away, a point with
none. Before anyone shows that, three things were done (14 November 2026).

**Recomputed by brute force.** Rays every 0.25 deg walked on the finest data in 0.1 m
steps near the observer (0.5 m, 5 m and 20 m farther out), with the classic great-circle
formulas and the unrearranged triangle formula; no stored profile, no core code.

| Point | Horizon, core minus brute force, 1440 azimuths | Sun visible, brute force (hourly samples) | Sun visible, core |
|---|---|---|---|
| Site record | -0.0003 to +0.0042 deg | 721 of 721 | 720.0 h |
| Point without Sun | 0 to +0.0122 deg | 0 of 721 | 0.0 h |

Tolerances (fixed before the run): the core not more than 0.002 deg below and 0.02 deg
above the brute force; visible time within 2 h. Starting the brute force 1 m from the
observer instead of one pixel changes nothing: no azimuth is limited by terrain closer
than 20 m. So the result is not produced by the search, the observer placement, the
handling of the local vertical or the edge of a raster.

**The geometry.**

| | Site record | Point without Sun |
|---|---|---|
| Terrain height above the reference sphere | 1815.2 m | 1799.1 m (16.1 m lower) |
| Slope over +-20 m | 3.9 deg, falling towards azimuth 331 | 6.2 deg, falling towards azimuth 258 |
| Horizon at 2 m | -3.7 to -0.2 deg | +4.4 to +13.6 deg in every azimuth |
| Distance of the terrain that sets the horizon | beyond 10 km in 78 % of the azimuths (median 78 km), within 1 km in 15 % | 30 to 82 m in every azimuth |

Around the point without Sun the terrain is higher in every direction: 4.3 to 10.4 m
higher on a ring of 40 m, 6.3 to 12.8 m on a ring of 60 m, and only at 150 m does part
of the ring fall below it. It sits at the bottom of a hollow about 100 m across. By
45 degree sector the lowest horizon is 4.4 deg (azimuth 225 to 270, terrain 50 m away)
and the highest 13.6 deg (azimuth 45 to 90, 30 m away). In the period the Sun's centre
stays between 0.07 and 2.81 deg of elevation as seen from there (angular radius 0.27
deg) and passes through every azimuth; its upper limb never comes closer to the horizon
than 3.2 deg.

**Sensitivity** (Sun-visible hours of 720, core horizon and event finder):

| Observer | The point | Moved 20 m, eight directions | Moved 40 m, eight directions |
|---|---|---|---|
| 2 m | 0 | 0 to 162 (five of eight stay at 0 to 2) | 150 to 612 |
| 5 m | 12 | 93 to 561 | 463 to 713 |
| 10 m | 526 | 526 to 718 | 685 to 720 |
| 20 m | 720 | 720 | 720 |

**Conclusion.** The computation is right for the surface it is given, and the answer
flips with a move of one to two pixels or with a few metres of observer height. The
result is therefore a statement about a hollow five pixels wide and a few metres deep
in the 20 m elevation model, not about the de Gerlache rim. Whether that hollow exists
on the Moon (a small crater would look like this) or comes from the way the model was
gridded cannot be decided from the model itself. What can be said: on this model, at a
2 m observer height, the lighting within 100 m of the record ranges from none to
continuous, and at 20 m every point examined has the Sun throughout.

## 5. Limits

1. **The stated numbers are inputs.** 0.05 deg, 1 m and 100 m are not properties of the
   LOLA products or of any lander. A defensible band needs the height and position
   accuracy of the elevation model from its documentation; with it, the terrain-height
   option gives each azimuth the error that fits the distance of its limiting terrain.
2. **What a 20 m pixel bounds.** The surface is linear between posts 20 m apart.
   Relief narrower than about two pixels is not in it at all, and no band covers what
   the model does not contain. Features two to five pixels wide are in it but rest on a
   handful of values (section 4). At a 2 m observer height the three site records move
   by up to 82 h, 169 h and 123 h of Sun (of 720) when shifted by one pixel; at 10 m by
   at most 7 h, 0 h and 0 h. So for a lander-height observer on a crest, a result is a
   property of the site only to the extent that it survives a shift of one or two
   pixels and the stated height error; the ellipse survey and the terrain-height band
   are the two checks for that, and results that fail them should be reported as
   resolution-limited.
3. **One sign for the whole profile.** Real errors differ from azimuth to azimuth. One
   sign everywhere is the unfavourable case for a single event and says little about how
   errors along the profile combine. The lowered profile also ignores the terrain behind
   the limiting point: if the limiting point were lower, the next ridge would set the
   horizon, so `possible` is an outer bound and the band is on the wide side.
4. **A survey, not a probability.** With 13 points, a part of the ellipse that covers less
   than a tenth of its area can be missed entirely. No statement like "visible with 90 %
   probability" follows from the share of points.
5. **Near terrain decides.** Where the horizon of a point is set by terrain tens of metres
   away, its windows rest on single 20 m pixels and on the 2 m observer height. The
   spread over an ellipse on a crest is mostly that.
6. **Cost.** Every sample point needs its own horizon (about 1 to 2 s) and its own event
   search; 24 months with 25 points take minutes per site.
7. Everything in [horizon.md](horizon.md), section 8, applies.
