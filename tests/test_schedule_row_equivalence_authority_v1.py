"""Schedule-row equivalence authority tests using real PDF text evidence."""
from __future__ import annotations

from collections import defaultdict

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_row_equivalence_authority import (
    SCHEDULE_ROW_EQUIVALENCE_DISTINCT,
    SCHEDULE_ROW_EQUIVALENCE_SCOPE_MISMATCH,
    SCHEDULE_ROW_EQUIVALENCE_TEXT_UNRESOLVED,
    ScheduleRowEquivalenceAuthority,
    ScheduleRowSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    page1 = doc.new_page(width=700, height=650)

    # Same rendered row emitted twice at the exact same coordinates. Native PDF
    # text extraction yields distinct observation ids but identical trusted
    # text/geometry.
    for _ in range(2):
        for text, x in (("W1", 50.0), ("900", 150.0), ("2100", 250.0)):
            page1.insert_text(fitz.Point(x, 500.0), text, color=(0, 0, 0))

    # Independent row with identical values at a different source location.
    for text, x in (("W1", 50.0), ("900", 150.0), ("2100", 250.0)):
        page1.insert_text(fitz.Point(x, 540.0), text, color=(0, 0, 0))

    # Same values and coordinates on another page are still distinct scope.
    page2 = doc.new_page(width=700, height=650)
    for text, x in (("W1", 50.0), ("900", 150.0), ("2100", 250.0)):
        page2.insert_text(fitz.Point(x, 500.0), text, color=(0, 0, 0))

    payload = doc.tobytes()
    doc.close()
    return payload


def _ingest():
    src = SourceVisibilityProducer(
        producer_method="schedule-row-equivalence-test",
        producer_version="1.0",
    )
    published = src.ingest_native_pdf_bytes(
        document_id="schedule-row-equivalence",
        source_bytes=_pdf(),
        source_locator="memory://schedule-row-equivalence.pdf",
    )
    return src, published


def _trusted_cells(src, published):
    authority = src.text_integrity_authority()
    result = []
    for observation_id in published.text_observation_ids:
        resolved = authority.resolve_text(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            resolved.status is EvidenceResolutionStatus.CORROBORATED
            and resolved.trusted_text is not None
            and resolved.receipt is not None
        ):
            result.append(
                (
                    observation_id,
                    str(resolved.trusted_text),
                    tuple(float(v) for v in resolved.receipt.geometry),
                    str(resolved.receipt.page_id),
                )
            )
    return result


def _selector(published, page_id: str, ids: tuple[str, ...]) -> ScheduleRowSelector:
    return ScheduleRowSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        schedule_page_id=page_id,
        schedule_row_observation_ids=ids,
    )


def test_duplicate_text_layer_rows_are_proven_same_by_authenticated_text_and_geometry() -> None:
    src, published = _ingest()
    cells = _trusted_cells(src, published)

    by_key = defaultdict(list)
    for observation_id, text, geometry, page_id in cells:
        if page_id == "1" and geometry[1] == 500.0:
            by_key[(text, geometry)].append(observation_id)

    assert len(by_key) == 3
    assert all(len(ids) == 2 for ids in by_key.values())

    ordered = sorted(by_key.items(), key=lambda item: item[0][1][0])
    left_ids = tuple(ids[0] for _key, ids in ordered)
    right_ids = tuple(ids[1] for _key, ids in ordered)

    authority = ScheduleRowEquivalenceAuthority.from_source_visibility_producer(src)
    result = authority.compare(
        _selector(published, "1", left_ids),
        _selector(published, "1", right_ids),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is True


def test_equal_row_values_at_different_geometry_are_proven_distinct() -> None:
    src, published = _ingest()
    cells = _trusted_cells(src, published)

    row_500 = tuple(
        observation_id
        for observation_id, _text, geometry, page_id in cells
        if page_id == "1" and geometry[1] == 500.0
    )[:3]
    row_540 = tuple(
        observation_id
        for observation_id, _text, geometry, page_id in cells
        if page_id == "1" and geometry[1] == 540.0
    )

    authority = ScheduleRowEquivalenceAuthority.from_source_visibility_producer(src)
    result = authority.compare(
        _selector(published, "1", row_500),
        _selector(published, "1", row_540),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert SCHEDULE_ROW_EQUIVALENCE_DISTINCT in result.reason_codes


def test_equal_row_values_on_different_pages_are_proven_distinct_scope() -> None:
    src, published = _ingest()
    cells = _trusted_cells(src, published)

    row_page1 = tuple(
        observation_id
        for observation_id, _text, geometry, page_id in cells
        if page_id == "1" and geometry[1] == 500.0
    )[:3]
    row_page2 = tuple(
        observation_id
        for observation_id, _text, geometry, page_id in cells
        if page_id == "2" and geometry[1] == 500.0
    )

    authority = ScheduleRowEquivalenceAuthority.from_source_visibility_producer(src)
    result = authority.compare(
        _selector(published, "1", row_page1),
        _selector(published, "2", row_page2),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proven_same is False
    assert SCHEDULE_ROW_EQUIVALENCE_DISTINCT in result.reason_codes
    assert SCHEDULE_ROW_EQUIVALENCE_SCOPE_MISMATCH in result.reason_codes


def test_unresolvable_row_observation_abstains() -> None:
    src, published = _ingest()
    cells = _trusted_cells(src, published)
    real_id = next(
        observation_id
        for observation_id, _text, geometry, page_id in cells
        if page_id == "1" and geometry[1] == 540.0
    )

    authority = ScheduleRowEquivalenceAuthority.from_source_visibility_producer(src)
    result = authority.compare(
        _selector(published, "1", (real_id,)),
        _selector(published, "1", ("forged-row-observation-id",)),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proven_same is False
    assert SCHEDULE_ROW_EQUIVALENCE_TEXT_UNRESOLVED in result.reason_codes
