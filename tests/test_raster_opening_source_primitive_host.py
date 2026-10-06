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
    source_ids: tuple[str, ...],
):
    # Deliberately bent assembled W4 geometry. The new fallback must not use
    # this polyline as host geometry; it may use only exact authenticated source
    # primitives carried by the physical identity.
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            is_curved=False,
            centerline_pts=(
                (20.0, 54.0),
                (95.0, 55.0),
                (220.0, 56.0),
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


def test_bent_w4_candidate_can_bind_only_from_its_exact_centered_source_primitive() -> None:
    record = _record("wall:host", source_ids=("raster:center", "raster:turn"))
    result = host._resolve_raster_source_primitive_host_from_lines(
        (record,),
        OPENING,
        _equivalence((record,)),
        {
            "raster:center": (20.0, 55.2, 220.0, 55.2),
            "raster:turn": (20.0, 48.0, 80.0, 49.0),
        },
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (host.RASTER_SOURCE_PRIMITIVE_HOST_RESOLVED,)
    assert len(result.bands) == 1
    assert result.bands[0].member_ids == ("wall:host",)
    assert result.bands[0].center_offset == pytest.approx(0.2)


def test_matching_source_line_not_carried_by_w4_identity_cannot_bind() -> None:
    record = _record("wall:host", source_ids=("raster:other",))
    result = host._resolve_raster_source_primitive_host_from_lines(
        (record,),
        OPENING,
        _equivalence((record,)),
        {"raster:center": (20.0, 55.0, 220.0, 55.0)},
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.bands == ()


def test_source_primitive_must_span_both_aperture_edges() -> None:
    record = _record("wall:host", source_ids=("raster:center",))
    result = host._resolve_raster_source_primitive_host_from_lines(
        (record,),
        OPENING,
        _equivalence((record,)),
        {"raster:center": (105.0, 55.0, 135.0, 55.0)},
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.bands == ()


def test_source_primitive_outside_cross_render_center_budget_cannot_bind() -> None:
    record = _record("wall:host", source_ids=("raster:center",))
    outside = host._RASTER_WHOLE_WALL_CENTER_TOL_PT + 0.01
    result = host._resolve_raster_source_primitive_host_from_lines(
        (record,),
        OPENING,
        _equivalence((record,)),
        {"raster:center": (20.0, 55.0 + outside, 220.0, 55.0 + outside)},
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.bands == ()


def test_two_distinct_source_primitive_hosts_conflict_instead_of_ranking() -> None:
    records = (
        _record("wall:a", source_ids=("raster:a",)),
        _record("wall:b", source_ids=("raster:b",)),
    )
    pair = (
        "wall:a",
        "wall:b",
        PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value,
    )
    result = host._resolve_raster_source_primitive_host_from_lines(
        records,
        OPENING,
        _equivalence(records, pair_classifications=(pair,)),
        {
            "raster:a": (20.0, 54.8, 220.0, 54.8),
            "raster:b": (20.0, 55.2, 220.0, 55.2),
        },
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.bands == ()
    assert result.reason_codes == (host.MULTIPLE_RASTER_SOURCE_PRIMITIVE_HOSTS,)


def test_proven_same_source_primitive_representations_collapse() -> None:
    records = (
        _record("wall:a", source_ids=("raster:a",)),
        _record("wall:b", source_ids=("raster:b",)),
    )
    pair = (
        "wall:a",
        "wall:b",
        PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value,
    )
    result = host._resolve_raster_source_primitive_host_from_lines(
        records,
        OPENING,
        _equivalence(
            records,
            pair_classifications=(pair,),
            groups=(("wall:a", "wall:b"),),
        ),
        {
            "raster:a": (20.0, 54.9, 220.0, 54.9),
            "raster:b": (20.0, 55.1, 220.0, 55.1),
        },
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.bands) == 1
    assert result.bands[0].member_equivalence_groups == (("wall:a", "wall:b"),)
