"""Georeferencing check against the crater catalogue (criterion: data/checkpoints/thresholds_catalogue.json)."""

import json

import numpy as np
import pytest

from lsn_data import catalogue_check as cc
from lsn_data.paths import repo_data_dir

REPORT = repo_data_dir() / "checkpoints" / "catalogue_report.json"


def test_classify_rules():
    assert cc.classify(150.0, 10.0, 100.0, True) == "confirmed_and_matters"
    assert cc.classify(40.0, 5.0, 100.0, True) == "detected_but_small"
    assert cc.classify(40.0, 5.0, 100.0, False) != "detected_but_small"
    assert cc.classify(10.0, 10.0, 100.0, True) == "ruled_out_to_matter_level"
    assert cc.classify(60.0, 30.0, 100.0, True) == "undecided"


def test_estimator_recovers_a_known_transform():
    rng = np.random.default_rng(0)
    R = rng.uniform(-200000, 200000, (300, 2))
    T0, delta, eps = np.array([30.0, -50.0]), 2e-4, 5e-4
    T = T0 + delta * np.column_stack([-R[:, 1], R[:, 0]]) + eps * R + rng.normal(0, 20, (300, 2))
    p, keep = cc.estimate(T, R)
    assert np.allclose(p[:2], T0, atol=10) and abs(p[2] - delta) < 2e-5 and abs(p[3] - eps) < 2e-5


def test_recorded_result_has_no_confirmed_shift():
    r = json.loads(REPORT.read_text(encoding="utf-8"))
    assert r["craters_used_after_outlier_rejection"] >= 100
    assert "confirmed_and_matters" not in r["classification"].values(), r["classification"]


@pytest.mark.needs_data
def test_recorded_result_is_reproduced():
    r = json.loads(REPORT.read_text(encoding="utf-8"))
    again = cc.run()
    assert again["estimates"] == r["estimates"]
    assert again["craters_used_after_outlier_rejection"] == r["craters_used_after_outlier_rejection"]
