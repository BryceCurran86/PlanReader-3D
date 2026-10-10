"""Q70 diagnostic only: report earliest unsupported floor measurement stage."""
from types import SimpleNamespace

from tools.diag_lot16_room_face_scope import _floor_quantity_first_failure


def _floor(**updates):
    props = {
        "physical_floor_surface_identity_resolved": True,
        "physical_floor_surface_id": "physical-floor-1",
        "source_room_face_record_id": "source-face-1",
        "evidence_ids": ("source-face-1",),
        "metric_area_m2": 8.64,
        "metric_area_quantity_id": "qty-room-1",
        "metric_area_authority": "documented_dimension",
        "area_page_pts2": 320.0,
    }
    props.update(updates)
    return SimpleNamespace(**props)


def _room(**updates):
    props = {
        "room_label": "TEST ROOM",
        "room_label_binding_record_id": "room-label-binding-1",
        "room_label_evidence_ids": ("source-label-1",),
    }
    props.update(updates)
    return SimpleNamespace(**props)


def test_area_pdf_points_never_proves_metric_floor() -> None:
    floor = _floor(
        metric_area_m2=None,
        metric_area_quantity_id=None,
        metric_area_authority=None,
        area_page_pts2=50000.0,
    )
    assert _floor_quantity_first_failure(floor, _room(), set()) == (
        "documented_dimension_or_physical_scale_measurement_unavailable"
    )


def test_floor_label_proof_is_required_before_metric_measurement() -> None:
    assert _floor_quantity_first_failure(
        _floor(), _room(room_label_binding_record_id=None), {"qty-room-1"}
    ) == "authenticated_room_label_ownership_unavailable"


def test_missing_real_quantity_receipt_is_not_treated_as_published() -> None:
    assert _floor_quantity_first_failure(_floor(), _room(), set()) == (
        "metric_floor_area_quantity_evidence_unavailable"
    )


def test_supported_metric_floor_with_real_quantity_is_ready() -> None:
    assert _floor_quantity_first_failure(
        _floor(), _room(), {"qty-room-1"}
    ) == "floor_area_quantity_prerequisites_resolved"


def test_source_face_evidence_precedes_area_measurement() -> None:
    assert _floor_quantity_first_failure(
        _floor(evidence_ids=()), _room(), {"qty-room-1"}
    ) == "source_room_face_evidence_unavailable"
