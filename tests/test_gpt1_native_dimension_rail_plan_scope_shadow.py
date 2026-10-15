"""Source-native long dimension rails are NOT plan viewport or scale grants."""
from __future__ import annotations

import hashlib

import fitz
import pytest

from pb_native_dimension_rail_plan_scope_shadow import (
    original_dimension_rail_plan_candidate,
)


def _pdf(*, gray=False, competing=False, width_conflict=False,
         missing_vertical=False, title=True):
    doc=fitz.open()
    page=doc.new_page(width=500,height=400)
    color=(.6,.6,.6) if gray else (0,0,0)
    lines=[
        ((100,40),(400,40)),
        ((100,60),(350,60)),
        ((90,350),(400,350)),
        ((45,100),(45,290)),
        ((460,100),(460,290)),
    ]
    if missing_vertical:
        lines=lines[:3]
    if competing:
        lines.append(((110,40),(390,40)))
    for idx,(a,b) in enumerate(lines):
        page.draw_line(a,b,color=color,width=(.48 if width_conflict and idx==4 else .24))
    if title:
        page.insert_text((410,375),"FLOOR PLAN",fontsize=9)
    data=doc.tobytes()
    doc.close()
    return data


def _result(data):
    return original_dimension_rail_plan_candidate(
        data,source_sha256=hashlib.sha256(data).hexdigest(),page_index=0,
    )


def test_source_long_rails_can_report_original_path_receipts_but_never_publish():
    data=_pdf()
    r=_result(data)
    frame=r["source_native_rail_region_candidate"]
    assert frame is not None
    assert frame["bbox_pdf_pts"]==[45.,40.,460.,350.]
    assert len({tuple(x) for x in frame["original_source_path_item_addresses"]})==4
    assert len(r["original_horizontal_rail_candidates"])==3
    assert len(r["original_vertical_rail_candidates"])==2
    assert len(r["original_exact_floor_plan_title_lines"])==1
    assert r["first_unclosed_gate"]=="source_rail_region_not_plan_viewport_or_room_authority"
    assert frame["source_native_closed_frame_proven"] is False
    assert frame["viewport_production_allowed"] is False
    assert r["source_plan_role_authenticated"] is False
    assert r["source_viewport_authenticated"] is False
    assert r["physical_wall_component_authenticated"] is False
    assert r["source_room_floor_owner_authenticated"] is False
    assert r["physical_scale_authenticated"] is False
    assert r["metric_area_published"] is False
    assert r["sealed_customer_quantity_ids"]==[]
    assert r["benchmark_match_or_score_granted"] is False


@pytest.mark.parametrize("mutation",[
    {"missing_vertical":True},{"gray":True},
    {"competing":True},{"width_conflict":True},
])
def test_incomplete_conflicting_or_foreign_stroke_rails_abstain(mutation):
    r=_result(_pdf(**mutation))
    assert r["source_native_rail_region_candidate"] is None
    assert not r["source_plan_role_authenticated"]
    assert r["sealed_customer_quantity_ids"]==[]


def test_title_text_cannot_mint_original_plan_role_without_actual_scope():
    r=_result(_pdf(title=False))
    assert not r["source_viewport_authenticated"]
    assert not r["physical_scale_authenticated"]
    assert r["source_native_rail_region_candidate"] is not None
    assert r["original_exact_floor_plan_title_lines"] == []


def test_original_source_sha_and_page_are_mandatory():
    data=_pdf()
    with pytest.raises(ValueError,match="SHA"):
        original_dimension_rail_plan_candidate(data,source_sha256="0"*64,page_index=0)
    with pytest.raises(ValueError,match="page_index"):
        original_dimension_rail_plan_candidate(data,source_sha256=hashlib.sha256(data).hexdigest(),page_index=1)
    with pytest.raises(TypeError):
        original_dimension_rail_plan_candidate(bytearray(data),source_sha256=hashlib.sha256(data).hexdigest(),page_index=0)
