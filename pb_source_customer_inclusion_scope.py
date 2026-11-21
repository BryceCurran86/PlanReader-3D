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
    # A missing optional scope is not a newly granted inclusion; upstream
    # source authority still controls. An explicitly null scope is ambiguous
    # and must never be rewritten as a customer inclusion.
    if "inclusion_status" not in metadata:
        return
    scope = metadata["inclusion_status"]
    if type(scope) is not str or scope.strip().upper() != "INCLUSION":
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


def require_uncontested_source_commercial_scope(quantity: QuantityEvidence) -> None:
    """An explicit source commercial-denial/unknown cannot become a customer YES.

    Missing optional metadata gives no authority: the existing original
    source-closed sealer must still independently grant commercial publishing.
    """
    if quantity.abstained or quantity.value is None:
        return
    meta = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    # A provisional original observation is explicitly noncommercial. The
    # source publisher may independently reissue a FIRM quantity after full
    # physical/source proof; the customer adapter verifies that new seal.
    # The intermediate source-only FIRM reissue is also intentionally
    # quantity_handoff_only and commercially false until the sealed customer
    # quantity/row bijection is authenticated. Never conflate source stage
    # with a final original commercial denial.
    if str(quantity.status).strip().casefold() != "firm":
        return
    if meta.get("quantity_handoff_only") is True:
        return
    if "commercial_projection_allowed" in meta and meta["commercial_projection_allowed"] is not True:
        raise SourceClosedRunConflictError("customer_source_commercial_scope_denied")


def _source_ceiling_declared_owner_matches(quantity: QuantityEvidence, ceiling: object) -> bool:
    """One universal source-identity predicate for original and reissued ceilings.

    The legacy provisional source refers to its ROOM and its own shadow
    quantity ID, not the later canonical-ceiling quantity ID. Therefore
    canonical input-entity ownership is checked by the final adapter, while
    any *explicitly declared* source identity must agree in either stage.
    """
    metadata = quantity.metadata if isinstance(quantity.metadata, Mapping) else {}
    expected = (
        ("document_id", getattr(ceiling, "document_id", None)),
        ("revision_id", getattr(ceiling, "revision_id", None)),
        ("snapshot_id", getattr(ceiling, "snapshot_id", None)),
        ("source_sha256", getattr(ceiling, "source_sha256", None)),
        ("canonical_ceiling_id", getattr(ceiling, "canonical_ceiling_id", None)),
        ("canonical_room_id", getattr(ceiling, "room_entity_id", None)),
        ("source_room_index_id", getattr(ceiling, "source_room_index_id", None)),
        ("room_area_quantity_id", getattr(ceiling, "room_area_quantity_id", None)),
        ("upstream_area_quantity_id", getattr(ceiling, "room_area_quantity_id", None)),
    )
    for key, value in expected:
        if key not in metadata:
            continue
        claimed = metadata[key]
        if (type(claimed) is not str or not claimed or claimed != claimed.strip()
                or type(value) is not str or not value
                or (claimed.lower() != value.lower() if key == "source_sha256"
                    else claimed != value)):
            return False
    return True


def original_legacy_ceiling_source_matches_owner(quantity: QuantityEvidence, ceiling: object) -> bool:
    """Check a provisional ORIGINAL against its ceiling before FIRM reissue.

    A bad provisional witness can never be repaired by a later adapter copying
    canonical metadata over it. It is removed from this candidate's customer
    projection only; independent other valid ceiling sources remain available.
    No geometry, identity or commercial permission is inferred here.
    """
    if type(quantity) is not QuantityEvidence:
        return False
    if quantity.abstained or quantity.value is None:
        return False
    return (
        quantity.unit in ("m2", "m²")
        and _source_ceiling_declared_owner_matches(quantity, ceiling)
    )


def require_source_ceiling_owner_parity(quantity: QuantityEvidence, ceiling: object) -> None:
    """Match every source-declared canonical ceiling owner field to its physical object."""
    if quantity.abstained or quantity.value is None:
        return
    if (len(quantity.input_entity_ids) != 1
            or quantity.input_entity_ids[0] != getattr(ceiling, "canonical_ceiling_id", None)
            or not _source_ceiling_declared_owner_matches(quantity, ceiling)):
        raise SourceClosedRunConflictError("source_ceiling_physical_owner_mismatch")
    if quantity.unit not in ("m2", "m²"):
        raise SourceClosedRunConflictError("source_ceiling_customer_unit_not_area")
