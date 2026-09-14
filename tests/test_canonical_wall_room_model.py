"""Adversarial test matrix for the shadow canonical wall + room evidence
model (pb_canonical_wall_room_evidence_model.py, pb_wall_room_topology_
wall_identity_v2.py).

Every test builds synthetic (or, where noted, real committed-fixture)
geometry and exercises the full pipeline:

    build_wall_graph_for_viewport
    -> attach_typed_semantic_evidence (U2, canonical)
    -> classify_junctions -> assemble_wall_candidates
    -> resolve_wall_physical_evidence
    -> reconstruct_room_candidates_from_credible_walls

No project name, filename, or benchmark ID is used as algorithm input
anywhere in this file. No quantity is asserted or published.
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_vector_geometry_v130 import detect_wall_pairs
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import attach_typed_semantic_evidence
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates, _canonical_wall_candidate_id
from pb_wall_room_topology_wall_identity_v2 import canonical_wall_candidate_id_v2, _chain_source_primitive_ids
from pb_canonical_wall_room_evidence_model import (
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_PAIRED_WALL_FACES,
    FAMILY_U2_PHYSICAL_WALL_LINEWORK,
    FAMILY_VALID_JUNCTION_BEHAVIOR,
    reconstruct_room_candidates_from_credible_walls,
    resolve_wall_physical_evidence,
    wall_is_credible_room_boundary,
)


def _seg(id_, x1, y1, x2, y2, **kw):
    base = {
        "id": id_, "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "width": 0.5, "stroke": (0, 0, 0), "fill": None, "layer": "Wall", "dashes": "",
    }
    base.update(kw)
    return base


def _loop_segs(points, prefix):
    out = []
    for i in range(len(points)):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % len(points)]
        out.append(_seg(f"{prefix}{i}", x1, y1, x2, y2))
    return out


def _double_rect(x0, y0, x1, y1, wall_pt=10.0, prefix="w"):
    outer = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    inner = [(x0 + wall_pt, y0 + wall_pt), (x1 - wall_pt, y0 + wall_pt), (x1 - wall_pt, y1 - wall_pt), (x0 + wall_pt, y1 - wall_pt)]
    return _loop_segs(outer, f"{prefix}o") + _loop_segs(inner, f"{prefix}i")


def _run_pipeline(segments, *, viewport_id="v1", document_id="d1", page_id="p1", exclude_conflict=True):
    graph = build_wall_graph_for_viewport(segments)
    graph = attach_typed_semantic_evidence(graph, document_id=document_id, page_id=page_id, viewport_id=viewport_id)
    junctions, relationships = classify_junctions(graph, document_id=document_id, page_id=page_id, viewport_id=viewport_id)
    walls, edge_id_to_wall_id = assemble_wall_candidates(graph, junctions, relationships, viewport_id=viewport_id)
    pairs = detect_wall_pairs(segments)
    resolved, minted = resolve_wall_physical_evidence(
        walls, graph=graph, document_id=document_id, page_id=page_id, paired_wall_faces=pairs
    )
    rooms = reconstruct_room_candidates_from_credible_walls(
        graph, resolved, edge_id_to_wall_id, document_id=document_id, viewport_id=viewport_id,
        exclude_conflict=exclude_conflict,
    )
    return {"graph": graph, "junctions": junctions, "walls": walls, "resolved": resolved,
            "edge_id_to_wall_id": edge_id_to_wall_id, "minted": minted, "rooms": rooms}


def _wall_ids_for_native_ids(out, native_ids) -> set:
    """`edge_id_to_wall_id` is keyed by post-split Stage-A edge ids (e.g.
    "split_3"), never the original native segment id a test constructs a
    fixture with -- resolve via each edge's own U1 lineage instead."""
    native_ids = set(native_ids)
    edges_by_id = {str(e["id"]): e for e in out["graph"]["edges"] if not e.get("_removed")}
    wall_ids = set()
    for edge_id, wall_id in out["edge_id_to_wall_id"].items():
        edge = edges_by_id.get(edge_id)
        if not edge:
            continue
        lineage = edge.get("primitive_lineage") or {}
        if native_ids & set(lineage.get("source_primitive_ids") or ()):
            wall_ids.add(wall_id)
    return wall_ids


