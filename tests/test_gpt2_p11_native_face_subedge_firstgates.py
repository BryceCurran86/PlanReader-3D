"""Shadow native subedge first gates: positive and adversarial PDF drawings."""
from copy import deepcopy
from types import SimpleNamespace

import fitz
import pytest

from tools.diag_gpt2_p11_native_face_subedge_firstgates import (
    inspect_local_edges, _first_w2_w4_face_geometry_gate,
)
from pb_migration_contracts import EvidenceResolutionStatus


def _source(lines):
    doc = fitz.open()
    page = doc.new_page(width=500, height=500)
    for a, b in lines:
        page.draw_line(fitz.Point(*a), fitz.Point(*b), width=0.3)
    drawings = page.get_drawings()
    doc.close()
    return drawings


def _scope(*, fragments, excludes=(), viewport=(0, 0, 500, 500),
           tainted=True, grid=False, w4_path=None):
    rec = SimpleNamespace(
        wall_candidate_id="wall-a",
        wall_candidate=SimpleNamespace(
            face_a_segment_ids=("e0",), face_b_segment_ids=(),
            centerline_pts=(tuple(fragments[0][0][:2]), tuple(fragments[0][0][2:]))
            if w4_path is None else w4_path,
        ),
        source_edge_fragments=tuple(
            SimpleNamespace(
                geometry=flat, source_primitive_ids=primitive_ids
            ) for flat, primitive_ids in fragments
        ),
    )
    boundary = SimpleNamespace(
        status="evaluated",
        excluded_boundary_primitives=tuple(excludes),
        contact_tolerance_pt=2.5,
        boundary_taint_reason_codes=(
            (("wall-a", ("viewport_crop", "excluded_source_contact")),)
            if tainted else ()
        ),
    )
    return SimpleNamespace(
        records=(rec,), boundary_evaluation=boundary,
        typed_semantic_evidence_atoms=(
            SimpleNamespace(
                kind='grid', status=EvidenceResolutionStatus.CANDIDATE,
                metadata={'polarity':'opposing','target_edge_id':'e0'},
                evidence_id='source-original-grid-atom',
                reason_codes=('source_lineage_dense_orthogonal_lattice',),
            ),
        ) if grid else (),
        viewport_bbox=viewport,
    )


def _witnesses(edge=((10, 10), (60, 10)), extra=False):
    records = [{
        "face_id": "face-1", "bounding_wall_ids": ("wall-a",),
        "boundary_wall_edges": (("wall-a", edge),),
    }]
    if extra:
        records.append({
            "face_id": "face-2", "bounding_wall_ids": ("wall-a",),
            "boundary_wall_edges": (("wall-a", edge),),
        })
    return tuple(records)


def _marks(verified=True, *, extra=False):
    faces = [{
        "shadow_face_id": "face-1",
        "source_w4_candidate_wall_ids": ["wall-a"],
    }]
    if extra:
        faces.append({
            "shadow_face_id": "face-2",
            "source_w4_candidate_wall_ids": ["wall-a"],
        })
    return [{
        "native_source_observation_id": "source-observation-A",
        "native_text_or_raster_source_verified": verified,
        "all_containing_shadow_faces": faces,
    }]


def _edges(out):
    return out["mark_local_subedges"][0]["original_owned_face_subedges"]


@pytest.mark.parametrize("original,w2,w4,expected", [
    (True, ((10,10),(60,10)), ((10,10),(60,10)),
     "original_native_w2_w4_geometry_consistent_candidate_only"),
    (True, ((10,10),(30,10)), ((10,10),(60,10)),
     "surviving_w2_fragment_missing_native_span"),
    (False, ((10,10),(60,10)), ((10,10),(60,10)),
     "surviving_w2_span_has_no_indexed_original_native_support"),
    (True, ((10,10),(60,10)), ((10,10),(20,20)),
     "w4_candidate_path_not_covering_surviving_w2_span"),
    (False, ((10,10),(30,10)), ((10,10),(60,10)),
     "w4_candidate_path_has_no_surviving_w2_or_indexed_native_span"),
    (False, ((10,10),(30,10)), ((10,10),(20,20)),
     "planar_face_subedge_not_in_w4_w2_native_path"),
])
def test_source_w2_w4_boundary_first_stage_classification(original,w2,w4,expected):
    fragment = SimpleNamespace(geometry=(*w2[0],*w2[1]))
    report = _first_w2_w4_face_geometry_gate(
        atom=((35,10),(40,10)), w4_centerline=w4,
        w2_fragments=(fragment,),
        native_covering_ids=("d0i0",) if original else (),
        native_unavailable=False,
    )
    assert report["first_geometry_path_disagreement"] == expected
    assert not report["room_authority_granted"]


