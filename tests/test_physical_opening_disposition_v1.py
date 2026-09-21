from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE,
    PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    for first, second in (
        ((25.0, 60.0), (110.0, 60.0)),
        ((150.0, 60.0), (275.0, 60.0)),
        ((25.0, 75.0), (110.0, 75.0)),
        ((150.0, 75.0), (275.0, 75.0)),
        ((110.0, 60.0), (110.0, 75.0)),
        ((150.0, 60.0), (150.0, 75.0)),
        # Unrelated source-visible geometry outside the opening topology.
        ((320.0, 20.0), (380.0, 20.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def test_disposition_separates_opening_support_from_examined_noncandidate_geometry() -> None:
    source = SourceVisibilityProducer(
        producer_method="semantic-disposition-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="disposition",
        source_bytes=_pdf(),
        source_locator="memory://disposition.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())

    dispositions = []
    for observation_id in published.visible_observation_ids:
        result = physical.classify_disposition(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        dispositions.append(result)

    opening_support = [
        item for item in dispositions
        if item.disposition == PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT
    ]
    examined_noncandidates = [
        item for item in dispositions
        if item.disposition == PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE
    ]

    assert len(opening_support) == 6
    assert all(item.status is EvidenceResolutionStatus.CORROBORATED for item in opening_support)
    assert len(examined_noncandidates) == 1
    assert examined_noncandidates[0].status is EvidenceResolutionStatus.CORROBORATED
    assert examined_noncandidates[0].existence_record is None
