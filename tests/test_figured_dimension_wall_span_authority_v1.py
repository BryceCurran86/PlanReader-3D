"""Synthetic proofs for pb_figured_dimension_wall_span_authority.py (shadow only).

Covers the required positive, negative, and metamorphic cases per the
Ghazi-lane task brief: witness-bound ownership, translation/rotation/scale/
input-order invariance, ambiguous walls, wrong orientation, sub-span
(door/window-shaped) dimensions, cross-viewport isolation, stale revision,
wrong source SHA, and same-wall conflicting figured dimensions.
"""
from __future__ import annotations

import math

import pytest

from pb_dimension_graph_constraint_engine import DimensionObservation
from pb_figured_dimension_evidence import BindingStatus, DimensionLayoutCalibration
from pb_migration_contracts import EvidenceResolutionStatus
from pb_migration_provider_envelope import ProviderContext
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_figured_dimension_wall_span_authority import (
    WALL_SPAN_AMBIGUOUS_WALLS,
    WALL_SPAN_ENDPOINT_COVERAGE_MISMATCH,
    WALL_SPAN_NOT_WITNESS_BOUND,
    WALL_SPAN_NO_CANDIDATE_WALL,
    WALL_SPAN_ORIENTATION_MISMATCH,
    WALL_SPAN_REVISION_STALE,
    WALL_SPAN_SOURCE_SHA_MISMATCH,
    WALL_SPAN_VIEWPORT_NOT_OWNED,
    detect_conflicting_wall_span_records,
    resolve_figured_wall_span_identity,
    to_owned_evidence_atom,
)

DOC_ID = "doc-1"
SHA = "a" * 64
REV = "rev-1"
SNAPSHOT = "snap-1"
VIEWPORT = "vp-floorplan-1"

CALIBRATION = DimensionLayoutCalibration(
    median_word_height_pt=8.0,
    line_search_distance_pt=16.0,
    witness_endpoint_distance_pt=3.0,
    chain_axis_tolerance_pt=4.4,
)


def _context(*, revision_id=REV, current_revision_id=REV, document_id=DOC_ID, source_sha256=SHA, owned_viewports=(VIEWPORT,)):
    return ProviderContext(
        run_id="run-1",
        workspace_id="ws-1",
        project_id="proj-1",
        document_id=document_id,
        source_sha256=source_sha256,
        revision_id=revision_id,
        current_revision_id=current_revision_id,
        selected_pages=(0,),
        owned_viewport_ids=owned_viewports,
        evidence_snapshot_id=SNAPSHOT,
    )


