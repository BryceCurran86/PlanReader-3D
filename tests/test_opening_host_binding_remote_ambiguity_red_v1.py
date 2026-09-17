"""Expected-red regression for remote physical-wall ambiguity in host binding.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

The selected opening has one unique four-piece host band. A fifth wall piece is
remote from the opening and cannot play any left/right jamb-adjacent host role.
Upstream physical-wall equivalence intentionally leaves that remote piece
AMBIGUOUS relative to one local piece because independent provenance does not
prove SAME or DISTINCT. That remote ambiguity must not invalidate the otherwise
unique local host proposition.

A second control keeps genuine same-role ambiguity fail-closed.
"""
from __future__ import annotations

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_physical_wall_candidate_authority import PhysicalWallCandidateRecord
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


OPENING = host._OpeningGeometry(
    origin=(0.0, 0.0),
    axis=(1.0, 0.0),
    normal=(0.0, 1.0),
    length=40.0,
    thickness=10.0,
)


def _record(
    wall_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    source_id: str | None = None,
) -> PhysicalWallCandidateRecord:
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
        confidence=0.5,
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"candidate-identity:{wall_id}",
        path_fingerprint=(start, end),
        source_primitive_ids=(source_id or f"source:{wall_id}",),
        edge_ids=(f"edge:{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=identity,
    )


def _base_records() -> tuple[PhysicalWallCandidateRecord, ...]:
    return (
        _record("left-top", (-100.0, -5.0), (0.0, -5.0)),
        _record("right-top", (40.0, -5.0), (140.0, -5.0)),
        _record("left-bottom", (-100.0, 5.0), (0.0, 5.0)),
        _record("right-bottom", (40.0, 5.0), (140.0, 5.0)),
    )


def _equivalence(
    records: tuple[PhysicalWallCandidateRecord, ...],
    *,
    pairs: tuple[tuple[str, str, PhysicalEquivalenceClass], ...] = (),
    ambiguous_ids: tuple[str, ...] = (),
) -> PhysicalWallEquivalenceResolution:
    ids = tuple(record.wall_candidate_id for record in records)
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(
            wall_id for wall_id in ids if wall_id not in set(ambiguous_ids)
        ),
        abstained_wall_ids=tuple(sorted(ambiguous_ids)),
        equivalence_groups=(),
        ambiguous_wall_ids=tuple(sorted(ambiguous_ids)),
        same_wall_ids=(),
        pair_classifications=tuple(
            sorted(
                (
                    min(left, right),
                    max(left, right),
                    classification.value,
                )
                for left, right, classification in pairs
            )
        ),
        blocking_reasons_by_wall_id={
            wall_id: ("ambiguous_physical_wall_equivalence",)
            for wall_id in ambiguous_ids
        },
    )


def test_remote_ambiguity_does_not_poison_unique_local_host_band() -> None:
    """Expected RED on main until the scope-wide ambiguity veto is narrowed."""
    base = _base_records()
    remote = _record(
        "remote-top",
        (200.0, -5.0),
        (260.0, -5.0),
        source_id="source:remote-independent-piece",
    )
    records = base + (remote,)
    equivalence = _equivalence(
        records,
        pairs=((
            "left-top",
            "remote-top",
            PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        ),),
        ambiguous_ids=("left-top", "remote-top"),
    )

    result = host._resolve_host_bands(records, OPENING, equivalence)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    assert result.bands[0].member_ids == tuple(
        sorted(record.wall_candidate_id for record in base)
    )
    assert "remote-top" not in result.bands[0].member_ids


def test_same_role_ambiguity_still_fails_closed() -> None:
    """Control: narrowing remote ambiguity must not weaken local ambiguity."""
    base = _base_records()
    duplicate = _record(
        "left-top-foreign",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:foreign-same-role",
    )
    records = base + (duplicate,)
    equivalence = _equivalence(
        records,
        pairs=((
            "left-top",
            "left-top-foreign",
            PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        ),),
        ambiguous_ids=("left-top", "left-top-foreign"),
    )

    result = host._resolve_host_bands(records, OPENING, equivalence)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes
