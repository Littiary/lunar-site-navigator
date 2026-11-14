# Uncertainty band and landing-ellipse survey

Code: `core/lsncore/uncertainty.py`, wiring in `core/lsncore/pipeline.py`. Tests:
`core/tests/test_uncertainty.py`, `core/tests/test_contract_v04.py`. Package fields:
contract 0.4, [`docs/contract/SPEC.md`](../contract/SPEC.md) section 5.7.

Status on 14 November 2026: the mechanics are checked against closed forms and a
brute-force scan. **The stated horizon error and the stated ellipse are inputs; neither
has been derived from the accuracy of the elevation model or of a lander.** The outputs
for real sites below are therefore "what if" numbers, not error bars of the tool.

## 1. What is asked, and what is assumed

**Stated horizon error.** *If the terrain horizon were higher or lower than computed by a
given angle, when would the body be visible?*

- Assumption: one common shift of the whole profile, the same at every azimuth and for
  every observer height.
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

**Circle of 100 m radius, 13 points**

| Site record | Sun visible at the site | Least, median, most over the points | Earth visible at the site | Least, median, most |
|---|---|---|---|---|
| Shackleton crater rim crest | 667.7 h | 423.8, 557.8, 667.7 h | 322.6 h | 306.0, 322.6, 322.7 h |
| de Gerlache crater rim crest | 720.0 h | 0.0, 531.2, 720.0 h | 352.5 h | 0.0, 304.8, 352.5 h |
| Mons Malapert summit | 701.2 h | 476.5, 540.1, 720.0 h | 592.6 h | 494.2, 579.1, 592.6 h |

Two things explain the spread. The site records are the highest DEM points of their
neighbourhood, so nearly every other point is worse: the centre is the best case by
construction, not a typical one. And the point with no Sun and no Earth at all near the
de Gerlache record lies 16 m below the crest in a hollow whose rim, about 50 m away, is
more than 4 deg high in every azimuth; whether that hollow is terrain or an artefact of
the 20 m elevation model was not examined.

## 4. Limits

1. **The stated numbers are inputs.** 0.05 deg and 100 m are not properties of the LOLA
   products or of any lander. A defensible horizon error needs the height and position
   accuracy of the elevation model and the distance of the limiting terrain (a 1 m height
   error is 0.057 deg at 1 km and 0.006 deg at 10 km).
2. **One common shift.** Real horizon errors differ from azimuth to azimuth. A common
   shift is the unfavourable case for a single event and says little about how errors
   along the profile combine.
3. **A survey, not a probability.** With 13 points, a part of the ellipse that covers less
   than a tenth of its area can be missed entirely. No statement like "visible with 90 %
   probability" follows from the share of points.
4. **Near terrain decides.** Where the horizon of a point is set by terrain tens of metres
   away, its windows rest on single 20 m pixels and on the 2 m observer height. The
   spread over an ellipse on a crest is mostly that.
5. **Cost.** Every sample point needs its own horizon (about 1 to 2 s) and its own event
   search; 24 months with 25 points take minutes per site.
6. Everything in [horizon.md](horizon.md), section 8, applies.