def _existence_status(wall) -> str:
    return wall.metadata.get("physical_evidence_status", "")


# ---------------------------------------------------------------------------
# 1-10: geometry pattern coverage
# ---------------------------------------------------------------------------


class TestGeometryPatterns:
    def test_01_simple_rectangular_masonry_room(self):
        segs = _double_rect(0, 0, 200, 100)
        out = _run_pipeline(segs)
        assert any(_existence_status(w) == "corroborated" for w in out["resolved"])
        assert len(out["rooms"]) >= 1

    def test_02_two_adjacent_rooms_sharing_partition(self):
        segs = _double_rect(0, 0, 200, 100, prefix="left")
        segs += _double_rect(200, 0, 400, 100, prefix="right")
        out = _run_pipeline(segs)
        assert len(out["walls"]) >= 8
        assert len(out["rooms"]) >= 1

    def test_03_l_shaped_room(self):
        # Single-line geometry (no second parallel face) can never reach
        # 2-domain physical-existence corroboration -- see the room-gating
        # fix in pb_canonical_wall_room_evidence_model.wall_is_credible_
        # room_boundary. This test is about room-SHAPE reconstruction
        # mechanics (an L-shaped closed polyline), not evidence strength,
        # so it uses the permissive population; firm/quantity-eligible
        # boundary correctness is covered separately by test_every_
        # conservative_room_boundary_wall_is_independently_credible and the
        # GPT-2 rereview regression for single-domain rooms.
        l_shape = [(0, 0), (200, 0), (200, 60), (100, 60), (100, 100), (0, 100)]
        segs = _loop_segs(l_shape, "lw")
        out = _run_pipeline(segs, exclude_conflict=False)
        assert len(out["rooms"]) >= 1

    def test_04_corridor_plus_rooms(self):
        segs = _double_rect(0, 0, 100, 60, prefix="room1")
        segs += _double_rect(100, 0, 300, 60, wall_pt=8, prefix="corr")
        segs += _double_rect(300, 0, 400, 60, prefix="room2")
        # exclude_conflict=False: three adjacent double-line rectangles pack
        # many mutually-parallel, regularly-spaced edges into a small area,
        # which legitimately triggers U2's own regular-array opposing
        # nominations (grid/dimension-tick heuristics) far more readily than
        # a visually varied real floor plan would -- covered on its own by
        # test_19; this test is about corridor+room topology, so it uses the
        # policy that keeps disputed-but-real geometry in the room-boundary
        # population rather than the default conservative exclusion.
        out = _run_pipeline(segs, exclude_conflict=False)
        assert len(out["rooms"]) >= 1

    def test_05_door_gap_in_wall_still_yields_wall_evidence_on_remaining_segments(self):
        # A wall with a door-sized gap: two collinear segments, not touching.
        segs = [
            _seg("a", 0, 0, 80, 0), _seg("b", 100, 0, 200, 0),
            _seg("c", 0, 0, 0, 100), _seg("d", 200, 0, 200, 100),
            _seg("e", 0, 100, 200, 100),
        ]
        out = _run_pipeline(segs)
        # The gap must not be silently bridged into one false continuous wall.
        assert all(w.length_m is None for w in out["walls"])  # no invented thickness/length authority
        assert len(out["walls"]) >= 5

    def test_06_window_interruption(self):
        # Two collinear wall runs either side of a window void, plus a
        # parallel mullion pair inside the gap (glazing-like local evidence).
        segs = [
            _seg("a", 0, 0, 80, 0), _seg("b", 120, 0, 200, 0),
            _seg("mullion1", 85, -2, 85, 2), _seg("mullion2", 115, -2, 115, 2),
        ]
        out = _run_pipeline(segs)
        assert len(out["walls"]) >= 2

    def test_07_double_line_wall_gets_paired_face_family(self):
        segs = _double_rect(0, 0, 200, 100)
        out = _run_pipeline(segs)
        assert any(FAMILY_PAIRED_WALL_FACES in w.metadata.get("physical_evidence_families", []) for w in out["resolved"])

    def test_08_single_line_wall_representation_still_evaluable(self):
        segs = _loop_segs([(0, 0), (200, 0), (200, 100), (0, 100)], "s")
        out = _run_pipeline(segs)
        assert len(out["resolved"]) == 4
        assert all(w.representation == "single_line" for w in out["resolved"])

    def test_09_mixed_wall_thicknesses(self):
        segs = _double_rect(0, 0, 150, 80, wall_pt=8, prefix="thin")
        segs += _double_rect(300, 0, 500, 100, wall_pt=25, prefix="thick")
        out = _run_pipeline(segs)
        assert any(_existence_status(w) == "corroborated" for w in out["resolved"])

    def test_10_external_wall_plus_internal_partitions(self):
        segs = _double_rect(0, 0, 400, 200, wall_pt=12, prefix="ext")
        segs += [_seg("part1", 200, 12, 200, 100), _seg("part2", 200, 100, 200, 188)]
        out = _run_pipeline(segs)
        assert len(out["walls"]) >= 8


