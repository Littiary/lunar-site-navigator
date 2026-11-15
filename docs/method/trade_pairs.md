# Mast-height trade and complementary site pairs

Code: `core/lsncore/trade.py`, `core/lsncore/pairs.py`, wiring in
`core/lsncore/pipeline.py`. Tests: `core/tests/test_trade_pairs.py`,
`core/tests/test_contract_v05.py`. Package fields: contract 0.5,
[`docs/contract/SPEC.md`](../contract/SPEC.md) sections 5.8 and 6a.

Status on 14 November 2026: both are arithmetic on visibility windows; the arithmetic is
checked against a closed form and against identities. **The outputs for real sites below
are not validated against an independent source.**

## 1. Definitions

**Mast-height trade.** The horizon is computed for all observer heights of a scenario in
one pass and the event finder runs for each. The trade table lists, per height, the total
time a window holds in the computed range, the longest continuous time it does not, the
Sun-visible time of the least sunlit complete lunar day, and the change of each against
the lowest height. Only the listed heights are computed.

**Site pairs.** For two sites A and B over the same time range and one window (Sun
visible, Earth visible, both visible):

```
either  = A or B        both = A and B        neither = not (A or B)
gain    = either - max(A, B)                  (what the second site adds)
covered = gain / (range - max(A, B))          (share of the better site's outage)
```

Each site is taken at its default observer height. The pairs package is computed from the
site packages alone and records their ids and content digests.

## 2. Checks

Thresholds were fixed in the test file before the code was written.

| Case | Threshold | Measured |
|---|---|---|
| Observer at the centre of a crater, body swinging like a sine about the horizontal; visible time for mast heights 0, 2, 10, 20, 50 m against the closed-form rim elevation, with the horizon from the real search and windows from the event finder | 5 s | 1.1 s |
| Trade table from hand-made windows | 1e-6 s | exact |
| Pair arithmetic on hand-made windows; identities on 50 random pairs (`either + neither = range`, `A + B = either + both`, gain not negative, symmetric) | 1e-6 s | exact |
| A pairs package recomputed from the two site packages it names | 1e-6 s | exact |

## 3. First outputs on LOLA terrain

Three site records of the data stream, terrain `LDEM_80S_20M` and `LDEM_60S_60M` version
2.0, 14 November 2026 to 14 November 2028 (17 544 h), eleven observer heights, Sun: any
part of the disc visible, Earth: centre above the horizon. Computed on 14 November 2026
with core commit 5c0cbaa; 294 s for the three sites.

*The 0 m figures below were computed before 15 November 2026, when the search began one
pixel from the site. With the ground at the site searched they are lower (in 30 days the
Sun is in view of a 0 m observer for 411 instead of 421 h at the Shackleton record, 387
instead of 544 h at de Gerlache, 440 instead of 517 h at Malapert;
[horizon.md](horizon.md), section 5.2). Figures for 1 m and above are not affected. To be
recomputed with the next published set.*

**Sun-visible share of the 24 months, by observer height**

| Site record | 0 m | 1 m | 2 m | 5 m | 10 m | 20 m | 50 m |
|---|---|---|---|---|---|---|---|
| Shackleton crater rim crest | 66.9 % | 76.1 % | 78.0 % | 80.6 % | 83.2 % | 86.3 % | 91.2 % |
| de Gerlache crater rim crest | 82.1 % | 83.7 % | 84.7 % | 86.3 % | 88.2 % | 88.5 % | 88.8 % |
| Mons Malapert summit | 60.8 % | 67.6 % | 72.5 % | 79.7 % | 84.8 % | 86.2 % | 88.7 % |

**Longest continuous time without the Sun, by observer height**

| Site record | 0 m | 2 m | 5 m | 10 m | 20 m | 50 m |
|---|---|---|---|---|---|---|
| Shackleton crater rim crest | 276 h | 188 h | 168 h | 134 h | 126 h | 61 h |
| de Gerlache crater rim crest | 264 h | 257 h | 257 h | 135 h | 135 h | 134 h |
| Mons Malapert summit | 370 h | 330 h | 307 h | 268 h | 261 h | 260 h |

The curves are not smooth: at the de Gerlache record the longest darkness stays at 257 h
from 1 m to 5 m, is 177 h at 8 m and 135 h from 10 m up. At the Malapert
record the Earth is in view for 81.6 % of the time at 2 m, 91.2 % at 10 m and for the whole
range from 20 m up; 26 of its 40 obstacles at 2 m are within 1 km, so that curve rests on
near terrain.

**Pairs, each site at 2 m**

| Pair | Apart | Sun visible at A, at B | At one of them at least | Longest time with the Sun at neither | The second site covers, of the better site's Sun outage |
|---|---|---|---|---|---|
| Shackleton rim crest and de Gerlache rim crest | 41 km | 78.0 %, 84.7 % | 97.0 % | 43 h | 81 % |
| Shackleton rim crest and Malapert summit | 127 km | 78.0 %, 72.5 % | 84.4 % | 188 h | 29 % |
| de Gerlache rim crest and Malapert summit | 115 km | 84.7 %, 72.5 % | 90.8 % | 163 h | 40 % |

For the Earth a second site adds nothing in any of the three pairs: at every time at
which the site with the shorter Earth view sees the Earth, the other sees it too
(checked on the stored windows: 0.00 h otherwise). These are outputs for three particular
DEM points; no claim is made about which pair of locations on the Moon is the best one.

## 4. Limits

1. **A mast changes the view of near terrain most.** Where the gain is large, the horizon
   is set by terrain within about 1 km, which rests on single 20 m pixels of the elevation
   model. The gain is then as uncertain as that terrain, and a different elevation model
   could give a different curve.
2. **Only listed heights.** Nothing is interpolated between them, and the curve need not
   be smooth: an obstacle is cleared at one height or it is not.
3. **A point observer.** The mast, its base, the lander and its shadow are not modelled.
4. **Pairs say when, not how.** "Either site sees the Sun" does not mean power reaches the
   site that does not: no line of sight between the sites, no cable and no relay is
   computed. The distance between the sites is given so that a reader can judge.
5. **Same range, default height.** Sites are compared over the scenario's range at their
   default observer height only.
6. Everything in [horizon.md](horizon.md), section 8, applies to each site.