def _wall(candidate_id, centerline_pts, *, viewport_id=VIEWPORT, thickness_m=None, thickness_authority=MeasurementAuthorityType.PROVISIONAL):
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="single_line",
        centerline_pts=tuple(centerline_pts),
        face_a_segment_ids=(f"{candidate_id}-edge-0",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=thickness_m,
        thickness_authority=thickness_authority,
        length_m=None,
        end_node_ids=(f"{candidate_id}-n0", f"{candidate_id}-n1"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
    )


def _observation(dimension_id, *, view_id=VIEWPORT, source_page=1, raw_text="3000", value=3000.0, unit="mm", endpoints=None, witness_targets=()):
    return DimensionObservation(
        dimension_id=dimension_id,
        source_page=source_page,
        view_id=view_id,
        bbox=(0.0, 0.0, 1.0, 1.0),
        raw_text=raw_text,
        value=value,
        unit=unit,
        endpoints=endpoints,
        witness_targets=witness_targets,
    )


def _resolve(observation, walls, *, binding_status=BindingStatus.WITNESS_BOUND.value, context=None, document_id=DOC_ID, source_sha256=SHA, calibration=CALIBRATION):
    return resolve_figured_wall_span_identity(
        observation,
        walls=walls,
        calibration=calibration,
        context=context or _context(),
        document_id=document_id,
        source_sha256=source_sha256,
        binding_status=binding_status,
    )


# ---------------------------------------------------------------------------
# POSITIVE
# ---------------------------------------------------------------------------

def test_single_wall_witness_bound_dimension_resolves():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"
    assert record.value_m == pytest.approx(3.0)
    atom = to_owned_evidence_atom(record)
    assert atom is not None
    assert atom.metadata["wall_candidate_id"] == "wall-A"
    assert atom.metadata["source_sha256"] == SHA
    assert atom.metadata["revision_id"] == REV
    assert atom.kind == "figured_dimension"


def _rotate(point, theta_rad):
    x, y = point
    return (x * math.cos(theta_rad) - y * math.sin(theta_rad), x * math.sin(theta_rad) + y * math.cos(theta_rad))


def test_translation_invariant():
    shift = (500.0, -250.0)
    wall = _wall("wall-A", [(0.0 + shift[0], 0.0 + shift[1]), (300.0 + shift[0], 0.0 + shift[1])])
    obs = _observation(
        "dim-1",
        endpoints=((0.0 + shift[0], 0.0 + shift[1]), (300.0 + shift[0], 0.0 + shift[1])),
        witness_targets=("w0", "w1"),
    )
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"


def test_rotation_invariant():
    theta = math.radians(37.0)
    p0, p1 = _rotate((0.0, 0.0), theta), _rotate((300.0, 0.0), theta)
    wall = _wall("wall-A", [p0, p1])
    obs = _observation("dim-1", endpoints=(p0, p1), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"


def test_drawing_scale_transformation_invariant():
    k = 4.0
    scaled_calibration = DimensionLayoutCalibration(
        median_word_height_pt=CALIBRATION.median_word_height_pt * k,
        line_search_distance_pt=CALIBRATION.line_search_distance_pt * k,
        witness_endpoint_distance_pt=CALIBRATION.witness_endpoint_distance_pt * k,
        chain_axis_tolerance_pt=CALIBRATION.chain_axis_tolerance_pt * k,
    )
    wall = _wall("wall-A", [(0.0, 0.0), (300.0 * k, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0 * k, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall], calibration=scaled_calibration)
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"
    # value_m is independent of page-geometry scale -- it comes from the
    # printed figured value, never from measured pixel/point distance.
    assert record.value_m == pytest.approx(3.0)


def test_input_order_invariance_both_endpoints_and_wall_points_swapped():
    wall = _wall("wall-A", [(300.0, 0.0), (0.0, 0.0)])  # wall points reversed
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w1", "w0"))  # obs endpoints not reversed
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"


def test_segment_splitting_invariance_straight_multi_point_centerline():
    # A wall whose centerline was represented as three collinear points
    # (e.g. a rejoined split) must resolve identically to a two-point wall.
    wall = _wall("wall-A", [(0.0, 0.0), (150.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"


# ---------------------------------------------------------------------------
# NEGATIVE
# ---------------------------------------------------------------------------

def test_dimension_text_near_wall_but_no_dimension_line_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=None, witness_targets=())
    record = _resolve(obs, [wall], binding_status=BindingStatus.UNSUPPORTED.value)
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NOT_WITNESS_BOUND in record.reason_codes


def test_line_with_one_terminator_missing_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=None, witness_targets=("w0",))
    record = _resolve(obs, [wall], binding_status=BindingStatus.PARTIAL_WITNESS.value)
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NOT_WITNESS_BOUND in record.reason_codes


def test_line_bound_without_witnesses_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=None, witness_targets=())
    record = _resolve(obs, [wall], binding_status=BindingStatus.LINE_BOUND.value)
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NOT_WITNESS_BOUND in record.reason_codes


def test_dimension_crosses_two_plausible_walls_is_ambiguous():
    # Two collinear, overlapping-endpoint walls on the same line -- both
    # geometrically eligible. Never resolved by nearest/first/smallest.
    wall_a = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    wall_b = _wall("wall-B", [(0.5, 0.0), (300.5, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall_a, wall_b])
    assert record.status is EvidenceResolutionStatus.CONFLICT
    assert WALL_SPAN_AMBIGUOUS_WALLS in record.reason_codes
    assert set(record.candidate_wall_ids) == {"wall-A", "wall-B"}


def test_dimension_belongs_to_neighbouring_wall_not_the_far_one():
    correct_wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    far_wall = _wall("wall-B", [(0.0, 500.0), (300.0, 500.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [correct_wall, far_wall])
    assert record.status is EvidenceResolutionStatus.CORROBORATED
    assert record.resolved_wall_id == "wall-A"


def test_room_width_dimension_perpendicular_to_wall_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])  # horizontal wall
    obs = _observation("dim-1", endpoints=((10.0, 0.0), (10.0, 250.0)), witness_targets=("w0", "w1"))  # vertical span
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NO_CANDIDATE_WALL in record.reason_codes


def test_door_width_subspan_dimension_does_not_claim_whole_wall():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    # A 90-unit span in the middle of a 300-unit wall (e.g. a door width),
    # not touching either wall endpoint.
    obs = _observation("dim-1", endpoints=((100.0, 0.0), (190.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall])
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NO_CANDIDATE_WALL in record.reason_codes
    assert record.geometry_checks[0].reasons == (WALL_SPAN_ENDPOINT_COVERAGE_MISMATCH,)


def test_dimension_in_another_viewport_is_excluded_not_cross_matched():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)], viewport_id="vp-other")
    obs = _observation("dim-1", view_id=VIEWPORT, endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall], context=_context(owned_viewports=(VIEWPORT, "vp-other")))
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NO_CANDIDATE_WALL in record.reason_codes


def test_viewport_not_owned_by_context_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall], context=_context(owned_viewports=("vp-unrelated",)))
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_VIEWPORT_NOT_OWNED in record.reason_codes


