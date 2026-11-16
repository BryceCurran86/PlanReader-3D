"""Unique-or-abstain exterior endpoint receipts; near-miss is never a join."""
from __future__ import annotations

from types import SimpleNamespace

from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_wall_graph_diagnostic import (
    NativeWallEndpointNearMiss,
    inspect_native_wall_graph,
)
from pb_source_native_exterior_endpoint_authority_shadow import (
    REASON_COMPETING,
    REASON_CONTACT_CANDIDATE,
    REASON_FOREIGN_VIEW,
    REASON_INVALID_SEPARATION,
    REASON_MISSING_NATIVE_PATH_OWNER,
    REASON_NEAR_MISS,
    REASON_OPENING_TOPOLOGY,
    REASON_SELF_PATH_COLLISION,
    ROLE_DIAGONAL_BRIDGE,
    ROLE_EXCLUSION,
    ROLE_EXTERIOR_OUTER_FACE,
    ROLE_INTERNAL_WALL,
    authenticate_external_wall_junction,
    classify_source_native_path_role,
    receipt_from_near_miss,
)


def _miss(*, sep, left=(1708,), right=(1704,), layers_left=("Enclosure_WallExternal",), layers_right=("Enclosure_WallExternal",)):
    return NativeWallEndpointNearMiss(
        tip_pdf_pts=(10.0, 0.5),
        native_path_ids=left,
        nearby_native_path_ids=right,
        separation_pdf_pts=sep,
        native_source_layers=layers_left,
        nearby_source_layers=layers_right,
        same_painted_exterior_layer_hint=False,
        physical_join_authenticated=False,
        measurement_authorized=False,
    )


def _drawing(layer, *, fill=(0.0, 0.0, 0.0)):
    return {"layer": layer, "fill": fill}


def test_point4252_exterior_near_miss_is_not_a_wall_join():
    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Enclosure_WallExternal"),
    )
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.4252, drawings=drawings,
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_NEAR_MISS
    receipt = receipt_from_near_miss(
        _miss(sep=0.4252, left=(0,), right=(1,)), drawings,
    )
    assert receipt.physical_join_authenticated is False
    assert receipt.can_issue_area is False
    assert receipt.measurement_authorized is False


def test_joinery_and_annotation_competitors_stay_unjoined():
    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Interior_Joinery"),
        _drawing("A-ANNO-TEXT"),
        _drawing("Floor_Slab"),
    )
    joinery_status, joinery_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=drawings,
    )
    assert joinery_status is EvidenceResolutionStatus.ABSTAINED
    assert joinery_reason == REASON_COMPETING
    anno_status, anno_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(2,),
        separation_pdf_pts=0.02, drawings=drawings,
    )
    assert anno_status is EvidenceResolutionStatus.ABSTAINED
    assert anno_reason == REASON_COMPETING
    slab_status, slab_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(3,),
        separation_pdf_pts=0.02, drawings=drawings,
    )
    assert slab_status is EvidenceResolutionStatus.ABSTAINED
    assert slab_reason == REASON_COMPETING


def test_representation_contact_same_exterior_paint_is_candidate_not_firm():
    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Enclosure_WallExternal"),
    )
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=drawings,
    )
    assert status is EvidenceResolutionStatus.CANDIDATE
    assert reason == REASON_CONTACT_CANDIDATE


def test_opening_chassis_is_topology_only_not_a_wall_join():
    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Enclosure_WallExternal"),
    )
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=drawings,
        opening_chassis_witness=True,
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_OPENING_TOPOLOGY


def test_two_point_one_four_eight_pt_is_not_commercial_snap_join():
    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Enclosure_WallExternal"),
    )
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=2.1448, drawings=drawings,
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_NEAR_MISS


def test_unwitnessed_222pt_span_is_not_authenticated_as_a_door():
    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Enclosure_WallExternal"),
    )
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=222.624, drawings=drawings,
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_NEAR_MISS


def test_missing_both_native_path_ids_is_not_a_candidate_join():
    valid = {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(99,), nearby_native_path_ids=(100,),
        separation_pdf_pts=0.02, drawings=(),
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_MISSING_NATIVE_PATH_OWNER
    empty_status, empty_reason = authenticate_external_wall_junction(
        native_path_ids=(), nearby_native_path_ids=(0,),
        separation_pdf_pts=0.02, drawings=(valid,),
    )
    assert empty_status is EvidenceResolutionStatus.ABSTAINED
    assert empty_reason == REASON_MISSING_NATIVE_PATH_OWNER


def test_missing_one_native_path_id_is_not_a_candidate_join():
    valid = {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(99,),
        separation_pdf_pts=0.02, drawings=(valid,),
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_MISSING_NATIVE_PATH_OWNER


def test_negative_separation_is_not_a_candidate_join():
    valid = {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=-1.0, drawings=(valid, valid),
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_INVALID_SEPARATION


def test_foreign_view_path_index_collision_stays_unjoined():
    left = {
        "layer": "Enclosure_WallExternal",
        "fill": (0, 0, 0),
        "viewport_id": "plan-a",
    }
    right = {
        "layer": "Enclosure_WallExternal",
        "fill": (0, 0, 0),
        "viewport_id": "plan-b",
    }
    missing_view = {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
    collision_status, collision_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=(left, right),
    )
    assert collision_status is EvidenceResolutionStatus.ABSTAINED
    assert collision_reason == REASON_FOREIGN_VIEW
    missing_status, missing_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=(left, missing_view),
    )
    assert missing_status is EvidenceResolutionStatus.ABSTAINED
    assert missing_reason == REASON_FOREIGN_VIEW
    same_view_status, same_view_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=(left, dict(right, viewport_id="plan-a")),
    )
    assert same_view_status is EvidenceResolutionStatus.CANDIDATE
    assert same_view_reason == REASON_CONTACT_CANDIDATE


def test_identical_native_path_cannot_witness_a_cross_path_junction():
    valid = {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)}
    status, reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(0,),
        separation_pdf_pts=0.0, drawings=(valid,),
    )
    assert status is EvidenceResolutionStatus.ABSTAINED
    assert reason == REASON_SELF_PATH_COLLISION


