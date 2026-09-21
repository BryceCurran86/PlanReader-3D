from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    GAP_CORROBORATED_DOOR_JAMB_LEAF,
    GAP_CORROBORATED_WINDOW_JAMB_PAIR,
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf(lines: tuple[tuple[tuple[float, float], tuple[float, float]], ...]) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=700, height=300)
    for first, second in lines:
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def _resolved_patterns(payload: bytes) -> set[str]:
    source = SourceVisibilityProducer(
        producer_method="generic-path-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="generic-path",
        source_bytes=payload,
        source_locator="memory://generic-path.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    patterns: set[str] = set()
    record_ids: set[str] = set()

    for observation_id in published.visible_observation_ids:
        result = physical.prove_existence(
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
            patterns.add(result.existence_record.structural_pattern)
            record_ids.add(result.existence_record.record_id)

    assert len(record_ids) == 1
    return patterns


def test_gap_plus_door_jamb_leaf_is_independent_physical_existence_path() -> None:
    payload = _pdf(
        (
            ((20.0, 100.0), (250.0, 100.0)),
            ((310.0, 100.0), (650.0, 100.0)),
            ((250.0, 100.0), (250.0, 140.0)),
        )
    )
    assert _resolved_patterns(payload) == {GAP_CORROBORATED_DOOR_JAMB_LEAF}


def test_gap_plus_window_jamb_pair_is_independent_physical_existence_path() -> None:
    payload = _pdf(
        (
            ((20.0, 100.0), (250.0, 100.0)),
            ((290.0, 100.0), (650.0, 100.0)),
            ((250.0, 100.0), (250.0, 140.0)),
            ((290.0, 100.0), (290.0, 140.0)),
        )
    )
    assert _resolved_patterns(payload) == {GAP_CORROBORATED_WINDOW_JAMB_PAIR}


def _resolved_record_ids(payload: bytes) -> set[str]:
    source = SourceVisibilityProducer(
        producer_method="generic-path-negative-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="generic-path-negative",
        source_bytes=payload,
        source_locator="memory://generic-path-negative.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    record_ids: set[str] = set()
    for observation_id in published.visible_observation_ids:
        result = physical.prove_existence(
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
    return record_ids


def test_wall_gap_alone_does_not_mint_physical_opening() -> None:
    payload = _pdf(
        (
            ((20.0, 100.0), (250.0, 100.0)),
            ((310.0, 100.0), (650.0, 100.0)),
        )
    )
    assert _resolved_record_ids(payload) == set()


def test_perpendicular_doorish_segment_without_wall_gap_does_not_mint_opening() -> None:
    payload = _pdf(
        (
            ((20.0, 100.0), (650.0, 100.0)),
            ((250.0, 100.0), (250.0, 140.0)),
        )
    )
    assert _resolved_record_ids(payload) == set()


def test_window_jamb_pair_without_wall_gap_does_not_mint_opening() -> None:
    payload = _pdf(
        (
            ((20.0, 100.0), (650.0, 100.0)),
            ((250.0, 100.0), (250.0, 140.0)),
            ((280.0, 100.0), (280.0, 140.0)),
        )
    )
    assert _resolved_record_ids(payload) == set()