def test_original_source_unavailable_never_falls_back_to_w2_or_w4_paint():
    segment = SimpleNamespace(geometry=(10,10,60,10))
    result = _first_w2_w4_face_geometry_gate(
        atom=((35,10),(40,10)), w4_centerline=((10,10),(60,10)),
        w2_fragments=(segment,), native_covering_ids=(),
        native_unavailable=True,
    )
    assert result["source_indexed_native_ink_spans_face_subedge"] is None
    assert result["first_geometry_path_disagreement"] == "original_indexed_source_unavailable"


def test_w4_exact_diagonal_deviation_from_original_native_grid_stays_negative():
    # A skewed W4 centerline may enclose a W5 face; neither the surviving
    # original W2 axis line nor original ink proves that diagonal.
    source = _source([((10, 10), (10, 60))])
    wall = _scope(
        fragments=(((10,10,10,60),("d0i0",)),),
        w4_path=((10,10),(10.25,59.8)),
    )
    result = inspect_local_edges(
        wall=wall, witnesses=_witnesses(edge=((10,10),(10.25,59.8))),
        marks=_marks(), drawings=source,
    )
    edge, = _edges(result)
    gate=edge["first_original_w2_w4_planar_geometry_gate"]
    assert gate["producer_w4_centerline_spans_face_subedge"] is True
    assert gate["surviving_w2_geometry_spans_face_subedge"] is False
    assert gate["source_indexed_native_ink_spans_face_subedge"] is False
    assert gate["first_geometry_path_disagreement"] == (
        "w4_candidate_path_has_no_surviving_w2_or_indexed_native_span"
    )
    assert not result["physical_room_published"]


def test_direct_native_ink_and_existing_w2_full_span_preserved_without_room_grant():
    drawings = _source([((10, 10), (60, 10))])
    wall = _scope(fragments=(((10, 10, 60, 10), ("d0i0",)),))
    original_wall = deepcopy(wall)
    original_marks = _marks()
    report = inspect_local_edges(
        wall=wall, witnesses=_witnesses(), marks=original_marks,
        drawings=drawings,
    )
    edge, = _edges(report)
    assert edge["indexed_native_ink_status"] == "one_or_more_original_native_items_span"
    assert edge["surviving_w2_full_edge_source_primitive_ids"] == ["d0i0"]
    assert edge["original_native_source_ids_covering_subedge"] == ["d0i0"]
    assert edge["whole_w4_candidate_taint_reasons_retained"] == [
        "viewport_crop", "excluded_source_contact"
    ]
    assert edge["subedge_inside_original_owned_viewport"] is True
    assert not edge["structural_wall_role_granted"]
    assert not report["physical_room_published"] and not report["metric_quantity_published"]
    assert wall == original_wall and original_marks == _marks()


def test_producer_source_lineage_grid_opposition_is_carried_without_room_promotion():
    drawings = _source([((10, 10), (60, 10))])
    wall = _scope(fragments=(((10, 10, 60, 10), ("d0i0",)),), grid=True)
    result = inspect_local_edges(
        wall=wall, witnesses=_witnesses(), marks=_marks(),
        drawings=drawings,
    )
    subedge, = _edges(result)
    assert subedge["indexed_native_ink_status"] == "one_or_more_original_native_items_span"
    assert subedge["producer_full_wall_grid_opposition"] is True
    assert subedge["producer_grid_opposition_evidence_ids"] == ["source-original-grid-atom"]
    assert result["mark_local_subedges"][0]["all_enclosing_w4_walls_typed_grid_opposed"]
    assert not result["physical_room_published"]


def test_source_ink_crosses_true_w2_gap_but_not_published():
    drawings = _source([((10, 10), (60, 10))])
    wall = _scope(fragments=(((10, 10, 29, 10), ("d0i0",)),))
    report = inspect_local_edges(
        wall=wall, witnesses=_witnesses(edge=((25, 10), (40, 10))),
        marks=_marks(), drawings=drawings,
    )
    edge, = _edges(report)
    assert edge["indexed_native_ink_status"] == "one_or_more_original_native_items_span"
    assert edge["surviving_w2_full_edge_source_primitive_ids"] == []
    assert not report["original_source_scope_complete_promoted"]


