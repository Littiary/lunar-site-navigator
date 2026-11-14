# Showing the obstacle: what hides the Sun or the Earth, and what it costs

Code: `core/lsncore/obstacles.py`, `core/lsncore/blocking.py`, wiring in
`core/lsncore/pipeline.py`. Tests: `core/tests/test_obstacles.py`,
`core/tests/test_contract_v02.py`. Package fields: contract 0.2,
[`docs/contract/SPEC.md`](../contract/SPEC.md) section 5.5.

Status on 14 November 2026: checked against closed-form cases. **Not compared with an
independent computation on real terrain.** The numbers for real sites below are outputs,
not validated results.

## 1. Definitions

**Obstacle.** The horizon stores, per azimuth, the terrain point that sets it. An obstacle
is a run of neighbouring azimuths whose limiting points lie at nearly the same distance:
two neighbours belong together if their distances differ by no more than 10 % of the
smaller one, or by no more than 50 m. Where the limiting point jumps, a new obstacle
begins. The profile is periodic; the grouping is done per observer height. An obstacle
whose highest point is closer than 1 km is flagged `near_field`.

**Limiting sample.** For a disc at a given instant, the horizon sample that limits its
view. Under the condition "any part of the disc visible" it is, among the samples under
the disc, the one where the upper edge of the disc stands highest above the horizon; for
a hidden disc that is where its first light will appear. Under the centre condition it is
the sample nearest to the azimuth of the centre; under "whole disc visible", the one
where the horizon reaches highest above the lower edge.

**Smooth sphere.** The same visibility condition evaluated with no terrain: a sphere
through the ground point of the site, horizon below the horizontal by the dip angle
`acos(r / (r + m))` (`r` distance of the site from the centre, `m` observer height). Same
direction table and same event finder as for the terrain.

**Lost and gained time.**

```
lost   = visible over the smooth sphere AND NOT visible over the terrain
gained = visible over the terrain AND NOT visible over the smooth sphere
```

computed with interval algebra on the visibility windows, so the totals have the accuracy
of the event times. A site that stands above its surroundings gains time: its terrain
horizon is lower than the smooth one.

**Blockers.** The lost time is split between obstacles: every sample of the series stands
for the half step before and after it, and its share of a lost interval goes to the
obstacle at its limiting sample. The shares add up to the lost time exactly; their
boundaries in time are resolved to the series step.

## 2. Checks

Thresholds were fixed in the test file before the code was written.

| Case | Threshold | Measured |
|---|---|---|
| A body circling at constant elevation behind a smooth ridge in the horizon; lost time against the closed-form duration (45.7 h) | 5 s | 0.9 s |
| Shares of the obstacles against the lost time | 1e-6 s | exact |
| A hill on a plain, through the real horizon search: two obstacles (hill, plain), also when the hill straddles azimuth 0; peak at the hill's bearing | exact counts; peak distance within 2 % | passes |
| Limiting sample on a sloping horizon against the closed-form offset `-r s / sqrt(1 + s^2)` | one azimuth step | passes |
| Balance `terrain = smooth - lost + gained` and consistency of list and arrays in a written package | 1e-6 s | passes |

## 3. First outputs on LOLA terrain

Three site records of the data stream (`data/sites/sites.json` on the data branch),
terrain `LDEM_80S_20M` and `LDEM_60S_60M` version 2.0, window 14 November to 14 December
2026 (720 h, southern summer), observer 2 m above the surface, Sun: any part visible,
Earth: centre above the horizon. Computed on 14 November 2026 with core commit 16a4957.

| Site record | Sun visible | Sun, smooth sphere | Lost | Gained | Earth visible | Earth, smooth sphere | Lost | Gained |
|---|---|---|---|---|---|---|---|---|
| Shackleton crater rim crest | 667.7 h | 720.0 h | 52.3 h | 0 | 322.6 h | 292.1 h | 0 | 30.5 h |
| de Gerlache crater rim crest | 720.0 h | 720.0 h | 0 | 0 | 352.5 h | 313.4 h | 0 | 39.1 h |
| Mons Malapert summit | 701.2 h | 464.8 h | 0 | 236.4 h | 592.6 h | 495.2 h | 0 | 97.5 h |

At the Shackleton record all 52.3 lost hours go to three obstacles 0.4 to 0.7 km from the
site (azimuths 333 to 9 degrees, 2.8 to 3.1 degrees high). They are near-field obstacles:
their height in the profile rests on a few 20 m pixels and on the 2 m observer height
(see limits). The profiles have 39 to 48 obstacles at 2 m. A site package for 30 days at
an hourly step is about 0.7 MB.

At the Malapert record the far-field bound of the horizon is 0.47 degrees: from 5 km above
the reference sphere, 300 km of search radius does not prove that nothing higher lies
beyond.

## 4. Limits

1. **One obstacle per instant.** The blocker is the obstacle at the limiting sample. Other
   terrain under the disc may hide parts of it at the same time and is not named.
2. **Obstacles are runs of the profile, not named features.** The rule looks at distance
   only. A long ridge can be split where the limiting point jumps along it, and two
   features at the same distance can be joined.
3. **Near-field obstacles are fragile.** They depend on single pixels of the elevation
   model and on the observer height; a different observer height can remove them. The
   package flags them, and the horizon note explains why.
4. **Resolution of the split.** Totals are as accurate as the event times; the moment at
   which the blocker changes from one obstacle to the next is known to the series step.
5. **The smooth sphere is a yardstick.** "Lost" and "gained" compare with a Moon without
   relief; they do not compare with another site or another date.
6. **The window matters.** Hours lost in one month say nothing about another season.
7. Everything in [horizon.md](horizon.md), section 8, applies.
