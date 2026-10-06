from types import SimpleNamespace

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateScopeResult
from pb_source_composite_room_face_authority import (
    SOURCE_COMPOSITE_ROOM_FACE_RESOLVED,
    compose_grid_separated_room_faces,
)
from pb_source_room_face_authority import (
    SourceRoomFaceRecord,
    SourceRoomFaceScopeResult,
)
from pb_source_room_label_authority import SourceRoomLabelScopeResult


LINEAGE = dict(
    document_id="doc",
    revision_id="rev",
    source_sha256="a" * 64,
    snapshot_id="snap",
    page_id="1",
    decision_scope_id="wall-source:page-1",
)


def _face(face_id, record_id, polygon, walls):
    area = 0.0
    for index, first in enumerate(polygon):
        second = polygon[(index + 1) % len(polygon)]
        area += first[0] * second[1] - second[0] * first[1]
    return SourceRoomFaceRecord(
        record_id=record_id,
        face_id=face_id,
        polygon_pdf_pts=tuple(polygon),
        bounding_wall_ids=tuple(walls),
        area_page_pts2=abs(area) * 0.5,
        **LINEAGE,
    )


def _wall_record(wall_id, *edge_ids):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            face_a_segment_ids=tuple(edge_ids),
            face_b_segment_ids=None,
        ),
    )


def _grid_atom(edge_id, evidence_id="ev_grid"):
    return EvidenceAtom(
        evidence_id=evidence_id,
        document_id="doc",
        page_id="1",
        kind="grid",
        method="typed_negative_geometry_shadow",
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("source_lineage_dense_orthogonal_lattice",),
        metadata={
            "polarity": "opposing",
            "target_edge_id": edge_id,
        },
    )


def _wall_scope(atoms):
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(
            _wall_record("w_sep", "e_sep"),
            _wall_record("w_left", "e_left"),
            _wall_record("w_right", "e_right"),
        ),
        source_observation_ids=(),
        reason_codes=("physical_wall_candidate_scope_resolved",),
        typed_semantic_evidence_atoms=tuple(atoms),
        **LINEAGE,
    )


def _room_scope(*, disconnected=False):
    left = _face(
        "face_left",
        "record_left",
        ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        ("w_left", "w_sep", "w_top_left", "w_bottom_left"),
    )
    x0 = 11.0 if disconnected else 10.0
    right = _face(
        "face_right",
        "record_right",
        ((x0, 0.0), (20.0, 0.0), (20.0, 10.0), (x0, 10.0)),
        ("w_sep", "w_right", "w_top_right", "w_bottom_right"),
    )
    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(left, right),
        reason_codes=("source_room_face_scope_resolved",),
        **LINEAGE,
    )


def _label_scope():
    candidate = SimpleNamespace(
        record_id="split_label_1",
        document_id=LINEAGE["document_id"],
        revision_id=LINEAGE["revision_id"],
        source_sha256=LINEAGE["source_sha256"],
        snapshot_id=LINEAGE["snapshot_id"],
        page_id=LINEAGE["page_id"],
        decision_scope_id=LINEAGE["decision_scope_id"],
        label="GENERIC TWO WORD",
        observation_ids=("obs_a", "obs_b"),
        word_evidence=(
            SimpleNamespace(authority_record_id="text_a"),
            SimpleNamespace(authority_record_id="text_b"),
        ),
        word_face_ids=("face_left", "face_right"),
        source_room_face_record_ids=("record_left", "record_right"),
    )
    return SourceRoomLabelScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("source_room_label_position_unresolved",),
        records=(),
        split_face_candidates=(candidate,),
        **LINEAGE,
    )


def test_grid_only_internal_separator_composes_one_room_face():
    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=_room_scope(),
        label_scope=_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (SOURCE_COMPOSITE_ROOM_FACE_RESOLVED,)
    assert len(result.records) == 1
    record = result.records[0]
    assert record.label == "GENERIC TWO WORD"
    assert record.constituent_face_ids == ("face_left", "face_right")
    assert record.separator_wall_ids == ("w_sep",)
    assert "w_sep" not in record.bounding_wall_ids
    assert record.area_page_pts2 == 200.0
    assert record.grid_evidence_ids == ("ev_grid",)


def test_grid_opposed_external_boundary_stays_fail_closed():
    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope(
            (
                _grid_atom("e_sep", "ev_sep"),
                _grid_atom("e_left", "ev_outer"),
            )
        ),
        room_scope=_room_scope(),
        label_scope=_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_label_candidate_ids == ("split_label_1",)


def test_non_grid_separator_stays_fail_closed():
    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope(()),
        room_scope=_room_scope(),
        label_scope=_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_label_candidate_ids == ("split_label_1",)


def test_disconnected_faces_do_not_merge_even_with_grid_evidence():
    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=_room_scope(disconnected=True),
        label_scope=_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
