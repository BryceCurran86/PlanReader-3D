from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateScopeResult,
    WithheldStructuralSegmentEvidence,
)
from pb_source_wall_topology_authority import _derive_scope_records


def _record(wall_id: str, first, second):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(centerline_pts=(first, second)),
    )


def _two_room_records(*, left_x: float = 50.0):
    # Mirror the wall-assembly producer contract: junctions split the outer
    # run at T-intersections, so each top/bottom segment has exact endpoints
    # at the divider rather than leaving the divider to cross a monolithic edge.
    return (
        _record("top-left", (left_x, 50.0), (150.0, 50.0)),
        _record("top-right", (150.0, 50.0), (250.0, 50.0)),
        _record("right", (250.0, 50.0), (250.0, 250.0)),
        _record("bottom-right", (250.0, 250.0), (150.0, 250.0)),
        _record("bottom-left", (150.0, 250.0), (left_x, 250.0)),
        _record("left", (left_x, 250.0), (left_x, 50.0)),
        _record("divider", (150.0, 50.0), (150.0, 250.0)),
    )


def _equivalence(records, *, group=()):
    ids = tuple(record.wall_candidate_id for record in records)
    grouped = set(group)
    reps = tuple(
        wall_id for wall_id in ids
        if wall_id not in grouped or wall_id == min(grouped)
    )
    return SimpleNamespace(
        representative_wall_ids=reps,
        abstained_wall_ids=(),
        ambiguous_wall_ids=(),
        same_wall_ids=tuple(sorted(grouped)),
        equivalence_groups=(tuple(sorted(group)),) if group else (),
    )


def _scope(
    records,
    *,
    withheld,
    viewport_bbox=(0.0, 0.0, 500.0, 500.0),
    equivalence=None,
):
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=False,
        records=tuple(records),
        source_observation_ids=(),
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        decision_scope_id="wall-source:viewport:1:test",
        reason_codes=(
            PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
            PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
        ),
        equivalence=equivalence or _equivalence(records),
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        scope_kind="viewport",
        viewport_id="view-1",
        viewport_bbox=viewport_bbox,
        viewport_view_type="floor_plan",
        viewport_status="derived",
        viewport_boundary_source="title_partition",
        scope_boundary_observation_ids=tuple(
            evidence.observation_id for evidence in withheld
        ),
        withheld_structural_segments=tuple(withheld),
    )


def _withheld(obs: str, geometry):
    return WithheldStructuralSegmentEvidence(
        observation_id=obs,
        raw_id=f"raw-{obs}",
        geometry=tuple(float(value) for value in geometry),
        layer="Structural - Bearing",
        reason_code=PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY,
    )


def test_unrelated_cropped_geometry_does_not_poison_closed_local_component() -> None:
    records = _two_room_records()
    scope = _scope(
        records,
        withheld=(_withheld("far", (400.0, 0.0, 400.0, 500.0)),),
    )
    result = _derive_scope_records(scope)

    assert len(result) == 7
    divider = next(
        evidence
        for key, evidence in result.items()
        if key[-1] == "divider"
    )
    assert divider.is_ambiguous is False
    assert divider.enclosed_space_count == 2
    assert divider.bounds_exterior is False

    one_sided = [
        evidence
        for evidence in result.values()
        if evidence.enclosed_space_count == 1 and not evidence.is_ambiguous
    ]
    assert one_sided
    assert all(evidence.bounds_exterior for evidence in one_sided)


def test_withheld_structural_primitive_crossing_component_forces_abstention() -> None:
    records = _two_room_records()
    scope = _scope(
        records,
        withheld=(_withheld("cross", (0.0, 100.0, 500.0, 100.0)),),
    )
    assert _derive_scope_records(scope) == {}


def test_component_touching_viewport_boundary_remains_incomplete() -> None:
    records = _two_room_records(left_x=0.0)
    scope = _scope(
        records,
        withheld=(_withheld("far", (400.0, 0.0, 400.0, 500.0)),),
    )
    assert _derive_scope_records(scope) == {}


def test_positive_same_group_uses_one_physical_wall_representative() -> None:
    base = list(_two_room_records())
    duplicate = _record("top-left-duplicate", (50.0, 50.0), (150.0, 50.0))
    records = tuple(base + [duplicate])
    equivalence = _equivalence(
        records,
        group=("top-left", "top-left-duplicate"),
    )
    scope = _scope(
        records,
        withheld=(_withheld("far", (400.0, 0.0, 400.0, 500.0)),),
        equivalence=equivalence,
    )

    result = _derive_scope_records(scope)
    assert len(result) == 7
    wall_ids = {key[-1] for key in result}
    assert "top-left" in wall_ids
    assert "top-left-duplicate" not in wall_ids


def test_incomplete_viewport_without_withheld_geometry_provenance_stays_closed() -> None:
    records = _two_room_records()
    scope = _scope(records, withheld=())
    assert _derive_scope_records(scope) == {}
