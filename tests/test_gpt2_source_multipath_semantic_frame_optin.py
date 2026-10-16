"""Original true line-built schedule recovers while ceiling remains unresolved."""
import hashlib
from pathlib import Path

import fitz
import pytest
import pb_viewport_segmentation as v

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _by_id(views):
    return {r.view_id:r for r in views}


def test_original_a120_correct_line_built_schedule_with_both_optins():
    data=ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    with fitz.open(stream=data,filetype="pdf") as doc:
        page=doc[8]
        original=v.segment_page_viewports(page,page_number=9)
        default=v.segment_page_viewports(
            page,page_number=9,
            source_connected_table_cell_shadow=False,
            source_native_multipath_semantic_frame_shadow=False,
        )
        assert original==default
        assert _by_id(default)["view_p9_4"].status=="resolved"
        assert _by_id(default)["view_p9_5"].status=="derived"

        source=v.segment_page_viewports(
            page,page_number=9,
            source_connected_table_cell_shadow=True,
            source_native_multipath_semantic_frame_shadow=True,
        )
        schedule=_by_id(source)["view_p9_4"]
        assert schedule.status=="resolved"
        assert all(abs(x-y)<.01 for x,y in zip(
            schedule.bounding_box,(1393.68,416.,1496.4,991.04)
        ))
        assert _by_id(source)["view_p9_5"].status!="resolved"
        assert _by_id(source)["view_p9_5"].status!="derived"
        assert not _by_id(source)["view_p9_5"].bounding_box
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_no_semantic_caption_means_no_source_grid_frame_claim():
    document=fitz.open()
    page=document.new_page(width=400,height=400)
    for x in [50,90,130,170]:
        page.draw_line((x,40),(x,200))
    for y in [40,80,120,160,200]:
        page.draw_line((50,y),(170,y))
    assert v._native_multipath_semantic_frame_candidates_shadow(page,[])==[]
    original=v.segment_page_viewports(page,page_number=1)
    shadow=v.segment_page_viewports(
        page,page_number=1,
        source_native_multipath_semantic_frame_shadow=True,
        source_connected_table_cell_shadow=True,
    )
    assert original==shadow==[]
    document.close()


def test_multiple_competing_semantic_titles_do_not_elect_frame():
    document=fitz.open()
    page=document.new_page(width=400,height=400)
    for x in [50,90,130,170]:
        page.draw_line((x,40),(x,200))
    for y in [40,80,120,160,200]:
        page.draw_line((50,y),(170,y))
    anchors=[
        v._TitleAnchor("CEILING FINISHES SCHEDULE",(60.,55.,110.,75.),
                       v.DrawingViewType.SCHEDULE.value),
        v._TitleAnchor("LEGEND",(60.,95.,115.,115.),
                       v.DrawingViewType.LEGEND.value),
    ]
    assert v._native_multipath_semantic_frame_candidates_shadow(page,anchors)==[]
    document.close()


def test_flags_are_exact_bool_not_numeric_truthiness():
    doc=fitz.open()
    p=doc.new_page()
    with pytest.raises(ValueError,match="explicit_bool"):
        v.segment_page_viewports(p,page_number=1,
            source_native_multipath_semantic_frame_shadow=1)
    with pytest.raises(ValueError,match="explicit_bool"):
        v.segment_page_viewports(p,page_number=1,
            source_connected_table_cell_shadow="true")
    doc.close()
