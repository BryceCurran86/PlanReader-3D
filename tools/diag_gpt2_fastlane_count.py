from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

import fitz

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    _row_groups_for_page,
    _schedule_entries_for_page,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
EXPECTED_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def status(value) -> str:
    return getattr(value, "value", str(value))


def main() -> None:
    source_bytes = PDF.read_bytes()
    sha = hashlib.sha256(source_bytes).hexdigest()
    if sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        page_ids = tuple(str(index + 1) for index in range(doc.page_count))

    source = SourceVisibilityProducer(
        producer_method="diag-gpt2-maryborough-opening-count-census",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-gpt2-maryborough-opening-count-census",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=page_ids,
    )

    integrity = source.text_integrity_authority()
    trusted = defaultdict(list)
    for observation_id in published.text_observation_ids:
        result = integrity.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        receipt = getattr(result, "receipt", None)
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.trusted_text is None
            or receipt is None
        ):
            continue
        trusted[str(receipt.page_id)].append(
            (
                observation_id,
                result.trusted_text,
                tuple(float(value) for value in receipt.geometry),
            )
        )

    rows = []
    for page_id in page_ids:
        grouped = _row_groups_for_page(trusted.get(page_id, ()))
        entries = _schedule_entries_for_page(grouped, int(page_id))
        for entry, observation_ids in entries:
            rows.append(
                {
                    "page_id": page_id,
                    "type_mark": entry.type_mark,
                    "width_mm": entry.width_mm,
                    "height_mm": entry.height_mm,
                    "description": entry.description,
                    "count": entry.count,
                    "count_explicit": bool(entry.count_explicit),
                    "dimension_basis": entry.dimension_basis,
                    "basis_source": entry.basis_source,
                    "parse_source": entry.parse_source,
                    "observation_ids": list(observation_ids),
                }
            )

    explicit = [row for row in rows if row["count_explicit"]]

    # The active plan topology page is independently source-authenticated by
    # the existing live project path. This diagnostic reads its current
    # producer-owned enumeration/completeness result; it does not promote it.
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("7",),
    )
    sem = composition.semantic_enumeration_result
    semrec = sem.record
    universe = composition.opening_universe_result
    unirec = universe.record

    binding_reason_counts = Counter(
        reason
        for trace in composition.opening_bindings
        for reason in trace.reason_codes
    )

    print(
        json.dumps(
            {
                "source_sha256": sha,
                "page_count": len(page_ids),
                "trusted_text_page_count": len(trusted),
                "schedule_entry_count": len(rows),
                "explicit_count_entry_count": len(explicit),
                "explicit_count_entries": explicit,
                "all_schedule_entries": rows,
                "semantic_enumeration": {
                    "status": status(sem.status),
                    "reason_codes": list(sem.reason_codes),
                    "record_present": semrec is not None,
                    "physical_opening_count": (
                        0 if semrec is None else len(semrec.physical_opening_record_ids)
                    ),
                    "structural_enumeration_complete": (
                        None if semrec is None else semrec.structural_enumeration_complete
                    ),
                    "physical_opening_universe_complete": (
                        None if semrec is None else semrec.physical_opening_universe_complete
                    ),
                    "residual_visible_observation_count": (
                        None if semrec is None else len(semrec.residual_visible_observation_ids)
                    ),
                    "conflict_observation_count": (
                        None if semrec is None else len(semrec.conflict_observation_ids)
                    ),
                },
                "opening_universe": {
                    "status": status(universe.status),
                    "source_decode_complete": universe.source_decode_complete,
                    "semantic_enumeration_complete": universe.semantic_enumeration_complete,
                    "decision_scope_complete": universe.decision_scope_complete,
                    "reason_codes": list(universe.reason_codes),
                    "record_present": unirec is not None,
                    "accounted_member_count": (
                        None if unirec is None else len(unirec.accounted_member_ids)
                    ),
                    "enumeration_state": (
                        None if unirec is None else unirec.enumeration_state
                    ),
                },
                "opening_binding_count": len(composition.opening_bindings),
                "resolved_opening_binding_count": sum(
                    1 for trace in composition.opening_bindings if trace.record_id
                ),
                "binding_reason_counts": dict(sorted(binding_reason_counts.items())),
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
