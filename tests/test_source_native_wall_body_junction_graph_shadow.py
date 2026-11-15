"""Physical source path/junction graph: L/T/cross, no collinear snap, no FIRM."""
from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_wall_body_junction_graph_shadow import (
    GEOMETRY_INFERRED,
    GEOMETRY_OBSERVED,
    JUNCTION_COLLINEAR_GAP,
    JUNCTION_CORNER_RETURN,
    JUNCTION_CROSS,
    JUNCTION_L,
    JUNCTION_MULTI,
    JUNCTION_T,
    REASON_INFERRED_JOIN_FORBIDDEN,
    REASON_MISSING_PROVENANCE,
    classify_source_wall_body_junctions,
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
