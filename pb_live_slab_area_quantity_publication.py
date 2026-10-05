"""QuantityEvidence publication for already-resolved canonical slab area.

This adapter never measures slab geometry. A positive quantity can only be
reissued from a LiveCanonicalSlabObject that already passed the source-bound
metric boundary and lineage gates in pb_live_canonical_slab_projection.
"""
from __future__ import annotations

import math
from collections.abc import Mapping

from pb_live_canonical_slab_projection import LiveCanonicalSlabObject
from pb_migration_contracts import QuantityEvidence, stable_contract_id


LIVE_SLAB_AREA_QUANTITY_SCHEMA_VERSION = "1.0.0"
LIVE_SLAB_AREA_QUANTITY_AUTHORITY = (
    "pb_live_canonical_slab_projection.resolved_metric_boundary_area"
)


def publish_live_slab_area_quantity(
    slab: LiveCanonicalSlabObject,
) -> QuantityEvidence | None:
    if type(slab) is not LiveCanonicalSlabObject:
        raise TypeError("slab must be LiveCanonicalSlabObject")
    if (
        not slab.canonical_slab_id
        or slab.canonical_slab_id != slab.physical_slab_id
        or not slab.document_id
        or not slab.revision_id
        or not slab.source_sha256
        or not slab.snapshot_id
        or not slab.boundary_id
        or not slab.slab_id
        or not slab.geometry_complete
    ):
        return None
    try:
        value = float(slab.area_m2)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(value) or value <= 0.0:
        return None

    provenance = slab.provenance if isinstance(slab.provenance, Mapping) else {}
    provenance_boundary_id = str(provenance.get("boundary_id") or "").strip()
    if provenance_boundary_id != slab.boundary_id:
        return None

    evidence_ids = tuple(
        dict.fromkeys(
            value
            for value in (
                slab.boundary_id,
                slab.slab_id,
                str(provenance.get("annotation_id") or "").strip(),
                str(provenance.get("dimension_evidence_id") or "").strip(),
            )
            if value
        )
    )
    if not evidence_ids:
        return None

    payload = {
        "schema_version": LIVE_SLAB_AREA_QUANTITY_SCHEMA_VERSION,
        "physical_slab_id": slab.physical_slab_id,
        "boundary_id": slab.boundary_id,
        "value_m2": value,
        "source_sha256": slab.source_sha256,
        "revision_id": slab.revision_id,
    }
    return QuantityEvidence(
        quantity_id=stable_contract_id("slab_area_quantity", payload),
        family="slab_area",
        semantic_key=f"slab_area:{slab.physical_slab_id}",
        value=value,
        unit="m2",
        input_entity_ids=(slab.physical_slab_id,),
        formula="resolved canonical slab metric boundary area",
        formula_version=LIVE_SLAB_AREA_QUANTITY_SCHEMA_VERSION,
        evidence_ids=evidence_ids,
        authority=LIVE_SLAB_AREA_QUANTITY_AUTHORITY,
        status="corroborated",
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=("live_slab_area_quantity_resolved",),
        metadata={
            "document_id": slab.document_id,
            "revision_id": slab.revision_id,
            "source_sha256": slab.source_sha256,
            "snapshot_id": slab.snapshot_id,
            "page_no": slab.source_page,
            "canonical_slab_id": slab.canonical_slab_id,
            "physical_slab_id": slab.physical_slab_id,
            "boundary_id": slab.boundary_id,
            "slab_type": slab.slab_type,
            "commercial_projection_allowed": False,
        },
    )


__all__ = [
    "LIVE_SLAB_AREA_QUANTITY_AUTHORITY",
    "LIVE_SLAB_AREA_QUANTITY_SCHEMA_VERSION",
    "publish_live_slab_area_quantity",
]
