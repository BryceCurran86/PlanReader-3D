"""Genuine diagonal figure-bound polygon metric candidates, not page scale."""
from dataclasses import replace
import math
import pytest

from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide
from pb_gpt1_general_figured_polygon_shadow import measure_general_figured_polygon_shadow
from pb_migration_contracts import EvidenceResolutionStatus as Status


def _shape(values=(4000,5000,3000)):
    ring=((0,0),(4,0),(0,3))
    return tuple(FiguredPhysicalSide(
        f"side-{i}",ring[i],ring[(i+1)%3],(f"ink-{i}",),
        value,(f"dim-{i}" if value is not None else None),
        ((f"witness-{i}-a",f"witness-{i}-b") if value is not None else ()),
    ) for i,value in enumerate(values))


def run(sides):
    return measure_general_figured_polygon_shadow(
        sides,source_sha256="a"*64,revision_id="r1",page_id="7",
        physical_room_id="room-1",
    )


def test_documented_diagonal_room_without_pdf_scale_yields_real_metric_area():
    got=run(_shape())
    assert got.status is Status.CANDIDATE
    assert math.isclose(got.candidate_area_m2,6.0,rel_tol=1e-12)
    assert got.source_side_ids==("side-0","side-1","side-2")
    assert len(got.source_vertices_pdf_pts)==3
    assert got.diagnostic_only is True


@pytest.mark.parametrize("known",[(4000,5000,None),(4000,None,3000),(None,5000,3000)])
def test_one_missing_dimension_closes_only_with_sourced_original_direction(known):
    result=run(_shape(known))
    assert result.status is Status.CANDIDATE
    assert math.isclose(result.candidate_area_m2,6.0,rel_tol=1e-12)


def test_two_unknown_nonparallel_lengths_are_unique_from_true_source_closure():
    result=run(_shape((4000,None,None)))
    assert result.status is Status.CANDIDATE
    assert math.isclose(result.candidate_area_m2,6.0,rel_tol=1e-12)
    assert result.closure_inferred_side_ids==("side-1","side-2")


def test_no_original_figures_is_underconstrained_not_a_pdf_scale():
    result=run(_shape((None,None,None)))
    assert result.status is Status.ABSTAINED
    assert result.candidate_area_m2 is None
    assert result.reason_codes==("source_general_polygon_underconstrained",)


def test_incompatible_figure_on_diagonal_does_not_warp_source_polygon():
    result=run(_shape((4000,5200,3000)))
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("source_general_polygon_figures_conflict",)


def test_competing_same_dimension_source_id_cannot_fund_two_distinct_sides():
    pieces=list(_shape())
    pieces[1]=replace(pieces[1],figured_dimension_id="dim-0")
    assert run(tuple(pieces)).status is Status.ABSTAINED


def test_original_ink_source_edge_chain_must_be_closed():
    pieces=list(_shape())
    pieces[1]=replace(pieces[1],end_pdf_pt=(1,3))
    assert run(tuple(pieces)).status is Status.ABSTAINED


def test_diagonal_measured_polygon_is_not_a_firm_quantity():
    result=run(_shape())
    assert result.diagnostic_only
    assert result.status is Status.CANDIDATE
    assert not hasattr(result,"quantity_id")
