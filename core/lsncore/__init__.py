"""Science core of the Lunar Site Navigator.

Every number the project shows is computed here and written to a versioned package
(see docs/contract/SPEC.md). Viewers only read packages.
"""

__version__ = "0.1.0"

# Incremented by a human decision whenever a change can alter computed numbers.
# It is part of every package id, so a change here invalidates cached packages.
SCIENCE_VERSION = 0
