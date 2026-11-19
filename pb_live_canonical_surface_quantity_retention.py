"""Retain source-validated canonical surface quantities in the original live app.

The floor and ceiling publishers already own source/metric promotion. This
runtime adapter checks the *final* physical/canonical owner again before the
quantities enter the same per-object coverage universe exposed to the app.
It neither measures geometry nor creates trade finish/customer rows.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_ceiling_area_quantity_publication import publish_live_ceiling_area_quantities
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_live_ceiling_lining_integration import LiveCeilingLiningResult
from pb_migration_contracts import QuantityEvidence


def _source_bound(
    quantities: Sequence[QuantityEvidence], objects: Sequence[object],
    *, family: str, owner_field: str, canonical_field: str,
) -> tuple[QuantityEvidence, ...]:
    """Fail closed for a mismatched published owner, not by silently picking one."""
    owners: dict[str, object] = {}
    for obj in objects:
        owner = getattr(obj, owner_field)
        if type(owner) is not str or not owner or owner != owner.strip():
            # A source publisher cannot truthfully bind a positive metric to an
            # anonymous physical surface. It can retain an unmeasured object.
            continue
        if owner in owners:
            raise ValueError(f"duplicate canonical {family} owner")
        owners[owner] = obj

    seen: set[str] = set()
    for quantity in quantities:
        if type(quantity) is not QuantityEvidence:
            raise TypeError("canonical surface publisher returned untyped quantity")
        if (
            quantity.family != family
            or quantity.abstained
            or quantity.status != "firm"
            or quantity.blocking_reasons
            or quantity.unit not in ("m2", "m²")
            or type(quantity.value) not in (float, int)
            or not math.isfinite(float(quantity.value))
            or float(quantity.value) <= 0.0
            or type(quantity.quantity_id) is not str
            or not quantity.quantity_id
            or quantity.quantity_id in seen
            or type(quantity.input_entity_ids) not in (list, tuple)
            or len(quantity.input_entity_ids) != 1
        ):
            raise ValueError(f"invalid published canonical {family} quantity")
        seen.add(quantity.quantity_id)
        owner_id = quantity.input_entity_ids[0]
        if type(owner_id) is not str or owner_id not in owners:
            raise ValueError(f"canonical {family} source owner missing")
        obj = owners[owner_id]
        metadata = quantity.metadata
        if not isinstance(metadata, dict):
            raise ValueError(f"canonical {family} metadata is not source-bound")
        source_sha = getattr(obj, "source_sha256")
        revision = getattr(obj, "revision_id")
        if (
            type(source_sha) is not str
            or len(source_sha) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in source_sha)
            or type(metadata.get("source_sha256")) is not str
            or metadata["source_sha256"].lower() != source_sha.lower()
            or metadata.get("revision_id") != revision
            or metadata.get(canonical_field) != getattr(obj, canonical_field)
            or (
                "document_id" in metadata and metadata["document_id"] is not None
                and metadata["document_id"] != getattr(obj, "document_id")
            )
            or not quantity.evidence_ids
            or not set(quantity.evidence_ids).issubset(set(getattr(obj, "evidence_ids")))
        ):
            raise ValueError(f"canonical {family} source lineage conflict")
    return tuple(quantities)


def live_floor_area_coverage_quantities(
    claim: LivePhysicalNetWallClaim,
) -> tuple[QuantityEvidence, ...]:
    """Admit only original publisher FIRM floor areas to live coverage."""
    published = publish_live_floor_area_quantities(claim)
    return _source_bound(
        published, claim.canonical_floors,
        family="floor_area", owner_field="physical_floor_surface_id",
        canonical_field="canonical_floor_id",
    )


def live_ceiling_area_coverage_quantities(
    result: LiveCeilingLiningResult,
) -> tuple[QuantityEvidence, ...]:
    """Admit only original publisher FIRM ceiling areas to live coverage."""
    published = publish_live_ceiling_area_quantities(result)
    return _source_bound(
        published, result.canonical_ceilings,
        family="ceiling_lining", owner_field="canonical_ceiling_id",
        canonical_field="canonical_ceiling_id",
    )


__all__ = [
    "live_floor_area_coverage_quantities",
    "live_ceiling_area_coverage_quantities",
]
