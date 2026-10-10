"""B03 room diagnostic never treats page-point area as metric evidence."""
from types import SimpleNamespace as Row

from tools.diag_gpt2_room_measurement_gates import inspect_room_measurement_gates


def _room():
    return Row(
        room_label="FREEZER", physical_room_id="room-1",
        canonical_room_id="canonical-1", source_room_face_record_id="face-1",
        room_label_binding_record_id="label-1",
        room_label_evidence_ids=("label-evidence-1",),
        evidence_ids=("wall-source-1",), page_id="7", viewport_id=None,
        geometry_complete=True, area_page_pts2=3666.592524,
    )


def _floor(area=None, quantity_id=None):
    return Row(
        room_entity_id="canonical-1", canonical_floor_id="floor-1",
        metric_area_m2=area, metric_geometry_complete=area is not None,
        metric_area_authority="figured_dimensions" if area else None,
        metric_area_quantity_id=quantity_id,
        commercial_quantity_authority=bool(quantity_id),
    )


def _claim(*floors):
    return Row(
        canonical_rooms=(_room(),), canonical_floors=floors,
        same_view_room_area_first_failure_codes=(("room-1", "dimension_unavailable"),),
        cross_view_room_area_first_failure_codes=(("room-1", "support_label_unavailable"),),
        physical_scale_first_failure_codes=(("room-1", ("scale_unavailable",)),),
        room_area_quantity_evidence=(), floor_finish_quantity_evidence=(),
        ceiling_lining_quantity_evidence=(), reason_codes=(),
        canonical_room_status="corroborated",
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(7,),
        canonical_wall_status="corroborated",
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(7,),
        canonical_floor_status="corroborated",
        canonical_floor_reason_codes=(),
    )


def test_source_polygon_area_never_promoted_to_metric():
    room = inspect_room_measurement_gates(_claim(_floor()))["rooms"][0]
    assert room["first_unclosed_gate"] == "METRIC_MEASUREMENT"
    assert room["metric_area_m2"] is None
    assert room["area_page_pts2"] == 3666.592524
    assert room["area_page_pts2_is_not_metric"] is True
    assert room["source_first_failure_reasons"]["physical_scale"] == [
        "scale_unavailable"
    ]


def test_verified_metric_floor_requires_commercial_quantity_handoff():
    row = inspect_room_measurement_gates(_claim(_floor(9.25)))["rooms"][0]
    assert row["first_unclosed_gate"] == "FLOOR_QUANTITY_PUBLICATION"
    assert row["metric_area_m2"] == 9.25
    ready = inspect_room_measurement_gates(
        _claim(_floor(9.25, "firm-q-1"))
    )["rooms"][0]
    # A caller-supplied flag on a synthetic row is not a producer reissue.
    assert ready["first_unclosed_gate"] == "FLOOR_QUANTITY_PUBLICATION"
    assert ready["floor_area_reissued_quantity_id"] is None
    assert ready["canonical_room_area_reissued_quantity_id"] is None


def test_duplicate_floor_owner_never_selects_first():
    room = inspect_room_measurement_gates(
        _claim(_floor(9.25), _floor(9.25))
    )["rooms"][0]
    assert room["first_unclosed_gate"] == "CANONICAL_FLOOR_OWNERSHIP"
    assert room["floor_match_count"] == 2
    assert room["metric_area_m2"] is None


def _documented_area_claim(*, source_sha="source-sha-verified", revision="revision-a"):
    floor = _floor(9.25, "owned-quantity-1")
    floor.metric_geometry_complete = False
    floor.commercial_quantity_authority = False
    floor.source_sha256 = "source-sha-verified"
    floor.revision_id = "revision-a"
    quantity = Row(
        quantity_id="owned-quantity-1",
        family="room_area",
        authority="documented_dimension",
        input_entity_ids=("producer-owned-source-room-1",),
        blocking_reasons=(),
        status="FIRM",
        value=9.25,
        unit="m2",
        abstained=False,
        evidence_ids=("source-area-evidence-1",),
        metadata={"source_sha256": source_sha, "revision_id": revision},
    )
    claim = _claim(floor)
    claim.room_area_quantity_evidence = (quantity,)
    return claim


