"""The package contract: writing, reading and validating packages.

The specification is docs/contract/SPEC.md; the machine-checkable schema is
docs/contract/schemas/lsn-contract.schema.json.
"""

from .io import (
    CONTRACT_NAME,
    CONTRACT_VERSION,
    Package,
    PackageWriter,
    canonical_json,
    compute_content_sha256,
    compute_package_id,
    contract_dir,
    contract_header,
    format_utc,
    read_package,
    write_index,
    write_json,
)
from .validate import (
    ContractError,
    load_schema,
    validate_document,
    validate_package,
)

__all__ = [
    "CONTRACT_NAME",
    "CONTRACT_VERSION",
    "ContractError",
    "Package",
    "PackageWriter",
    "canonical_json",
    "compute_content_sha256",
    "compute_package_id",
    "contract_dir",
    "contract_header",
    "format_utc",
    "load_schema",
    "read_package",
    "validate_document",
    "validate_package",
    "write_index",
    "write_json",
]
