"""Test support: a test that cannot run because the SPICE kernels are absent is skipped.

The kernels are downloaded inputs (``python -m lsncore.ephem.fetch_kernels``), not part
of the repository. A test that reaches ``kernels.load()`` without them raises
``kernels.KernelsMissing``, in its own body or in a fixture. The ``conftest.py`` of each
test folder that uses SPICE passes its reports through ``kernels_missing_to_skip``, which
turns exactly that error into a skip whose reason names the missing file and the command
that fetches it. Any other error stays an error.
"""

from __future__ import annotations

from . import kernels


def kernels_missing_to_skip(item, call, report):
    """Return ``report``, marked as skipped if the phase failed with ``KernelsMissing``."""
    if call.excinfo is not None and call.excinfo.errisinstance(kernels.KernelsMissing):
        path, line = item.reportinfo()[:2]
        report.outcome = "skipped"
        report.longrepr = (str(path), (line or 0) + 1, f"Skipped: {call.excinfo.value}")
    return report
