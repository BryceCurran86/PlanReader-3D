from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import (
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(
            f"source sha mismatch: expected {EXPECTED_SOURCE_SHA}, got {source_sha}"
        )

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_opening_quantity_stack",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-opening-quantity-stack",
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
    quantities = publish_live_opening_area_quantities(opening_composition)

    canonical = tuple(opening_composition.canonical_openings)
    kind_counts = Counter(
        str(opening.opening_kind) if opening.opening_kind is not None else "None"
        for opening in canonical
    )
    area_basis_counts = Counter(
        str(opening.area_basis) if opening.area_basis is not None else "None"
        for opening in canonical
    )
    quantity_basis_counts = Counter(
        str(quantity.metadata.get("area_basis"))
        for quantity in quantities
    )

    rows = []
    quantity_by_opening = {
        str(quantity.metadata.get("canonical_opening_id")): quantity
        for quantity in quantities
    }
    for opening in sorted(canonical, key=lambda item: item.canonical_opening_id):
        quantity = quantity_by_opening.get(opening.canonical_opening_id)
        rows.append(
            {
                "opening_id": opening.canonical_opening_id,
                "page_id": opening.page_id,
                "structural_pattern": opening.structural_pattern,
                "opening_kind": opening.opening_kind,
                "host_wall_id": opening.host_wall_id,
                "host_frame_record_id": opening.host_frame_record_id,
                "area_m2": opening.area_m2,
                "area_basis": opening.area_basis,
                "figured_area_record_id": opening.figured_area_record_id,
                "quantity_published": quantity is not None,
                "quantity_value": None if quantity is None else quantity.value,
                "quantity_unit": None if quantity is None else quantity.unit,
                "quantity_record_id": None if quantity is None else quantity.evidence_id,
            }
        )

    payload = {
        "source_sha256": source_sha,
        "page_id": PAGE_ID,
        "wall_opening_status": wall_opening.status.value,
        "wall_opening_reasons": list(wall_opening.reason_codes),
        "physical_opening_record_count": (
            0
            if wall_opening.semantic_enumeration_result.record is None
            else len(
                wall_opening.semantic_enumeration_result.record.physical_opening_record_ids
            )
        ),
        "host_bound_count": sum(
            1
            for trace in wall_opening.opening_bindings
            if trace.host_wall_id is not None
        ),
        "host_frame_resolved_count": sum(
            1
            for trace in wall_opening.host_frames
            if trace.record_id is not None
        ),
        "opening_composition_status": opening_composition.status.value,
        "opening_composition_reasons": list(opening_composition.reason_codes),
        "canonical_opening_count": len(canonical),
        "canonical_host_resolved_count": sum(
            1 for opening in canonical if opening.host_wall_id
        ),
        "canonical_kind_resolved_count": sum(
            1 for opening in canonical if opening.opening_kind
        ),
        "canonical_area_resolved_count": sum(
            1 for opening in canonical if opening.area_m2 is not None
        ),
        "kind_counts": dict(sorted(kind_counts.items())),
        "area_basis_counts": dict(sorted(area_basis_counts.items())),
        "quantity_count": len(quantities),
        "quantity_basis_counts": dict(sorted(quantity_basis_counts.items())),
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