def test_partial_path_id_overlap_is_not_a_candidate_join():
    drawings = (
        {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)},
        {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)},
        {"layer": "Enclosure_WallExternal", "fill": (0, 0, 0)},
    )
    overlap_status, overlap_reason = authenticate_external_wall_junction(
        native_path_ids=(0, 1), nearby_native_path_ids=(1, 2),
        separation_pdf_pts=0.0, drawings=drawings,
    )
    assert overlap_status is EvidenceResolutionStatus.ABSTAINED
    assert overlap_reason == REASON_SELF_PATH_COLLISION
    duplicate_status, duplicate_reason = authenticate_external_wall_junction(
        native_path_ids=(0, 0), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=drawings,
    )
    assert duplicate_status is EvidenceResolutionStatus.ABSTAINED
    assert duplicate_reason == REASON_SELF_PATH_COLLISION
    disjoint_status, disjoint_reason = authenticate_external_wall_junction(
        native_path_ids=(0,), nearby_native_path_ids=(1,),
        separation_pdf_pts=0.02, drawings=drawings,
    )
    assert disjoint_status is EvidenceResolutionStatus.CANDIDATE
    assert disjoint_reason == REASON_CONTACT_CANDIDATE


def test_graph_near_miss_receipts_never_apply_commercial_snap_join():
    def strip(source_id, bounds):
        return SimpleNamespace(
            polygon=box(*bounds),
            native_path_indices=lambda: (source_id,),
        )

    drawings = (
        _drawing("Enclosure_WallExternal"),
        _drawing("Enclosure_WallExternal"),
    )
    graph = inspect_native_wall_graph(
        (strip(0, (0, 0, 10, 1)), strip(1, (10.4252, 0, 20.4252, 1))),
        source_drawings=drawings,
    )
    assert graph.second_stage_join_applied is False
    assert graph.endpoint_near_miss_total >= 1
    receipt = receipt_from_near_miss(graph.endpoint_near_misses[0], drawings)
    assert receipt.status is EvidenceResolutionStatus.ABSTAINED
    assert receipt.reason == REASON_NEAR_MISS
    assert receipt.native_path_ids[0] in (0, 1)
    assert receipt.nearby_native_path_ids[0] in (0, 1)
    assert receipt.native_source_layers == ("Enclosure_WallExternal",)


def _line(layer, a, b, **extra):
    row = {
        "layer": layer,
        "fill": extra.pop("fill", (0.0, 0.0, 0.0)),
        "color": extra.pop("color", (0.0, 0.0, 0.0)),
        "dashes": extra.pop("dashes", ""),
        "items": (("l", a, b),),
    }
    row.update(extra)
    return row


def test_native_roles_reject_exclusion_and_diagonal_without_raster_hull():
    assert classify_source_native_path_role(
        _line("Enclosure_WallExternal", (0, 0), (80, 0), dashes="[3 2] 0"),
    ) == ROLE_EXCLUSION
    assert classify_source_native_path_role(
        _line("A-WALL", (0, 10), (80, 10), color=(0.1, 0.9, 0.1), fill=None),
    ) == ROLE_EXCLUSION
    assert classify_source_native_path_role(
        _line("A-ANNO-DIMS", (0, 20), (80, 20)),
    ) == ROLE_EXCLUSION
    assert classify_source_native_path_role(
        _line("Interior_Joinery", (0, 30), (80, 30)),
    ) == ROLE_EXCLUSION
    assert classify_source_native_path_role(
        _line("Enclosure_WallExternal", (210, 130), (800, 490)),
    ) == ROLE_DIAGONAL_BRIDGE
    assert classify_source_native_path_role(
        _line("Enclosure_WallExternal", (0, 0), (80, 0)),
    ) == ROLE_EXTERIOR_OUTER_FACE
    assert classify_source_native_path_role(
        _line("A-WALL", (0, 0), (80, 0)),
    ) == ROLE_INTERNAL_WALL


def test_freestanding_timber_post_classified_as_role_exclusion():
    """Isolated square timber post (e.g. 140x140 path 4102) is excluded from exterior walls."""
    post_drawing = {
        "layer": "Enclosure_WallExternal",
        "rect": (400.0, 400.0, 404.0, 404.0),
        "fill": (0.0, 0.0, 0.0),
    }
    assert classify_source_native_path_role(post_drawing) == ROLE_EXCLUSION
