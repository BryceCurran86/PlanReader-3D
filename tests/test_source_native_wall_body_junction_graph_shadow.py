"""Physical source path/junction graph: L/T/cross, no collinear snap, no FIRM."""
from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from shapely import affinity

from pb_source_native_exterior_endpoint_authority_shadow import REASON_COMPETING
from pb_source_native_wall_body_junction_graph_shadow import (
    GEOMETRY_INFERRED,
    GEOMETRY_OBSERVED,
    JUNCTION_COLLINEAR_GAP,
    JUNCTION_CORNER_RETURN,
    JUNCTION_CROSS,
    JUNCTION_L,
    JUNCTION_MULTI,
    JUNCTION_T,
    JUNCTION_WINDOW_CONTINUITY,
    REASON_DUPLICATE_PATH_OWNER,
    REASON_INFERRED_JOIN_FORBIDDEN,
    REASON_LAYER_NOT_PHYSICAL,
    REASON_MISSING_PROVENANCE,
    REASON_NON_STRUCTURAL,
    REASON_UNCLOSED_EXTERIOR,
    REASON_WINDOW_NO_UNIQUE_JAMB,
    authenticate_window_continuity_topology,
    audit_source_native_exterior_cycle,
    classify_source_wall_body_junctions,
    classify_window_continuity_edges,
)


def _strip(source_id, bounds):
    return SimpleNamespace(
        polygon=box(*bounds),
        path_index=source_id,
        native_path_indices=lambda: (source_id,),
    )


def _drawing(layer="Enclosure_WallExternal"):
    return {"layer": layer, "fill": (0.0, 0.0, 0.0)}


def _kinds(junctions):
    return {item.junction_kind for item in junctions}


def test_l_corner_is_observed_candidate_not_firm():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10, 0, 11, 10)))
    drawings = (_drawing(), _drawing())
    bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert {item.provenance.geometry_kind for item in bodies} == {GEOMETRY_OBSERVED}
    assert JUNCTION_CORNER_RETURN in _kinds(junctions) or JUNCTION_L in _kinds(junctions)
    assert all(item.physical_join_authenticated is False for item in junctions)
    assert all(item.measurement_authorized is False for item in junctions)
    assert all(item.provenance_geometry_kind != GEOMETRY_INFERRED for item in junctions)


def test_t_junction_does_not_invent_a_through_wall():
    bars = (_strip(0, (0, 4, 20, 5)), _strip(1, (9, 0, 10, 4)))
    drawings = (_drawing("A-WALL"), _drawing("A-WALL"))
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert JUNCTION_T in _kinds(junctions)
    assert all(item.physical_join_authenticated is False for item in junctions)


def test_cross_junction_keeps_both_bodies():
    bars = (_strip(0, (0, 5, 20, 7)), _strip(1, (9, 0, 11, 20)))
    drawings = (_drawing("A-WALL"), _drawing("A-WALL"))
    bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert len(bodies) == 2
    assert JUNCTION_CROSS in _kinds(junctions)
    assert all(item.measurement_authorized is False for item in junctions)


def test_collinear_gap_is_not_snapped_into_a_wall():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10.4, 0, 20, 1)))
    drawings = (_drawing(), _drawing())
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    gaps = [item for item in junctions if item.junction_kind == JUNCTION_COLLINEAR_GAP]
    assert gaps
    assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in gaps)
    assert all(item.reason == REASON_INFERRED_JOIN_FORBIDDEN for item in gaps)
    assert all(item.physical_join_authenticated is False for item in gaps)


def test_multi_face_meeting_abstains_without_wall_body_authority():
    bars = (
        _strip(0, (0, 10, 20, 11)),
        _strip(1, (10, 0, 11, 10)),
        _strip(2, (10, 11, 11, 21)),
    )
    drawings = (_drawing("A-WALL"), _drawing("A-WALL"), _drawing("A-WALL"))
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert JUNCTION_MULTI in _kinds(junctions)
    multi = [item for item in junctions if item.junction_kind == JUNCTION_MULTI]
    assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in multi)


def test_missing_path_ids_fail_closed_on_provenance():
    bar = SimpleNamespace(
        polygon=box(0, 0, 10, 1),
        path_index=0,
        native_path_indices=lambda: (),
    )
    bodies, _junctions = classify_source_wall_body_junctions((bar,), ())
    assert bodies[0].status is EvidenceResolutionStatus.ABSTAINED
    assert bodies[0].reason == REASON_MISSING_PROVENANCE
    assert bodies[0].physical_wall_authenticated is False


