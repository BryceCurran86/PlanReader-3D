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


def _face(face_id, record_id, polygon, walls, boundary_wall_edges=()):
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
        boundary_wall_edges=tuple(boundary_wall_edges),
        **LINEAGE,
    )


def _wall_record(wall_id, *edge_ids):
    centerlines = {
        "w_sep": ((10.0, 0.0), (10.0, 10.0)),
        "w_lm": ((10.0, 0.0), (10.0, 10.0)),
        "w_mr": ((20.0, 0.0), (20.0, 10.0)),
        "w_left": ((0.0, 0.0), (0.0, 10.0)),
        "w_right": ((30.0, 0.0), (30.0, 10.0)),
    }
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            face_a_segment_ids=tuple(edge_ids),
            face_b_segment_ids=None,
            centerline_pts=centerlines.get(
                wall_id, ((1000.0, 1000.0), (1001.0, 1001.0))
            ),
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
        (
            ("w_bottom_left", ((0.0, 0.0), (10.0, 0.0))),
            ("w_sep", ((10.0, 0.0), (10.0, 10.0))),
            ("w_top_left", ((0.0, 10.0), (10.0, 10.0))),
            ("w_left", ((0.0, 0.0), (0.0, 10.0))),
        ),
    )
    x0 = 11.0 if disconnected else 10.0
    right = _face(
        "face_right",
        "record_right",
        ((x0, 0.0), (20.0, 0.0), (20.0, 10.0), (x0, 10.0)),
        ("w_sep", "w_right", "w_top_right", "w_bottom_right"),
        (
            ("w_bottom_right", ((x0, 0.0), (20.0, 0.0))),
            ("w_right", ((20.0, 0.0), (20.0, 10.0))),
            ("w_top_right", ((x0, 10.0), (20.0, 10.0))),
            ("w_sep", ((x0, 0.0), (x0, 10.0))),
        ),
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


def _three_cell_wall_scope(atoms):
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(
            _wall_record("w_lm", "e_lm"),
            _wall_record("w_mr", "e_mr"),
            _wall_record("w_left", "e_left"),
            _wall_record("w_right", "e_right"),
        ),
        source_observation_ids=(),
        reason_codes=("physical_wall_candidate_scope_resolved",),
        typed_semantic_evidence_atoms=tuple(atoms),
        **LINEAGE,
    )


def _three_cell_room_scope():
    left = _face(
        "face_left",
        "record_left",
        ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        ("w_left", "w_lm", "w_top_left", "w_bottom_left"),
        (
            ("w_bottom_left", ((0.0, 0.0), (10.0, 0.0))),
            ("w_lm", ((10.0, 0.0), (10.0, 10.0))),
            ("w_top_left", ((0.0, 10.0), (10.0, 10.0))),
            ("w_left", ((0.0, 0.0), (0.0, 10.0))),
        ),
    )
    middle = _face(
        "face_middle",
        "record_middle",
        ((10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0)),
        ("w_lm", "w_mr", "w_top_middle", "w_bottom_middle"),
        (
            ("w_bottom_middle", ((10.0, 0.0), (20.0, 0.0))),
            ("w_mr", ((20.0, 0.0), (20.0, 10.0))),
            ("w_top_middle", ((10.0, 10.0), (20.0, 10.0))),
            ("w_lm", ((10.0, 0.0), (10.0, 10.0))),
        ),
    )
    right = _face(
        "face_right",
        "record_right",
        ((20.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0)),
        ("w_mr", "w_right", "w_top_right", "w_bottom_right"),
        (
            ("w_bottom_right", ((20.0, 0.0), (30.0, 0.0))),
            ("w_right", ((30.0, 0.0), (30.0, 10.0))),
            ("w_top_right", ((20.0, 10.0), (30.0, 10.0))),
            ("w_mr", ((20.0, 0.0), (20.0, 10.0))),
        ),
    )
    return SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(left, middle, right),
        reason_codes=("source_room_face_scope_resolved",),
        **LINEAGE,
    )


