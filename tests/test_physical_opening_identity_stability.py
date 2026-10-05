from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _g17_opening_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320.0, height=220.0)
    for y in (100.0, 110.0):
        page.draw_line(
            fitz.Point(20.0, y),
            fitz.Point(100.0, y),
            color=(0, 0, 0),
            width=1,
        )
        page.draw_line(
            fitz.Point(140.0, y),
            fitz.Point(260.0, y),
            color=(0, 0, 0),
            width=1,
        )
    for x in (100.0, 140.0):
        page.draw_line(
            fitz.Point(x, 100.0),
            fitz.Point(x, 110.0),
            color=(0, 0, 0),
            width=1,
        )
    payload = bytes(doc.tobytes())
    doc.close()
    return payload


def _resolved_opening_ids(
    source_bytes: bytes,
    *,
    producer_method: str,
    producer_version: str,
) -> tuple[str, tuple[str, ...]]:
    source = SourceVisibilityProducer(
        producer_method=producer_method,
        producer_version=producer_version,
    )
    published = source.ingest_native_pdf_bytes(
        document_id="physical-opening-stable-identity",
        source_bytes=source_bytes,
        source_locator="memory://physical-opening-stable-identity.pdf",
        page_ids=("1",),
    )
    authority = PhysicalOpeningAuthority(source.authority())

    record_ids: set[str] = set()
    for observation_id in published.visible_observation_ids:
        result = authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            record_ids.add(result.existence_record.record_id)

    assert len(record_ids) == 1
    return published.snapshot.snapshot_id, tuple(sorted(record_ids))


def test_physical_opening_id_ignores_producer_method_and_version_churn() -> None:
    source_bytes = _g17_opening_pdf()
    first_snapshot, first_ids = _resolved_opening_ids(
        source_bytes,
        producer_method="physical-opening-identity-producer-a",
        producer_version="1.0.0",
    )
    second_snapshot, second_ids = _resolved_opening_ids(
        source_bytes,
        producer_method="physical-opening-identity-producer-b",
        producer_version="9.9.9",
    )

    # Snapshot identity remains evidence/reproducibility provenance and should
    # change when the producer implementation identity changes.
    assert first_snapshot != second_snapshot

    # The same source-owned physical geometry must not be renamed by that
    # evidence implementation change.
    assert first_ids == second_ids