def test_duplicate_path_owner_is_rejected():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(0, (20, 0, 30, 1)))
    drawings = (_drawing(),)
    bodies, _junctions = classify_source_wall_body_junctions(bars, drawings)
    assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in bodies)
    assert all(item.reason == REASON_DUPLICATE_PATH_OWNER for item in bodies)


def test_l_t_cross_records_page_viewport_and_pdf_coords():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10, 0, 11, 10)))
    drawings = (
        {"layer": "Enclosure_WallExternal", "fill": (0.0, 0.0, 0.0), "viewport_id": "vp-a"},
        {"layer": "Enclosure_WallExternal", "fill": (0.0, 0.0, 0.0), "viewport_id": "vp-a"},
    )
    bodies, junctions = classify_source_wall_body_junctions(bars, drawings, page_index=2)
    assert all(item.provenance.page_index == 2 for item in bodies)
    assert all(item.provenance.viewport_id == "vp-a" for item in bodies)
    assert all(item.provenance.native_path_ids for item in bodies)
    assert all(item.page_index == 2 for item in junctions)
    assert all(len(item.contact_pdf_pts) == 2 for item in junctions)
    assert all(item.provenance.geometry_kind == GEOMETRY_OBSERVED for item in bodies)


def test_annotation_furniture_swing_green_dim_are_not_structural_joins():
    wall = _strip(0, (0, 4, 20, 6))
    rivals = (
        (_strip(1, (9, 0, 11, 20)), {"layer": "A-ANNO-TEXT", "fill": (0.0, 0.0, 0.0)}),
        (_strip(1, (9, 0, 11, 20)), {"layer": "A-FURNITURE", "fill": (0.0, 0.0, 0.0)}),
        (_strip(1, (9, 0, 11, 20)), {"layer": "Interior_Joinery", "fill": (0.0, 0.0, 0.0)}),
        (_strip(1, (9, 0, 11, 20)), {"layer": "A-WALL", "fill": (0.1, 0.9, 0.1)}),
        (_strip(1, (9, 0, 11, 20)), {"layer": "A-ANNO-DIMS", "fill": (0.0, 0.0, 0.0)}),
    )
    wall_drawing = _drawing()
    for rival, drawing in rivals:
        _bodies, junctions = classify_source_wall_body_junctions(
            (wall, rival), (wall_drawing, drawing),
        )
        assert junctions
        assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in junctions)
        assert all(
            item.reason in {REASON_COMPETING, REASON_NON_STRUCTURAL}
            for item in junctions
        )
        assert all(item.physical_join_authenticated is False for item in junctions)


def test_diagonal_furniture_crossing_is_not_a_structural_join():
    wall = _strip(0, (0, 4, 20, 6))
    diagonal = _strip(1, (9, 0, 11, 20))
    drawings = (
        _drawing(),
        {
            "layer": "Enclosure_WallExternal",
            "fill": (0.0, 0.0, 0.0),
            "items": (("l", (210, 130), (800, 490)),),
        },
    )
    _bodies, junctions = classify_source_wall_body_junctions((wall, diagonal), drawings)
    assert junctions
    assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in junctions)
    assert all(item.reason == REASON_NON_STRUCTURAL for item in junctions)


def test_acacia_222pt_gap_stays_open_and_unjoined():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (232.6, 0, 242.6, 1)))
    drawings = (_drawing(), _drawing())
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert all(item.junction_kind != JUNCTION_COLLINEAR_GAP for item in junctions)
    assert all(item.physical_join_authenticated is False for item in junctions)
    cycle = audit_source_native_exterior_cycle(bars, drawings, page_index=1)
    assert cycle["candidate_outer_cycle_count"] == 0
    first = cycle["first_unclosed_endpoint"]
    assert first is not None
    assert first["reason"] == REASON_UNCLOSED_EXTERIOR
    assert set(first["native_path_ids"]) | set(first["nearby_native_path_ids"]) == {0, 1}
    assert first["separation_pdf_pts"] == 222.6
    assert first["physical_join_authenticated"] is False
    assert cycle["measurement_authorized"] is False
    assert cycle["layer_name_physical_promotion"] is False


def test_point4252_collinear_gap_is_not_a_join():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10.4252, 0, 20.4252, 1)))
    drawings = (_drawing(), _drawing())
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    gaps = [item for item in junctions if item.junction_kind == JUNCTION_COLLINEAR_GAP]
    assert gaps
    assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in gaps)
    assert all(item.reason == REASON_INFERRED_JOIN_FORBIDDEN for item in gaps)


