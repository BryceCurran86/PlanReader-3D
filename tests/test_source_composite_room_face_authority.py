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
    assert _edge_key(((0.0, 0.0), (10**500, 0.0))) is None


def test_nonfinite_source_wall_cannot_generate_local_grid_adjacency():
    from pb_source_composite_room_face_authority import (
        _grid_local_adjacency,
        _local_edge_owners,
    )
    from types import SimpleNamespace

    source_face_a = SimpleNamespace(
        face_id="a",
        boundary_wall_edges=(("W-grid", ((float("nan"), 0.0), (5.0, 0.0))),),
    )
    source_face_b = SimpleNamespace(
        face_id="b",
        boundary_wall_edges=(("W-grid", ((float("nan"), 0.0), (5.0, 0.0))),),
    )
    source_scope = SimpleNamespace(records=(source_face_a, source_face_b))
    assert _local_edge_owners(source_scope) == {}
    assert _grid_local_adjacency(source_scope, {"W-grid"}) == {}



def test_null_wall_identity_cannot_own_any_composite_room_subedge():
    from pb_source_composite_room_face_authority import (
        _grid_local_adjacency,
        _local_edge_owners,
    )
    from types import SimpleNamespace

    source_scope = SimpleNamespace(records=(
        SimpleNamespace(face_id="a", boundary_wall_edges=((None, ((0, 0), (10, 0))),)),
        SimpleNamespace(face_id="b", boundary_wall_edges=(("", ((10, 0), (0, 0))),)),
    ))
    assert _local_edge_owners(source_scope) == {}
    assert _grid_local_adjacency(source_scope, {"None", ""}) == {}


def test_source_grid_subedges_node_at_exact_split_endpoints():
    """Two authentic W4 wall receipts may use different exact subedge cuts."""
    from dataclasses import replace

    scope = _room_scope()
    left, right = scope.records
    new_right_edges = []
    for wall, edge in right.boundary_wall_edges:
        if wall == "w_sep":
            new_right_edges.extend((
                (wall, ((10.0, 0.0), (10.0, 4.0))),
                (wall, ((10.0, 4.0), (10.0, 10.0))),
            ))
        else:
            new_right_edges.append((wall, edge))
    split_scope = replace(scope, records=(
        left, replace(right, boundary_wall_edges=tuple(new_right_edges)),
    ))

    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=split_scope,
        label_scope=_label_scope(),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    assert result.records[0].area_page_pts2 == 200.0
    assert result.records[0].separator_wall_ids == ("w_sep",)


def test_source_grid_edge_noding_requires_exact_axis_and_same_w4_wall():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import _grid_local_adjacency
    scope = _room_scope()
    left, right = scope.records
    incompatible = []
    for wall, edge in right.boundary_wall_edges:
        if wall == "w_sep":
            incompatible.extend((
                (wall, ((10.00001, 0.0), (10.00001, 4.0))),
                (wall, ((10.00001, 4.0), (10.00001, 10.0))),
            ))
        else:
            incompatible.append((wall, edge))
    offset_scope = replace(scope, records=(
        left, replace(right, boundary_wall_edges=tuple(incompatible)),
    ))
    assert _grid_local_adjacency(offset_scope, {"w_sep"}) == {}
    assert compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=offset_scope,
        label_scope=_label_scope(),
    ).records == ()

    # Matching geometry associated with a different W4 wall is never an owner.
    foreign = tuple(
        ("w_wrong", edge) if wall == "w_sep" else (wall, edge)
        for wall, edge in right.boundary_wall_edges
    )
    foreign_scope = replace(scope, records=(
        left, replace(right, boundary_wall_edges=foreign),
    ))
    assert _grid_local_adjacency(foreign_scope, {"w_sep"}) == {}


def test_grid_noding_rejects_duplicate_and_three_sided_source_owners():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import _grid_local_adjacency
    scope = _room_scope()
    left, right = scope.records
    dup_scope = replace(scope, records=(
        replace(left, boundary_wall_edges=left.boundary_wall_edges +
                (("w_sep", ((10.0, 0.0), (10.0, 10.0))),)),
        right,
    ))
    assert _grid_local_adjacency(dup_scope, {"w_sep"}) == {}
    assert compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=dup_scope,
        label_scope=_label_scope(),
    ).records == ()

    third = replace(left, face_id="unrelated_third_face",
                    record_id="unrelated_third_record")
    triple_scope = replace(scope, records=(left, right, third))
    assert _grid_local_adjacency(triple_scope, {"w_sep"}) == {}


def test_touching_grid_source_edges_without_positive_span_do_not_connect():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import _grid_local_adjacency
    scope = _room_scope()
    left, right = scope.records
    left_edges = tuple(
        (wall, ((10.0, 0.0), (10.0, 5.0))) if wall == "w_sep"
        else (wall, edge) for wall, edge in left.boundary_wall_edges
    )
    right_edges = tuple(
        (wall, ((10.0, 5.0), (10.0, 10.0))) if wall == "w_sep"
        else (wall, edge) for wall, edge in right.boundary_wall_edges
    )
    disconnected = replace(scope, records=(
        replace(left, boundary_wall_edges=left_edges),
        replace(right, boundary_wall_edges=right_edges),
    ))
    assert _grid_local_adjacency(disconnected, {"w_sep"}) == {}
    assert compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=disconnected,
        label_scope=_label_scope(),
    ).records == ()


def test_source_grid_union_rejects_overlapping_face_interiors():
    from dataclasses import replace
    original = _room_scope()
    left, right = original.records
    # Even with the same W4 receipt, an internally overlapping source-face
    # footprint is not a true room-cell partition and must not be composed.
    inflated = replace(right,
        polygon_pdf_pts=((8.0, 0.0), (20.0, 0.0),
                         (20.0, 10.0), (8.0, 10.0)),
        area_page_pts2=120.0,
    )
    overlapped = replace(original, records=(left, inflated))
    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=overlapped,
        label_scope=_label_scope(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()


def test_source_endpoint_sweep_preserves_overlapping_same_face_multiplicity():
    """A sweep must not collapse duplicate overlaps into a fake two-sided owner."""
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts,
    )

    scope = _room_scope()
    left, right = scope.records
    right_edges = []
    for wall, edge in right.boundary_wall_edges:
        if wall == "w_sep":
            right_edges.extend((
                (wall, ((10.0, 0.0), (10.0, 6.0))),
                (wall, ((10.0, 4.0), (10.0, 10.0))),
            ))
        else:
            right_edges.append((wall, edge))
    modified = replace(scope, records=(
        left, replace(right, boundary_wall_edges=tuple(right_edges)),
    ))
    noded = _atomic_source_wall_edge_counts(modified, {"w_sep"})
    shared = noded[("w_sep", ((10.0, 4.0), (10.0, 6.0)))]
    assert shared["face_left"] == 1
    assert shared["face_right"] == 2
    result = compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=modified,
        label_scope=_label_scope(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()


def test_source_endpoint_sweep_preserves_adjacent_same_face_segments():
    """An end and start at the same authentic cut keep one face owner."""
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts,
    )

    scope = _room_scope()
    left, right = scope.records
    right_edges = []
    for wall, edge in right.boundary_wall_edges:
        if wall == "w_sep":
            right_edges.extend((
                (wall, ((10.0, 0.0), (10.0, 4.0))),
                (wall, ((10.0, 4.0), (10.0, 10.0))),
            ))
        else:
            right_edges.append((wall, edge))
    modified = replace(scope, records=(
        left, replace(right, boundary_wall_edges=tuple(right_edges)),
    ))
    noded = _atomic_source_wall_edge_counts(modified, {"w_sep"})
    for start, end in ((0.0, 4.0), (4.0, 10.0)):
        assert noded[("w_sep", ((10.0, start), (10.0, end)))] == {
            "face_left": 1, "face_right": 1,
        }


