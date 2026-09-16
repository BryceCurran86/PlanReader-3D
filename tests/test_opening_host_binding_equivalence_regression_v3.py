"""Regression coverage for #381 physical-wall equivalence consumption.

These tests exercise the narrow production helper that receives only
producer-owned wall records plus producer-owned PhysicalWallEquivalenceResolution.
They intentionally do not create a second equivalence classifier in the host
layer: SAME/DISTINCT/AMBIGUOUS comes entirely from pb_physical_wall_identity.
"""
from __future__ import annotations

from dataclasses import fields

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
    path_fingerprint: tuple[tuple[float, float], ...] | None = None,
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
        path_fingerprint=path_fingerprint or (start, end),
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
    same_groups: tuple[tuple[str, ...], ...] = (),
    representatives: tuple[str, ...] | None = None,
    ambiguous_ids: tuple[str, ...] = (),
) -> PhysicalWallEquivalenceResolution:
    ids = tuple(record.wall_candidate_id for record in records)
    reps = representatives if representatives is not None else ids
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(reps),
        abstained_wall_ids=tuple(ambiguous_ids),
        equivalence_groups=tuple(tuple(sorted(group)) for group in same_groups),
        ambiguous_wall_ids=tuple(sorted(ambiguous_ids)),
        same_wall_ids=tuple(sorted({member for group in same_groups for member in group})),
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


def _resolve(
    records: tuple[PhysicalWallCandidateRecord, ...],
    equivalence: PhysicalWallEquivalenceResolution,
):
    return host._resolve_host_bands(records, OPENING, equivalence)


def test_control_genuine_unique_host_resolves_before_contradiction() -> None:
    records = _base_records()
    result = _resolve(records, _equivalence(records))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    assert result.bands[0].member_ids == tuple(sorted(record.wall_candidate_id for record in records))


def test_record_names_candidate_identity_without_claiming_physical_identity() -> None:
    names = {field.name for field in fields(host.OpeningHostBindingRecord)}
    assert "member_candidate_identity_ids" in names
    assert "member_equivalence_groups" in names
    assert "member_physical_identity_ids" not in names


def test_same_path_different_provenance_ambiguous_blocks_host() -> None:
    """A. Geometry equality is not physical sameness proof."""
    base = _base_records()
    duplicate = _record(
        "left-top-foreign-provenance",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:independent-duplicate",
        path_fingerprint=base[0].physical_identity.path_fingerprint,
    )
    records = base + (duplicate,)
    equivalence = _equivalence(
        records,
        pairs=((
            "left-top",
            "left-top-foreign-provenance",
            PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        ),),
        representatives=("right-top", "left-bottom", "right-bottom"),
        ambiguous_ids=("left-top", "left-top-foreign-provenance"),
    )
    result = _resolve(records, equivalence)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes


def test_duplicate_reversed_representation_collapses_only_with_positive_same_proof() -> None:
    """B. Reversal/duplication is harmless only after upstream SAME proof."""
    base = _base_records()
    original = base[0]
    reversed_duplicate = _record(
        "left-top-reversed",
        (0.0, -5.0),
        (-100.0, -5.0),
        source_id=original.physical_identity.source_primitive_ids[0],
        path_fingerprint=original.physical_identity.path_fingerprint,
    )
    records = base + (reversed_duplicate,)
    same_group = tuple(sorted(("left-top", "left-top-reversed")))
    equivalence = _equivalence(
        records,
        pairs=((
            "left-top",
            "left-top-reversed",
            PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
        ),),
        same_groups=(same_group,),
        representatives=("left-top", "right-top", "left-bottom", "right-bottom"),
    )
    result = _resolve(records, equivalence)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    band = result.bands[0]
    assert "left-top-reversed" not in band.member_ids
    assert same_group in band.member_equivalence_groups
    assert band.member_ids == tuple(sorted(record.wall_candidate_id for record in base))


def test_split_representation_is_not_arbitrarily_collapsed() -> None:
    """C. Overlapping/split candidate pieces need upstream equivalence proof."""
    base = _base_records()
    split = _record(
        "left-top-split",
        (-55.0, -5.0),
        (0.0, -5.0),
        source_id="source:split-piece",
    )
    records = base + (split,)
    equivalence = _equivalence(
        records,
        pairs=((
            "left-top",
            "left-top-split",
            PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
        ),),
        representatives=("right-top", "left-bottom", "right-bottom"),
        ambiguous_ids=("left-top", "left-top-split"),
    )
    result = _resolve(records, equivalence)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()


def test_contradiction_monotonicity_ambiguous_extra_representation_cannot_strengthen_host() -> None:
    """D. Adding ambiguous relevant evidence turns a valid host into blocked."""
    base = _base_records()
    before = _resolve(base, _equivalence(base))
    assert before.status is EvidenceResolutionStatus.CORROBORATED
    assert len(before.bands) == 1

    extra = _record(
        "left-top-ambiguous-extra",
        (-100.0, -5.0),
        (0.0, -5.0),
        source_id="source:new-contradiction",
        path_fingerprint=base[0].physical_identity.path_fingerprint,
    )
    records = base + (extra,)
    after = _resolve(
        records,
        _equivalence(
            records,
            pairs=((
                "left-top",
                "left-top-ambiguous-extra",
                PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE,
            ),),
            representatives=("right-top", "left-bottom", "right-bottom"),
            ambiguous_ids=("left-top", "left-top-ambiguous-extra"),
        ),
    )
    assert after.status is EvidenceResolutionStatus.CONFLICT
    assert after.bands == ()