def test_firm_documented_area_is_measured_without_metric_polygon() -> None:
    """A valid documented area does not imply a metrically scaled polygon."""
    room = inspect_room_measurement_gates(_documented_area_claim())["rooms"][0]
    assert room["metric_area_m2"] == 9.25
    assert room["metric_geometry_complete"] is False
    assert room["firm_documented_area_receipt"] is True
    assert room["first_unclosed_gate"] == "FLOOR_QUANTITY_PUBLICATION"


def test_stale_documented_area_receipt_does_not_bypass_metric_gate() -> None:
    for stale in (
        _documented_area_claim(source_sha="other-source-sha"),
        _documented_area_claim(revision="other-revision"),
    ):
        room = inspect_room_measurement_gates(stale)["rooms"][0]
        assert room["firm_documented_area_receipt"] is False
        assert room["first_unclosed_gate"] == "METRIC_MEASUREMENT"
        assert room["metric_area_m2"] is None


def test_duplicate_documented_receipt_ids_do_not_grant_area() -> None:
    claim = _documented_area_claim()
    claim.room_area_quantity_evidence = (
        *claim.room_area_quantity_evidence,
        claim.room_area_quantity_evidence[0],
    )
    room = inspect_room_measurement_gates(claim)["rooms"][0]
    assert room["firm_documented_area_receipt"] is False
    assert room["first_unclosed_gate"] == "METRIC_MEASUREMENT"


def test_wrong_family_or_untrusted_measurement_source_stays_unmeasured() -> None:
    for bad_field, value in (
        ("family", "wall_area"),
        ("authority", "raw_label_guess"),
        ("input_entity_ids", ()),
        ("blocking_reasons", ("conflicted_measurement",)),
    ):
        claim = _documented_area_claim()
        setattr(claim.room_area_quantity_evidence[0], bad_field, value)
        row = inspect_room_measurement_gates(claim)["rooms"][0]
        assert row["firm_documented_area_receipt"] is False, bad_field
        assert row["first_unclosed_gate"] == "METRIC_MEASUREMENT", bad_field


def test_conflicting_source_face_metadata_cannot_validate_documented_area() -> None:
    claim = _documented_area_claim()
    claim.canonical_floors[0].source_room_face_record_id = "physical-face-1"
    claim.room_area_quantity_evidence[0].metadata["source_room_face_record_id"] = "other-face"
    row = inspect_room_measurement_gates(claim)["rooms"][0]
    assert row["first_unclosed_gate"] == "METRIC_MEASUREMENT"
    assert row["firm_documented_area_receipt"] is False


def test_mismatched_source_page_rejects_documented_receipt() -> None:
    claim = _documented_area_claim()
    claim.canonical_floors[0].page_id = "7"
    claim.room_area_quantity_evidence[0].metadata["page_no"] = "8"
    row = inspect_room_measurement_gates(claim)["rooms"][0]
    assert row["firm_documented_area_receipt"] is False
    assert row["first_unclosed_gate"] == "METRIC_MEASUREMENT"


def test_mismatched_room_snapshot_rejects_documented_receipt() -> None:
    claim = _documented_area_claim()
    claim.canonical_floors[0].snapshot_id = "room-snapshot-1"
    claim.room_area_quantity_evidence[0].metadata["room_snapshot_id"] = "room-snapshot-2"
    row = inspect_room_measurement_gates(claim)["rooms"][0]
    assert row["firm_documented_area_receipt"] is False
    assert row["first_unclosed_gate"] == "METRIC_MEASUREMENT"



