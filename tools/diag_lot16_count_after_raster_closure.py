from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_opening_count_quantity_publication import (
    publish_live_authenticated_opening_count_quantities,
)
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_count_after_raster_closure",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-count-after-raster-closure",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    opening_composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    area_quantities = publish_live_opening_area_quantities(opening_composition)
    count_quantities = publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )

    semantic = wall_opening.semantic_enumeration_result
    semantic_record = semantic.record
    universe = wall_opening.opening_universe_result
    universe_record = universe.record

    physical = wall_opening.physical_opening_authority
    visibility = source.authority()

    def observation_row(observation_id: str) -> dict:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=str(observation_id),
        )
        visible = visibility.resolve_visible(selector)
        observation = visible.observation
        disposition = physical.classify_disposition(selector)
        return {
            "observation_id": str(observation_id),
            "visible_status": visible.status.value,
            "observation_kind": None if observation is None else observation.observation_kind,
            "geometry": None if observation is None else list(observation.geometry),
            "source_primitive_ref": None if observation is None else observation.source_primitive_ref,
            "disposition_status": disposition.status.value,
            "disposition": disposition.disposition,
            "disposition_reasons": list(disposition.reason_codes),
            "candidate_ids": list(disposition.candidate_ids),
        }

    residual_rows = []
    conflict_rows = []
    if semantic_record is not None:
        residual_rows = [
            observation_row(observation_id)
            for observation_id in semantic_record.residual_visible_observation_ids
        ]
        conflict_rows = [
            observation_row(observation_id)
            for observation_id in semantic_record.conflict_observation_ids
        ]

    payload = {
        "source_sha256": source_sha,
        "semantic_status": semantic.status.value,
        "semantic_reason_codes": [] if semantic_record is None else list(semantic_record.reason_codes),
        "structural_enumeration_complete": None if semantic_record is None else semantic_record.structural_enumeration_complete,
        "physical_opening_universe_complete": None if semantic_record is None else semantic_record.physical_opening_universe_complete,
        "physical_opening_record_count": 0 if semantic_record is None else len(semantic_record.physical_opening_record_ids),
        "opening_universe_status": universe.status.value,
        "opening_universe_reason_codes": list(universe.reason_codes),
        "source_decode_complete": universe.source_decode_complete,
        "semantic_enumeration_complete": universe.semantic_enumeration_complete,
        "decision_scope_complete": universe.decision_scope_complete,
        "accounted_member_count": 0 if universe_record is None else len(universe_record.accounted_member_ids),
        "host_bound_count": sum(1 for x in wall_opening.opening_bindings if x.host_wall_id is not None),
        "canonical_opening_count": len(opening_composition.canonical_openings),
        "kind_resolved_count": sum(1 for x in opening_composition.canonical_openings if x.opening_kind),
        "area_resolved_count": sum(1 for x in opening_composition.canonical_openings if x.area_m2 is not None),
        "opening_area_quantity_count": len(area_quantities),
        "opening_count_quantity_count": len(count_quantities),
        "residual_visible_count": len(residual_rows),
        "conflict_visible_count": len(conflict_rows),
        "residual_visible_rows": residual_rows,
        "conflict_visible_rows": conflict_rows,
        "opening_count_quantities": [
            {
                "quantity_id": q.quantity_id,
                "value": q.value,
                "unit": q.unit,
                "input_entity_ids": list(q.input_entity_ids),
                "evidence_ids": list(q.evidence_ids),
                "metadata": dict(q.metadata or {}),
            }
            for q in count_quantities
        ],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
