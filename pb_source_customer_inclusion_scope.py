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
    scope = metadata.get("inclusion_status")
    if scope is not None and (
        type(scope) is not str or scope.strip().upper() != "INCLUSION"
    ):
        raise SourceClosedRunConflictError("customer_source_inclusion_scope_unresolved")
