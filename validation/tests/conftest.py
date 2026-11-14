"""These tests use SPICE. Where the kernels have not been downloaded they are skipped, with the command that fetches them."""

import pytest

from lsncore.ephem.testing import kernels_missing_to_skip


@pytest.hookimpl(wrapper=True)
def pytest_runtest_makereport(item, call):
    return kernels_missing_to_skip(item, call, (yield))
