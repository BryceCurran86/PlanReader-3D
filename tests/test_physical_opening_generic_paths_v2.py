from __future__ import annotations

import fitz
import pb_physical_opening_authority as opening_module

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



def test_dense_unrelated_segments_do_not_restore_gap_times_all_segment_scans(
    monkeypatch,
) -> None:
    base = (
        ((20.0, 100.0), (250.0, 100.0)),
        ((290.0, 100.0), (650.0, 100.0)),
        ((250.0, 100.0), (250.0, 140.0)),
        ((290.0, 100.0), (290.0, 140.0)),
    )
    noise = tuple(
        (
            (20.0 + float(index % 120) * 5.0, 220.0 + float(index // 120) * 3.0),
            (22.0 + float(index % 120) * 5.0, 222.0 + float(index // 120) * 3.0),
        )
        for index in range(720)
    )
    payload = _pdf((*base, *noise))

    source = SourceVisibilityProducer(
        producer_method="generic-path-dense-noise-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="generic-path-dense-noise",
        source_bytes=payload,
        source_locator="memory://generic-path-dense-noise.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())

    original_hypot = opening_module.math.hypot
    calls = 0

    def counted_hypot(*args):
        nonlocal calls
        calls += 1
        return original_hypot(*args)

    monkeypatch.setattr(opening_module.math, "hypot", counted_hypot)

    result = physical.prove_existence(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=published.visible_observation_ids[0],
        )
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PHYSICAL_OPENING_EXISTS
    assert result.existence_record is not None
    assert (
        result.existence_record.structural_pattern
        == GAP_CORROBORATED_WINDOW_JAMB_PAIR
    )
    # A brute-force left/right jamb scan alone would make roughly
    # 4 * len(noise) endpoint-distance calls for this single gap.
    assert calls < len(noise) * 2
