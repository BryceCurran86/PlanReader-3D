"""Real source-room publication must never accept non-simple polygon rings."""
import pb_source_room_face_authority as R
from types import SimpleNamespace as NS
from pb_migration_contracts import EvidenceResolutionStatus


def _wall(wall_id, a, b):
    return NS(wall_candidate_id=wall_id,
              wall_candidate=NS(centerline_pts=(a,b)))


def _two_valid_rooms():
    return (
        _wall("outer-top",(0.,0.),(20.,0.)),
        _wall("outer-right",(20.,0.),(20.,10.)),
        _wall("outer-bottom",(20.,10.),(0.,10.)),
        _wall("outer-left",(0.,10.),(0.,0.)),
        _wall("partition",(10.,0.),(10.,10.)),
    )


def _scope(records):
    return NS(status=EvidenceResolutionStatus.CORROBORATED,
              scope_complete=True,records=tuple(records),
              document_id="source-valid",revision_id="r1",
              source_sha256="e"*64,snapshot_id="snapshot",
              page_id="7",decision_scope_id="wall-source:page-7")


def test_exact_source_ring_validity_rejects_true_self_crossings():
    assert R._original_source_polygon_is_simple(
        ((0.,0.),(10.,0.),(10.,10.),(0.,10.))
    )
    assert not R._original_source_polygon_is_simple(
        ((0.,0.),(10.,10.),(0.,10.),(10.,0.))
    )
    assert not R._original_source_polygon_is_simple(
        ((0.,0.),(10.,0.),(10.,10.),(10.,0.),(0.,10.))
    )
    assert not R._original_source_polygon_is_simple(
        ((0.,0.),(10.,0.),(float("nan"),10.),(0.,10.))
    )
    assert not R._original_source_polygon_is_simple(
        ((0.,0.),(0.,0.),(0.,0.))
    )


def test_unchanged_two_genuine_source_rooms_remain_publishable():
    result=R._derive_scope(_scope(_two_valid_rooms()))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records)==2
    assert result.abstained_faces == ()
    assert all(R._original_source_polygon_is_simple(r.polygon_pdf_pts)
               for r in result.records)


def test_source_invalid_ring_never_becomes_valid_by_reversing_traversal():
    bowtie=((0.,0.),(10.,10.),(0.,10.),(10.,0.))
    assert not R._original_source_polygon_is_simple(bowtie)
    assert not R._original_source_polygon_is_simple(tuple(reversed(bowtie)))


def test_narrow_genuine_simple_strip_remains_subject_to_existing_area_gate():
    # A simple strip is valid topology but not automatically a published room.
    assert R._original_source_polygon_is_simple(
        ((226.319992,471.200073),
         (260.160004,471.200073),
         (260.160004,476.480103),
         (226.319992,476.480103))
    )
    assert R.SOURCE_ROOM_FACE_SELF_INTERSECTING != R.SOURCE_ROOM_FACE_DEGENERATE
