"""Source-polygon validity cannot be inferred from a canonical face receipt."""
from types import SimpleNamespace

import pytest

from pb_live_canonical_floor_surface import _floor_from_room
from pb_live_canonical_coverage_registry import _physical_identity_resolved
from pb_live_canonical_room_composition import (
    _room_object_from_record,
    _room_object_from_composite_record,
    _source_room_geometry_complete_diagnostic_only,
)


VALID = ((0., 0.), (4., 0.), (4., 4.), (0., 4.))
CROSSING = ((0., 0.), (4., 0.), (4., 4.), (0., 4.), (2., -1.))


def native_room(polygon=VALID, *, area=16.0):
    return SimpleNamespace(
        document_id="original-document", revision_id="original-revision",
        source_sha256="a" * 64, snapshot_id="original-snapshot",
        page_id="7", decision_scope_id="original-floor-view",
        face_id="face-1", record_id="source-face-1",
        polygon_pdf_pts=polygon, area_page_pts2=area,
        bounding_wall_ids=("original-wall-a", "original-wall-b"),
        label="FREEZER", label_candidate_record_id="native-label-1",
        label_evidence_ids=("original-word-evidence",),
        evidence_ids=("source-face-1",),
    )


def original_room(record):
    return _room_object_from_record(
        record, viewport_id="original-floor-view",
        canonical_wall_ids_by_candidate=None,
        unresolved_wall_candidate_ids=(),
    )


def composite_room(record):
    return _room_object_from_composite_record(
        record, viewport_id="original-floor-view",
        canonical_wall_ids_by_candidate=None,
        unresolved_wall_candidate_ids=(),
    )


def test_real_ring_crossing_with_positive_page_area_abstains_before_canonical_geometry():
    invalid = original_room(native_room(CROSSING, area=12.0))
    assert invalid.room_label is None
    assert invalid.source_room_face_record_id == "source-face-1"
    assert invalid.area_page_pts2 == 12.0
    assert invalid.geometry_complete is False
    assert invalid.metric_geometry_complete is False
    assert invalid.room_label_reason_codes == ()
    assert invalid.polygon_pdf_pts == CROSSING
    assert invalid.coordinate_unit == "pdf_pt"
    assert invalid.evidence_ids == ("source-face-1",)
    floor = _floor_from_room(invalid)
    assert floor.geometry_complete is False
    assert floor.physical_floor_surface_identity_resolved is False
    assert floor.metric_geometry_complete is False
    assert floor.metric_area_m2 is None
    assert _physical_identity_resolved(floor) is False

    # Same source evidence preserves stable identity; no buffer(0) repaired
    # geometry may change it or claim a source metric value.
    again = original_room(native_room(CROSSING, area=12.0))
    assert again.canonical_room_id == invalid.canonical_room_id
    assert again.polygon_pdf_pts == CROSSING


def test_valid_original_polygon_preserves_existing_canonical_geometry_contract():
    original = original_room(native_room())
    assert original.geometry_complete is True
    assert original.metric_geometry_complete is False
    assert original.room_label_reason_codes == ()
    assert original.polygon_pdf_pts == VALID
    assert original.area_page_pts2 == 16.
    good_floor = _floor_from_room(original)
    assert good_floor.geometry_complete is True
    assert good_floor.physical_floor_surface_identity_resolved is True
    assert _physical_identity_resolved(good_floor) is True


@pytest.mark.parametrize("polygon,area", [
    (VALID, float("nan")),
    (VALID, 0.0),
    (VALID, -7.0),
    (((0., 0.), (1., 1.), (0., 0.)), 5.0),
    (((0., 0.), (4., 0.), (4., 4.), (0., float("nan"))), 16.),
    (((0., 0.), (4., 0.), (4., 4.), (0., 4.), (0., 0.)), 0.),
])
def test_nonpositive_or_invalid_source_data_cannot_mint_geometry_completeness(
    polygon, area,
):
    assert not _source_room_geometry_complete_diagnostic_only(
        native_room(polygon, area=area)
    )


def test_composite_uses_same_original_polygon_validity_gate():
    valid = composite_room(native_room())
    assert valid.geometry_complete is True
    invalid = composite_room(native_room(CROSSING, area=12.0))
    assert invalid.geometry_complete is False
    assert invalid.room_label_reason_codes == ("source_composite_room_face_resolved",)
    assert invalid.metric_geometry_complete is False
    assert invalid.source_room_face_record_id == "source-face-1"
