"""Source-neutral MAX review regressions: unknown cells and dense edge buckets."""
from itertools import permutations

import pytest

import pb_viewport_segmentation as v
import test_f07_text_cell_plan_frame_shadow as fixture


@pytest.mark.parametrize('note_at', ((65.,285.), (480.,285.), (65.,52.)))
def test_note_outside_cells_cannot_turn_unknown_grid_text_into_blank_tiles(note_at):
    box = (60.,40.,500.,300.)
    for note in (False, True):
        doc,page = fixture._new_page()
        fixture._frame(page,box)
        fixture._contiguous_grid(page,80.,60.,10,8,40.,25.,labelled=False)
        if note:
            page.insert_text(note_at,'NOTE',fontsize=6)
        doc=fixture._reopen(doc)
        page=doc[0]
        cal=fixture._calibration(page)
        assert v._frame_looks_like_table(box,page,cal,allow_line_grid_only=False)
        assert v._frame_looks_like_source_connected_text_cell_table(
            box,page,cal,v._text_fragments(page),allow_line_grid_only=False)
        doc.close()


def test_dense_edge_buckets_abstain_on_work_exhaustion_and_do_not_mutate(monkeypatch):
    # Distinct overlapping source rectangles still create quadratic bucket
    # fanout below the rectangle cap. No giant allocation is needed to prove it.
    rects = tuple((0.,float(i)/100.,10.,20.+float(i)/100.) for i in range(20))
    rects += tuple((10.,float(i)/100.,20.,20.+float(i)/100.) for i in range(20))
    before=tuple(rects)
    monkeypatch.setattr(v,'_TABLE_EDGE_MESH_MAX_PAIR_CHECKS',100)
    assert v._source_edge_connected_rects(rects) is None
    assert v._source_edge_connected_rects(tuple(reversed(rects))) is None
    assert rects == before


def test_unknown_mesh_budget_never_lifts_table_veto_even_with_sparse_text(monkeypatch):
    doc=fixture._tile_plan()
    page=doc[0]
    cal=fixture._calibration(page)
    monkeypatch.setattr(v,'_TABLE_EDGE_MESH_MAX_PAIR_CHECKS',1)
    assert v._frame_source_edge_mesh(fixture.FRAME,page) is None
    assert v._frame_looks_like_source_connected_text_cell_table(
        fixture.FRAME,page,cal,v._text_fragments(page),allow_line_grid_only=False)
    assert fixture._vector_resolved(fixture._segment(doc,**{fixture.FLAG:True})) == []
    doc.close()


def test_mesh_budget_is_evaluated_once_for_all_qualified_families(monkeypatch):
    doc=fixture._lattice_plan()
    count=0
    def unavailable(frame,page):
        nonlocal count
        count+=1
        return None
    monkeypatch.setattr(v,'_frame_source_edge_mesh',unavailable)
    page=doc[0]
    assert v._frame_looks_like_source_connected_text_cell_table(
        fixture.FRAME,page,fixture._calibration(page),v._text_fragments(page),
        allow_line_grid_only=False)
    assert count == 1
    doc.close()


def test_all_near_nested_container_relations_survive_permutations():
    a=(0.,0.,1000.,1000.)
    b=(-5.,-5.,1005.,1005.)
    band=(10.,900.,990.,1010.)
    for items in permutations((a,b,band)):
        kept,relations=v._collapse_near_nested_band_frames(items)
        assert set(kept) == {a,b}
        assert relations == sorted(((band,a),(band,b)))