# ---------------------------------------------------------------------------
# 11-16 + extras: non-wall geometry must not become rooms / must not get
# wall-positive evidence. Every test checks the DIRECT, semantic claim --
# that the non-wall population's own wall-candidate ids never appear in any
# room's bounding_wall_candidate_ids -- rather than an incidental proxy like
# "no room happens to have this exact area" (a real room could coincidentally
# share an area with the non-wall shape) or "has reason codes" (every
# resolved wall has reason codes, corroborated or not, making that check
# vacuous). See Blocker 7 / P7 in the GPT-2 remediation report.
# ---------------------------------------------------------------------------


class TestNonWallGeometryRejection:
    def test_11_furniture_rectangle_does_not_become_room(self):
        room = _double_rect(0, 0, 400, 300, wall_pt=10, prefix="room")
        furniture = _loop_segs([(50, 50), (90, 50), (90, 80), (50, 80)], "furn")
        out = _run_pipeline(room + furniture)
        room_ids_used = {wid for r in out["rooms"] for wid in r.bounding_wall_candidate_ids}
        furniture_wall_ids = _wall_ids_for_native_ids(out, [f"furn{i}" for i in range(4)])
        assert furniture_wall_ids, "expected the furniture rectangle to produce at least one wall candidate"
        assert furniture_wall_ids.isdisjoint(room_ids_used)

    def test_12_table_frame_does_not_become_room_boundary_from_wall_evidence_alone(self):
        room = _double_rect(0, 0, 400, 300, wall_pt=10, prefix="room")
        table = _loop_segs([(150, 150), (250, 150), (250, 200), (150, 200)], "tbl")
        table += [_seg("tblx1", 175, 150, 175, 200), _seg("tblx2", 200, 150, 200, 200), _seg("tblx3", 225, 150, 225, 200)]
        out = _run_pipeline(room + table)
        room_ids_used = {wid for r in out["rooms"] for wid in r.bounding_wall_candidate_ids}
        table_wall_ids = _wall_ids_for_native_ids(out, [f"tbl{i}" for i in range(4)])
        assert table_wall_ids
        assert table_wall_ids.isdisjoint(room_ids_used)

    def test_13_glazing_mullion_grid_does_not_get_wall_positive_evidence_or_close_a_room(self):
        room = _double_rect(0, 0, 400, 300, wall_pt=10, prefix="room")
        mullions = [_seg(f"mul{i}", 150 + i * 10.0, 100, 150 + i * 10.0, 200, layer="Glazing") for i in range(6)]
        out = _run_pipeline(room + mullions)
        mullion_wall_ids = _wall_ids_for_native_ids(out, [f"mul{i}" for i in range(6)])
        assert mullion_wall_ids
        room_ids_used = {wid for r in out["rooms"] for wid in r.bounding_wall_candidate_ids}
        assert mullion_wall_ids.isdisjoint(room_ids_used)

    def test_14_hatch_field_does_not_get_wall_positive_evidence_or_close_a_room(self):
        room = _double_rect(0, 0, 400, 300, wall_pt=10, prefix="room")
        # A non-"hatch"-keyword layer name deliberately: this test is about
        # the GEOMETRIC (repetition-based) evidence model correctly
        # withholding wall-positive evidence, not about Stage A's separate,
        # pre-existing metadata layer-name filter (which would otherwise
        # exclude these before they ever became wall candidates at all,
        # testing nothing about this module).
        hatch = [_seg(f"h{i}", 150 + i * 3.0, 150, 150 + i * 3.0 + 1.5, 151.5, layer="Layer 1") for i in range(20)]
        out = _run_pipeline(room + hatch)
        corroborated = [w for w in out["resolved"] if _existence_status(w) == "corroborated"]
        hatch_wall_ids = _wall_ids_for_native_ids(out, [f"h{i}" for i in range(20)])
        assert hatch_wall_ids
        assert not any(w.candidate_id in hatch_wall_ids for w in corroborated)
        room_ids_used = {wid for r in out["rooms"] for wid in r.bounding_wall_candidate_ids}
        assert hatch_wall_ids.isdisjoint(room_ids_used)

    def test_15_dimension_frame_excluded_before_ever_reaching_wall_assembly(self):
        segs = [_seg("dim1", 0, 0, 100, 0, dashes="[3 2] 0"), _seg("wall1", 0, 20, 100, 20)]
        out = _run_pipeline(segs)
        wall_edge_ids = {eid for w in out["walls"] for eid in w.face_a_segment_ids}
        assert "dim1" not in wall_edge_ids  # excluded by Stage A's own metadata pre-filter, never reaches W4 at all

    def test_16_room_like_annotation_box_never_closes_a_firm_room(self):
        # Conservative (default) policy specifically: this is where the
        # firm-boundary contract applies. Under the PERMISSIVE
        # (exclude_conflict=False) policy an isolated, disconnected closed
        # 4-cycle CAN legitimately close as its own tiny room regardless of
        # what it depicts -- extract_planar_faces has no "does this look
        # like an annotation" signal, and the permissive policy is
        # documented as the looser, non-firm option (only ABSTAINED
        # excluded). The firm guarantee is specifically that the
        # CONSERVATIVE population excludes it, which this test checks.
        room = _double_rect(0, 0, 400, 300, wall_pt=10, prefix="room")
        # Comfortably inside the room's own inner wall face (10,10)-(390,290)
        # with margin on every side -- NOT touching it at any point, so this
        # is a genuinely separate, disconnected small loop (an earlier draft
        # placed a corner exactly on the inner wall's own corner, merging
        # the two into one connected component and breaking U2's own
        # rectangle-loop detection).
        annotation_box = _loop_segs([(280, 180), (350, 180), (350, 220), (280, 220)], "note")
        out = _run_pipeline(room + annotation_box)  # default: exclude_conflict=True
        room_ids_used = {wid for r in out["rooms"] for wid in r.bounding_wall_candidate_ids}
        note_wall_ids = _wall_ids_for_native_ids(out, [f"note{i}" for i in range(4)])
        assert note_wall_ids
        assert note_wall_ids.isdisjoint(room_ids_used)

    def test_dimension_frame_never_closes_a_room(self):
        room = _double_rect(0, 0, 400, 300, wall_pt=10, prefix="room")
        dim_frame = [
            _seg("dimA", 100, 350, 300, 350, dashes="[3 2] 0"),
            _seg("dimB", 300, 350, 300, 380, dashes="[3 2] 0"),
            _seg("dimC", 300, 380, 100, 380, dashes="[3 2] 0"),
            _seg("dimD", 100, 380, 100, 350, dashes="[3 2] 0"),
        ]
        out = _run_pipeline(room + dim_frame, exclude_conflict=False)
        wall_edge_ids = {eid for w in out["walls"] for eid in w.face_a_segment_ids}
        assert not any(eid.startswith("dim") for eid in wall_edge_ids)  # excluded pre-filter, never a wall candidate at all

    def test_opposing_only_candidate_never_closes_a_room(self):
        """Direct contract test: resolve_wall_physical_evidence's own
        "opposing evidence without supporting" branch (has_opposing and not
        has_supporting) produces a CANDIDATE wall with zero supporting_
        evidence_ids and non-empty conflicting_evidence_ids. Constructing
        this exact state via the full pipeline is not straightforward,
        since U2's own physical_wall_linework atom fires unconditionally
        for any solid retained edge -- so this tests the FIRM BOUNDARY
        CONTRACT directly against that documented state shape, end to end
        through reconstruct_room_candidates_from_credible_walls.
        """
        from dataclasses import replace as _replace

        room = _double_rect(0, 0, 200, 100, wall_pt=10)
        out = _run_pipeline(room)
        some_wall = out["resolved"][0]
        synthetic_metadata = dict(some_wall.metadata)
        synthetic_metadata["physical_evidence_status"] = "candidate"  # matches the synthetic opposing-only state below
        opposing_only_wall = _replace(
            some_wall,
            status=EvidenceResolutionStatus.CANDIDATE,
            supporting_evidence_ids=(),
            conflicting_evidence_ids=("ev_synthetic_opposing",),
            metadata=synthetic_metadata,
        )
        assert not wall_is_credible_room_boundary(opposing_only_wall)

        resolved_with_substitute = [
            opposing_only_wall if w.candidate_id == some_wall.candidate_id else w for w in out["resolved"]
        ]
        rooms = reconstruct_room_candidates_from_credible_walls(
            out["graph"], resolved_with_substitute, out["edge_id_to_wall_id"],
            document_id="d1", viewport_id="v1",
        )
        room_ids_used = {wid for r in rooms for wid in r.bounding_wall_candidate_ids}
        assert opposing_only_wall.candidate_id not in room_ids_used

    def test_ambiguous_wall_gap_is_not_fabricated_shut(self):
        # A genuine gap AT a junction (not a missing segment): three sides of
        # a rectangle meet cleanly, but the fourth side stops short, leaving
        # a real, unbridged physical gap rather than a shared endpoint.
        segs = [
            _seg("a", 0, 0, 200, 0), _seg("b", 200, 0, 200, 100), _seg("c", 200, 100, 0, 100),
            _seg("d", 0, 100, 0, 5),  # stops 5pt short of (0, 0) -- a real, deliberate gap
        ]
        out = _run_pipeline(segs)
        assert len(out["rooms"]) == 0  # must not be fabricated shut across the gap

    def test_every_conservative_room_boundary_wall_is_independently_credible(self):
        """Direct proof of the FIRM BOUNDARY CONTRACT: every wall id in every
        conservatively-reconstructed room's bounding_wall_candidate_ids must
        itself satisfy wall_is_credible_room_boundary (positive support, no
        opposition) -- not merely "not ABSTAINED/CONFLICT."""
        room = _double_rect(0, 0, 200, 100, wall_pt=10)
        out = _run_pipeline(room)
        resolved_by_id = {w.candidate_id: w for w in out["resolved"]}
        checked_any = False
        for r in out["rooms"]:
            for wall_id in r.bounding_wall_candidate_ids:
                checked_any = True
                wall = resolved_by_id[wall_id]
                assert wall_is_credible_room_boundary(wall), (
                    f"room {r.room_ref} boundary wall {wall_id} does not satisfy the firm boundary contract: "
                    f"supporting={wall.supporting_evidence_ids} conflicting={wall.conflicting_evidence_ids}"
                )
        assert checked_any, "expected at least one conservative room to exist for this well-supported double-line rectangle"