def test_source_w4_node_counts_are_scoped_once_across_competing_labels(monkeypatch):
    """Candidate abstention semantics stay unchanged without per-label noding."""
    import pb_source_composite_room_face_authority as module

    original = module._atomic_source_wall_edge_counts
    calls = []

    def measured(room_scope, grid_walls):
        calls.append((room_scope, frozenset(grid_walls)))
        return original(room_scope, grid_walls)

    monkeypatch.setattr(module, "_atomic_source_wall_edge_counts", measured)
    room_scope = _three_cell_room_scope()
    result = compose_grid_separated_room_faces(
        wall_scope=_three_cell_wall_scope(
            (_grid_atom("e_lm", "ev_lm"), _grid_atom("e_mr", "ev_mr"))
        ),
        room_scope=room_scope,
        label_scope=_three_cell_label_scope(competing_split=True),
    )
    assert len(calls) == 1
    assert calls[0][0] is room_scope
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.records == ()
    assert set(result.unresolved_label_candidate_ids) == {
        "split_label_primary",
        "split_label_competing",
    }


def test_gpt2_b02_duplicate_w4_candidate_id_does_not_authenticate_separator():
    """Original Maryborough exposed different W4 candidates with one address.

    A shared W4 address does not prove wall physical equivalence or an exact
    separator. Preserve independent source-owned walls and all face records.
    """
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _fully_grid_opposed_wall_evidence,
    )

    original = _wall_scope((_grid_atom("e_sep"), _grid_atom("e_left")))
    clean_ids, clean_receipts = _fully_grid_opposed_wall_evidence(original)
    assert "w_sep" in clean_ids and "w_left" in clean_ids
    assert clean_receipts["w_sep"]
    duplicate = _wall_record("w_sep", "another_original_source_edge")
    contaminated = replace(
        original, records=(*original.records, duplicate)
    )
    quarantined, receipts = _fully_grid_opposed_wall_evidence(contaminated)
    assert "w_sep" not in quarantined
    assert "w_sep" not in receipts
    assert "w_left" in quarantined
    assert receipts["w_left"] == clean_receipts["w_left"]
    # Exactly the same producer ID repeated twice is also nonunique and
    # cannot silently grant two physical face-cell ownership claims.
    repeated = replace(
        original, records=(*original.records, original.records[0])
    )
    repeated_ids, _ = _fully_grid_opposed_wall_evidence(repeated)
    assert "w_sep" not in repeated_ids

    # A candidate union relying on a colliding W4 separator must abstain.
    attempted = compose_grid_separated_room_faces(
        wall_scope=contaminated,
        room_scope=_room_scope(),
        label_scope=_label_scope(),
    )
    assert attempted.records == ()
    assert attempted.status is EvidenceResolutionStatus.ABSTAINED


def test_gpt2_b02_duplicate_source_face_or_receipt_blocks_room_composite():
    from dataclasses import replace

    original=_room_scope()
    wall=_wall_scope((_grid_atom("e_sep"),))
    label=_label_scope()
    positive=compose_grid_separated_room_faces(
        wall_scope=wall,room_scope=original,label_scope=label
    )
    assert positive.status is EvidenceResolutionStatus.CORROBORATED
    assert len(positive.records)==1

    a,b=original.records
    for corrupted in (
        replace(original,records=(a,b,replace(a,record_id="another-source"))),
        replace(original,records=(a,replace(b,record_id=a.record_id))),
    ):
        result=compose_grid_separated_room_faces(
            wall_scope=wall,room_scope=corrupted,label_scope=label
        )
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.records == ()
        assert result.unresolved_label_candidate_ids == ("split_label_1",)
        # Original source record universe must remain auditable, never deleted.
        assert len(corrupted.records) in (2,3)


def test_gpt2_b02_invalid_w4_source_key_cannot_impersonate_grid_wall():
    """Fail closed even when a typed GRID atom points to an apparent string ID."""
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _fully_grid_opposed_wall_evidence,
    )
    for invalid in (None, 42, "", "  ", " w_sep"):
        source = _wall_scope((_grid_atom("e_sep"),))
        original = source.records[0]
        forged = SimpleNamespace(
            wall_candidate_id=invalid,
            wall_candidate=original.wall_candidate,
        )
        amended = replace(source, records=(forged, *source.records[1:]))
        grid, receipts = _fully_grid_opposed_wall_evidence(amended)
        assert "w_sep" not in grid
        assert "w_sep" not in receipts
        assert not grid
    # Unaffected producer-owned walls still publish their exact independent
    # grid opposition when another wall has an invalid address.
    source=_wall_scope((_grid_atom("e_sep"),_grid_atom("e_left")))
    forged=SimpleNamespace(
        wall_candidate_id=None,
        wall_candidate=source.records[0].wall_candidate,
    )
    amended=replace(source, records=(forged,*source.records[1:]))
    grid,receipts=_fully_grid_opposed_wall_evidence(amended)
    assert grid=={"w_left"}
    assert receipts["w_left"]


def test_gpt2_split_label_exact_word_face_source_receipts_required():
    """B01: Native word owners cannot borrow foreign face record ancestry."""
    from dataclasses import replace
    wall_scope = _wall_scope((_grid_atom("e_sep"),))
    room_scope = _room_scope()
    label_scope = _label_scope()
    positive = compose_grid_separated_room_faces(
        wall_scope=wall_scope, room_scope=room_scope, label_scope=label_scope
    )
    assert len(positive.records) == 1
    original = label_scope.split_face_candidates[0]
    for invalid in (
        ("foreign-a", "record_right"),
        ("record_right", "record_left"),
        ("record_left",),
        (),
        ("record_left", "record_right", "unexpected"),
    ):
        tampered = SimpleNamespace(**vars(original))
        tampered.source_room_face_record_ids = invalid
        label_scope_invalid = replace(
            label_scope, split_face_candidates=(tampered,)
        )
        rejected = compose_grid_separated_room_faces(
            wall_scope=wall_scope, room_scope=room_scope,
            label_scope=label_scope_invalid,
        )
        assert rejected.records == ()
        assert rejected.status is EvidenceResolutionStatus.ABSTAINED
    for field, stale in (
        ("source_sha256", "b" * 64),
        ("snapshot_id", "different-room-snapshot"),
        ("page_id", "another-page"),
        ("decision_scope_id", "foreign-floor-viewport"),
    ):
        tampered = SimpleNamespace(**vars(original))
        setattr(tampered, field, stale)
        rejected = compose_grid_separated_room_faces(
            wall_scope=wall_scope, room_scope=room_scope,
            label_scope=replace(
                label_scope, split_face_candidates=(tampered,)
            ),
        )
        assert rejected.records == ()


def test_gpt2_b02_composite_rejects_stringified_missing_source_receipts():
    """None and numeric upstream identities are not physical room ancestry."""
    from dataclasses import replace
    import copy
    wall=_wall_scope((_grid_atom("e_sep"),))
    room=_room_scope()
    labelled=_label_scope()
    assert len(compose_grid_separated_room_faces(
        wall_scope=wall,room_scope=room,label_scope=labelled
    ).records)==1
    left,right=room.records
    for malformed in (None, 73, "", " record_right"):
        contaminated=replace(room,records=(
            left,replace(right,record_id=malformed)
        ))
        candidate=copy.copy(labelled.split_face_candidates[0])
        candidate.source_room_face_record_ids=(
            "record_left",str(malformed),
        )
        result=compose_grid_separated_room_faces(
            wall_scope=wall,room_scope=contaminated,
            label_scope=replace(labelled,split_face_candidates=(candidate,))
        )
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.records == ()

    # A native producer face ID of integer 7 cannot be owned by the string
    # "7" in word evidence, even with exactly matching source geometry.
    numeric=replace(room,records=(left,replace(right,face_id=7)))
    candidate=copy.copy(labelled.split_face_candidates[0])
    candidate.word_face_ids=("face_left","7")
    result=compose_grid_separated_room_faces(
        wall_scope=wall,room_scope=numeric,
        label_scope=replace(labelled,split_face_candidates=(candidate,))
    )
    assert result.records == ()
    assert result.status is EvidenceResolutionStatus.ABSTAINED


