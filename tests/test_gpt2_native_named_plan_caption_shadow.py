"""Native local-plan inset caption source only: no viewport promotion."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

from pb_source_native_named_plan_caption_shadow import (
    find_native_named_plan_caption_candidates_shadow as census,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _page(*lines):
    pdf=fitz.open()
    page=pdf.new_page(width=700,height=700)
    for index,line in enumerate(lines):
        page.insert_text((40,60+40*index),line,fontsize=11)
    return pdf,page


def test_native_exact_room_plan_caption_is_observed_without_viewport_role():
    pdf,page=_page("PROP. PWD PLAN")
    try:
        result=census(page,page_number=9)
        assert len(result)==1
        assert result[0]["native_named_plan_subject"]=="PWD"
        assert result[0]["native_caption_text"]=="PROP. PWD PLAN"
        assert result[0]["source_local_plan_caption_candidate_only"]
        assert not result[0]["new_physical_plan_viewport_granted"]
        assert not result[0]["new_room_identity_or_metric_granted"]
        assert result[0]["original_native_word_source_receipts"]
    finally:
        pdf.close()


@pytest.mark.parametrize("text",[
    "PWD", "PWD PLAN", "SITE PLAN", "REFER TO PROP. PWD PLAN",
    "PROP. PWD PLAN (TYPICAL)", "PROP. PWD PLAN - DETAIL",
    "PROP. PWD PLAN 1:25", "DRAWING TITLE PROP. PWD PLAN",
    "PROP. FLOOR FINISHES PLAN REF A140", "PROP. PLAN", "SCHEDULE",
])
def test_ambiguous_title_or_note_substring_does_not_mint_local_caption(text):
    pdf,page=_page(text)
    try:
        assert census(page,page_number=9)==[]
    finally:
        pdf.close()


def test_competing_named_insets_remain_independent_and_stable():
    pdf,page=_page("PROP. LAUNDRY PLAN","PROP. PWD PLAN",
                   "PROP. AMBULANT TOILETS PLAN")
    try:
        a=census(page,page_number=26)
        b=census(page,page_number=26)
        assert a==b and len(a)==3
        assert {item["native_named_plan_subject"] for item in a} == {
            "LAUNDRY","PWD","AMBULANT TOILETS"
        }
        assert all(not item["new_physical_plan_viewport_granted"] for item in a)
    finally:
        pdf.close()


def test_real_original_carries_all_four_named_amendities_source_local_plans():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SOURCE_SHA
    expected={
        24:("AMENITIES","PROP. AMENITIES PLAN"),
        25:("LAUNDRY","PROP. LAUNDRY PLAN"),
        26:("PWD","PROP. PWD PLAN"),
        27:("AMBULANT TOILETS","PROP. AMBULANT TOILETS PLAN"),
    }
    with fitz.open(stream=raw,filetype="pdf") as doc:
        assert len(doc)==31
        for page_number,(subject,literal) in expected.items():
            result=census(doc[page_number-1],page_number=page_number)
            selected=[r for r in result if r["native_named_plan_subject"]==subject]
            assert len(selected)==1
            assert selected[0]["native_caption_text"]==literal
            assert selected[0]["original_native_word_source_receipts"]
            assert all(not x["new_physical_plan_viewport_granted"] for x in result)
            assert all(not x["new_room_identity_or_metric_granted"] for x in result)
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SOURCE_SHA


def test_native_caption_must_be_finite_and_source_line_complete():
    source=SimpleNamespace(get_text=lambda kind: (
        {"blocks":[{"type":0,"lines":[{
            "bbox":(0,float("nan"),100,15),
            "dir":(1,0),"spans":[{"text":"PROP. PWD PLAN"}]
        }]}]} if kind=="dict"
        else [(0,0,10,10,"PROP.",0,0,0),
              (11,0,20,10,"PWD",0,0,1),
              (21,0,40,10,"PLAN",0,0,2)]
    ))
    assert census(source,page_number=1)==[]
