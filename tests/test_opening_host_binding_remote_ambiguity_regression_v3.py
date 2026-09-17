"""Permanent regressions for role-local host-binding ambiguity consumption."""
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
    ambiguous = set(ambiguous_ids)
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(
            record.wall_candidate_id
            for record in records
            if record.wall_candidate_id not in ambiguous
        ),
        abstained_wall_ids=tuple(sorted(ambiguous)),
        equivalence_groups=(),
        ambiguous_wall_ids=tuple(sorted(ambiguous)),
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
            for wall_id in ambiguous
        },
    )


def test_remote_ambiguity_does_not_poison_unique_local_host_band() -> None:
    base = _base_records()
    remote = _record("remote-top", (200.0, -5.0), (260.0, -5.0))
    records = base + (remote,)
    result = host._resolve_host_bands(
        records,
        OPENING,
        _equivalence(
            records,
            pairs=((
                "left-top",
                "remote-top",
                PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
            ),),
            ambiguous_ids=("left-top", "remote-top"),
        ),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1


def test_cross_role_ambiguity_does_not_poison_unique_local_host_band() -> None:
    records = _base_records()
    result = host._resolve_host_bands(
        records,
        OPENING,
        _equivalence(
            records,
            pairs=((
                "left-top",
                "left-bottom",
                PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
            ),),
            ambiguous_ids=("left-top", "left-bottom"),
        ),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1


def test_same_role_ambiguity_remains_fail_closed() -> None:
    base = _base_records()
    duplicate = _record(
        "left-top-shadow",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:foreign",
    )
    records = base + (duplicate,)
    result = host._resolve_host_bands(
        records,
        OPENING,
        _equivalence(
            records,
            pairs=((
                "left-top",
                "left-top-shadow",
                PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
            ),),
            ambiguous_ids=("left-top", "left-top-shadow"),
        ),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes


def test_unexplained_locally_relevant_ambiguous_id_remains_fail_closed() -> None:
    records = _base_records()
    result = host._resolve_host_bands(
        records,
        OPENING,
        _equivalence(records, ambiguous_ids=("left-top",)),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes
