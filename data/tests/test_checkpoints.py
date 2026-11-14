"""The three data checkpoints on the real files. Skipped when the data is not under the data root."""

import json

import pytest

from lsn_data import checkpoints
from lsn_data.paths import data_root

pytestmark = pytest.mark.needs_data


@pytest.fixture(scope="module")
def report():
    return checkpoints.run_all(data_root())


def test_checkpoint_1_checksums(report):
    assert report["checkpoint_1_checksums"]["passed"], report["checkpoint_1_checksums"]


def test_checkpoint_2_georeferencing(report):
    c = report["checkpoint_2_georeferencing"]
    assert c["passed"], json.dumps(c, indent=1)


def test_checkpoint_3_values_and_reference_radius(report):
    c = report["checkpoint_3_values_and_reference_radius"]
    assert c["passed"], json.dumps(c, indent=1)