def test_gpt2_b01_grid_component_first_gate_uses_real_producer_not_synthetic_merger():
    from tools.diag_gpt2_grid_component_first_failure import (
        inspect_split_grid_component_first_failure,
    )
    source_walls=_wall_scope((_grid_atom("e_sep"),))
    source_rooms=_room_scope()
    source_labels=_label_scope()
    label=source_labels.split_face_candidates[0]
    row=inspect_split_grid_component_first_failure(
        label,wall_scope=source_walls,room_scope=source_rooms,
        label_scope=source_labels,
    )
    assert row["first_unclosed_gate"]=="production_grid_composite_available"
    assert row["production_composite_record_id_observed_only"]
    assert row["source_room_composite_published_by_diagnostic"] is False
    assert row["source_room_metric_area_published"] is False

    no_grid=inspect_split_grid_component_first_failure(
        label,wall_scope=_wall_scope(()),room_scope=source_rooms,
        label_scope=source_labels,
    )
    assert no_grid["first_unclosed_gate"]=="no_producer_authenticated_grid_opposed_w4"
    gap=inspect_split_grid_component_first_failure(
        label,wall_scope=source_walls,room_scope=_room_scope(disconnected=True),
        label_scope=source_labels,
    )
    assert gap["first_unclosed_gate"]=="split_words_not_connected_by_exact_grid_owned_edges"
    assert not gap["connected_component_source_face_ids_diagnostic_only"]


def test_gpt2_b01_grid_component_first_gate_rejects_stale_label_face_receipt():
    from tools.diag_gpt2_grid_component_first_failure import (
        inspect_split_grid_component_first_failure,
    )
    from dataclasses import replace
    walls=_wall_scope((_grid_atom("e_sep"),))
    rooms=_room_scope()
    labels=_label_scope()
    original=labels.split_face_candidates[0]
    forged=SimpleNamespace(**vars(original))
    forged.source_room_face_record_ids=("foreign-source-face", "record_right")
    first=inspect_split_grid_component_first_failure(
        forged,wall_scope=walls,room_scope=rooms,
        label_scope=replace(labels,split_face_candidates=(forged,)),
    )
    assert first["first_unclosed_gate"]=="split_label_source_face_receipt_mismatch"
    for bad in ((),("face_left",),("face_left",73),("face_left","missing")):
        forged=SimpleNamespace(**vars(original))
        forged.word_face_ids=bad
        row=inspect_split_grid_component_first_failure(
            forged,wall_scope=walls,room_scope=rooms,
            label_scope=replace(labels,split_face_candidates=(forged,)),
        )
        assert row["first_unclosed_gate"] in (
            "split_source_word_face_identity_unresolved",
            "split_source_face_or_receipt_ambiguous",
        )
        assert row["source_room_metric_area_published"] is False


def test_gpt2_b01_precomputed_source_w4_grid_indexes_preserve_first_gate():
    from tools.diag_gpt2_grid_component_first_failure import (
        inspect_split_grid_component_first_failure,
    )
    from pb_source_composite_room_face_authority import (
        _fully_grid_opposed_wall_evidence, _grid_local_adjacency,
    )
    walls=_wall_scope((_grid_atom("e_sep"),))
    rooms=_room_scope()
    labels=_label_scope()
    grid,evidence=_fully_grid_opposed_wall_evidence(walls)
    adjacency=_grid_local_adjacency(rooms,grid)
    candidate=labels.split_face_candidates[0]
    unindexed=inspect_split_grid_component_first_failure(
        candidate,wall_scope=walls,room_scope=rooms,label_scope=labels
    )
    indexed=inspect_split_grid_component_first_failure(
        candidate,wall_scope=walls,room_scope=rooms,label_scope=labels,
        grid_walls=grid,grid_evidence=evidence,grid_adjacency=adjacency,
    )
    assert indexed==unindexed
    assert indexed["source_room_composite_published_by_diagnostic"] is False

def test_gpt2_grid_component_cannot_stringify_or_overwrite_native_source_faces():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _grid_connected_component, _fully_grid_opposed_wall_evidence,
        _grid_local_adjacency,
    )
    walls = _wall_scope((_grid_atom("e_sep"),))
    rooms = _room_scope()
    grid, _ = _fully_grid_opposed_wall_evidence(walls)
    adjacency = _grid_local_adjacency(rooms, grid)
    candidate = ("face_left", "face_right")
    authentic = _grid_connected_component(
        candidate, room_scope=rooms,
        fully_grid_wall_ids=grid, adjacency=adjacency
    )
    assert authentic is not None
    for ids in (
        "face_left", ("face_left", 9), ("face_left", None),
        ("face_left", " face_right"), ("face_left",),
    ):
        assert _grid_connected_component(
            ids, room_scope=rooms, fully_grid_wall_ids=grid,
            adjacency=adjacency
        ) is None
    left,right = rooms.records
    for invalid in (
        replace(rooms, records=(left,right,replace(left,record_id="other"))),
        replace(rooms, records=(left,replace(right,record_id=left.record_id))),
        replace(rooms, records=(left,replace(right,face_id=None))),
    ):
        assert _grid_connected_component(
            candidate, room_scope=invalid, fully_grid_wall_ids=grid,
            adjacency=adjacency
        ) is None



def test_gpt2_duplicated_split_label_producer_id_cannot_evade_competing_label_gate():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _component_has_conflicting_label,
    )
    labels = _label_scope()
    original = labels.split_face_candidates[0]
    component = ("face_left", "face_right")
    assert not _component_has_conflicting_label(
        component,original,label_scope=labels
    )
    other = SimpleNamespace(**vars(original))
    contaminated = replace(
        labels,split_face_candidates=(original,other)
    )
    assert _component_has_conflicting_label(
        component,original,label_scope=contaminated
    )
    actual = compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=_room_scope(),label_scope=contaminated,
    )
    assert actual.records == ()
    assert actual.status is EvidenceResolutionStatus.ABSTAINED



def test_gpt2_b01_repeated_exact_source_label_producer_receipt_is_not_unique():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _component_has_conflicting_label,
    )
    labels=_label_scope()
    single=labels.split_face_candidates[0]
    component=("face_left","face_right")
    # One exact producer-sealed native line may be used once, but two
    # occurrences in the same sealed scope cannot create two rooms.
    assert not _component_has_conflicting_label(component,single,label_scope=labels)
    duplicated=replace(labels,split_face_candidates=(single,single))
    assert _component_has_conflicting_label(component,single,label_scope=duplicated)
    published=compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=_room_scope(),label_scope=duplicated,
    )
    assert published.records==()
    assert published.status is EvidenceResolutionStatus.ABSTAINED



def test_gpt2_b01_original_composite_wall_receipt_requires_typed_exact_w4_id():
    from dataclasses import replace
    walls=_wall_scope((_grid_atom("e_sep"),))
    faces=_room_scope()
    labels=_label_scope()
    assert len(compose_grid_separated_room_faces(
        wall_scope=walls, room_scope=faces, label_scope=labels
    ).records)==1
    first,second=faces.records
    old_wall,source_edge=first.boundary_wall_edges[0]
    assert isinstance(old_wall,str)
    for invalid in (None,27,"", "  ",old_wall+" "):
        contaminated=replace(
            first,boundary_wall_edges=((invalid,source_edge),*first.boundary_wall_edges[1:])
        )
        scope=replace(faces,records=(contaminated,second))
        result=compose_grid_separated_room_faces(
            wall_scope=walls,room_scope=scope,label_scope=labels
        )
        assert result.records==()
        assert result.status is EvidenceResolutionStatus.ABSTAINED