def _three_cell_label_scope(*, middle_label=False, competing_split=False):
    candidate = SimpleNamespace(
        record_id="split_label_primary",
        document_id=LINEAGE["document_id"],
        revision_id=LINEAGE["revision_id"],
        source_sha256=LINEAGE["source_sha256"],
        snapshot_id=LINEAGE["snapshot_id"],
        page_id=LINEAGE["page_id"],
        decision_scope_id=LINEAGE["decision_scope_id"],
        label="GENERIC ROOM",
        observation_ids=("obs_left", "obs_right"),
        word_evidence=(
            SimpleNamespace(authority_record_id="text_left"),
            SimpleNamespace(authority_record_id="text_right"),
        ),
        word_face_ids=("face_left", "face_right"),
        source_room_face_record_ids=("record_left", "record_right"),
    )
    split_candidates = [candidate]
    if competing_split:
        split_candidates.append(
            SimpleNamespace(
                record_id="split_label_competing",
                document_id=LINEAGE["document_id"],
                revision_id=LINEAGE["revision_id"],
                source_sha256=LINEAGE["source_sha256"],
                snapshot_id=LINEAGE["snapshot_id"],
                page_id=LINEAGE["page_id"],
                decision_scope_id=LINEAGE["decision_scope_id"],
                label="OTHER ROOM",
                observation_ids=("obs_middle", "obs_other"),
                word_evidence=(
                    SimpleNamespace(authority_record_id="text_middle"),
                    SimpleNamespace(authority_record_id="text_other"),
                ),
                word_face_ids=("face_middle", "face_right"),
                source_room_face_record_ids=("record_middle", "record_right"),
            )
        )
    records = (
        (SimpleNamespace(face_id="face_middle", label="OTHER ROOM"),)
        if middle_label
        else ()
    )
    return SourceRoomLabelScopeResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("source_room_label_position_unresolved",),
        records=records,
        split_face_candidates=tuple(split_candidates),
        **LINEAGE,
    )


