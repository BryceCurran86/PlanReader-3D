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
    assert ready["first_unclosed_gate"] == "ROOM_FLOOR_QUANTITY_READY"


def test_duplicate_floor_owner_never_selects_first():
    room = inspect_room_measurement_gates(
        _claim(_floor(9.25), _floor(9.25))
    )["rooms"][0]
    assert room["first_unclosed_gate"] == "CANONICAL_FLOOR_OWNERSHIP"
    assert room["floor_match_count"] == 2
    assert room["metric_area_m2"] is None