def test_gpt2_source_label_observation_and_word_authority_receipts_are_native():
    from dataclasses import replace
    import copy
    walls=_wall_scope((_grid_atom("e_sep"),))
    rooms=_room_scope()
    original_scope=_label_scope()
    assert len(compose_grid_separated_room_faces(
        wall_scope=walls,room_scope=rooms,label_scope=original_scope
    ).records)==1
    original=original_scope.split_face_candidates[0]
    for bad in (None,7,""," ", "native-receipt "):
        label=copy.copy(original)
        label.observation_ids=(bad,"obs_b")
        withheld=compose_grid_separated_room_faces(
            wall_scope=walls,room_scope=rooms,
            label_scope=replace(original_scope,split_face_candidates=(label,))
        )
        assert withheld.records == ()
        assert withheld.status is EvidenceResolutionStatus.ABSTAINED
        label=copy.copy(original)
        label.word_evidence=(
            SimpleNamespace(authority_record_id=bad),
            SimpleNamespace(authority_record_id="text_b"),
        )
        withheld=compose_grid_separated_room_faces(
            wall_scope=walls,room_scope=rooms,
            label_scope=replace(original_scope,split_face_candidates=(label,))
        )
        assert withheld.records == ()
        assert withheld.status is EvidenceResolutionStatus.ABSTAINED



def test_gpt2_original_split_label_candidate_identity_must_be_exact():
    from dataclasses import replace
    import copy
    base=_label_scope()
    original=base.split_face_candidates[0]
    walls=_wall_scope((_grid_atom("e_sep"),))
    rooms=_room_scope()
    assert len(compose_grid_separated_room_faces(
        wall_scope=walls,room_scope=rooms,label_scope=base
    ).records)==1
    for invalid in (None,37,""," "," split_label_1","split_label_1 "):
        cand=copy.copy(original)
        cand.record_id=invalid
        result=compose_grid_separated_room_faces(
            wall_scope=walls,room_scope=rooms,
            label_scope=replace(base,split_face_candidates=(cand,))
        )
        assert result.records==()
        assert result.status is EvidenceResolutionStatus.ABSTAINED
    for invalid_label in (None,79,"","   "):
        cand=copy.copy(original)
        cand.label=invalid_label
        result=compose_grid_separated_room_faces(
            wall_scope=walls,room_scope=rooms,
            label_scope=replace(base,split_face_candidates=(cand,))
        )
        assert result.records==()



def test_gpt2_atomic_grid_index_rejects_non_native_source_wall_identifiers():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts,
    )
    source=_room_scope()
    left,right=source.records
    clean=_atomic_source_wall_edge_counts(source,{"w_sep"})
    assert clean
    bad_face=replace(source,records=(replace(left,face_id=73),right))
    invalid=_atomic_source_wall_edge_counts(bad_face,{"w_sep"})
    assert all("73" not in owners for owners in invalid.values())
    for wall in (None,7,""," w_sep","w_sep "):
        injected=replace(left,boundary_wall_edges=(
            (wall,left.boundary_wall_edges[0][1]),
            *left.boundary_wall_edges[1:],
        ))
        invalid=_atomic_source_wall_edge_counts(
            replace(source,records=(injected,right)),{"w_sep"}
        )
        assert all(
            key[0] not in ("None","7"," w_sep","w_sep ")
            for key in invalid
        )
    assert _atomic_source_wall_edge_counts(source,{"w_sep"})==clean



def test_gpt2_local_wall_edge_index_never_coerces_source_owner_ids():
    from dataclasses import replace
    from pb_source_composite_room_face_authority import _local_edge_owners
    source=_room_scope()
    left,right=source.records
    clean=_local_edge_owners(source)
    assert clean
    for bad in (None,71,""," w_left","w_left "):
        altered=replace(left,boundary_wall_edges=(
            (bad,left.boundary_wall_edges[0][1]),
            *left.boundary_wall_edges[1:],
        ))
        index=_local_edge_owners(replace(source,records=(altered,right)))
        assert all(
            key[0] not in ("None","71"," w_left","w_left ")
            for key in index
        )
    bad_face=replace(source,records=(replace(left,face_id=None),right))
    assert all("None" not in owners for owners in _local_edge_owners(bad_face).values())
    assert _local_edge_owners(source)==clean


def test_gpt2_original_source_face_receipt_collection_must_be_sequence():
    from dataclasses import replace
    import copy
    labels=_label_scope()
    first=labels.split_face_candidates[0]
    for malformed in (7, {"record_left":"record_right"}, "record_left", True):
        candidate=copy.copy(first)
        candidate.source_room_face_record_ids=malformed
        result=compose_grid_separated_room_faces(
            wall_scope=_wall_scope((_grid_atom("e_sep"),)),
            room_scope=_room_scope(),
            label_scope=replace(labels,split_face_candidates=(candidate,)),
        )
        assert result.records==()
        assert result.status is EvidenceResolutionStatus.ABSTAINED
    positive=compose_grid_separated_room_faces(
        wall_scope=_wall_scope((_grid_atom("e_sep"),)),
        room_scope=_room_scope(),label_scope=labels,
    )
    assert len(positive.records)==1

def test_gpt2_b01_original_grid_union_first_failure_preserves_real_boundary():
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts, _fully_grid_opposed_wall_evidence,
    )
    room=_room_scope()
    wall=_wall_scope((_grid_atom("e_sep"),))
    grid,evidence=_fully_grid_opposed_wall_evidence(wall)
    indexed=_atomic_source_wall_edge_counts(room,grid)
    ids=("face_left","face_right")
    actual=_physical_union_first_unclosed_gate(
        ids,room_scope=room,fully_grid_wall_ids=grid,
        grid_evidence=evidence,local_counts=indexed,
    )
    assert actual["physical_union_first_unclosed_gate"]==(
        "source_boundary_gates_passed_candidate_only"
    )
    assert actual["physical_union_internal_separator_edge_count"]>0
    assert actual["physical_union_external_grid_edge_count"]==0
    assert actual["new_room_geometry_published"] is False
    assert actual["new_metric_area_published"] is False

    invalid=_physical_union_first_unclosed_gate(
        ids,room_scope=_room_scope(disconnected=True),
        fully_grid_wall_ids=grid,grid_evidence=evidence,local_counts=None,
    )
    assert invalid["physical_union_first_unclosed_gate"]==(
        "source_union_disconnected_overlapping_or_has_holes"
    )
    assert invalid["new_metric_area_published"] is False




def test_gpt2_b01_source_atomic_wall_edge_multiplicity_remains_untrusted():
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts, _fully_grid_opposed_wall_evidence,
    )
    room=_room_scope()
    grid,evidence=_fully_grid_opposed_wall_evidence(
        _wall_scope((_grid_atom("e_sep"),))
    )
    local=_atomic_source_wall_edge_counts(room,grid)
    edge=next(iter(local))
    contaminated={**local,edge:{"face_left":3}}
    invalid=_physical_union_first_unclosed_gate(
        ("face_left","face_right"),
        room_scope=room,fully_grid_wall_ids=grid,
        grid_evidence=evidence,local_counts=contaminated,
    )
    assert invalid["physical_union_first_unclosed_gate"]==(
        "source_atomic_wall_edge_multiplicity_invalid"
    )
    assert not invalid["new_room_geometry_published"]
    assert not invalid["new_metric_area_published"]




def test_gpt2_b01_union_diagnostic_rejects_duplicate_original_face_receipts():
    from dataclasses import replace
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    room=_room_scope()
    left,right=room.records
    for contaminated in (
        replace(room, records=(left,right,replace(left,record_id="alternate"))),
        replace(room, records=(left,replace(right,record_id=left.record_id))),
    ):
        detail=_physical_union_first_unclosed_gate(
            ("face_left","face_right"),
            room_scope=contaminated,
            fully_grid_wall_ids={"w_sep"},
            grid_evidence={"w_sep":("source-w4-grid-receipt",)},
            local_counts={},
        )
        assert detail["physical_union_first_unclosed_gate"]==(
            "source_component_face_receipt_conflict"
        )
        assert detail["new_room_geometry_published"] is False
        assert detail["new_metric_area_published"] is False