def test_grid_component_completion_recovers_unlabelled_intervening_face():
    result = compose_grid_separated_room_faces(
        wall_scope=_three_cell_wall_scope(
            (
                _grid_atom("e_lm", "ev_lm"),
                _grid_atom("e_mr", "ev_mr"),
            )
        ),
        room_scope=_three_cell_room_scope(),
        label_scope=_three_cell_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    record = result.records[0]
    assert record.constituent_face_ids == (
        "face_left",
        "face_middle",
        "face_right",
    )
    assert record.separator_wall_ids == ("w_lm", "w_mr")
    assert record.area_page_pts2 == 300.0
    assert record.grid_evidence_ids == ("ev_lm", "ev_mr")
    assert "w_lm" not in record.bounding_wall_ids
    assert "w_mr" not in record.bounding_wall_ids


def test_grid_component_completion_requires_all_label_seed_faces_connected():
    result = compose_grid_separated_room_faces(
        wall_scope=_three_cell_wall_scope((_grid_atom("e_lm", "ev_lm"),)),
        room_scope=_three_cell_room_scope(),
        label_scope=_three_cell_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_label_candidate_ids == ("split_label_primary",)


def test_grid_component_completion_blocks_authenticated_label_conflict():
    result = compose_grid_separated_room_faces(
        wall_scope=_three_cell_wall_scope(
            (
                _grid_atom("e_lm", "ev_lm"),
                _grid_atom("e_mr", "ev_mr"),
            )
        ),
        room_scope=_three_cell_room_scope(),
        label_scope=_three_cell_label_scope(middle_label=True),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert result.unresolved_label_candidate_ids == ("split_label_primary",)


def test_grid_component_completion_blocks_competing_split_label():
    result = compose_grid_separated_room_faces(
        wall_scope=_three_cell_wall_scope(
            (
                _grid_atom("e_lm", "ev_lm"),
                _grid_atom("e_mr", "ev_mr"),
            )
        ),
        room_scope=_three_cell_room_scope(),
        label_scope=_three_cell_label_scope(competing_split=True),
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert set(result.unresolved_label_candidate_ids) == {
        "split_label_primary",
        "split_label_competing",
    }


def test_grid_component_completion_preserves_repeated_physical_outer_wall():
    left = _face(
        "face_left",
        "record_left",
        ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        ("w_left", "w_lm", "w_top", "w_bottom"),
        (
            ("w_bottom", ((0.0, 0.0), (10.0, 0.0))),
            ("w_lm", ((10.0, 0.0), (10.0, 10.0))),
            ("w_top", ((0.0, 10.0), (10.0, 10.0))),
            ("w_left", ((0.0, 0.0), (0.0, 10.0))),
        ),
    )
    middle = _face(
        "face_middle",
        "record_middle",
        ((10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0)),
        ("w_lm", "w_mr", "w_top", "w_bottom"),
        (
            ("w_bottom", ((10.0, 0.0), (20.0, 0.0))),
            ("w_mr", ((20.0, 0.0), (20.0, 10.0))),
            ("w_top", ((10.0, 10.0), (20.0, 10.0))),
            ("w_lm", ((10.0, 0.0), (10.0, 10.0))),
        ),
    )
    right = _face(
        "face_right",
        "record_right",
        ((20.0, 0.0), (30.0, 0.0), (30.0, 10.0), (20.0, 10.0)),
        ("w_mr", "w_right", "w_top", "w_bottom"),
        (
            ("w_bottom", ((20.0, 0.0), (30.0, 0.0))),
            ("w_right", ((30.0, 0.0), (30.0, 10.0))),
            ("w_top", ((20.0, 10.0), (30.0, 10.0))),
            ("w_mr", ((20.0, 0.0), (20.0, 10.0))),
        ),
    )
    room_scope = SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(left, middle, right),
        reason_codes=("source_room_face_scope_resolved",),
        **LINEAGE,
    )

    result = compose_grid_separated_room_faces(
        wall_scope=_three_cell_wall_scope(
            (
                _grid_atom("e_lm", "ev_lm"),
                _grid_atom("e_mr", "ev_mr"),
            )
        ),
        room_scope=room_scope,
        label_scope=_three_cell_label_scope(),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    record = result.records[0]
    assert record.separator_wall_ids == ("w_lm", "w_mr")
    assert "w_top" in record.bounding_wall_ids
    assert "w_bottom" in record.bounding_wall_ids

def test_long_grid_wall_with_more_than_two_global_owners_uses_local_adjacency():
    top_left = _face(
        "top_left",
        "record_top_left",
        ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        ("w_outer_left_top", "w_long_grid", "w_top_left", "w_mid_left"),
        (
            ("w_top_left", ((0.0, 0.0), (10.0, 0.0))),
            ("w_long_grid", ((10.0, 0.0), (10.0, 10.0))),
            ("w_mid_left", ((0.0, 10.0), (10.0, 10.0))),
            ("w_outer_left_top", ((0.0, 0.0), (0.0, 10.0))),
        ),
    )
    top_right = _face(
        "top_right",
        "record_top_right",
        ((10.0, 0.0), (20.0, 0.0), (20.0, 10.0), (10.0, 10.0)),
        ("w_long_grid", "w_outer_right_top", "w_top_right", "w_mid_right"),
        (
            ("w_top_right", ((10.0, 0.0), (20.0, 0.0))),
            ("w_outer_right_top", ((20.0, 0.0), (20.0, 10.0))),
            ("w_mid_right", ((10.0, 10.0), (20.0, 10.0))),
            ("w_long_grid", ((10.0, 0.0), (10.0, 10.0))),
        ),
    )
    bottom_left = _face(
        "bottom_left",
        "record_bottom_left",
        ((0.0, 10.0), (10.0, 10.0), (10.0, 20.0), (0.0, 20.0)),
        ("w_outer_left_bottom", "w_long_grid", "w_mid_left", "w_bottom_left"),
        (
            ("w_mid_left", ((0.0, 10.0), (10.0, 10.0))),
            ("w_long_grid", ((10.0, 10.0), (10.0, 20.0))),
            ("w_bottom_left", ((0.0, 20.0), (10.0, 20.0))),
            ("w_outer_left_bottom", ((0.0, 10.0), (0.0, 20.0))),
        ),
    )
    bottom_right = _face(
        "bottom_right",
        "record_bottom_right",
        ((10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)),
        ("w_long_grid", "w_outer_right_bottom", "w_mid_right", "w_bottom_right"),
        (
            ("w_mid_right", ((10.0, 10.0), (20.0, 10.0))),
            ("w_outer_right_bottom", ((20.0, 10.0), (20.0, 20.0))),
            ("w_bottom_right", ((10.0, 20.0), (20.0, 20.0))),
            ("w_long_grid", ((10.0, 10.0), (10.0, 20.0))),
        ),
    )
    room_scope = SourceRoomFaceScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(top_left, top_right, bottom_left, bottom_right),
        reason_codes=("source_room_face_scope_resolved",),
        **LINEAGE,
    )
    wall_scope = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True,
        records=(
            SimpleNamespace(
                wall_candidate_id="w_long_grid",
                wall_candidate=SimpleNamespace(
                    face_a_segment_ids=("e_long_grid",),
                    face_b_segment_ids=None,
                    centerline_pts=((10.0, 0.0), (10.0, 20.0)),
                ),
            ),
        ),
        source_observation_ids=(),
        reason_codes=("physical_wall_candidate_scope_resolved",),
        typed_semantic_evidence_atoms=(
            _grid_atom("e_long_grid", "ev_long_grid"),
        ),
        **LINEAGE,
    )
    candidate = SimpleNamespace(
        record_id="split_label_top",
        document_id=LINEAGE["document_id"],
        revision_id=LINEAGE["revision_id"],
        source_sha256=LINEAGE["source_sha256"],
        snapshot_id=LINEAGE["snapshot_id"],
        page_id=LINEAGE["page_id"],
        decision_scope_id=LINEAGE["decision_scope_id"],
        label="GENERIC TWO WORD",
        observation_ids=("obs_top_left", "obs_top_right"),
        word_evidence=(
            SimpleNamespace(authority_record_id="text_top_left"),
            SimpleNamespace(authority_record_id="text_top_right"),
        ),
        word_face_ids=("top_left", "top_right"),
        source_room_face_record_ids=("record_top_left", "record_top_right"),
    )
    label_scope = SourceRoomLabelScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("source_room_label_position_unresolved",),
        records=(),
        split_face_candidates=(candidate,),
        **LINEAGE,
    )

    result = compose_grid_separated_room_faces(
        wall_scope=wall_scope,
        room_scope=room_scope,
        label_scope=label_scope,
    )

    # One long W4 grid chain owns two disjoint local separator subedges.
    # Starting in the top pair must traverse only the exact shared top subedge;
    # point contact with the lower pair is not room adjacency.
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    assert result.records[0].constituent_face_ids == ("top_left", "top_right")


def test_planarized_source_wall_edges_reject_nonfinite_coordinates():
    # A malformed source edge cannot be a globally shared grid separator.
    from pb_source_composite_room_face_authority import _edge_key

    assert _edge_key(((0.0, 0.0), (10.0, 0.0))) == (
        (0.0, 0.0), (10.0, 0.0)
    )
    assert _edge_key(((10.0, 0.0), (0.0, 0.0))) == (
        (0.0, 0.0), (10.0, 0.0)
    )
    for value in (float("nan"), float("inf"), float("-inf")):
        assert _edge_key(((0.0, 0.0), (value, 0.0))) is None
        assert _edge_key(((value, 1.0), (2.0, 1.0))) is None
    assert _edge_key(((0.0, 0.0), (0.0, 0.0))) is None
    assert _edge_key(((0.0, 0.0), ())) is None