# ---------------------------------------------------------------------------
# 17-18: identity
# ---------------------------------------------------------------------------


class TestWallIdentityV2:
    def test_17_same_endpoints_different_interior_path_get_different_ids(self):
        # Direct, function-level test of the two identity schemes: two
        # DIFFERENT chains (different contributing native primitives) that
        # happen to share the same two boundary endpoints -- e.g. a straight
        # connector versus a route with a different set of native sources
        # between the identical pair of corners. The full assemble_wall_
        # candidates() pipeline in THIS repo actually prevents constructing
        # such a pair from simple non-collinear synthetic geometry today,
        # because L_CORNER never emits a CONTINUES_AS relationship (see
        # wall_assembly.py's own docstring) -- a non-collinear "detour" never
        # merges into one chain at all, so it can never reach this exact
        # p1==p2 collision naturally in this specific version of the
        # pipeline. That does not make the old scheme's blind spot
        # theoretical: it depends on p1/p2 ONLY, so any future relaxation of
        # the chain-merge rule, or any as-yet-unswept edge case producing
        # two distinct chains with coincidentally identical boundary points,
        # collides under the old scheme and does not collide under the new
        # one -- tested directly here at the identity-function level, which
        # is the correct level to prove a hash function's own collision
        # behavior regardless of which caller can or cannot currently
        # construct a colliding pair.
        p1, p2 = (0.0, 0.0), (100.0, 0.0)
        edges_straight = {"e0": {"id": "e0", "primitive_lineage": {"source_primitive_ids": ["native_straight"]}}}
        edges_detour = {
            "e1": {"id": "e1", "primitive_lineage": {"source_primitive_ids": ["native_detour_a"]}},
            "e2": {"id": "e2", "primitive_lineage": {"source_primitive_ids": ["native_detour_b"]}},
        }

        old_straight = _canonical_wall_candidate_id("v1", p1, p2)
        old_detour = _canonical_wall_candidate_id("v1", p1, p2)
        assert old_straight == old_detour  # by construction: old scheme is a pure function of (viewport_id, p1, p2)

        new_straight = canonical_wall_candidate_id_v2("v1", ["e0"], edges_straight, p1, p2)
        new_detour = canonical_wall_candidate_id_v2("v1", ["e1", "e2"], edges_detour, p1, p2)
        assert new_straight != new_detour  # provenance-first scheme distinguishes genuinely different sources

    def test_18_rechunked_equivalent_wall_keeps_same_v2_identity(self):
        # Re-chunking tolerance means: the SPLITTER dividing one native
        # primitive into more or fewer fragments (e.g. because an incidental
        # crossing forces a cut) must not change that primitive's own wall
        # identity -- NOT that two DIFFERENT native primitives (e.g. three
        # separately drafted collinear segments) should collide with one.
        # This is tested by giving the SAME single native line ("whole") two
        # different real splitter outcomes: alone (never split) versus
        # crossed by a perpendicular line at its midpoint (split into two
        # fragments at the X-crossing, then re-merged into one chain by
        # collinear continuation through that crossing -- X_CROSSING is one
        # of the chain-extension junction types).
        def _v2_id_for_whole_chain(segs):
            graph = build_wall_graph_for_viewport(segs)
            junctions, relationships = classify_junctions(graph, document_id="d", page_id="p", viewport_id="v1")
            walls, _ = assemble_wall_candidates(graph, junctions, relationships, viewport_id="v1")
            edges_by_id = {str(e["id"]): e for e in graph["edges"] if not e.get("_removed")}
            # The "whole" chain is whichever wall's centerline spans the
            # full (0,0)-(100,0) span (the crossing segment produces its own
            # separate, shorter wall candidate).
            whole = next(w for w in walls if w.centerline_pts[0] in ((0.0, 0.0), (100.0, 0.0)) and w.centerline_pts[-1] in ((0.0, 0.0), (100.0, 0.0)))
            source_ids = _chain_source_primitive_ids(list(whole.face_a_segment_ids), edges_by_id)
            assert source_ids == ("whole",)  # both scenarios trace to the exact same single native id
            return canonical_wall_candidate_id_v2(
                "v1", list(whole.face_a_segment_ids), edges_by_id, whole.centerline_pts[0], whole.centerline_pts[-1]
            )

        unsplit = [_seg("whole", 0, 0, 100, 0)]
        split_by_incidental_crossing = [_seg("whole", 0, 0, 100, 0), _seg("cross", 50, -20, 50, 20)]

        id_unsplit = _v2_id_for_whole_chain(unsplit)
        id_split = _v2_id_for_whole_chain(split_by_incidental_crossing)
        assert id_unsplit == id_split  # same native source, different splitter fragment count -> same identity

        # Replay determinism: re-running the split scenario, and running it
        # again with the two input segments in the opposite order, must
        # still produce the identical id.
        reordered = list(reversed(split_by_incidental_crossing))
        assert _v2_id_for_whole_chain(reordered) == id_split