def test_gpt2_b01_exterior_grid_owned_source_wall_ids_are_reported_not_assumed():
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts,_fully_grid_opposed_wall_evidence,
    )
    room=_room_scope()
    walls=_wall_scope((_grid_atom("e_sep"),_grid_atom("e_left")))
    grid,evidence=_fully_grid_opposed_wall_evidence(walls)
    assert "w_left" in grid and "w_sep" in grid
    row=_physical_union_first_unclosed_gate(
        ("face_left","face_right"),room_scope=room,
        fully_grid_wall_ids=grid,grid_evidence=evidence,
        local_counts=_atomic_source_wall_edge_counts(room,grid),
    )
    assert row["physical_union_first_unclosed_gate"]==(
        "source_external_grid_owned_subedge_room_incomplete"
    )
    assert "w_left" in row["physical_union_external_grid_w4_ids_diagnostic_only"]
    assert row["physical_union_external_grid_w4_id_count"]>=1
    assert row["new_room_geometry_published"] is False
    assert row["new_metric_area_published"] is False




def test_gpt2_dry_store_competing_room_label_receipts_are_source_face_owned():
    from dataclasses import replace
    from tools.diag_gpt2_grid_component_first_failure import (
        inspect_split_grid_component_first_failure,
    )
    rooms=_room_scope()
    walls=_wall_scope((_grid_atom("e_sep"),))
    labels=_label_scope()
    original=labels.split_face_candidates[0]
    disputed=SimpleNamespace(
        record_id="actual-other-label-receipt",
        face_id="face_left",
        label="OTHER ROOM",
    )
    scope=replace(labels,records=(disputed,))
    row=inspect_split_grid_component_first_failure(
        original,wall_scope=walls,room_scope=rooms,label_scope=scope,
    )
    assert row["first_unclosed_gate"]==(
        "grid_connected_component_has_competing_room_label"
    )
    assert row["competing_original_label_receipt_count"]==1
    assert row["competing_original_label_receipts_diagnostic_only"]==[{
        "producer_receipt_id":"actual-other-label-receipt",
        "native_room_label":"OTHER ROOM",
        "competing_source_face_ids":["face_left"],
        "source_direct_room_label_record_only":True,
    }]
    assert row["source_room_composite_published_by_diagnostic"] is False
    assert row["source_room_metric_area_published"] is False




def test_gpt2_union_diagnostic_unhashable_source_receipt_stays_unavailable():
    from dataclasses import replace
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    room=_room_scope()
    left,right=room.records
    for bad_receipt in ([],{"unsafe":"value"},73,None," record_right"):
        bad=replace(room,records=(left,replace(right,record_id=bad_receipt)))
        report=_physical_union_first_unclosed_gate(
            ("face_left","face_right"),room_scope=bad,
            fully_grid_wall_ids={"w_sep"},grid_evidence={"w_sep":("authentic-grid",)},
            local_counts=None,
        )
        assert report["physical_union_first_unclosed_gate"]==(
            "source_component_face_receipt_conflict"
        )
        assert not report["new_room_geometry_published"]
        assert not report["new_metric_area_published"]




def test_gpt2_grid_first_gate_requires_nonempty_aggregate_separator_evidence():
    from tools.diag_gpt2_grid_component_first_failure import (
        _internal_grid_source_evidence_present,
    )
    edges=(
        ("w_a",((0.,0.),(1.,0.))),
        ("w_b",((1.,0.),(2.,0.))),
    )
    assert _internal_grid_source_evidence_present(
        edges,{"w_a":(),"w_b":("source-w4-grid-b",)}
    )
    assert _internal_grid_source_evidence_present(
        edges,{"w_a":("source-w4-grid-a",),"w_b":()}
    )
    assert not _internal_grid_source_evidence_present(
        edges,{"w_a":(),"w_b":()}
    )
    assert not _internal_grid_source_evidence_present(edges,{})



def test_gpt2_w4_collision_reports_both_original_source_records_without_equivalence():
    from tools.diag_gpt2_grid_component_first_failure import (
        diagnose_original_w4_address_collisions,
    )
    source=(
        SimpleNamespace(
            wall_candidate_id="w4-reused",
            wall_candidate=SimpleNamespace(centerline_pts=((0.,0.),(1.,0.))),
            source_edge_fragments=(SimpleNamespace(edge_id="source-edge-1",
                source_primitive_ids=("native-primitive-1",)),),
            physical_identity=SimpleNamespace(
                candidate_identity_id="shadow-wall-one",
                source_primitive_ids=("native-primitive-1",),
                edge_ids=("source-edge-1",),
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        ),
        SimpleNamespace(
            wall_candidate_id="w4-reused",
            wall_candidate=SimpleNamespace(centerline_pts=((5.,5.),(6.,5.))),
            source_edge_fragments=(SimpleNamespace(edge_id="source-edge-2",
                source_primitive_ids=("native-primitive-2",)),),
            physical_identity=SimpleNamespace(
                candidate_identity_id="shadow-wall-two",
                source_primitive_ids=("native-primitive-2",),
                edge_ids=("source-edge-2",),
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        ),
        SimpleNamespace(
            wall_candidate_id="independent",
            wall_candidate=SimpleNamespace(centerline_pts=((3.,2.),(4.,2.))),
            source_edge_fragments=(),
        ),
        SimpleNamespace(
            wall_candidate_id=[],
            wall_candidate=SimpleNamespace(centerline_pts=((0.,0.),(0.,1.))),
            source_edge_fragments=(),
        ),
    )
    report=diagnose_original_w4_address_collisions(source)
    assert report["colliding_original_w4_ids"]==["w4-reused"]
    assert report["individual_original_record_count"]==2
    assert [row["source_record_ordinal"] for row in report[
        "original_collision_records_diagnostic_only"
    ]]==[0,1]
    assert [
        row["source_fragment_primitive_ids_sample"]
        for row in report["original_collision_records_diagnostic_only"]
    ]==[[["native-primitive-1"]],[["native-primitive-2"]]]
    assert [
        row["source_fragment_edge_ids_sample"]
        for row in report["original_collision_records_diagnostic_only"]
    ]==[["source-edge-1"],["source-edge-2"]]
    assert report["original_collision_records_diagnostic_only"][0][
        "original_centerline_points_diagnostic_only"
    ] != report["original_collision_records_diagnostic_only"][1][
        "original_centerline_points_diagnostic_only"
    ]
    assert [
        row["shadow_physical_candidate_identity_id"]
        for row in report["original_collision_records_diagnostic_only"]
    ] == ["shadow-wall-one", "shadow-wall-two"]
    assert [
        row["shadow_identity_source_primitive_ids_sample"]
        for row in report["original_collision_records_diagnostic_only"]
    ] == [["native-primitive-1"], ["native-primitive-2"]]
    assert all(
        row["source_fragment_receipts_complete"]
        and row["shadow_identity_lineage_valid"]
        and row["shadow_physical_identity_status"] == "corroborated"
        for row in report["original_collision_records_diagnostic_only"][:2]
    )
    assert not report["physical_wall_equivalence_proven"]
    assert all(
        row["physical_wall_equivalence_proven"] is False
        and row["source_room_boundary_published"] is False
        for row in report["original_collision_records_diagnostic_only"]
    )



def test_gpt2_missing_original_w4_fragment_or_shadow_identity_is_not_valid_lineage():
    from tools.diag_gpt2_grid_component_first_failure import (
        diagnose_original_w4_address_collisions,
    )
    broken=SimpleNamespace(
        wall_candidate_id="reused-native-w4",
        wall_candidate=SimpleNamespace(centerline_pts=((1.,2.),(3.,4.))),
        source_edge_fragments=(),
        physical_identity=None,
    )
    well_formed=SimpleNamespace(
        wall_candidate_id="reused-native-w4",
        wall_candidate=SimpleNamespace(centerline_pts=((5.,6.),(7.,8.))),
        source_edge_fragments=(SimpleNamespace(
            edge_id="source-edge-id",
            source_primitive_ids=("source-w2-primitive",),
        ),),
        physical_identity=SimpleNamespace(
            candidate_identity_id="w4-shadow-not-equivalence",
            source_primitive_ids=("source-w2-primitive",),
            edge_ids=("source-edge-id",),
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )
    report=diagnose_original_w4_address_collisions((broken,well_formed))
    assert report["individual_original_record_count"]==2
    missing,real=report["original_collision_records_diagnostic_only"]
    assert missing["source_fragment_receipts_complete"] is False
    assert missing["shadow_identity_lineage_valid"] is False
    assert real["source_fragment_receipts_complete"] is True
    assert real["shadow_identity_lineage_valid"] is True
    assert real["original_fragment_primitives_owned_by_shadow_identity"] is True
    assert missing["original_fragment_primitives_owned_by_shadow_identity"] is False
    assert missing["physical_wall_equivalence_proven"] is False
    assert real["physical_wall_equivalence_proven"] is False



def test_gpt2_original_w4_fragment_lineage_mismatch_does_not_prove_shared_wall():
    from tools.diag_gpt2_grid_component_first_failure import (
        diagnose_original_w4_address_collisions,
    )
    def row(source_primitive,shadow_primitive):
        return SimpleNamespace(
            wall_candidate_id="colliding-original-address",
            wall_candidate=SimpleNamespace(centerline_pts=((0.,0.),(10.,0.))),
            source_edge_fragments=(SimpleNamespace(
                edge_id="real-original-edge",source_primitive_ids=(source_primitive,),
            ),),
            physical_identity=SimpleNamespace(
                candidate_identity_id="candidate-shadow-only",
                source_primitive_ids=(shadow_primitive,),
                edge_ids=("real-original-edge",),
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        )
    rows=diagnose_original_w4_address_collisions((
        row("source-primitive-one","source-primitive-one"),
        row("source-primitive-two","unrelated-primitive"),
    ))["original_collision_records_diagnostic_only"]
    assert rows[0]["original_fragment_primitives_owned_by_shadow_identity"] is True
    assert rows[1]["original_fragment_primitives_owned_by_shadow_identity"] is False
    assert all(r["physical_wall_equivalence_proven"] is False for r in rows)
    assert all(r["source_room_boundary_published"] is False for r in rows)



def test_gpt2_first_invalid_source_polygon_reports_original_face_receipt():
    from dataclasses import replace
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    faces=_room_scope()
    original,other=faces.records
    invalid=replace(original,polygon_pdf_pts=(
        (0.,0.),(10.,10.),(10.,0.),(0.,10.),
    ))
    report=_physical_union_first_unclosed_gate(
        ("face_left","face_right"),
        room_scope=replace(faces,records=(invalid,other)),
        fully_grid_wall_ids=set(),grid_evidence={},local_counts=None,
    )
    assert report["physical_union_first_unclosed_gate"] == "source_component_polygon_invalid"
    failed=report["invalid_constituent_source_face_receipts_diagnostic_only"]
    assert any(
        row["original_source_face_id"]=="face_left"
        and row["original_source_face_record_id"]==original.record_id
        and row["physical_room_polygon_published"] is False
        for row in failed
    )
    assert report["physical_union_invalid_constituent_face_count"]>=1
    assert report["new_room_geometry_published"] is False



def test_gpt2_failed_two_sided_source_w4_reports_original_edge_and_owners():
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts,_fully_grid_opposed_wall_evidence,
    )
    faces=_room_scope()
    grid,_=_fully_grid_opposed_wall_evidence(_wall_scope((_grid_atom("e_sep"),)))
    counts=_atomic_source_wall_edge_counts(faces,grid)
    report=_physical_union_first_unclosed_gate(
        ("face_left","face_right"),room_scope=faces,
        fully_grid_wall_ids=set(),grid_evidence={},local_counts=counts,
    )
    assert report["physical_union_first_unclosed_gate"]==(
        "source_internal_wall_edge_not_two_sided_grid_owned"
    )
    witness=report["first_invalid_internal_wall_receipt_diagnostic_only"]
    assert witness["original_w4_wall_id"]
    assert len(witness["original_atomic_wall_edge_pdf_pts"])==2
    assert witness["grid_opposed_source_wall_authenticated"] is False
    assert witness["no_wall_or_room_equivalence_inferred"] is True
    assert report["new_metric_area_published"] is False


def test_gpt2_w4_fragment_edge_must_belong_to_its_own_source_shadow():
    from tools.diag_gpt2_grid_component_first_failure import (
        diagnose_original_w4_address_collisions,
    )
    def candidate(shadow_edges):
        return SimpleNamespace(
            wall_candidate_id="colliding-source-w4",
            wall_candidate=SimpleNamespace(centerline_pts=((0.,0.),(8.,0.))),
            source_edge_fragments=(SimpleNamespace(
                edge_id="source-edge-original",
                source_primitive_ids=("original-primitive",),
            ),),
            physical_identity=SimpleNamespace(
                candidate_identity_id="shadow-native-id",
                source_primitive_ids=("original-primitive",),
                edge_ids=shadow_edges,
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        )
    entries=diagnose_original_w4_address_collisions((
        candidate(("source-edge-original",)),
        candidate(("foreign-edge",)),
    ))["original_collision_records_diagnostic_only"]
    assert entries[0]["original_fragment_primitives_owned_by_shadow_identity"]
    assert entries[1]["original_fragment_primitives_owned_by_shadow_identity"]
    assert entries[0]["original_fragment_edges_owned_by_shadow_identity"] is True
    assert entries[1]["original_fragment_edges_owned_by_shadow_identity"] is False
    assert entries[0]["shadow_source_geometry_and_lineage_usable_diagnostic_only"] is True
    assert entries[1]["shadow_source_geometry_and_lineage_usable_diagnostic_only"] is False
    assert not any(row["physical_wall_equivalence_proven"] for row in entries)


def test_gpt2_original_w4_fragment_edge_id_must_belong_to_its_shadow_lineage():
    from tools.diag_gpt2_grid_component_first_failure import (
        diagnose_original_w4_address_collisions,
    )
    def row(fragment_edge, shadow_edge):
        return SimpleNamespace(
            wall_candidate_id="one-reused-native-w4-address",
            wall_candidate=SimpleNamespace(centerline_pts=((0.,0.),(10.,0.))),
            source_edge_fragments=(SimpleNamespace(
                edge_id=fragment_edge,
                source_primitive_ids=("source-primitive",),
            ),),
            physical_identity=SimpleNamespace(
                candidate_identity_id="original-shadow-only",
                source_primitive_ids=("source-primitive",),
                edge_ids=(shadow_edge,),
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        )
    rows=diagnose_original_w4_address_collisions((
        row("original-edge-a","original-edge-a"),
        row("foreign-edge","different-shadow-edge"),
    ))["original_collision_records_diagnostic_only"]
    assert rows[0]["original_fragment_primitives_owned_by_shadow_identity"]
    assert rows[1]["original_fragment_primitives_owned_by_shadow_identity"]
    assert rows[0]["original_fragment_edges_owned_by_shadow_identity"] is True
    assert rows[1]["original_fragment_edges_owned_by_shadow_identity"] is False
    assert all(r["physical_wall_equivalence_proven"] is False for r in rows)


def test_competing_split_label_malformed_native_face_inventory_abstains_not_crashes():
    """Do not stringify foreign face IDs or raise on corrupted original words."""
    import copy
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _component_has_conflicting_label,
    )

    labels = _label_scope()
    original = labels.split_face_candidates[0]
    faces = ("face_left", "face_right")
    walls = _wall_scope((_grid_atom("e_sep"),))
    rooms = _room_scope()
    assert not _component_has_conflicting_label(
        faces, original, label_scope=labels
    )
    assert len(compose_grid_separated_room_faces(
        wall_scope=walls, room_scope=rooms, label_scope=labels
    ).records) == 1

    for foreign_words in (
        None, 7, "face_left", (), (" face_left",),
        ("face_right ",), ("face_left", None),
        ("face_right", 7), ("face_left", ["face_right"]),
    ):
        foreign = copy.copy(original)
        foreign.record_id = "independent-original-label"
        foreign.word_face_ids = foreign_words
        scope = replace(
            labels, split_face_candidates=(original, foreign)
        )
        assert _component_has_conflicting_label(
            faces, original, label_scope=scope
        )
        output = compose_grid_separated_room_faces(
            wall_scope=walls, room_scope=rooms, label_scope=scope
        )
        assert output.records == ()
        assert output.status is EvidenceResolutionStatus.ABSTAINED

    # An authenticated distinct word-face inventory must not be rewritten
    # into a competing owner by casting IDs or proximity.
    unrelated = copy.copy(original)
    unrelated.record_id = "independent-original-label"
    unrelated.word_face_ids = ("foreign_face_a", "foreign_face_b")
    scope = replace(labels, split_face_candidates=(original, unrelated))
    assert not _component_has_conflicting_label(
        faces, original, label_scope=scope
    )
    output = compose_grid_separated_room_faces(
        wall_scope=walls, room_scope=rooms, label_scope=scope
    )
    assert len(output.records) == 1
    assert output.status is EvidenceResolutionStatus.CANDIDATE
    assert output.unresolved_label_candidate_ids == ("independent-original-label",)


def test_corrupt_native_constituent_polygon_abstains_without_source_room_repair():
    """Invalid original PDF face coordinates cannot mint a composite room."""
    from dataclasses import replace

    walls = _wall_scope((_grid_atom("e_sep"),))
    faces = _room_scope()
    labels = _label_scope()
    assert len(compose_grid_separated_room_faces(
        wall_scope=walls, room_scope=faces, label_scope=labels
    ).records) == 1
    first, second = faces.records
    for invalid_ring in (
        ("not-a-source-coordinate",),
        ((0.0, 0.0), (10.0, 0.0), (10.0, "not-numeric"), (0.0, 10.0)),
    ):
        damaged = replace(first, polygon_pdf_pts=invalid_ring)
        result = compose_grid_separated_room_faces(
            wall_scope=walls,
            room_scope=replace(faces, records=(damaged, second)),
            label_scope=labels,
        )
        assert result.records == ()
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.unresolved_label_candidate_ids == ("split_label_1",)


def test_native_source_geos_exception_cannot_abort_room_handoff(monkeypatch):
    """A GEOS topology failure is an unresolved source face, never a repair."""
    import pb_source_composite_room_face_authority as module
    from shapely.errors import GEOSException

    wall_scope = _wall_scope((_grid_atom("e_sep"),))
    room_scope = _room_scope()
    label_scope = _label_scope()

    def bad_geos(*_args, **_kwargs):
        raise GEOSException("synthetic GEOS source ring/topology failure")

    for target in ("Polygon", "unary_union"):
        with monkeypatch.context() as patch:
            patch.setattr(module, target, bad_geos)
            result = module.compose_grid_separated_room_faces(
                wall_scope=wall_scope,
                room_scope=room_scope,
                label_scope=label_scope,
            )
            assert result.status is EvidenceResolutionStatus.ABSTAINED
            assert result.records == ()
            assert result.unresolved_label_candidate_ids == ("split_label_1",)


def test_original_external_grid_w4_diagnostic_preserves_exact_atomic_edge_and_face():
    """The source wall's unclosed physical subedge is not an inferred room."""
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
    )
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts, _fully_grid_opposed_wall_evidence,
    )
    faces = _room_scope()
    walls = _wall_scope((_grid_atom("e_sep"), _grid_atom("e_left")))
    grid, evidence = _fully_grid_opposed_wall_evidence(walls)
    result = _physical_union_first_unclosed_gate(
        ("face_left", "face_right"), room_scope=faces,
        fully_grid_wall_ids=grid, grid_evidence=evidence,
        local_counts=_atomic_source_wall_edge_counts(faces, grid),
    )
    assert result["physical_union_first_unclosed_gate"] == (
        "source_external_grid_owned_subedge_room_incomplete"
    )
    rows = result["physical_union_external_grid_atomic_subedges_diagnostic_only"]
    assert rows
    rows = [r for r in rows if r["original_w4_wall_id"] == "w_left"]
    assert len(rows) == 1
    assert rows[0]["original_atomic_wall_edge_pdf_pts"] == [
        [0.0, 0.0], [0.0, 10.0]
    ]
    assert rows[0]["source_component_face_ids"] == ["face_left"]
    assert rows[0]["original_global_source_face_ids"] == ["face_left"]
    assert rows[0]["new_wall_or_room_equivalence_inferred"] is False
    assert rows[0]["source_edge_used_to_mint_physical_room"] is False
    assert result["new_room_geometry_published"] is False


def test_original_w4_w2_grid_opposition_report_keeps_native_edge_receipts():
    """One W4 address needs every W2 edge's own original source opposition."""
    from types import SimpleNamespace
    from dataclasses import replace
    from tools.diag_gpt2_grid_component_first_failure import (
        inspect_original_w4_grid_opposition_first_gate,
    )
    walls = _wall_scope((_grid_atom("e_sep", "opposed-source-evidence"),))
    positive = inspect_original_w4_grid_opposition_first_gate(walls, "w_sep")
    assert positive["original_w4_source_candidate_count"] == 1
    assert positive["original_w2_edge_ids_diagnostic_only"] == ["e_sep"]
    assert positive["source_grid_opposed_w2_edge_ids_diagnostic_only"] == ["e_sep"]
    assert positive["missing_original_grid_opposed_w2_edge_ids_diagnostic_only"] == []
    assert positive["original_w4_grid_first_gate"] == (
        "source_w2_grid_opposition_observed_not_physical_equivalence"
    )
    assert positive["physical_wall_equivalence_proven"] is False
    assert positive["original_w4_grid_opposition_published"] is False

    missing = inspect_original_w4_grid_opposition_first_gate(
        _wall_scope(()), "w_sep"
    )
    assert missing["missing_original_grid_opposed_w2_edge_ids_diagnostic_only"] == [
        "e_sep"
    ]
    assert missing["original_w4_grid_first_gate"] == (
        "source_w2_grid_opposition_missing"
    )
    assert missing["room_geometry_published"] is False

    unrelated = inspect_original_w4_grid_opposition_first_gate(
        walls, "nonexistent-wall"
    )
    assert unrelated["original_w4_grid_first_gate"] == "source_w4_identity_unavailable"
    duplicate_scope = replace(
        walls, records=(*walls.records, walls.records[0])
    )
    duplicate = inspect_original_w4_grid_opposition_first_gate(
        duplicate_scope, "w_sep"
    )
    assert duplicate["original_w4_grid_first_gate"] == "source_w4_identity_collision"
    assert duplicate["physical_wall_equivalence_proven"] is False

    for invalid in (None, 42, " w_sep", "", "w_sep "):
        row = inspect_original_w4_grid_opposition_first_gate(walls, invalid)
        assert row["original_w4_grid_first_gate"] == "source_w4_identity_unavailable"
        assert row["room_geometry_published"] is False

    # A numeric original W2 edge must NOT become a plausible literal "42"
    # simply because the older production helper stringifies its key.
    import copy
    original = walls.records[0]
    corrupt = copy.copy(original)
    corrupt.wall_candidate = copy.copy(original.wall_candidate)
    corrupt.wall_candidate.face_a_segment_ids = (42,)
    corrupted = replace(
        walls, records=(corrupt, *walls.records[1:])
    )
    invalid_w2 = inspect_original_w4_grid_opposition_first_gate(
        corrupted, "w_sep"
    )
    assert invalid_w2["original_w4_grid_first_gate"] == (
        "source_w2_fragment_identity_unavailable"
    )
    assert invalid_w2["room_geometry_published"] is False


def test_original_w2_native_lineage_crosscheck_is_only_diagnostic():
    """Actual W2 edge + original source metadata still cannot classify a GRID."""
    import copy
    from dataclasses import replace
    from tools.diag_gpt2_grid_component_first_failure import (
        inspect_original_w4_grid_opposition_first_gate,
    )

    original = _wall_scope(())
    record = copy.copy(original.records[0])
    record.physical_identity = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        edge_ids=("e_sep",),
        source_primitive_ids=("source-line-a",),
    )
    record.source_edge_fragments = (
        SimpleNamespace(edge_id="e_sep", source_primitive_ids=("source-line-a",)),
    )
    descriptor = SimpleNamespace(
        wall_candidate_id="w_sep",
        source_primitive_ids=("source-line-a",),
        matched_source_primitive_ids=("source-line-a",),
        missing_source_primitive_ids=(),
    )
    metadata = SimpleNamespace(
        status="described",
        page_id=LINEAGE["page_id"],
        decision_scope_id=LINEAGE["decision_scope_id"],
        descriptors=(descriptor,),
    )
    source = replace(
        original, records=(record, *original.records[1:]),
        source_metadata_table=metadata,
    )
    output = inspect_original_w4_grid_opposition_first_gate(source, "w_sep")
    assert output["original_w4_grid_first_gate"] == "source_w2_grid_opposition_missing"
    assert output["missing_original_grid_opposed_w2_edge_ids_diagnostic_only"] == [
        "e_sep"
    ]
    witness = output["original_w2_fragment_source_receipts_diagnostic_only"][0]
    assert witness["native_source_primitive_ids"] == ["source-line-a"]
    assert witness["original_w2_w4_native_lineage_crosschecked_diagnostic_only"] is True
    assert witness["original_w2_w4_native_lineage_first_gate_diagnostic_only"] == (
        "w2_w4_shadow_and_native_receipts_agree_role_still_unproven"
    )
    assert witness["source_parent_membership_proven"] is False
    assert witness["source_grid_or_wall_role_authenticated_by_crosscheck"] is False
    assert output["physical_wall_equivalence_proven"] is False
    assert output["room_geometry_published"] is False

    # An exact native ID must be cross-checked against BOTH the W4 shadow
    # identity and the actual source metadata. Shared names alone cannot pass.
    def first_gate(*, identity=None, table=None, fragments=None):
        altered = copy.copy(record)
        altered.physical_identity = identity if identity is not None else (
            record.physical_identity
        )
        altered.source_edge_fragments = fragments if fragments is not None else (
            record.source_edge_fragments
        )
        scoped = replace(
            source, records=(altered, *source.records[1:]),
            source_metadata_table=table if table is not None else metadata,
        )
        row = inspect_original_w4_grid_opposition_first_gate(scoped, "w_sep")
        witness = row["original_w2_fragment_source_receipts_diagnostic_only"][0]
        assert witness["original_w2_w4_native_lineage_crosschecked_diagnostic_only"] is False
        assert witness["source_grid_or_wall_role_authenticated_by_crosscheck"] is False
        assert row["original_w4_grid_first_gate"] == "source_w2_grid_opposition_missing"
        return witness["original_w2_w4_native_lineage_first_gate_diagnostic_only"]

    assert first_gate(identity=SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        edge_ids=("different-edge",),
        source_primitive_ids=("source-line-a",),
    )) == "w2_edge_absent_from_w4_shadow_identity"
    assert first_gate(identity=SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        edge_ids=("e_sep",),
        source_primitive_ids=("foreign-source",),
    )) == "source_primitive_absent_from_w4_shadow_identity"
    assert first_gate(table=SimpleNamespace(
        status="described",
        page_id="different-source-page",
        decision_scope_id=LINEAGE["decision_scope_id"],
        descriptors=(descriptor,),
    )) == "original_native_scope_metadata_unavailable"
    assert first_gate(table=SimpleNamespace(
        status="described",
        page_id=LINEAGE["page_id"],
        decision_scope_id=LINEAGE["decision_scope_id"],
        descriptors=(descriptor, descriptor),
    )) == "original_native_w4_descriptor_not_unique"
    assert first_gate(table=SimpleNamespace(
        status="described",
        page_id=LINEAGE["page_id"],
        decision_scope_id=LINEAGE["decision_scope_id"],
        descriptors=(SimpleNamespace(
            wall_candidate_id="w_sep",
            source_primitive_ids=("source-line-a",),
            matched_source_primitive_ids=(),
            missing_source_primitive_ids=("source-line-a",),
        ),),
    )) == "original_native_source_receipt_unavailable_or_conflicting"
    assert first_gate(fragments=(
        SimpleNamespace(edge_id="e_sep", source_primitive_ids=(42,)),
    )) == "source_fragment_receipt_unavailable"


