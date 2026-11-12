"""Source-attested Section A-A section-cut to region candidates; no quantities."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json

import pytest

from planreader_next.engine import NativePage, NativeWord, NativeSegment, SourceConflict, load_native_page
from planreader_next.section_scope import source_section_cut, section_cut_region_height_candidates


def _word(ref, text, x, y, w=10, h=9):
    return NativeWord(ref, text, (x, y, x+w, y+h))


def _fixtures():
    sha="e"*64
    plan_words=(
        _word("word:b0:l0:w0:i0","A",95,20),
        _word("word:b0:l1:w0:i1","A0.7",93,30,w=14),
        _word("word:b1:l0:w0:i2","A",95,400),
        _word("word:b1:l1:w0:i3","A0.7",93,410,w=14),
    )
    segments=tuple(
        NativeSegment(f"cut-dash-{i}","line",100,45+i*18,100,55+i*18)
        for i in range(20)
    )
    plan=NativePage(sha,2,plan_words,(),segments)
    section=NativePage(sha,6,(
        _word("word:b2:l0:w0:i4","Section",210,250,w=35),
        _word("word:b2:l0:w1:i5","A-A",248,250,w=18),
        _word("height","2700",101,121,w=7,h=18),
        _word("ffl","FFL",89,202),
        _word("fcl","FCL",105,48),
    ),(),(NativeSegment("height-chain","line",105,54,105,208),))
    regions=[
        {"region_id":"bed","status":"candidate","room_label_words":[
            {"text":"BED","ref":"bed-word"}],
         "boundary_polygon_pdf_pts":[[75,120],[130,120],[130,235],[75,235]]},
        {"region_id":"robe","status":"candidate","room_label_words":[
            {"text":"ROBE","ref":"robe-word"}],
         "boundary_polygon_pdf_pts":[[80,290],[110,290],[110,350],[80,350]]},
        {"region_id":"outside","status":"candidate","room_label_words":[
            {"text":"GARAGE","ref":"garage-word"}],
         "boundary_polygon_pdf_pts":[[200,120],[260,120],[260,235],[200,235]]},
    ]
    return plan,section,regions


def test_source_cut_has_exact_two_plan_markers_and_native_dashed_segments():
    plan,section,_=_fixtures()
    found=source_section_cut(plan,section)
    assert found["plan_marker_word_refs"] == [
        "word:b0:l0:w0:i0","word:b0:l1:w0:i1",
        "word:b1:l0:w0:i2","word:b1:l1:w0:i3"]
    assert len(found["plan_dashed_source_segment_refs"])==20
    assert found["section_reference"]=="A-A"
    assert found["source_cut_line_authenticated"] is True
    assert found["applies_to_all_rooms"] is False
    assert not found["commercial_publishable"]


def test_cut_height_intersects_only_source_regions_it_physically_crosses():
    plan,section,regions=_fixtures()
    result=section_cut_region_height_candidates(plan,section,regions)
    found={x["region_id"]:x for x in result["cut_intersecting_region_candidates"]}
    assert set(found)=={"bed","robe"}
    assert all(x["height_mm_source_candidate"]=="2700" for x in found.values())
    assert all(x["height_applied_to_room"] is False for x in found.values())
    assert all(x["room_identity_authenticated"] is False for x in found.values())
    assert result["height_applied_to_any_room"] is False
    assert result["commercial_publishable"] is False
    assert result["official_score"] is None


def test_absent_source_dashes_cannot_be_replaced_by_fabricated_marker_line():
    plan,section,_=_fixtures()
    plan=replace(plan,segments=plan.segments[:3])
    with pytest.raises(SourceConflict,match="section_cut_source_dashes_incomplete"):
        source_section_cut(plan,section)


def test_section_marker_and_title_must_match_the_same_source_document():
    plan,section,_=_fixtures()
    with pytest.raises(SourceConflict,match="section_cut_cross_page_source_mismatch"):
        source_section_cut(plan,replace(section,source_sha256="f"*64))
    with pytest.raises(SourceConflict,match="section_title_source_not_authenticated"):
        source_section_cut(plan,replace(section,words=section.words[2:]))
    with pytest.raises(SourceConflict,match="section_cut_markers_not_unique"):
        source_section_cut(replace(plan,words=plan.words[:2]),section)


def test_broken_dashed_chain_abstains_instead_of_inventing_section():
    plan,section,_=_fixtures()
    broken=plan.segments[:7]+plan.segments[13:]
    with pytest.raises(SourceConflict,match="section_cut_dashes_disconnected"):
        source_section_cut(replace(plan,segments=broken),section)


def test_polygon_duplicate_or_invalid_region_rejected_without_quantity():
    plan,section,regions=_fixtures()
    with pytest.raises(SourceConflict,match="section_region_identity_duplicate"):
        section_cut_region_height_candidates(plan,section,regions+[regions[0]])
    with pytest.raises(SourceConflict,match="section_region_boundary_invalid"):
        section_cut_region_height_candidates(plan,section,[
            dict(regions[0],boundary_polygon_pdf_pts=[[0,0],[10,10],[0,10],[10,0]])
        ])


def test_actual_3laurel_section_cut_and_candidate_intersections_if_original_provisioned():
    import os
    original=os.environ.get("PLANREADER_3LAUREL_ORIGINAL_PDF")
    if not original or not Path(original).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    plan=load_native_page(Path(original),2)
    section=load_native_page(Path(original),6)
    assert plan.source_sha256 == "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
    found=source_section_cut(plan,section)
    assert len(found["plan_dashed_source_segment_refs"])==20
    assert found["plan_marker_word_refs"] == [
        "word:b138:l0:w0:i719","word:b138:l1:w0:i720",
        "word:b139:l0:w0:i721","word:b139:l1:w0:i722",
    ]
    from planreader_next.enclosure import propose_room_enclosures
    regions=propose_room_enclosures(plan,Path(original))["regions"]
    outcome=section_cut_region_height_candidates(plan,section,regions)
    assert outcome["height_mm_source_candidate"]=="2700"
    assert len(outcome["cut_intersecting_region_candidates"])==3
    assert sorted(x["room_label_words"] for x in outcome["cut_intersecting_region_candidates"] if len(x["room_label_words"])==1)==[["BED"],["ROBE"]]
    assert not outcome["height_applied_to_any_room"]
    assert not outcome["commercial_publishable"]
