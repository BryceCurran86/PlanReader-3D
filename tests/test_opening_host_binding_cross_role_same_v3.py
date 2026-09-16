"""Regression for Item 4B SAME groups that span structural host roles."""
from __future__ import annotations

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_physical_wall_candidate_authority import PhysicalWallCandidateRecord
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution, PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


OPENING = host._OpeningGeometry(
    origin=(0.0, 0.0),
    axis=(1.0, 0.0),
    normal=(0.0, 1.0),
    length=40.0,
    thickness=10.0,
)


def _record(wall_id: str, start: tuple[float, float], end: tuple[float, float]):
    wall = WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=(start, end),
        face_a_segment_ids=(f"edge:{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"node:{wall_id}:a", f"node:{wall_id}:b"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.5,
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"candidate:{wall_id}",
        path_fingerprint=(start, end),
        source_primitive_ids=(f"source:{wall_id}",),
        edge_ids=(f"edge:{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def test_proven_same_group_spanning_wall_faces_does_not_delete_a_host_role() -> None:
    left_top = _record("left-top", (-100.0, -5.0), (0.0, -5.0))
    right_top = _record("right-top", (40.0, -5.0), (140.0, -5.0))
    left_bottom = _record("left-bottom", (-100.0, 5.0), (0.0, 5.0))
    right_bottom = _record("right-bottom", (40.0, 5.0), (140.0, 5.0))
    records = (left_top, right_top, left_bottom, right_bottom)

    left_group = ("left-bottom", "left-top")
    right_group = ("right-bottom", "right-top")
    equivalence = PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        # Only one global representative per SAME group, exactly as upstream
        # equivalence publication does. The non-representative face role still
        # carries source geometry and must not disappear from host proof.
        representative_wall_ids=("left-bottom", "right-bottom"),
        abstained_wall_ids=("left-top", "right-top"),
        equivalence_groups=(left_group, right_group),
        ambiguous_wall_ids=(),
        same_wall_ids=tuple(sorted(left_group + right_group)),
        pair_classifications=(
            ("left-bottom", "left-top", "same_physical_wall"),
            ("right-bottom", "right-top", "same_physical_wall"),
        ),
        blocking_reasons_by_wall_id={
            "left-top": ("equivalent_physical_wall_represented_by:left-bottom",),
            "right-top": ("equivalent_physical_wall_represented_by:right-bottom",),
        },
    )

    result = host._resolve_host_bands(records, OPENING, equivalence)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    band = result.bands[0]
    assert set(band.member_ids) == {record.wall_candidate_id for record in records}
    assert set(band.member_equivalence_groups) == {left_group, right_group}