def test_pos_external_grid_atomic_source_fragment_cannot_mint_second_face():
    """Exact source W2 fragment receipts never equal physical two-sided closure."""
    import copy
    from dataclasses import replace
    from pb_source_composite_room_face_authority import (
        _atomic_source_wall_edge_counts, _fully_grid_opposed_wall_evidence,
    )
    from tools.diag_gpt2_grid_component_first_failure import (
        _physical_union_first_unclosed_gate,
        inspect_external_atomic_grid_w2_source_fragments,
    )
    faces = _room_scope()
    walls = _wall_scope((_grid_atom("e_sep"), _grid_atom("e_left")))
    grid, evidence = _fully_grid_opposed_wall_evidence(walls)
    union = _physical_union_first_unclosed_gate(
        ("face_left", "face_right"),
        room_scope=faces, fully_grid_wall_ids=grid,
        grid_evidence=evidence,
        local_counts=_atomic_source_wall_edge_counts(faces, grid),
    )
    assert union["physical_union_first_unclosed_gate"] == (
        "source_external_grid_owned_subedge_room_incomplete"
    )
    original_left = copy.copy(walls.records[1])
    original_left.source_edge_fragments = (
        SimpleNamespace(
            edge_id="original-W2-left",
            geometry=((0., 0.), (0., 10.)),
            source_primitive_ids=("original-source-primitive-1",),
        ),
    )
    w2_scope = replace(
        walls, records=(walls.records[0], original_left, walls.records[2])
    )
    result = inspect_external_atomic_grid_w2_source_fragments(w2_scope, union)
    assert len(result) == 1
    assert result[0]["original_w4_wall_id"] == "w_left"
    assert result[0]["original_global_source_face_ids_diagnostic_only"] == [
        "face_left"
    ]
    assert result[0]["original_w4_candidate_record_count"] == 1
    assert result[0]["source_first_unclosed_gate"] == (
        "original_w2_fragment_observed_second_face_missing"
    )
    assert result[0]["source_w2_fragment_candidates_diagnostic_only"] == [{
        "original_w2_edge_id": "original-W2-left",
        "native_source_primitive_ids": ["original-source-primitive-1"],
        "exact_source_quantized_collinearity_only": True,
        "second_face_owner_proven": False,
    }]
    assert result[0]["source_second_face_owner_authenticated"] is False
    assert result[0]["source_w2_grid_role_authenticated_by_this_diagnostic"] is False
    assert result[0]["source_room_geometry_or_area_published"] is False

    # Nearby/parallel native geometry may NEVER stand in for the actual source
    # fragment, even though a different source face is geometrically nearby.
    misplaced = copy.copy(original_left)
    misplaced.source_edge_fragments = (
        SimpleNamespace(
            edge_id="wrong-native-W2",
            geometry=((1., 0.), (1., 10.)),
            source_primitive_ids=("native-other",),
        ),
    )
    no_fragment = replace(
        walls, records=(walls.records[0], misplaced, walls.records[2])
    )
    assert inspect_external_atomic_grid_w2_source_fragments(
        no_fragment, union
    )[0]["source_first_unclosed_gate"] == (
        "original_atomic_wall_subedge_w2_fragment_unavailable"
    )

    # Competing physical W4 producer records cannot be silently collapsed.
    duplicated = replace(w2_scope, records=(*w2_scope.records, original_left))
    assert inspect_external_atomic_grid_w2_source_fragments(
        duplicated, union
    )[0]["source_first_unclosed_gate"] == "original_w4_identity_collision"

    corrupt = copy.copy(original_left)
    corrupt.source_edge_fragments = (
        SimpleNamespace(
            edge_id="bad-w2", geometry=((0., 0.), (0., 10.)),
            source_primitive_ids=("",),
        ),
    )
    corrupt_scope = replace(
        walls, records=(walls.records[0], corrupt, walls.records[2])
    )
    assert inspect_external_atomic_grid_w2_source_fragments(
        corrupt_scope, union
    )[0]["source_first_unclosed_gate"] == (
        "original_w2_fragment_source_receipt_invalid"
    )
