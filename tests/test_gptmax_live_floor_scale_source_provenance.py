"""Original physical scale -> exact canonical floor authority; no scale from strings."""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_floor_area_scale_provenance import (
    LiveFloorScaleSourceReceipt,
    source_owned_floor_scale_receipt,
    validated_floor_scale_metadata,
)
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_page_scale_calibration_authority import (
    ScaleSourceReading, ScaleSourceType,
    resolve_page_scale_calibration,
    scale_calibration_fingerprint,
)
from pb_physical_scale_authority import PhysicalScaleEvidence, PhysicalScaleSelector
from pb_physical_scale_calibration_bridge import (
    PHYSICAL_SCALE_CALIBRATION_RESOLVED,
    PhysicalScaleCalibrationBridgeResult,
)
from tests.test_live_floor_area_quantity_publication_integrity import (
    _claim_with, _source_area,
)
from tests.test_live_floor_finish_area_source_closed_export import _floor


def _typed_inputs():
    floor = replace(_floor(), metric_area_authority=MeasurementAuthorityType.PDF_SCALED.value)
    calibration = resolve_page_scale_calibration(
        page_no=1,
        sheet_label="",
        readings=(ScaleSourceReading(
            source_type=ScaleSourceType.SCALE_BAR.value,
            scale_text="1:50", ratio=50.0, confidence=1.0,
        ),),
        revision_id="rev-1",
    )
    physical = PhysicalScaleEvidence(
        selector=PhysicalScaleSelector(
            document_id=floor.document_id, revision_id=floor.revision_id,
            source_sha256=floor.source_sha256, snapshot_id=floor.snapshot_id,
            page_id=floor.page_id, viewport_id=floor.viewport_id,
        ),
        record_id="source-native-physical-scale-1",
        source_kind="native_graphic_scale_bar",
        source_span_pt=float(calibration.px_per_m),
        physical_span_mm=1000.0,
        points_per_mm=float(calibration.px_per_m / 1000.0),
        mm_per_point=float(1000.0 / calibration.px_per_m),
        source_segment_observation_ids=("original-scale-ink",),
        source_text_observation_ids=("original-scale-text",),
        viewport_id=floor.viewport_id,
    )
    physical = replace(
        physical,
        record_id=stable_contract_id(
            "physical_scale_v1",
            {
                "selector": physical.selector.key,
                "source_kind": physical.source_kind,
                "source_span_pt": round(physical.source_span_pt, 12),
                "physical_span_mm": round(physical.physical_span_mm, 9),
                "points_per_mm": round(physical.points_per_mm, 15),
                "source_segment_observation_ids": physical.source_segment_observation_ids,
                "source_text_observation_ids": physical.source_text_observation_ids,
            },
            digest_chars=32,
        ),
    )
    source = replace(
        _source_area(),
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        metadata={
            **_source_area().metadata,
            "scale_fingerprint": scale_calibration_fingerprint(calibration),
            "room_snapshot_id": floor.snapshot_id,
            "source_room_face_record_id": floor.source_room_face_record_id,
        },
    )
    bridge = PhysicalScaleCalibrationBridgeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(PHYSICAL_SCALE_CALIBRATION_RESOLVED,),
        calibration=calibration,
        physical_scale_evidence=physical,
    )
    return floor, source, bridge


def _binding():
    floor, source, bridge = _typed_inputs()
    receipt = source_owned_floor_scale_receipt(floor=floor, quantity=source, bridge=bridge)
    assert receipt is not None
    return floor, source, bridge, receipt


def _claim(source, floor, *receipts):
    return replace(
        _claim_with(source),
        canonical_floors=(floor,),
        source_owned_floor_scale_receipts=tuple(receipts),
    )


def test_exact_original_source_scale_reaches_floor_quantity_and_only_after_source_receipt():
    floor, source, bridge, receipt = _binding()
    without = publish_live_floor_area_quantities(_claim(source, floor))
    assert len(without) == 1
    assert without[0].authority == "pdf_scaled"
    assert "resolved_scale_id" not in without[0].metadata
    assert "scale_status" not in without[0].metadata
    actual = publish_live_floor_area_quantities(_claim(source, floor, receipt))
    assert len(actual) == 1
    assert actual[0].quantity_id == without[0].quantity_id
    assert actual[0].value == without[0].value
    assert actual[0].metadata["resolved_scale_id"] == bridge.physical_scale_evidence.record_id
    assert actual[0].metadata["scale_status"] == "resolved"
    assert actual[0].metadata["scale_conflicts"] == ()
    assert actual[0].metadata["scale_fingerprint"] == scale_calibration_fingerprint(bridge.calibration)


