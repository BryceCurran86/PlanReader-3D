"""Source dimension-anchored affine metric sections: never a guessed plan scale."""
import math
from dataclasses import replace
from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide, measure_figured_room_edge_chain_shadow
)
from pb_gpt1_figured_metric_plane_shadow import (
    OriginalInternalSourceSection,
    resolve_source_figured_metric_plane_shadow,
    measure_source_internal_sections_on_metric_plane_shadow,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status


def _parent():
    source=((0,0),(10,0),(10,5),(0,5))
    sides=tuple(FiguredPhysicalSide(
        f"side-{i}",source[i],source[(i+1)%4],(f"ink-{i}",),
        {0:5000,1:2000}.get(i),
        f"figure-{i}" if i in (0,1) else None,
        (f"witness-{i}-a",f"witness-{i}-b") if i in (0,1) else (),
    ) for i in range(4))
    result=measure_figured_room_edge_chain_shadow(
        sides,source_sha256="a"*64,revision_id="rev",page_id="7",
        physical_room_id="one-physical-room"
    )
    assert result.status is Status.CANDIDATE
    return result


def _section(name,ring):
    return OriginalInternalSourceSection(
        name,(f"{name}-segment-1",f"{name}-segment-2"),
        ring,(f"original-{name}-mark",),
    )


def test_independent_two_axis_figures_support_internal_halfroom_sections():
    parent=_parent()
    plane=resolve_source_figured_metric_plane_shadow(parent)
    assert plane.status is Status.CANDIDATE
    left=_section("food-service",((0,0),(5,0),(5,5),(0,5)))
    right=_section("pos",((5,0),(10,0),(10,5),(5,5)))
    result=measure_source_internal_sections_on_metric_plane_shadow(
        parent,plane,(left,right))
    assert result.status is Status.CANDIDATE
    assert result.measured_section_areas_m2 == (("food-service",5.0),("pos",5.0))
    assert result.remaining_unallocated_room_area_m2 == 0


def test_partially_measured_original_open_plan_does_not_assign_remaining_area():
    parent=_parent()
    plane=resolve_source_figured_metric_plane_shadow(parent)
    left=_section("food-service",((0,0),(4,0),(4,5),(0,5)))
    result=measure_source_internal_sections_on_metric_plane_shadow(
        parent,plane,(left,))
    assert result.status is Status.CANDIDATE
    assert math.isclose(result.measured_section_areas_m2[0][1],4.)
    assert math.isclose(result.remaining_unallocated_room_area_m2,6.)


def test_competing_mismatched_source_metric_polygon_vertices_abstain():
    parent=_parent()
    vertices=list(parent.metric_vertices_mm)
    vertices[3]=(vertices[3][0]+250,vertices[3][1])
    invalid=replace(parent,metric_vertices_mm=tuple(vertices))
    assert resolve_source_figured_metric_plane_shadow(invalid).status is Status.ABSTAINED


def test_external_or_overlapping_sections_remain_unpublished():
    parent=_parent()
    plane=resolve_source_figured_metric_plane_shadow(parent)
    inner=_section("first",((1,1),(7,1),(7,4),(1,4)))
    overlap=_section("second",((6,2),(9,2),(9,5),(6,5)))
    outer=_section("outside",((8,1),(12,1),(12,3),(8,3)))
    for arr in ((inner,overlap),(outer,)):
        out=measure_source_internal_sections_on_metric_plane_shadow(parent,plane,arr)
        assert out.status is Status.ABSTAINED
        assert out.measured_section_areas_m2 == ()


def test_foreign_earlier_producer_scope_cannot_launder_sections():
    parent=_parent()
    plane=resolve_source_figured_metric_plane_shadow(parent)
    old=replace(parent,revision_id="other-revision")
    out=measure_source_internal_sections_on_metric_plane_shadow(
        old,plane,(_section("section",((1,1),(2,1),(2,2),(1,2))),))
    assert out.status is Status.ABSTAINED


def test_neither_source_parent_nor_derived_internal_metric_is_firm():
    parent=_parent()
    plane=resolve_source_figured_metric_plane_shadow(parent)
    result=measure_source_internal_sections_on_metric_plane_shadow(
        parent,plane,(_section("candidate",((1,1),(2,1),(2,2),(1,2))),))
    assert result.diagnostic_only is True
    assert result.status is Status.CANDIDATE
    assert not hasattr(result,"quantity_id")
