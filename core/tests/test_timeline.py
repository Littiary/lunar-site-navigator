"""The reusable time objects: uniform grid and interval algebra."""

import numpy as np
import pytest

from lsncore.timeline import IntervalSet, TimeGrid

DOMAIN = (0.0, 100.0)


def test_grid_times_and_round_trip():
    grid = TimeGrid(10.0, 2.5, 5)
    assert grid.times().tolist() == [10.0, 12.5, 15.0, 17.5, 20.0]
    assert grid.end_et_s == 20.0
    obj = grid.to_contract("2026-11-14T00:00:00.000Z", "2026-11-14T00:00:10.000Z")
    assert TimeGrid.from_contract(obj) == grid


def test_normalisation_merges_sorts_and_clips():
    s = IntervalSet([(50, 60), (-5, 10), (10, 20), (55, 70), (30, 30), (95, 200)], DOMAIN)
    assert s.as_list() == [[0, 20], [50, 70], [95, 100]]
    assert s.total_s() == 45.0
    assert s.longest_s() == 20.0
    assert s.clipped_start and s.clipped_end


def test_union_intersection_complement():
    a = IntervalSet([(0, 30), (60, 80)], DOMAIN)
    b = IntervalSet([(20, 65), (90, 100)], DOMAIN)
    assert a.union(b).as_list() == [[0, 80], [90, 100]]
    assert a.intersection(b).as_list() == [[20, 30], [60, 65]]
    assert a.complement().as_list() == [[30, 60], [80, 100]]
    assert IntervalSet.empty(DOMAIN).complement() == IntervalSet.full(DOMAIN)


def test_algebra_identities():
    rng = np.random.default_rng(7)
    for _ in range(50):
        a = IntervalSet(np.sort(rng.uniform(0, 100, (4, 2)), axis=1), DOMAIN)
        b = IntervalSet(np.sort(rng.uniform(0, 100, (4, 2)), axis=1), DOMAIN)
        assert a.complement().complement() == a
        # the measure is additive: |A| + |B| = |A or B| + |A and B|
        assert a.total_s() + b.total_s() == pytest.approx(
            a.union(b).total_s() + a.intersection(b).total_s(), abs=1e-9
        )
        # De Morgan
        assert a.union(b).complement() == a.complement().intersection(b.complement())
        assert a.total_s() + a.complement().total_s() == pytest.approx(100.0, abs=1e-9)


def test_close_gaps_and_drop_short():
    s = IntervalSet([(0, 10), (12, 20), (40, 41), (60, 90)], DOMAIN)
    assert s.close_gaps(2.0).as_list() == [[0, 20], [40, 41], [60, 90]]
    assert s.drop_short(5.0).as_list() == [[0, 10], [12, 20], [60, 90]]


def test_domains_must_match():
    with pytest.raises(ValueError):
        IntervalSet([(0, 1)], (0, 10)).union(IntervalSet([(0, 1)], (0, 20)))


def test_from_samples_interpolates_crossings():
    grid = TimeGrid(0.0, 10.0, 5)  # t = 0, 10, 20, 30, 40
    values = np.array([-1.0, 1.0, 3.0, -1.0, -3.0])
    s = IntervalSet.from_samples(grid, values)
    assert s.as_list() == [[5.0, 27.5]]
    assert not s.clipped_start and not s.clipped_end
    above = IntervalSet.from_samples(grid, values, threshold=-2.0)
    assert above.as_list() == [[0.0, 35.0]]
    assert above.clipped_start


def test_from_samples_treats_nan_as_condition_not_met():
    grid = TimeGrid(0.0, 10.0, 5)
    s = IntervalSet.from_samples(grid, np.array([1.0, 1.0, np.nan, 1.0, 1.0]))
    assert s.as_list() == [[0.0, 10.0], [30.0, 40.0]]