def test_malformed_documented_area_value_never_crashes_or_claims_metric() -> None:
    for invalid in (None, "not-a-number", "9.25", True, float("nan"),
                    float("inf"), -1.0, 0.0):
        claim = _documented_area_claim()
        claim.room_area_quantity_evidence[0].value = invalid
        row = inspect_room_measurement_gates(claim)["rooms"][0]
        assert row["firm_documented_area_receipt"] is False, invalid
        assert row["metric_area_m2"] is None, invalid
        assert row["first_unclosed_gate"] == "METRIC_MEASUREMENT", invalid


def test_missing_source_owner_sha_and_revision_cannot_prove_documented_area() -> None:
    for field in ("source_sha256", "revision_id"):
        claim = _documented_area_claim()
        setattr(claim.canonical_floors[0], field, "")
        claim.room_area_quantity_evidence[0].metadata[field] = ""
        row = inspect_room_measurement_gates(claim)["rooms"][0]
        assert row["firm_documented_area_receipt"] is False, field
        assert row["first_unclosed_gate"] == "METRIC_MEASUREMENT", field


def test_malformed_documented_receipt_metadata_fails_closed() -> None:
    for invalid in (None, "not-a-dict", ["not-a-pair"]):
        claim = _documented_area_claim()
        claim.room_area_quantity_evidence[0].metadata = invalid
        row = inspect_room_measurement_gates(claim)["rooms"][0]
        assert row["firm_documented_area_receipt"] is False, invalid
        assert row["metric_area_m2"] is None, invalid



def test_real_canonical_room_firm_receipt_traces_through_both_reissuers() -> None:
    from dataclasses import replace
    from tests.test_live_floor_area_quantity_publication_integrity import (
        _claim_with_canonical_room, _source_area,
    )

    claim = _claim_with_canonical_room(_source_area())
    owned = replace(
        claim.canonical_rooms[0],
        room_label="SOURCE-VERIFIED ROOM",
        room_label_binding_record_id="source-label-binding",
        room_label_evidence_ids=("source-label-evidence",),
    )
    claim = replace(claim, canonical_rooms=(owned,))
    report = inspect_room_measurement_gates(claim)
    assert report["reissued_floor_area_quantity_count"] == 1
    assert report["reissued_canonical_room_area_quantity_count"] == 1
    assert len(report["rooms"]) == 1
    room = report["rooms"][0]
    assert room["metric_area_m2"] == 8.64
    assert room["metric_geometry_complete"] is False
    assert room["firm_documented_area_receipt"] is True
    assert room["commercial_quantity_authority_flag"] is False
    assert room["floor_area_reissued_quantity_id"]
    assert room["canonical_room_area_reissued_quantity_id"]
    # Reissue is authenticated, but no sealing/customer-output verification
    # has run; the diagnostic may not claim a commercially completed row.
    assert room["first_unclosed_gate"] == "SEALED_CUSTOMER_PROJECTION_UNVERIFIED"


def test_competing_real_room_owner_can_reissue_floor_but_not_room() -> None:
    from dataclasses import replace
    from tests.test_live_floor_area_quantity_publication_integrity import (
        _claim_with_canonical_room, _source_area,
    )

    claim = _claim_with_canonical_room(_source_area())
    genuine = replace(
        claim.canonical_rooms[0],
        room_label="SOURCE-VERIFIED ROOM",
        room_label_binding_record_id="source-label-binding",
        room_label_evidence_ids=("source-label-evidence",),
    )
    competing = replace(
        genuine, canonical_room_id="competing-canonical-room",
        source_room_face_record_id="another-source-face",
        room_label=None, room_label_binding_record_id=None,
        room_label_evidence_ids=(),
    )
    claim = replace(claim, canonical_rooms=(genuine, competing))
    report = inspect_room_measurement_gates(claim)
    assert report["reissued_floor_area_quantity_count"] == 1
    assert report["reissued_canonical_room_area_quantity_count"] == 0
    assert len(report["rooms"]) == 1
    room = report["rooms"][0]
    assert room["floor_area_reissued_quantity_id"]
    assert room["canonical_room_area_reissued_quantity_id"] is None
    assert room["first_unclosed_gate"] == "CANONICAL_ROOM_AREA_REISSUE"