def test_zero_separation_collinear_flush_does_not_invent_a_wall():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10, 0, 20, 1)))
    drawings = (_drawing(), _drawing())
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert all(item.junction_kind != JUNCTION_COLLINEAR_GAP for item in junctions)
    assert all(item.physical_join_authenticated is False for item in junctions)


def test_gap_spanning_unrelated_room_is_not_a_join():
    bars = (
        _strip(0, (0, 0, 10, 1)),
        _strip(1, (50, 0, 60, 1)),
        _strip(2, (25, 0, 26, 20)),
    )
    drawings = (_drawing(), _drawing(), _drawing("A-WALL"))
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    assert all(
        not (
            set(item.left_path_ids) | set(item.right_path_ids) == {0, 1}
            and item.status is not EvidenceResolutionStatus.ABSTAINED
        )
        for item in junctions
    )
    cycle = audit_source_native_exterior_cycle(bars, drawings)
    assert cycle["candidate_outer_cycle_count"] == 0
    assert cycle["first_unclosed_endpoint"]["reason"] == REASON_UNCLOSED_EXTERIOR


def test_rotation_and_translation_keep_l_corner_kind():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10, 0, 11, 10)))
    drawings = (_drawing(), _drawing())
    _bodies, original = classify_source_wall_body_junctions(bars, drawings)

    def moved(dx, dy, angle=0.0):
        out = []
        for item in bars:
            geom = affinity.translate(item.polygon, xoff=dx, yoff=dy)
            if angle:
                geom = affinity.rotate(geom, angle, origin=(0, 0))
            out.append(SimpleNamespace(
                polygon=geom,
                path_index=item.path_index,
                native_path_indices=item.native_path_indices,
            ))
        return tuple(out)

    for transformed in (moved(40, 15), moved(0, 0, 90)):
        _bodies, junctions = classify_source_wall_body_junctions(transformed, drawings)
        assert _kinds(original) == _kinds(junctions)
        assert all(item.measurement_authorized is False for item in junctions)


def test_exterior_layer_name_is_not_physical_wall_authority():
    bars = (
        _strip(0, (0, 0, 20, 1)),
        _strip(1, (19, 0, 20, 20)),
        _strip(2, (0, 19, 20, 20)),
        _strip(3, (0, 0, 1, 20)),
    )
    drawings = (_drawing(), _drawing(), _drawing(), _drawing())
    cycle = audit_source_native_exterior_cycle(bars, drawings, page_index=1)
    assert cycle["layer_name_physical_promotion"] is False
    assert cycle["physical_wall_authenticated"] is False
    assert cycle["measurement_authorized"] is False
    assert cycle["snap_join_applied"] is False
    if cycle["candidate_outer_cycle_count"] == 1:
        assert cycle["reason"] != REASON_LAYER_NOT_PHYSICAL or cycle["status"] != "FIRM"


def test_window_continuity_without_unique_jambs_abstains():
    bars = (_strip(0, (0, 0, 10, 1)), _strip(1, (10.4, 0, 20, 1)))
    drawings = (_drawing(), _drawing())
    _bodies, junctions = classify_source_wall_body_junctions(bars, drawings)
    edges = classify_window_continuity_edges(junctions, drawings, page_index=2)
    assert edges
    assert all(item.junction_kind == JUNCTION_WINDOW_CONTINUITY for item in edges)
    assert all(item.status is EvidenceResolutionStatus.ABSTAINED for item in edges)
    assert all(item.reason == REASON_WINDOW_NO_UNIQUE_JAMB for item in edges)
    assert all(item.measurement_authorized is False for item in edges)
    assert all(item.provenance_geometry_kind == GEOMETRY_INFERRED for item in edges)


def test_window_continuity_unique_hosts_jambs_sill_is_topology_only():
    drawings = tuple(_drawing() for _ in range(6))
    status, reason = authenticate_window_continuity_topology(
        left_host_path_ids=(0,),
        right_host_path_ids=(1,),
        left_jamb_path_ids=(2,),
        right_jamb_path_ids=(3,),
        sill_or_floor_path_ids=(4,),
        drawings=drawings,
    )
    assert status is EvidenceResolutionStatus.CANDIDATE
    assert "topology_only" in reason
    missing, missing_reason = authenticate_window_continuity_topology(
        left_host_path_ids=(0,),
        right_host_path_ids=(1,),
        left_jamb_path_ids=(),
        right_jamb_path_ids=(3,),
        sill_or_floor_path_ids=(4,),
        drawings=drawings,
    )
    assert missing is EvidenceResolutionStatus.ABSTAINED
    assert missing_reason == REASON_WINDOW_NO_UNIQUE_JAMB
