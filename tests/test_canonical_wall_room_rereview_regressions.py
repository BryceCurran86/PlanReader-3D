"""Minimal adversarial regressions found during exact-head re-review of PR #286.

These tests intentionally exercise only the newly identified defects. They do
not rewrite the canonical wall/room architecture or publish quantities.
"""
from types import SimpleNamespace

from pb_canonical_wall_room_evidence_model import _paired_face_atom
from pb_wall_room_topology_wall_identity_v2 import canonical_wall_candidate_id_v2
from tests.test_canonical_wall_room_model import _existence_status, _run_pipeline, _loop_segs


def test_paired_face_does_not_credit_disjoint_unrelated_child_sharing_native_parent_with_geometry():
    """Disjoint descendants do not prove which descendant owns a native pair.

    A pair referring to one native parent cannot be credited to every child
    carrying that parent merely because the children are spatially disjoint.
    The pair itself must be localized to the intended descendant.
    """
    edges_by_id = {
        "left_child": {
            "id": "left_child",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 40.0,
            "y2": 0.0,
            "primitive_lineage": {"source_primitive_ids": ["native_shared"]},
        },
        "right_child": {
            "id": "right_child",
            "x1": 60.0,
            "y1": 0.0,
            "x2": 100.0,
            "y2": 0.0,
            "primitive_lineage": {"source_primitive_ids": ["native_shared"]},
        },
    }
    right_wall = SimpleNamespace(
        candidate_id="right_wall",
        viewport_id="v1",
        face_a_segment_ids=("right_child",),
        face_b_segment_ids=(),
    )
    pair_for_left_subspan = {
        "face_a": "native_shared",
        "face_b": "native_parallel_partner",
        "gap_pt": 10.0,
        "overlap_pt": 40.0,
    }
    atom = _paired_face_atom(
        right_wall,
        [pair_for_left_subspan],
        edges_by_id,
        document_id="doc",
        page_id="page",
    )
    assert atom is None


def test_hybrid_identity_distinguishes_same_provenance_same_endpoints_different_paths():
    """The required path distinction must not rely on different provenance.

    Both hypotheses intentionally have the same viewport, endpoints, and
    native provenance. Their contributing edge geometry describes different
    interior paths. If the identity API only hashes p1/p2 plus provenance,
    they collide even though the physical paths differ.
    """
    straight_edges = {
        "s": {
            "id": "s",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 100.0,
            "y2": 0.0,
            "primitive_lineage": {"source_primitive_ids": ["native_same"]},
        }
    }
    detour_edges = {
        "d1": {
            "id": "d1",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 50.0,
            "y2": 20.0,
            "primitive_lineage": {"source_primitive_ids": ["native_same"]},
        },
        "d2": {
            "id": "d2",
            "x1": 50.0,
            "y1": 20.0,
            "x2": 100.0,
            "y2": 0.0,
            "primitive_lineage": {"source_primitive_ids": ["native_same"]},
        },
    }
    straight_id = canonical_wall_candidate_id_v2(
        "v1", ["s"], straight_edges, (0.0, 0.0), (100.0, 0.0)
    )
    detour_id = canonical_wall_candidate_id_v2(
        "v1", ["d1", "d2"], detour_edges, (0.0, 0.0), (100.0, 0.0)
    )
    assert straight_id != detour_id


def test_firm_room_cannot_be_built_only_from_single_domain_positive_wall_support():
    """Room confidence must not bootstrap weak wall confidence.

    This single-line L-shaped loop has positive uncontested native-metadata
    support but no two-domain physical-existence corroboration. It therefore
    must not be reported through the conservative/firm room path.
    """
    points = [(0, 0), (200, 0), (200, 60), (100, 60), (100, 100), (0, 100)]
    out = _run_pipeline(_loop_segs(points, "weak"))
    assert out["resolved"]
    assert all(_existence_status(w) != "corroborated" for w in out["resolved"])
    assert len(out["rooms"]) == 0
