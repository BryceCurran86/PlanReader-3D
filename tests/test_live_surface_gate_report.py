"""Regression tests for conservative live surface gate classification."""
from types import SimpleNamespace

from scripts.report_live_surface_gates import first_observed_surface_gate


def _room(complete=True):
    return SimpleNamespace(
        geometry_complete=complete,
        source_room_face_record_id="source-face-1",
    )


def _floor(area=None, quantity_id=None, authority=None):
    return SimpleNamespace(
        source_room_face_record_id="source-face-1",
        metric_area_m2=area,
        metric_area_quantity_id=quantity_id,
        metric_area_authority=authority,
    )


def test_unmeasured_room_does_not_infer_metric_area():
    assert first_observed_surface_gate(_room(), (_floor(),)) == "metric_floor_area_authority_unavailable"


def test_incomplete_room_cannot_claim_metric_area():
    assert first_observed_surface_gate(_room(False), (_floor(3.0, "q1", "documented_dimension"),)) == "source_room_geometry_incomplete"


def test_duplicate_floor_identity_is_fail_closed():
    floor = _floor(3.0, "q1", "documented_dimension")
    assert first_observed_surface_gate(_room(), (floor, floor)) == "canonical_floor_identity_unavailable_or_ambiguous"


def test_documented_area_is_only_producer_present_not_sealed():
    floor = _floor(3.0, "q1", "documented_dimension")
    assert first_observed_surface_gate(_room(), (floor,)) == "metric_floor_area_producer_present_not_yet_sealing_verified"