def test_copied_physical_scale_id_is_not_original_producer_record():
    floor, source, bridge, receipt = _binding()
    forged = replace(receipt.physical_scale_evidence, record_id="user-supplied-scale-identifier")
    assert source_owned_floor_scale_receipt(
        floor=floor, quantity=source,
        bridge=replace(bridge, physical_scale_evidence=forged)
    ) is None
    assert validated_floor_scale_metadata(
        replace(receipt, physical_scale_evidence=forged),
        floor=floor, source=source,
    ) is None


def test_no_borrowed_metadata_can_grant_commercial_scale_without_original_receipt():
    floor, source, _bridge = _typed_inputs()
    poison = replace(source, metadata={
        **source.metadata,
        "resolved_scale_id": "forged",
        "scale_status": "resolved",
        "scale_conflicts": (),
    })
    out = publish_live_floor_area_quantities(_claim(poison, floor))
    assert len(out) == 1
    assert not {"resolved_scale_id", "scale_status", "scale_conflicts"} & set(out[0].metadata)


def test_documented_dimension_floor_publication_unchanged():
    original = _claim_with(_source_area())
    first = publish_live_floor_area_quantities(original)
    new = replace(original, source_owned_floor_scale_receipts=())
    assert publish_live_floor_area_quantities(new) == first


def test_source_scale_receipt_not_manually_constructible():
    floor, source, bridge = _typed_inputs()
    legit = source_owned_floor_scale_receipt(floor=floor, quantity=source, bridge=bridge)
    assert legit is not None
    with pytest.raises(TypeError, match="producer-owned bridge"):
        LiveFloorScaleSourceReceipt(
            **{k: getattr(legit, k) for k in legit.__dataclass_fields__ if k != "_seal"}
        )


@pytest.mark.parametrize("field,new_value", [
    ("document_id", "foreign-document"),
    ("revision_id", "stale-revision"),
    ("source_sha256", "b" * 64),
    ("snapshot_id", "other-snapshot"),
    ("page_id", "2"),
    ("viewport_id", "other-viewport"),
    ("canonical_floor_id", "other-canonical-floor"),
    ("physical_floor_surface_id", "another-floor"),
    ("source_room_face_record_id", "other-source-face"),
    ("room_entity_id", "another-room"),
    ("room_area_quantity_id", "another-upstream-area"),
    ("scale_fingerprint", "replayed-wrong-calibration-fingerprint"),
])
def test_source_receipt_identity_tampering_never_grants_scale(field, new_value):
    floor, source, _bridge, receipt = _binding()
    invalid = replace(receipt, **{field: new_value})
    assert validated_floor_scale_metadata(invalid, floor=floor, source=source) is None
    output = publish_live_floor_area_quantities(_claim(source, floor, invalid))
    assert len(output) == 1
    assert "resolved_scale_id" not in output[0].metadata


def test_duplicate_or_competing_physical_scale_receipts_fail_closed():
    floor, source, _bridge, receipt = _binding()
    competing = replace(receipt, physical_scale_evidence=replace(
        receipt.physical_scale_evidence, record_id="another-original-scale-bar"
    ))
    for candidates in ((receipt, receipt), (receipt, competing), (competing, receipt)):
        out = publish_live_floor_area_quantities(_claim(source, floor, *candidates))
        assert len(out) == 1 and "resolved_scale_id" not in out[0].metadata


def test_unverified_or_conflicted_calibration_cannot_become_floor_scale():
    floor, source, bridge, _receipt = _binding()
    invalid = (
        replace(bridge, status=EvidenceResolutionStatus.CONFLICT),
        replace(bridge, reason_codes=("physical_scale_calibration_invalid",)),
        replace(bridge, calibration=replace(bridge.calibration, status="conflicting", is_verified=False)),
        replace(bridge, physical_scale_evidence=None),
    )
    for altered in invalid:
        assert source_owned_floor_scale_receipt(
            floor=floor, quantity=source, bridge=altered
        ) is None


