from __future__ import annotations

from types import SimpleNamespace

import pb_opening_host_binding_authority as host
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateRecord
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution, PhysicalWallIdentity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate


OPENING = host._OpeningGeometry(
    origin=(0.0, 0.0), axis=(1.0, 0.0), normal=(0.0, 1.0), length=40.0, thickness=10.0
)


def _record(wall_id, start, end, raw_id):
    wall = WallCandidate(
        candidate_id=wall_id, viewport_id="wall-source:page-1", representation="single_line",
        centerline_pts=(start, end), face_a_segment_ids=(f"edge:{wall_id}",), face_b_segment_ids=None,
        is_curved=False, curve_control_pts=None, thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL, length_m=None,
        end_node_ids=(f"{wall_id}:a", f"{wall_id}:b"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved", level_id=None, status=EvidenceResolutionStatus.CANDIDATE, confidence=0.5,
    )
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id, viewport_id=wall.viewport_id,
        candidate_identity_id=f"identity:{wall_id}", path_fingerprint=(start, end),
        source_primitive_ids=(raw_id,), edge_ids=(f"edge:{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(wall_id, wall, identity)


def _equivalence(records, ambiguous=()):
    ids = tuple(r.wall_candidate_id for r in records)
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(i for i in ids if i not in set(ambiguous)),
        abstained_wall_ids=tuple(ambiguous), equivalence_groups=(),
        ambiguous_wall_ids=tuple(ambiguous), same_wall_ids=(), pair_classifications=(),
        blocking_reasons_by_wall_id={i: ("ambiguous_physical_wall_equivalence",) for i in ambiguous},
    )


def _obs(obs_id, raw_id, line):
    return SimpleNamespace(
        observation_id=obs_id, source_primitive_ref="visible:segment:" + raw_id,
        geometry=tuple(float(v) for v in line),
    )


def _opening_records():
    return (
        _obs("lt", "lt", (-100, -5, 0, -5)),
        _obs("rt", "rt", (40, -5, 140, -5)),
        _obs("lb", "lb", (-100, 5, 0, 5)),
        _obs("rb", "rb", (40, 5, 140, 5)),
        _obs("jl", "jl", (0, -5, 0, 5)),
        _obs("jr", "jr", (40, -5, 40, 5)),
    )


def _wall_records():
    return (
        _record("wall-lt", (-100, -5), (0, -5), "lt"),
        _record("wall-rt", (40, -5), (140, -5), "rt"),
        _record("wall-lb", (-100, 5), (0, 5), "lb"),
        _record("wall-rb", (40, 5), (140, 5), "rb"),
    )


def test_exact_two_face_lineage_resolves_despite_pagewide_ambiguity():
    records = _wall_records()
    result = host._resolve_two_face_lineage_host_from_records(
        _opening_records(), records, _equivalence(records, ambiguous=tuple(r.wall_candidate_id for r in records)), OPENING
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    assert result.reason_codes == (host.SOURCE_TWO_FACE_LINEAGE_HOST_RESOLVED,)
    assert result.bands[0].member_ids == tuple(sorted(r.wall_candidate_id for r in records))


def test_exact_two_face_lineage_conflicts_when_one_source_face_has_two_w4_owners():
    records = _wall_records()
    duplicate = _record("wall-lt-duplicate", (-100, -5), (0, -5), "lt")
    all_records = records + (duplicate,)
    result = host._resolve_two_face_lineage_host_from_records(
        _opening_records(), all_records, _equivalence(all_records), OPENING
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_TWO_FACE_LINEAGE_AMBIGUOUS in result.reason_codes


def test_exact_two_face_lineage_rechecks_w4_geometry_role():
    records = list(_wall_records())
    records[0] = _record("wall-lt-bad", (-100, -5), (-20, -5), "lt")
    records = tuple(records)
    result = host._resolve_two_face_lineage_host_from_records(
        _opening_records(), records, _equivalence(records), OPENING
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.bands == ()
    assert host.HOST_TWO_FACE_LINEAGE_GEOMETRY_MISMATCH in result.reason_codes