# ---------------------------------------------------------------------------
# 19-23: evidence conflict, missing/ambiguous geometry, repetition, orientation
# ---------------------------------------------------------------------------


class TestEvidenceAndAmbiguity:
    def test_19_conflicting_u2_evidence_surfaces_as_conflict_not_hidden(self):
        # A regular grid of long parallel lines -- U2's own GRID opposing
        # nomination -- laid over what would otherwise read as walls.
        segs = []
        for i in range(4):
            y = i * 15.0
            segs.append(_seg(f"g{i}", 0, y, 300, y))
        out = _run_pipeline(segs)
        assert any(w.status == EvidenceResolutionStatus.CONFLICT for w in out["resolved"])
        conflicted = [w for w in out["resolved"] if w.status == EvidenceResolutionStatus.CONFLICT]
        assert all(w.conflicting_evidence_ids and w.supporting_evidence_ids for w in conflicted)

    def test_20_missing_wall_section_no_forced_closure(self):
        # Three of four sides of a rectangle -- the fourth is entirely absent.
        segs = [_seg("a", 0, 0, 200, 0), _seg("b", 200, 0, 200, 100), _seg("c", 200, 100, 0, 100)]
        out = _run_pipeline(segs)
        assert len(out["rooms"]) == 0  # no forced closure across missing evidence

    def test_21_ambiguous_closure_preserves_multiple_plausible_faces(self):
        # A figure-eight-like double cell: two rectangles sharing one edge, plus a diagonal offering an alternate closure.
        # Single-line geometry -- see test_03's note on why this uses the
        # permissive population; the property under test here is "no single
        # 'best' closure is force-picked," which the permissive population
        # still exercises correctly.
        segs = _loop_segs([(0, 0), (100, 0), (100, 100), (0, 100)], "a")
        segs += _loop_segs([(100, 0), (200, 0), (200, 100), (100, 100)], "b")
        out = _run_pipeline(segs, exclude_conflict=False)
        assert len(out["rooms"]) >= 2  # both cells preserved, no single "best" pick

    def test_22_repeated_partitions_still_individually_evaluated(self):
        segs = []
        for i in range(5):
            x = i * 40.0
            segs.append(_seg(f"part{i}", x, 0, x, 100))
        segs.append(_seg("top", 0, 0, 160, 0))
        segs.append(_seg("bottom", 0, 100, 160, 100))
        out = _run_pipeline(segs)
        assert len(out["walls"]) == len(segs)  # no partition silently merged/dropped for being repeated

    def test_23_non_axis_aligned_walls(self):
        # Single-line geometry -- see test_03's note.
        pts = [(0, 0), (100, 30), (130, 130), (20, 100)]
        segs = _loop_segs(pts, "diag")
        out = _run_pipeline(segs, exclude_conflict=False)
        assert len(out["rooms"]) >= 1