def test_stale_revision_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall], context=_context(revision_id="rev-old", current_revision_id="rev-new"))
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_REVISION_STALE in record.reason_codes


def test_wrong_source_sha_abstains():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [wall], source_sha256="b" * 64)  # context still has SHA "a"*64
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_SOURCE_SHA_MISMATCH in record.reason_codes


def test_no_candidate_wall_at_all_abstains():
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [])
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NO_CANDIDATE_WALL in record.reason_codes


def test_l_shaped_wall_is_never_attributed_a_single_run_dimension():
    l_wall = _wall("wall-L", [(0.0, 0.0), (300.0, 0.0), (300.0, 300.0)])
    obs = _observation("dim-1", endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    record = _resolve(obs, [l_wall])
    assert record.status is EvidenceResolutionStatus.ABSTAINED
    assert WALL_SPAN_NO_CANDIDATE_WALL in record.reason_codes


# ---------------------------------------------------------------------------
# CONFLICT / DUPLICATE reconciliation across multiple records
# ---------------------------------------------------------------------------

def test_duplicate_agreeing_dimensions_on_same_wall_are_not_flagged_conflicting():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs1 = _observation("dim-1", raw_text="3000", value=3000.0, endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    obs2 = _observation("dim-2", raw_text="3000", value=3000.0, endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w2", "w3"))
    r1, r2 = _resolve(obs1, [wall]), _resolve(obs2, [wall])
    assert r1.status is EvidenceResolutionStatus.CORROBORATED
    assert r2.status is EvidenceResolutionStatus.CORROBORATED
    conflicts = detect_conflicting_wall_span_records([r1, r2])
    assert conflicts == {}


def test_conflicting_dimensions_on_same_wall_are_flagged_never_averaged():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs1 = _observation("dim-1", raw_text="3000", value=3000.0, endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w0", "w1"))
    obs2 = _observation("dim-2", raw_text="3500", value=3500.0, endpoints=((0.0, 0.0), (300.0, 0.0)), witness_targets=("w2", "w3"))
    r1, r2 = _resolve(obs1, [wall]), _resolve(obs2, [wall])
    assert r1.status is EvidenceResolutionStatus.CORROBORATED
    assert r2.status is EvidenceResolutionStatus.CORROBORATED
    conflicts = detect_conflicting_wall_span_records([r1, r2])
    assert "wall-A" in conflicts
    assert len(conflicts["wall-A"]) == 2


def test_to_owned_evidence_atom_returns_none_for_non_corroborated():
    wall = _wall("wall-A", [(0.0, 0.0), (300.0, 0.0)])
    obs = _observation("dim-1", endpoints=None, witness_targets=())
    record = _resolve(obs, [wall], binding_status=BindingStatus.UNSUPPORTED.value)
    assert to_owned_evidence_atom(record) is None
