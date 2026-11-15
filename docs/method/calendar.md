# Opportunity calendar and slip tolerance

Code: `core/lsncore/calendar.py`, wiring in `core/lsncore/pipeline.py`. Tests:
`core/tests/test_calendar.py`, `core/tests/test_contract_v03.py`. Package fields:
contract 0.3, [`docs/contract/SPEC.md`](../contract/SPEC.md) section 5.6.

Status on 14 November 2026: the arithmetic is checked against closed forms and a
brute-force scan. It works on the visibility windows of a site and inherits their
accuracy and their limits. **The outputs for real sites below are not validated against
an independent source.**

## 1. Definitions

**Lunar day.** The computed range is cut where the Sun crosses the 180 degree meridian of
the body-fixed frame (the middle of the far side, close to new Moon). The boundaries come
from the Sun's position in the direction table and are the same for every site, so the
rows of two sites line up. The first and the last period are cut by the ends of the range
and are marked incomplete.

**Calendar.** For every lunar day and observer height: the time for which the Sun is
visible, the Earth is visible, both are visible, and the longest stretch inside the lunar
day without the Sun or without the Earth. "Visible" is the scenario's condition for the
body (by default: any part of the Sun's disc; the centre of the Earth's disc).

**Requirement.** Stated in the scenario as a list of conditions on visibility windows:
the condition holds at landing; it holds without interruption for a given time from
landing; it holds for a given total time within the mission duration. All must hold.

**Landing windows.** The set of landing times for which the requirement holds. It follows
from the edges of the visibility windows by interval arithmetic: an unbroken stretch
`[a, b]` of visibility admits landings in `[a, b - T]` for a continuous requirement `T`;
the total inside a sliding mission window is a piecewise-linear function of the landing
time whose crossings are solved exactly. No dates are tried.

**Slip tolerance.** For a planned landing inside a landing window: the time to the end of
that window. The landing can be delayed by up to this much and the requirement still
holds. If the planned time is not feasible, the tolerance is 0 and the wait to the next
window is reported. Nothing is assumed beyond the computed range: a requirement that
cannot be checked inside the range counts as not met, and a window that ends at the last
time that can be judged gives a lower bound.

**The end of what can be judged.** The last landing time that can be judged
(`latest_landing`) is the end of the computed range minus the mission duration, for
every requirement that states a duration. A landing window can end without any event
ending it in two ways: at `latest_landing`, or where a "continuous from landing"
condition can no longer be proven because the visibility it needs is still going on
when the range ends (the end of the range minus its required time). Such a window is
marked as cut, and a slip tolerance inside it is a lower bound. A planned landing later
than that is neither feasible nor infeasible: it gets no slip report, and the package
says so in its warnings.

Until 15 November 2026 the core applied the first rule only to requirements with a
"total within the mission" condition. For the others (two of the three example
requirements) `latest_landing` was the end of the range, the feasible share was divided
by too long a time (about 1 % too low over 24 months) and a last window that ends there
was not marked as cut. An independent review found it; the landing windows themselves
were right. The example requirement of section 3 has such a condition, so the table
there was not affected.

## 2. Checks

Thresholds were fixed in the test file before the code was written.

| Case | Threshold | Measured |
|---|---|---|
| Lunar-day boundaries for a Sun circling at a constant rate, against the closed form | 5 s | 0.004 s |
| Totals per lunar day add up to the window totals; a window equal to one period | 1e-6 s | exact |
| Landing windows of the three condition kinds against hand-computed sets | 1e-6 s | exact |
| Landing windows of 25 random cases (three conditions each) against a scan in 1 s steps | 2 s | passes |
| Slip report: inside a window, outside, no window, window cut by the range | 1e-6 s | exact |
| The end of what can be judged, case of the review: 30 days, Earth always in view, Sun from day 5 to the end, 10 days of unbroken sunlight, mission of 10 days, landing planned on day 12. Expected, fixed before the fix: latest landing day 20, feasible share 0.75, window cut, slip of 8 days a lower bound | 1e-6 s; 1e-12 | failed before the fix (day 30, 0.50, not cut), passes |
| A window that ends at an event is not marked; a window cut by a condition that cannot be proven is marked whatever the mission duration; the three example requirements end at latest landing when the Sun stays up | exact | passes |
| A planned landing after what can be judged gets no slip report and a sentence in the warnings | exact | passes |

One literal in the first version of the boundary test was a miscount (six boundaries in
200 days; there are seven for the phase used). The count is now taken from the closed
form. No tolerance was changed.

## 3. First outputs on LOLA terrain

Three site records of the data stream, terrain `LDEM_80S_20M` and `LDEM_60S_60M` version
2.0, 14 November 2026 to 14 November 2028, hourly series, observer 2 m. 25 periods, 23 of
them complete (mean length 708.65 h). Computed on 14 November 2026 with core commit
b60e6c4. Three sites took 141 s; a site package is 4.3 to 5.1 MB.

| Site record | Sun visible, share over the complete lunar days | Sun-visible hours per lunar day: least, median, most | Longest stretch without the Sun inside a lunar day: least, median, most | Earth visible, share |
|---|---|---|---|---|
| Shackleton crater rim crest | 76.7 % | 357, 571, 657 h | 49, 67, 121 h | 52.2 % |
| de Gerlache crater rim crest | 83.5 % | 418, 663, 711 h | 0, 28, 257 h | 57.1 % |
| Mons Malapert summit | 70.4 % | 379, 457, 686 h | 23, 122, 187 h | 81.4 % |

The least sunlit lunar days fall between March and July (southern winter) at all three.

**Example requirement** (chosen by the team to show the mechanism; it is not a mission
requirement from any agency): Earth in view at landing, six days of unbroken sunlight
from landing, Earth in view for at least half of a 14-day stay.

| Site record | Landing windows in 24 months | Share of the range that is a feasible landing time | Longest, median window | Planned 1 June 2027 | Planned 10 January 2027 |
|---|---|---|---|---|---|
| Shackleton crater rim crest | 18 | 15.7 % | 8.8 d, 6.7 d | not feasible; next window in 48.9 d | not feasible; next window in 0.4 d |
| de Gerlache crater rim crest | 24 | 23.1 % | 9.7 d, 8.1 d | not feasible; next window in 20.8 d | feasible; can slip 7.6 d |
| Mons Malapert summit | 30 | 42.3 % | 22.4 d, 9.3 d | not feasible; next window in 11.2 d | not feasible; next window in 0.9 d |

At the Malapert record the feasible share depends strongly on the observer height: 32.9 %
on the surface, 42.3 % at 2 m, 72.6 % at 20 m. The summit's horizon is set by terrain
within 1 km in most azimuths, so these numbers rest on a few DEM pixels.

## 4. Limits

1. **The requirement is an input.** The tool reports when a stated requirement holds; it
   does not know what a mission needs.
2. **Window edges carry the horizon's uncertainty.** A landing window ends where a
   visibility window ends. Near-field obstacles and DEM errors move those edges by hours
   near the poles; the uncertainty band (contract 0.4) shows by how much for a stated
   horizon error.
3. **Range.** Landings later than the end of the range minus the mission duration cannot
   be judged and are not in the windows. `feasible_fraction` is the share of the time up
   to that instant, not of the whole range. Between that instant and the end of the range
   some landings could in fact be ruled out (the Earth is not in view at landing); the
   package does not say so for a planned landing there.
4. **Sun visibility is geometric.** "Visible" means any part of the disc above the terrain
   horizon. Power needs the lit fraction and the panel; eclipses by the Earth are in the
   eclipse-aware window `sun_lit`, which a requirement can name instead of `sun_visible`.
5. **Lunar-day boundaries** are a convention for binning. Hours per lunar day of a site
   whose Sun-visible stretches straddle the boundary are split between two rows.
6. Everything in [horizon.md](horizon.md), section 8, applies.