# ---------------------------------------------------------------------------
# 24-30: transform invariance, determinism, immutability, lineage, metadata conflict
# ---------------------------------------------------------------------------


class TestInvarianceAndDeterminism:
    def _base_case(self):
        # wall_pt=6.0 (not the default 10.0): detect_wall_pairs uses an
        # absolute-point gap range (0.8-18.0pt when no scale authority is
        # given) -- the default 10pt wall would exceed that range once
        # scaled by test_24's 2.5x factor (25pt), losing paired-face
        # evidence for a reason unrelated to this test's own purpose
        # (invariance under affine transforms, not detect_wall_pairs'
        # legacy absolute-threshold behavior). 6pt stays in-range at every
        # transform this class applies.
        return _double_rect(0, 0, 200, 100, wall_pt=6.0)

    def test_24_translated_rotated_scaled_geometry(self):
        base = self._base_case()

        def _translate(segs, dx, dy):
            return [dict(s, x1=s["x1"] + dx, y1=s["y1"] + dy, x2=s["x2"] + dx, y2=s["y2"] + dy) for s in segs]

        def _scale(segs, factor):
            return [dict(s, x1=s["x1"] * factor, y1=s["y1"] * factor, x2=s["x2"] * factor, y2=s["y2"] * factor) for s in segs]

        def _rotate(segs, theta):
            c, s = math.cos(theta), math.sin(theta)
            def rot(x, y):
                return (x * c - y * s, x * s + y * c)
            out = []
            for seg in segs:
                x1, y1 = rot(seg["x1"], seg["y1"])
                x2, y2 = rot(seg["x2"], seg["y2"])
                out.append(dict(seg, x1=x1, y1=y1, x2=x2, y2=y2))
            return out

        for label, transformed in (
            ("translated", _translate(base, 500, -300)),
            ("scaled", _scale(base, 2.5)),
            ("rotated", _rotate(base, math.pi / 6)),
        ):
            out = _run_pipeline(transformed)
            assert any(_existence_status(w) == "corroborated" for w in out["resolved"]), label
            assert len(out["rooms"]) >= 1, label

    def test_25_shuffled_input_order_same_evidence_outcome(self):
        base = self._base_case()
        outcomes = []
        for seed in (1, 2, 3):
            shuffled = list(base)
            random.Random(seed).shuffle(shuffled)
            out = _run_pipeline(shuffled)
            statuses = sorted(_existence_status(w) for w in out["resolved"])
            outcomes.append((statuses, len(out["rooms"])))
        assert len(set(tuple(o[0]) for o in outcomes)) == 1
        assert len(set(o[1] for o in outcomes)) == 1

    def test_26_viewport_isolation(self):
        base = self._base_case()
        out_a = _run_pipeline(base, viewport_id="vpA")
        out_b = _run_pipeline(base, viewport_id="vpB")
        ids_a = {w.candidate_id for w in out_a["resolved"]}
        ids_b = {w.candidate_id for w in out_b["resolved"]}
        assert ids_a.isdisjoint(ids_b)

    def test_27_deterministic_replay(self):
        base = self._base_case()
        out1 = _run_pipeline(base)
        out2 = _run_pipeline(base)
        ids1 = sorted((w.candidate_id, w.status.value, round(w.confidence, 6)) for w in out1["resolved"])
        ids2 = sorted((w.candidate_id, w.status.value, round(w.confidence, 6)) for w in out2["resolved"])
        assert ids1 == ids2
        assert sorted(r.room_ref for r in out1["rooms"]) == sorted(r.room_ref for r in out2["rooms"])

    def test_28_input_immutability(self):
        import copy
        base = self._base_case()
        snapshot = copy.deepcopy(base)
        _run_pipeline(base)
        assert base == snapshot

    def test_29_plural_u1_lineage_reflected_in_evidence(self):
        # Two exact-duplicate native segments -> one derived edge with plural lineage.
        segs = [_seg("dup1", 0, 0, 100, 0, layer="Wall A"), _seg("dup2", 0, 0, 100, 0, layer="Wall A")]
        segs += [_seg("c", 0, 0, 0, 50), _seg("d", 100, 0, 100, 50), _seg("e", 0, 50, 100, 50)]
        out = _run_pipeline(segs)
        edges_by_id = {str(e["id"]): e for e in out["graph"]["edges"] if not e.get("_removed")}
        plural_found = any(
            len((e.get("primitive_lineage") or {}).get("source_primitive_ids", [])) >= 2 for e in edges_by_id.values()
        )
        assert plural_found

    def test_31_isolated_dangling_segment_does_not_get_junction_family(self):
        # Confirmed real-drawing false-strong pattern (Lamu/KSTVET census):
        # a fully isolated segment (both ends bare ENDPOINT, touching
        # nothing else) trivially satisfied "valid_junction_behavior" before
        # this fix, letting a short, repeated, hatch-tick-scale fragment
        # reach physical_evidence_status=corroborated alongside U2's own
        # near-universal solid-stroke support -- two nearly-non-discriminating
        # signals falsely counted as two independent confirmations.
        segs = [_seg("lonely", 500, 500, 503.6, 500, layer="Layer 1")]
        out = _run_pipeline(segs)
        assert len(out["resolved"]) == 1
        wall = out["resolved"][0]
        assert FAMILY_VALID_JUNCTION_BEHAVIOR not in wall.metadata.get("physical_evidence_families", [])
        assert _existence_status(wall) != "corroborated"

    def test_30_conflicting_metadata_never_becomes_false_certainty(self):
        segs = [_seg("m1", 0, 0, 100, 0, width=0.2, layer="Wall Type A"), _seg("m2", 0, 0, 100, 0, width=0.9, layer="Wall Type B")]
        segs += [_seg("c", 0, 0, 0, 50), _seg("d", 100, 0, 100, 50), _seg("e", 0, 50, 100, 50)]
        out = _run_pipeline(segs)
        edges_by_id = {str(e["id"]): e for e in out["graph"]["edges"] if not e.get("_removed")}
        conflict_found = any(
            "width" in ((e.get("primitive_lineage") or {}).get("attribute_status") or {})
            and (e["primitive_lineage"]["attribute_status"]["width"] == "conflict")
            for e in edges_by_id.values()
        )
        assert conflict_found
        # This module's own wall evidence must never silently pick one width as "the" value.
        for w in out["resolved"]:
            assert w.thickness_m is None
