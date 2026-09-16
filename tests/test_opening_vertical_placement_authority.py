"""Production regressions for opening vertical-placement authority."""
from __future__ import annotations

import dataclasses
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_vertical_placement_authority import (
    ROW_VERTICAL_BASIS_UNPROVEN,
    ROW_VERTICAL_ORDER_INVALID,
    ROW_VERTICAL_ROW_UNAVAILABLE,
    ROW_VERTICAL_UNITS_CONFLICT,
    ROW_VERTICAL_UNITS_UNPROVEN,
    OpeningVerticalPlacementAuthority,
    OpeningVerticalPlacementProducer,
    OpeningVerticalPlacementSelector,
    ScheduleRowVerticalPlacementAuthority,
    ScheduleRowVerticalPlacementProducer,
    ScheduleRowVerticalPlacementSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _draw_opening,
    _ingest,
    _opening_selector,
)

SCOPE = "vertical-placement-production:page-1"


def _pdf(
    *,
    sill_heading: str = "ROUGH-OPENING-SILL-MM",
    head_heading: str = "ROUGH-OPENING-HEAD-MM",
    sill_value: str = "900",
    head_value: str = "3000",
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=760, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    page.insert_text(fitz.Point(112.0, 106.0), "W1")
    xs = (50.0, 150.0, 250.0, 350.0, 520.0)
    for text, x in zip(
        ("MARK", "WIDTH", "HEIGHT", sill_heading, head_heading),
        xs,
    ):
        page.insert_text(fitz.Point(x, 500.0), text)
    for text, x in zip(("W1", "900", "2100", sill_value, head_value), xs):
        page.insert_text(fitz.Point(x, 530.0), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def _fixture(payload: bytes | None = None):
    src = SourceVisibilityProducer(
        producer_method="vertical-placement-production-test",
        producer_version="1.0",
    )
    published = _ingest(src, payload or _pdf(), "vertical-placement-production")
    opening_selector = _opening_selector(published, src.authority())
    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    binding = binder.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=SCOPE,
    )
    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.record is not None
    row_producer = ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(src)
    row_selector = ScheduleRowVerticalPlacementSelector(
        document_id=binding.record.document_id,
        revision_id=binding.record.revision_id,
        source_sha256=binding.record.source_sha256,
        snapshot_id=binding.record.snapshot_id,
        schedule_page_id=binding.record.schedule_page_id,
        schedule_row_observation_ids=binding.record.schedule_row_observation_ids,
    )
    opening_selector_v = OpeningVerticalPlacementSelector(
        document_id=binding.record.document_id,
        revision_id=binding.record.revision_id,
        source_sha256=binding.record.source_sha256,
        snapshot_id=binding.record.snapshot_id,
        decision_scope_id=binding.record.decision_scope_id,
        opening_record_id=binding.record.opening_record_id,
    )
    return src, binder, binding, row_producer, row_selector, opening_selector_v


def _opening_producer(binder, row_producer):
    return OpeningVerticalPlacementProducer.from_authorities(
        binding_authority=binder.authority(),
        row_vertical_placement_authority=row_producer.authority(),
    )


def test_producers_and_authorities_are_sealed() -> None:
    src = SourceVisibilityProducer(producer_method="seal", producer_version="1.0")
    with pytest.raises(TypeError):
        ScheduleRowVerticalPlacementProducer(src)
    with pytest.raises(ValueError):
        ScheduleRowVerticalPlacementAuthority({}, _seal=object())
    with pytest.raises(ValueError):
        OpeningVerticalPlacementAuthority({}, _seal=object())


def test_public_surfaces_are_selector_only_no_vertical_truth_inputs() -> None:
    forbidden = {
        "z0", "z1", "z0_mm", "z1_mm", "sill", "head", "height",
        "height_mm", "units", "raw_text", "confidence", "nearest", "radius",
    }
    assert not (
        set(inspect.signature(ScheduleRowVerticalPlacementProducer.publish_scope).parameters)
        & forbidden
    )
    assert not (
        set(inspect.signature(OpeningVerticalPlacementProducer.publish_scope).parameters)
        & forbidden
    )


def test_explicit_rough_opening_mm_placement_resolves_and_replays() -> None:
    _src, binder, _binding, row_producer, row_selector, opening_selector = _fixture()
    row_result = row_producer.publish_scope(row_selector)
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.z0_mm == 900.0
    assert row_result.evidence.z1_mm == 3000.0
    assert row_result.evidence.units == "mm"
    assert row_producer.authority().resolve(row_selector) == row_result

    producer = _opening_producer(binder, row_producer)
    result = producer.publish_scope(opening_selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.z0_mm == 900.0
    assert result.evidence.z1_mm == 3000.0
    assert producer.authority().resolve(opening_selector) == result


def test_explicit_metres_normalize_only_when_source_states_metres() -> None:
    _src, binder, _binding, row_producer, row_selector, opening_selector = _fixture(
        _pdf(
            sill_heading="ROUGH-OPENING-SILL-M",
            head_heading="ROUGH-OPENING-HEAD-M",
            sill_value="0.9m",
            head_value="3.0m",
        )
    )
    row_result = row_producer.publish_scope(row_selector)
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.z0_mm == 900.0
    assert row_result.evidence.z1_mm == 3000.0
    producer = _opening_producer(binder, row_producer)
    assert producer.publish_scope(opening_selector).status is EvidenceResolutionStatus.CORROBORATED


@pytest.mark.parametrize(
    "sill_heading,head_heading",
    [
        ("SILL-MM", "HEAD-MM"),
        ("FRAME-SILL-MM", "FRAME-HEAD-MM"),
        ("LEAF-SILL-MM", "LEAF-HEAD-MM"),
        ("CLEAR-OPENING-SILL-MM", "CLEAR-OPENING-HEAD-MM"),
    ],
)
def test_non_structural_vertical_semantics_abstain(
    sill_heading: str,
    head_heading: str,
) -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector_v = _fixture(
        _pdf(sill_heading=sill_heading, head_heading=head_heading)
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert ROW_VERTICAL_BASIS_UNPROVEN in result.reason_codes
    assert result.evidence is None


def test_rough_opening_without_units_does_not_assume_mm() -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector_v = _fixture(
        _pdf(
            sill_heading="ROUGH-OPENING-SILL",
            head_heading="ROUGH-OPENING-HEAD",
        )
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert ROW_VERTICAL_UNITS_UNPROVEN in result.reason_codes


def test_conflicting_header_and_cell_units_fail_closed() -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector_v = _fixture(
        _pdf(sill_value="0.9m", head_value="3.0m")
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert ROW_VERTICAL_UNITS_CONFLICT in result.reason_codes


def test_top_not_above_bottom_conflicts() -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector_v = _fixture(
        _pdf(sill_value="3000", head_value="900")
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert ROW_VERTICAL_ORDER_INVALID in result.reason_codes
    assert result.evidence is None


def test_height_only_does_not_imply_sill_zero() -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector_v = _fixture(
        _pdf(sill_heading="NOTE", head_heading="NOTE2", sill_value="", head_value="")
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


def test_wrong_opening_lineage_cannot_reuse_placement() -> None:
    _src, binder, _binding, row_producer, row_selector, opening_selector = _fixture()
    assert row_producer.publish_scope(row_selector).status is EvidenceResolutionStatus.CORROBORATED
    producer = _opening_producer(binder, row_producer)
    assert producer.publish_scope(opening_selector).status is EvidenceResolutionStatus.CORROBORATED
    tampered = dataclasses.replace(opening_selector, opening_record_id="wrong-opening")
    result = producer.publish_scope(tampered)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


def test_caller_invented_row_observation_id_cannot_mint_placement() -> None:
    _src, _binder, binding, row_producer, row_selector, _opening_selector_v = _fixture()
    assert binding.record is not None
    wrong = dataclasses.replace(
        row_selector,
        schedule_row_observation_ids=("caller-invented-row",),
    )
    result = row_producer.publish_scope(wrong)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert ROW_VERTICAL_ROW_UNAVAILABLE in result.reason_codes
