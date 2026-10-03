from __future__ import annotations

from dataclasses import replace

import pytest

from pb_document_joinery_head_height_authority import (
    DocumentJoineryHeadHeightEvidence,
    DocumentJoineryHeadHeightResult,
    JOINERY_HEAD_HEIGHT_RESOLVED,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_joinery_figured_area_authority import (
    OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED,
    OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT,
    OPENING_JOINERY_FIGURED_AREA_RESOLVED,
    OPENING_JOINERY_FIGURED_AREA_SINGLE_WIDTH_REQUIRED,
    resolve_opening_joinery_figured_area,
)
from pb_opening_kind_authority import resolve_opening_kind
from pb_opening_label_dimension_authority import OpeningLabelDimensionEvidence
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningExistenceRecord,
)


SHA = "a" * 64


def _opening() -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id="opening-1",
        source_observation_ids=("source-opening-1",),
        source_lineage_root_ids=("root-opening-1",),
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        page_id="3",
        viewport_id="vp-plan-1",
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=("fixture",),
        producer_method="fixture",
        producer_version="1",
        producer_generation=1,
    )


def _label(
    *,
    values: tuple[float, ...] = (870.0,),
    semantic_kind: str | None = "door",
    area_m2: float | None = None,
) -> OpeningLabelDimensionEvidence:
    return OpeningLabelDimensionEvidence(
        evidence_id="label-1",
        opening_record_id="opening-1",
        page_id="3",
        viewport_id="vp-plan-1",
        source_text_observation_ids=("text-width-1",),
        raw_text="870 cs",
        dimension_values_mm=values,
        semantic_kind=semantic_kind,
        area_m2=area_m2,
        axis_order_resolved=False,
    )


def _joinery_result(
    *,
    height_mm: float = 2100.0,
) -> DocumentJoineryHeadHeightResult:
    return DocumentJoineryHeadHeightResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(JOINERY_HEAD_HEIGHT_RESOLVED,),
        evidence=DocumentJoineryHeadHeightEvidence(
            evidence_id="joinery-height-1",
            document_id="doc-1",
            revision_id="rev-1",
            source_sha256=SHA,
            snapshot_id="snap-1",
            head_height_mm=height_mm,
            source_page_ids=("4", "5"),
            source_text_observation_ids=("text-height-1", "text-height-2"),
            raw_texts=("JOINERY HEIGHTS TO BE 2100 AFL U.N.O.",),
        ),
    )


def _door_kind():
    return resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        label_kind="door",
    )


def test_single_figured_door_width_and_document_joinery_height_publish_area() -> None:
    result = resolve_opening_joinery_figured_area(
        opening=_opening(),
        label=_label(),
        joinery_height=_joinery_result(),
        opening_kind=_door_kind(),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_JOINERY_FIGURED_AREA_RESOLVED,)
    assert result.evidence is not None
    assert result.evidence.width_mm == 870.0
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.area_m2 == pytest.approx(1.827)
    assert result.evidence.basis == "figured_opening_width_x_joinery_height"
    assert result.evidence.source_text_observation_ids == (
        "text-width-1",
        "text-height-1",
        "text-height-2",
    )


def test_joinery_height_route_does_not_apply_to_window() -> None:
    kind = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        label_kind="window",
    )
    result = resolve_opening_joinery_figured_area(
        opening=_opening(),
        label=_label(semantic_kind="window"),
        joinery_height=_joinery_result(),
        opening_kind=kind,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED in result.reason_codes


def test_two_axis_label_stays_on_existing_figured_pair_route() -> None:
    result = resolve_opening_joinery_figured_area(
        opening=_opening(),
        label=_label(values=(1200.0, 1810.0), area_m2=2.172),
        joinery_height=_joinery_result(),
        opening_kind=_door_kind(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_JOINERY_FIGURED_AREA_SINGLE_WIDTH_REQUIRED in result.reason_codes


def test_joinery_height_lineage_must_match_physical_opening() -> None:
    height = _joinery_result()
    assert height.evidence is not None
    height = replace(
        height,
        evidence=replace(height.evidence, revision_id="other-rev"),
    )
    result = resolve_opening_joinery_figured_area(
        opening=_opening(),
        label=_label(),
        joinery_height=height,
        opening_kind=_door_kind(),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None
    assert OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT in result.reason_codes


def test_label_must_belong_to_exact_physical_opening() -> None:
    result = resolve_opening_joinery_figured_area(
        opening=_opening(),
        label=replace(_label(), opening_record_id="opening-other"),
        joinery_height=_joinery_result(),
        opening_kind=_door_kind(),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None
    assert OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT in result.reason_codes


def test_conflicting_opening_kind_blocks_figured_joinery_area() -> None:
    kind = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        schedule_trade_type="windows",
        label_kind="door",
    )
    result = resolve_opening_joinery_figured_area(
        opening=_opening(),
        label=_label(),
        joinery_height=_joinery_result(),
        opening_kind=kind,
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None
    assert OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED in result.reason_codes
