from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
)


OPENING = host._OpeningGeometry(
    origin=(100.0, 55.0),
    axis=(1.0, 0.0),
    normal=(0.0, 1.0),
    length=40.0,
    thickness=10.0,
)


def _record(
    wall_id: str,
    *,
    offset: float = 0.0,
    start: float = 20.0,
    end: float = 220.0,
):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            is_curved=False,
            centerline_pts=(
                (start, 55.0 + offset),
                (end, 55.0 + offset),
            ),
        ),
        physical_identity=SimpleNamespace(
            candidate_identity_id=f"candidate:{wall_id}",
        ),
    )


def _equivalence(
    records,
    *,
    pair_classifications=(),
    groups=(),
    ambiguous=(),
):
    ids = tuple(record.wall_candidate_id for record in records)
    grouped_ids = {member for group in groups for member in group}
    representatives = tuple(
        wall_id for wall_id in ids
        if wall_id not in grouped_ids
    ) + tuple(
        sorted(group)[0] for group in groups
    )
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(dict.fromkeys(representatives)),
        abstained_wall_ids=(),
        equivalence_groups=tuple(tuple(sorted(group)) for group in groups),
        ambiguous_wall_ids=tuple(sorted(ambiguous)),
        same_wall_ids=tuple(
            sorted({member for group in groups for member in group})
        ),
        pair_classifications=tuple(pair_classifications),
        blocking_reasons_by_wall_id={},
    )


def test_one_centered_whole_wall_spanning_raster_aperture_resolves_host() -> None:
    records = (_record("wall:host"),)
    result = host._resolve_raster_whole_wall_host(
        records,
        OPENING,
        _equivalence(records),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (host.RASTER_WHOLE_WALL_HOST_RESOLVED,)
    assert len(result.bands) == 1
    assert result.bands[0].member_ids == ("wall:host",)
    assert result.bands[0].center_offset == pytest.approx(0.0)


def test_cross_render_pixel_equality_is_allowed_but_not_general_proximity() -> None:
    inside = host._RASTER_WHOLE_WALL_CENTER_TOL_PT - 0.01
    outside = host._RASTER_WHOLE_WALL_CENTER_TOL_PT + 0.01

    inside_records = (_record("wall:inside", offset=inside),)
    inside_result = host._resolve_raster_whole_wall_host(
        inside_records,
        OPENING,
        _equivalence(inside_records),
    )
    assert len(inside_result.bands) == 1

    outside_records = (_record("wall:outside", offset=outside),)
    outside_result = host._resolve_raster_whole_wall_host(
        outside_records,
        OPENING,
        _equivalence(outside_records),
    )
    assert outside_result.status is EvidenceResolutionStatus.CORROBORATED
    assert outside_result.bands == ()


def test_wall_must_extend_beyond_both_opening_edges() -> None:
    left_stops = (_record("wall:left-stops", start=100.0, end=220.0),)
    right_stops = (_record("wall:right-stops", start=20.0, end=140.0),)

    assert host._resolve_raster_whole_wall_host(
        left_stops,
        OPENING,
        _equivalence(left_stops),
    ).bands == ()
    assert host._resolve_raster_whole_wall_host(
        right_stops,
        OPENING,
        _equivalence(right_stops),
    ).bands == ()


def test_two_distinct_centered_whole_walls_conflict_instead_of_ranking() -> None:
    records = (
        _record("wall:a", offset=-0.2),
        _record("wall:b", offset=0.2),
    )
    pair = (
        "wall:a",
        "wall:b",
        PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
    )
    result = host._resolve_raster_whole_wall_host(
        records,
        OPENING,
        _equivalence(records, pair_classifications=(pair,)),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert result.reason_codes == (host.MULTIPLE_RASTER_WHOLE_WALL_HOSTS,)


def test_ambiguous_centered_whole_wall_equivalence_fails_closed() -> None:
    records = (
        _record("wall:a", offset=-0.2),
        _record("wall:b", offset=0.2),
    )
    pair = (
        "wall:a",
        "wall:b",
        PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value,
    )
    result = host._resolve_raster_whole_wall_host(
        records,
        OPENING,
        _equivalence(
            records,
            pair_classifications=(pair,),
            ambiguous=("wall:a", "wall:b"),
        ),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes


def test_proven_same_duplicate_whole_wall_representations_collapse() -> None:
    records = (
        _record("wall:a", offset=-0.1),
        _record("wall:b", offset=0.1),
    )
    pair = (
        "wall:a",
        "wall:b",
        PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value,
    )
    result = host._resolve_raster_whole_wall_host(
        records,
        OPENING,
        _equivalence(
            records,
            pair_classifications=(pair,),
            groups=(("wall:a", "wall:b"),),
        ),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    assert result.bands[0].member_equivalence_groups == (
        ("wall:a", "wall:b"),
    )