def test_missing_or_drifting_native_scale_ink_and_text_proof_is_rejected():
    floor, source, bridge, _receipt = _binding()
    physical = bridge.physical_scale_evidence
    invalid = (
        replace(physical, source_segment_observation_ids=()),
        replace(physical, source_text_observation_ids=()),
        replace(physical, source_text_observation_ids=("repeated", "repeated")),
        replace(physical, source_kind="copied_title_block_scale"),
        replace(physical, viewport_id=None),
        replace(physical, points_per_mm=physical.points_per_mm * 2.0),
        replace(physical, source_span_pt=physical.source_span_pt * 2.0),
    )
    for altered in invalid:
        assert source_owned_floor_scale_receipt(
            floor=floor, quantity=source,
            bridge=replace(bridge, physical_scale_evidence=altered),
        ) is None


def test_replayed_source_area_calibration_or_page_identity_is_not_authority():
    floor, source, bridge, _receipt = _binding()
    mismatches = (
        replace(source, metadata={**source.metadata, "scale_fingerprint": "foreign"}),
        replace(source, metadata={**source.metadata, "source_sha256": "b" * 64}),
        replace(source, metadata={**source.metadata, "page_no": "01"}),
        replace(source, metadata={**source.metadata, "viewport_id": "foreign"}),
        replace(source, metadata={**source.metadata, "room_snapshot_id": "foreign"}),
        replace(source, metadata={**source.metadata, "source_room_face_record_id": "foreign"}),
        replace(source, quantity_id="other-area"),
    )
    for wrong in mismatches:
        assert source_owned_floor_scale_receipt(
            floor=floor, quantity=wrong, bridge=bridge
        ) is None


def test_bounded_original_page_scale_can_bind_derived_room_viewport_but_not_other_ink():
    floor, source, bridge, _receipt = _binding()
    # A source room can have page-wide physical geometry and an independently
    # source-proven original PDF scale bar. The emitted area owns one derived
    # viewport ID, and that is the receipt's address.
    floor = replace(floor, viewport_id=None)
    phys = bridge.physical_scale_evidence
    source_owned_page = replace(
        bridge, physical_scale_evidence=replace(
            phys,
            selector=replace(phys.selector, viewport_id=None),
            viewport_id=None,
        ),
    )
    receipt = source_owned_floor_scale_receipt(floor=floor, quantity=source, bridge=source_owned_page)
    assert receipt is not None
    assert receipt.viewport_id == source.metadata["viewport_id"]
    assert validated_floor_scale_metadata(receipt, floor=floor, source=source) is not None
    bad = replace(source_owned_page.physical_scale_evidence,
                  selector=replace(phys.selector, viewport_id="unrelated-viewport"),
                  viewport_id="unrelated-viewport")
    assert source_owned_floor_scale_receipt(
        floor=floor, quantity=source,
        bridge=replace(source_owned_page, physical_scale_evidence=bad)
    ) is None


def test_tamper_mutable_calibration_after_receipt_creation_invalidates_original_fingerprint():
    floor, source, _bridge, receipt = _binding()
    receipt.calibration.px_per_m *= 2.0
    assert validated_floor_scale_metadata(receipt, floor=floor, source=source) is None



def test_second_source_scale_claim_for_same_physical_floor_or_upstream_room_blocks_authority():
    floor, source, _bridge, receipt = _binding()
    # Different canonical address with the SAME physical owner is still a
    # competing scale claim; a one-to-one floor cannot silently select one.
    variants = (
        replace(receipt, canonical_floor_id="other-canonical-floor"),
        replace(receipt, source_room_face_record_id="other-source-face"),
        replace(receipt, room_area_quantity_id="another-upstream-area"),
    )
    for competing in variants:
        output = publish_live_floor_area_quantities(_claim(source, floor, receipt, competing))
        assert len(output) == 1
        assert "resolved_scale_id" not in output[0].metadata


def test_non_native_manual_or_unverified_scale_cannot_borrow_original_bar_identity():
    floor, source, bridge, _receipt = _binding()
    original = bridge.calibration
    for status, source_type, method in (
        ("user_approved", "manual", "MANUAL"),
        ("valid", "title_block", "TITLE_BLOCK"),
        ("provisional", "scale_bar", "SCALE_BAR"),
        ("valid", "scale_bar", "OCR_TEXT"),
    ):
        other = replace(original, status=status, source_type=source_type, method=method)
        changed = replace(source, metadata={
            **source.metadata, "scale_fingerprint": scale_calibration_fingerprint(other)
        })
        assert source_owned_floor_scale_receipt(
            floor=floor,
            quantity=changed,
            bridge=replace(bridge, calibration=other),
        ) is None