def test_orthogonal_native_crossing_does_not_cover_face_subedge():
    drawings = _source([((10, 0), (10, 80))])
    wall = _scope(fragments=(((10, 0, 10, 80), ("d0i0",)),))
    edge, = _edges(inspect_local_edges(
        wall=wall, witnesses=_witnesses(), marks=_marks(),
        drawings=drawings,
    ))
    assert edge["indexed_native_ink_status"] == "no_indexed_native_item_spans_w4_face_subedge"
    assert edge["original_native_source_ids_covering_subedge"] == []


def test_absent_native_item_remains_unavailable_and_cannot_imply_ink_absence():
    wall = _scope(fragments=(((10, 10, 60, 10), ("d99999i0",)),))
    edge, = _edges(inspect_local_edges(
        wall=wall, witnesses=_witnesses(), marks=_marks(),
        drawings=_source([((10, 10), (60, 10))]),
    ))
    assert edge["indexed_native_ink_status"] == "indexed_original_pdf_source_unavailable"
    assert edge["indexed_original_ink_receipts"][0]["original_indexed_ink_spans_subedge"] is None


def test_excluded_source_touch_and_viewport_crop_stay_as_typed_negatives():
    from pb_physical_wall_candidate_authority import ExcludedBoundaryPrimitive
    drawings = _source([((10, 10), (60, 10))])
    excluded = ExcludedBoundaryPrimitive(
        category="crosses_scope_boundary",
        source_observation_id="excluded-original",
        x1=35, y1=10, x2=35, y2=80,
    )
    wall = _scope(
        fragments=(((10, 10, 60, 10), ("d0i0",)),),
        excludes=(excluded,), viewport=(20, 0, 500, 500),
    )
    edge, = _edges(inspect_local_edges(
        wall=wall, witnesses=_witnesses(), marks=_marks(),
        drawings=drawings,
    ))
    assert edge["original_excluded_primitive_subedge_contact_ids"] == ["excluded-original"]
    assert edge["subedge_inside_original_owned_viewport"] is False
    assert edge["whole_w4_candidate_taint_reasons_retained"]
    assert not edge["source_local_room_authority_granted"]


def test_two_shadow_face_adjacencies_retained_not_structural_two_sided_proof():
    drawings = _source([((10, 10), (60, 10))])
    wall = _scope(fragments=(((10, 10, 60, 10), ("d0i0",)),))
    report = inspect_local_edges(
        wall=wall, witnesses=_witnesses(extra=True),
        marks=_marks(extra=True), drawings=drawings,
    )
    assert len(report["mark_local_subedges"]) == 2
    for row in report["mark_local_subedges"]:
        assert len(row["original_owned_face_subedges"][0][
            "other_shadow_face_ids_sharing_same_w4_subedge"
        ]) == 1
        assert not row["original_room_ring_authentication"]


def test_face_wall_inventory_and_replayed_w4_ids_fail_closed():
    drawings = _source([((10, 10), (60, 10))])
    wall = _scope(fragments=(((10, 10, 60, 10), ("d0i0",)),))
    with pytest.raises(ValueError, match="mark_to_w4_wall_inventory_drift"):
        inspect_local_edges(
            wall=wall, witnesses=_witnesses(),
            marks=[dict(_marks()[0], all_containing_shadow_faces=[
                dict(_marks()[0]["all_containing_shadow_faces"][0],
                     source_w4_candidate_wall_ids=["foreign-wall"])
            ])], drawings=drawings,
        )
    with pytest.raises(ValueError, match="replayed_w4_shadow_face_id"):
        inspect_local_edges(
            wall=wall, witnesses=_witnesses() * 2, marks=_marks(),
            drawings=drawings,
        )


@pytest.mark.parametrize("transform", [
    lambda x, y: (x + 80, y + 70),
    lambda x, y: (200 - y, x + 110),
    lambda x, y: (2 * x, 2 * y),
])
def test_translation_rotation_scale_and_original_source_order(transform):
    a, b = transform(10, 10), transform(60, 10)
    drawings = _source([(a, b), (transform(15, 30), transform(65, 30))])
    frag = (*a, *b)
    wall = _scope(fragments=((frag, ("d0i0",)),))
    witness = _witnesses(edge=(b, a))
    out1 = inspect_local_edges(
        wall=wall, witnesses=witness, marks=_marks(),
        drawings=drawings,
    )
    out2 = inspect_local_edges(
        wall=wall, witnesses=witness, marks=deepcopy(_marks()),
        drawings=deepcopy(drawings),
    )
    assert out1 == out2
    assert _edges(out1)[0]["indexed_native_ink_status"] == "one_or_more_original_native_items_span"
