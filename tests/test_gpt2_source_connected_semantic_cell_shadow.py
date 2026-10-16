"""Native rectangle-cell edge proof without table, viewport or metric promotion."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_source_connected_semantic_cell_shadow import (
    _source_contact_axis,
    _family_connected_cell_witness,
    audit_source_rect_cell_lattice as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _grid(page, *, gap_x, gap_y, width=20, height=15, cols=3, rows=3):
    for y in range(rows):
        for x in range(cols):
            px=30+x*(width+gap_x)
            py=30+y*(height+gap_y)
            page.draw_rect(fitz.Rect(px,py,px+width,py+height),
                           color=(0,0,0),width=.48)


def test_true_shared_source_table_cells_are_candidate_not_authority():
    doc=fitz.open()
    page=doc.new_page(width=250,height=250)
    _grid(page,gap_x=0,gap_y=0)
    result=audit(page,candidate_frame_bbox=(0,0,250,250))
    assert result["connected_cell_lattice_candidate_only"]
    assert result["first_remaining_table_gate"] == (
        "connected_native_cells_still_need_semantic_table_owner"
    )
    assert not result["positive_table_cell_authority"]
    assert not result["physical_ceiling_or_material_authority"]
    assert not result["view_separation_authority"]
    assert result["new_quantity_evidence"] == 0
    doc.close()


def test_separate_lamps_on_perfect_repeated_centres_are_not_cells():
    doc=fitz.open()
    page=doc.new_page(width=250,height=250)
    _grid(page,gap_x=25,gap_y=25,cols=4,rows=4)
    result=audit(page,candidate_frame_bbox=(0,0,250,250))
    assert not result["connected_cell_lattice_candidate_only"]
    assert result["first_remaining_table_gate"] == (
        "no_shared_source_cell_edges_in_both_axes"
    )
    assert len(result["repeated_source_rectangle_families"]) >= 1
    assert not result["positive_table_cell_authority"]
    doc.close()


def test_corner_touch_and_overlap_cannot_splice_table_cell_network():
    left=(0,0,10,10)
    corner=(10,10,20,20)
    overlapping=(5,5,15,15)
    xadj=(10,0,20,10)
    yadj=(0,10,10,20)
    assert _source_contact_axis(left, corner) is None
    assert _source_contact_axis(left, overlapping) is None
    assert _source_contact_axis(left, xadj) == "native_x_shared_edge"
    assert _source_contact_axis(left, yadj) == "native_y_shared_edge"
    assert _source_contact_axis(xadj, left) == "native_x_shared_edge"
    assert _source_contact_axis(yadj, left) == "native_y_shared_edge"


def test_translation_scale_order_invariance_of_positive_contact():
    cells=[(x*20,y*15,x*20+20,y*15+15)
           for x in range(3) for y in range(3)]
    def confirmed(rows):
        return any(
            c["two_axis_source_connected_cell_lattice_candidate"]
            for c in _family_connected_cell_witness(rows,min_source_cell_count=8)
        )
    assert confirmed(cells)
    assert confirmed(list(reversed(cells)))
    assert confirmed([tuple(x*2+100 for x in box) for box in cells])
    assert confirmed([tuple(x*.5-70 for x in box) for box in cells])


def test_scope_cap_and_invalid_shapes_fail_closed():
    doc=fitz.open()
    p=doc.new_page()
    _grid(p,gap_x=0,gap_y=0)
    with pytest.raises(ValueError):
        audit(p,candidate_frame_bbox=(0,0,0,30))
    with pytest.raises(ValueError):
        audit(p,candidate_frame_bbox=(0,0,250,250),max_source_rectangles=0)
    assert audit(p,candidate_frame_bbox=(0,0,250,250),
                 max_source_rectangles=1)["status"] == "source_rectangle_scope_cap_exceeded"
    doc.close()


def test_original_a120_false_table_rectangles_do_not_form_shared_cell_lattice():
    original=ORIGINAL.read_bytes()
    assert hashlib.sha256(original).hexdigest()==SHA
    with fitz.open(stream=original,filetype="pdf") as document:
        page=document[8]
        # This is the admitted semantic schedule "frame" in source CI #2863.
        # This replay tests rectangle topology, not an alternative viewport.
        frame=(279.8399963378906,471.2000732421875,
               1217.0399169921875,1376.719970703125)
        result=audit(page,candidate_frame_bbox=frame)
        assert result["status"] == "read_only_original_rectangle_cell_contact_inventory"
        assert result["source_candidate_scope_complete"]
        assert result["repeated_source_rectangle_families"]
        assert not result["connected_cell_lattice_candidate_only"]
        assert result["first_remaining_table_gate"] == (
            "no_shared_source_cell_edges_in_both_axes"
        )
        assert not result["positive_table_cell_authority"]
        assert not result["view_separation_authority"]
        assert not result["physical_ceiling_or_material_authority"]
        assert result["new_quantity_evidence"] == 0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA
