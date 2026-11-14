from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture(scope="session")
def synth_label() -> Path:
    return FIXTURES / "synth_s90_100m.lbl"


def pytest_collection_modifyitems(config, items):
    from lsn_data.paths import raw_dir

    have = (raw_dir() / "LDEM_80S_20M" / "ldem_80s_20m.img").exists()
    if have:
        return
    skip = pytest.mark.skip(reason="LOLA data not downloaded under the data root (run `python -m lsn_data fetch`)")
    for item in items:
        if "needs_data" in item.keywords:
            item.add_marker(skip)
