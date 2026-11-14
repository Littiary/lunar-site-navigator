# Test data

`contract-sample/packages/` is a byte-for-byte copy of `docs/contract/sample/packages/`
from the core stream (branch `core`, commit `4555fd9`, contract 0.5). It is
pinned here so the Unreal tests run from this folder alone.

- Every value in it is synthetic: invented by a formula for interface testing. It describes
  no real place and no real date.
- Do not edit these files. To refresh them after a contract change, run
  `unreal/Scripts/refresh_fixture.ps1 <git ref>` and rerun the tests.
- At run time the scene prefers `docs/contract/sample/packages/` when that folder exists
  (after the core branch is merged) and falls back to this copy.
