"""Source-neutral customer inclusion policy for independently issued quantities.

An explicitly excluded or unresolved source quantity must not be given an
INCLUSION label by a downstream presentation adapter. Source geometry and
schedules own the decision; this module makes no classification of ink.
"""
from __future__ import annotations

from collections.abc import Mapping

from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError


def require_uncontested_source_inclusion(quantity: QuantityEvidence) -> None:
    """Fail closed for nonabstained numeric source quantities with a non-inclusion scope."""
    if quantity.abstained or quantity.value is None:
        return
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    if "inclusion_status" not in metadata:
        return
    scope = metadata["inclusion_status"]
    if (
        type(scope) is not str or scope.strip().upper() != "INCLUSION"
    ):
        raise SourceClosedRunConflictError("customer_source_inclusion_scope_unresolved")


def unique_customer_ceiling_owners(ceilings):
    """Reject duplicate canonical ceiling identities before customer location mapping."""
    result = {}
    for ceiling in ceilings:
        key = getattr(ceiling, "canonical_ceiling_id", None)
        if type(key) is not str or not key or key != key.strip():
            continue
        if key in result:
            raise SourceClosedRunConflictError("duplicate_canonical_ceiling_customer_owner")
        result[key] = ceiling
    return result
