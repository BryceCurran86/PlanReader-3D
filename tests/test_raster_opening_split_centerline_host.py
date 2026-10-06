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
    start: float,
    end: float,
    offset: float = 0.0,
    source_ids: tuple[str, ...] = ("raster:shared",),
):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            is_curved=False,
            centerline_pts=(
                (start, 55.0 + offset),
                (end, 55.0 + offset),
            ),
            reason_codes=(),
        ),
        physical_identity=SimpleNamespace(
            usable=True,
            candidate_identity_id=f"candidate:{wall_id}",
            source_primitive_ids=source_ids,
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
        wall_id for wall_id in ids if wall_id not in grouped_ids
    ) + tuple(sorted(group)[0] for group in groups)
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


def test_shared_source_centerline_fragments_resolve_one_raster_host() -> None:
    left = _record(
        "wall:left",
        start=20.0,
        end=99.7,
        offset=-0.10,
    )
    right = _record(
        "wall:right",
        start=140.2,
        end=220.0,
        offset=-0.20,
    )
    records = (left, right)

    result = host._resolve_raster_split_centerline_host(
        records,
        OPENING,
        _equivalence(records),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (host.RASTER_SPLIT_CENTERLINE_HOST_RESOLVED,)
    assert len(result.bands) == 1
    assert result.bands[0].member_ids == ("wall:left", "wall:right")
    assert result.bands[0].center_offset == pytest.approx(-0.15)


def test_geometrically_matching_fragments_without_shared_source_do_not_bind() -> None:
    records = (
        _record(
            "wall:left",
            start=20.0,
            end=100.0,
            source_ids=("raster:left",),
        ),
        _record(
            "wall:right",
            start=140.0,
            end=220.0,
            source_ids=("raster:right",),
        ),
    )
    result = host._resolve_raster_split_centerline_host(
        records,
        OPENING,
        _equivalence(records),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.bands == ()


def test_fragment_outside_cross_render_equality_budget_does_not_bind() -> None:
    outside = host._RASTER_WHOLE_WALL_CENTER_TOL_PT + 0.01
    records = (
        _record(
            "wall:left",
            start=20.0,
            end=100.0,
            offset=outside,
        ),
        _record(
            "wall:right",
            start=140.0,
            end=220.0,
            offset=outside,
        ),
    )
    result = host._resolve_raster_split_centerline_host(
        records,
        OPENING,
        _equivalence(records),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.bands == ()


def test_fragment_must_terminate_at_the_proven_aperture_edge() -> None:
    records = (
        _record("wall:left", start=20.0, end=97.0),
        _record("wall:right", start=143.0, end=220.0),
    )
    result = host._resolve_raster_split_centerline_host(
        records,
        OPENING,
        _equivalence(records),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.bands == ()


def test_two_distinct_shared_source_fragment_pairs_conflict() -> None:
    records = (
        _record(
            "wall:left:a",
            start=20.0,
            end=100.0,
            offset=-0.2,
            source_ids=("raster:a",),
        ),
        _record(
            "wall:right:a",
            start=140.0,
            end=220.0,
            offset=-0.2,
            source_ids=("raster:a",),
        ),
        _record(
            "wall:left:b",
            start=20.0,
            end=100.0,
            offset=0.3,
            source_ids=("raster:b",),
        ),
        _record(
            "wall:right:b",
            start=140.0,
            end=220.0,
            offset=0.3,
            source_ids=("raster:b",),
        ),
    )
    pairs = (
        (
            "wall:left:a",
            "wall:left:b",
            PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
        ),
        (
            "wall:right:a",
            "wall:right:b",
            PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
        ),
    )
    result = host._resolve_raster_split_centerline_host(
        records,
        OPENING,
        _equivalence(records, pair_classifications=pairs),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert result.reason_codes == (
        host.MULTIPLE_RASTER_SPLIT_CENTERLINE_HOSTS,
    )


def test_ambiguous_role_equivalence_blocks_split_centerline_host() -> None:
    records = (
        _record(
            "wall:left:a",
            start=20.0,
            end=100.0,
            offset=-0.1,
        ),
        _record(
            "wall:left:b",
            start=20.0,
            end=100.0,
            offset=0.1,
        ),
        _record(
            "wall:right",
            start=140.0,
            end=220.0,
        ),
    )
    pair = (
        "wall:left:a",
        "wall:left:b",
        PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value,
    )
    result = host._resolve_raster_split_centerline_host(
        records,
        OPENING,
        _equivalence(
            records,
            pair_classifications=(pair,),
            ambiguous=("wall:left:a", "wall:left:b"),
        ),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert host.HOST_EQUIVALENCE_AMBIGUOUS in result.reason_codes
