from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OPENING_LABEL_DIMENSION_AMBIGUOUS,
    OPENING_LABEL_DIMENSION_RESOLVED,
    OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE,
    OpeningLabelDimensionProducer,
    parse_opening_label_dimensions,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def test_parser_accepts_full_metric_opening_labels_without_resolving_axis_order() -> None:
    window = parse_opening_label_dimensions("1,200 - 1,810 asw")
    assert window is not None
    assert window.dimension_values_mm == (1200.0, 1810.0)
    assert window.semantic_kind == "window"
    assert window.area_m2 == pytest.approx(2.172)
    assert window.compact_hundreds_used is False

    door = parse_opening_label_dimensions("2,100 - 4,800 Panel Lift Door")
    assert door is not None
    assert door.dimension_values_mm == (2100.0, 4800.0)
    assert door.semantic_kind == "door"
    assert door.area_m2 == pytest.approx(10.08)


def test_parser_accepts_typed_compact_hundred_mm_notation_only() -> None:
    door = parse_opening_label_dimensions("21 - 15 - asd")
    assert door is not None
    assert door.dimension_values_mm == (2100.0, 1500.0)
    assert door.semantic_kind == "door"
    assert door.compact_hundreds_used is True

    window = parse_opening_label_dimensions("18 - 09 adh")
    assert window is not None
    assert window.dimension_values_mm == (1800.0, 900.0)
    assert window.semantic_kind == "window"

    # Untyped two-digit arithmetic/text cannot silently become dimensions.
    assert parse_opening_label_dimensions("21 - 15") is None


def test_parser_keeps_single_dimension_separate_and_rejects_clear_zone_text() -> None:
    sliding = parse_opening_label_dimensions("1,200 vsd")
    assert sliding is not None
    assert sliding.dimension_values_mm == (1200.0,)
    assert sliding.semantic_kind == "door"
    assert sliding.area_m2 is None

    assert parse_opening_label_dimensions("900x1200 CLEAR") is None
    assert parse_opening_label_dimensions("04 - 06 Niche") is None
    assert parse_opening_label_dimensions("Scale 1:100") is None


def _pdf(
    *,
    labels: tuple[tuple[float, float, str], ...],
) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=220.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((140.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        for x, y, text in labels:
            page.insert_text(fitz.Point(x, y), text, fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _ingest(payload: bytes, name: str):
    source = SourceVisibilityProducer(
        producer_method="opening-label-dimension-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-label:" + name,
        source_bytes=payload,
        source_locator="fixture:" + name,
    )
    return source, published


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _opening_selector(source, published) -> ObservationSelector:
    physical = source.physical_opening_authority()
    found = {}
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = selector
    assert len(found) == 1
    return next(iter(found.values()))


def test_producer_binds_one_figured_pair_by_gap_projection_not_nearest_choice() -> None:
    source, published = _ingest(
        _pdf(labels=((88.0, 124.0, "900 - 1200 asw"),)),
        "positive",
    )
    selector = _opening_selector(source, published)
    producer = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    result = producer.publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_LABEL_DIMENSION_RESOLVED,)
    assert result.evidence is not None
    assert result.evidence.dimension_values_mm == (900.0, 1200.0)
    assert result.evidence.semantic_kind == "window"
    assert result.evidence.area_m2 == pytest.approx(1.08)
    assert result.evidence.axis_order_resolved is False
    assert result.evidence.source_text_observation_ids


def test_two_distinct_eligible_callouts_conflict_instead_of_picking_closest() -> None:
    source, published = _ingest(
        _pdf(
            labels=(
                (88.0, 121.0, "900 - 1200 asw"),
                (88.0, 130.0, "1000 - 1200 asw"),
            )
        ),
        "ambiguous",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None
    assert OPENING_LABEL_DIMENSION_AMBIGUOUS in result.reason_codes


def test_spatially_remote_label_cannot_bind_even_when_text_is_plausible() -> None:
    source, published = _ingest(
        _pdf(labels=((235.0, 124.0, "900 - 1200 asw"),)),
        "remote",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE in result.reason_codes
