from __future__ import annotations

from types import SimpleNamespace

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_opening_local_host_binding_authority import (
    OPENING_LOCAL_HOST_AMBIGUOUS,
    OPENING_LOCAL_HOST_PAGE_SCOPE_REQUIRED,
    OpeningLocalHostBindingResult,
    _resolve_local_band_from_page_scope,
)
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


def _record(wall_id: str, start, end, *, source_id: str | None = None):
    wall=WallCandidate(
        candidate_id=wall_id,
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=(start,end),
        face_a_segment_ids=(f"edge:{wall_id}",),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=(f"{wall_id}:a",f"{wall_id}:b"),
        junction_types=(JunctionType.ENDPOINT,JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        confidence=0.5,
    )
    ident=PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id=wall.viewport_id,
        candidate_identity_id=f"identity:{wall_id}",
        path_fingerprint=(start,end),
        source_primitive_ids=(source_id or f"source:{wall_id}",),
        edge_ids=(f"edge:{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=wall,
        physical_identity=ident,
    )


def _band(center: float=0.0):
    top=center-5.0
    bottom=center+5.0
    return (
        _record(f"lt:{center}",(-100.0,top),(0.0,top)),
        _record(f"rt:{center}",(40.0,top),(140.0,top)),
        _record(f"lb:{center}",(-100.0,bottom),(0.0,bottom)),
        _record(f"rb:{center}",(40.0,bottom),(140.0,bottom)),
    )


def _equivalence(records, *, pairs=(), ambiguous=()):
    ambiguous=set(ambiguous)
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(
            r.wall_candidate_id for r in records
            if r.wall_candidate_id not in ambiguous
        ),
        abstained_wall_ids=tuple(sorted(ambiguous)),
        equivalence_groups=(),
        ambiguous_wall_ids=tuple(sorted(ambiguous)),
        same_wall_ids=(),
        pair_classifications=tuple(
            sorted(
                (
                    min(a,b),
                    max(a,b),
                    c.value,
                )
                for a,b,c in pairs
            )
        ),
        blocking_reasons_by_wall_id={
            wall_id:("ambiguous_physical_wall_equivalence",)
            for wall_id in ambiguous
        },
    )


def _scope(records, *, kind="page", complete=False, equivalence=None):
    return SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_kind=kind,
        scope_complete=complete,
        records=tuple(records),
        equivalence=equivalence or _equivalence(tuple(records)),
        reason_codes=(
            "physical_wall_candidate_scope_resolved",
            "physical_wall_candidate_scope_cropped_at_viewport_boundary",
        ) if not complete else ("physical_wall_candidate_scope_resolved",),
    )


def test_incomplete_page_scope_can_prove_one_unique_local_host_band() -> None:
    records=_band()
    result=_resolve_local_band_from_page_scope(
        _scope(records,complete=False),
        OPENING,
    )
    assert not isinstance(result,OpeningLocalHostBindingResult)
    assert len(result.member_ids)==4
    assert abs(result.center_offset)<=1e-9


def test_incomplete_viewport_scope_never_uses_page_local_exception() -> None:
    records=_band()
    result=_resolve_local_band_from_page_scope(
        _scope(records,kind="viewport",complete=False),
        OPENING,
    )
    assert isinstance(result,OpeningLocalHostBindingResult)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_LOCAL_HOST_PAGE_SCOPE_REQUIRED in result.reason_codes


def test_two_local_host_bands_remain_ambiguous() -> None:
    records=_band(0.0)+_band(20.0)
    result=_resolve_local_band_from_page_scope(
        _scope(records,complete=False),
        OPENING,
    )
    assert isinstance(result,OpeningLocalHostBindingResult)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_LOCAL_HOST_AMBIGUOUS in result.reason_codes


def test_same_role_ambiguous_representation_remains_conflict() -> None:
    base=_band()
    extra=_record("lt-shadow",(-100.0,-5.0),(0.0,-5.0),source_id="foreign")
    records=base+(extra,)
    eq=_equivalence(
        records,
        pairs=((
            "lt:0.0",
            "lt-shadow",
            PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        ),),
        ambiguous=("lt:0.0","lt-shadow"),
    )
    result=_resolve_local_band_from_page_scope(
        _scope(records,complete=False,equivalence=eq),
        OPENING,
    )
    assert isinstance(result,OpeningLocalHostBindingResult)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert OPENING_LOCAL_HOST_AMBIGUOUS in result.reason_codes
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes


def test_remote_ambiguity_does_not_poison_unique_local_host() -> None:
    base=_band()
    remote=_record("remote",(200.0,-5.0),(260.0,-5.0))
    records=base+(remote,)
    eq=_equivalence(
        records,
        pairs=((
            "lt:0.0",
            "remote",
            PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        ),),
        ambiguous=("lt:0.0","remote"),
    )
    result=_resolve_local_band_from_page_scope(
        _scope(records,complete=False,equivalence=eq),
        OPENING,
    )
    assert not isinstance(result,OpeningLocalHostBindingResult)
    assert len(result.member_ids)==4


def test_complete_page_scope_uses_same_local_proof_without_special_ranking() -> None:
    records=_band()
    result=_resolve_local_band_from_page_scope(
        _scope(records,complete=True),
        OPENING,
    )
    assert not isinstance(result,OpeningLocalHostBindingResult)
    assert len(result.member_ids)==4
