# Proposal: keep runtime limits apart from correctness tests

Status: a proposal, written on 15 November 2026 at the request of the review. Nothing
described here is implemented. The limits themselves are not in question and are not to
be changed by it.

## What is wrong today

Five tests of the core check that a result is right and, in the same function, that it
was computed within a wall-clock limit:

| Test | Limit | What it also checks |
|---|---|---|
| `test_horizon.py::test_one_site_runs_within_the_time_budget` | 5 s | nothing else (already separate) |
| `test_horizon.py::test_nothing_is_missed_on_lola_data` | 5 s | completeness against a 1 m scan at three places |
| `test_moon_terrain.py::test_a_mid_latitude_site_on_the_global_product` | 5 s | completeness, then the package and its product record |
| `test_near_field.py::test_site_records_on_the_5_m_near_field` | 15 s | completeness, then the package and its terrain source |
| `test_custom_site.py::test_a_30_day_custom_package_is_written_within_half_a_minute` | 30 s | that the package is complete and valid |

Three things follow, all seen on 14 and 15 November:

1. **A slow machine turns a correctness test red.** With other programs running, the
   5 s tests measured 5.0 to 6.5 s and the 30 s test 522 s, with the code unchanged: the
   published code and the code of that night took the same time side by side (5.32 s and
   5.35 s for the same call, the same number of lattice points walked), where the day
   before it had taken 1.6 s. A reader of the test report cannot tell "the result is
   wrong" from "the laptop was busy".
2. **The assertions after the timing line do not run.** In the second, third and fourth
   test the package is checked after the limit. When the limit fails, those checks are
   skipped without a word, so a red run says less about correctness than a green one.
3. **Best of three does not help against a machine that is slow throughout.** It removes
   a short disturbance (its purpose, [horizon.md](horizon.md), section 6), not a load
   that lasts for the whole test, nor the slowing of the processor after some seconds of
   sustained work.

## Proposal

1. **One function for correctness, one for the limit.** Each of the four mixed tests is
   split. The correctness function keeps every assertion except the limit. A new
   function next to it, named `test_runtime_...`, holds only the timed call and the
   limit, with the same limit, the same call and the same best of three. About forty
   lines move; no line of the core changes, and no limit.
2. **A marker.** The runtime functions carry `@pytest.mark.runtime`, registered in
   `pytest.ini`. Then:
   - `pytest -m "not runtime"` is the correctness suite. It must be green on any machine
     in any state, and it is what a merge is judged by.
   - `pytest -m runtime` is the runtime suite: five tests, a minute or two. It is run on
     its own, on a machine that is doing nothing else, and its result is recorded with
     the conditions (point 3).
   - Plain `pytest` still runs both, so nothing is skipped by default; the names and the
     marker make the two kinds of red distinguishable in the summary.
3. **The conditions are part of the result.** Each runtime test first times a fixed piece
   of arithmetic (for example twenty sines of four million numbers, 0.6 s on the team
   laptop when it is not slowed) and puts that figure, and the processor load where the
   system gives it, into its message. A failure then reads "5.4 s against 5 s; reference
   work took 1.9 s instead of 0.6 s", which says at once what kind of failure it is.
4. **A slow machine: fail or say "not measured"?** This is the one decision in the
   proposal. Either
   - (a) the runtime test fails whenever the limit is exceeded, and the message carries
     the conditions; or
   - (b) if the reference work of point 3 takes more than twice its usual time, the test
     is reported as skipped with the reason "machine slowed: not a measurement", and
     otherwise as in (a).

   Recommendation: (a). A skip can hide a real slowdown for as long as the machine is
   busy, and the rule of the project is that a timing failure under load is reported
   with the load, not made to disappear. With points 1 to 3 in place a failure of this
   kind no longer touches the correctness suite, which is what matters for a merge.

## What does not change

The limits (5 s, 15 s, 30 s), the best of three, the calls that are timed, and the
figures in the method notes. The proposal changes where the limit is asserted and what
the failure message says, nothing else.
