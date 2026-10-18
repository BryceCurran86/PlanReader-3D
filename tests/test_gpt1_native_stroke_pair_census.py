"""Native source wall ink census preserves one-to-many and unmatched paths."""
import fitz
import pytest

from tools.gpt1_native_stroke_pair_census import native_stroke_correspondence_census


def _original_two_pages(tmp_path):
    pdf=fitz.open()
    room=pdf.new_page(width=900,height=700)
    room.draw_line((100,100),(100,300),color=(0,0,0),width=.48)
    room.draw_line((100,300),(300,300),color=(0,0,0),width=.48)
    room.draw_line((300,300),(300,100),color=(0,0,0),width=.48)
    room.draw_line((300,100),(100,100),color=(0,0,0),width=.48)
    room.draw_line((500,100),(500,300),color=(.5,.5,.5),width=.24)
    finish=pdf.new_page(width=900,height=700)
    # Source-specific shift; never try to infer it from a nearby label.
    finish.draw_line((178,100),(178,300),color=(0,0,0),width=.48)
    finish.draw_line((178,100),(178,300),color=(0,0,0),width=.48)
    finish.draw_line((178,300),(378,300),color=(0,0,0),width=.48)
    finish.draw_line((378,300),(378,100),color=(0,0,0),width=.48)
    # The last room edge is genuinely missing from finish sheet.
    finish.draw_line((600,100),(600,300),color=(0,0,0),width=.48)
    file=tmp_path/"original_private_example.pdf"
    pdf.save(file)
    pdf.close()
    return file


def _census(pdf,**kwargs):
    params=dict(
        original_pdf_path=pdf,
        room_page_number=1,finish_page_number=2,
        room_window_pdf_pt=(50,50,550,400),
        finish_window_pdf_pt=(128,50,700,400),
        candidate_dx_pt=78,candidate_dy_pt=0,
    )
    params.update(kwargs)
    return native_stroke_correspondence_census(**params)


def test_black_native_source_strokes_keep_unique_duplicate_and_missing_cases(tmp_path):
    out=_census(_original_two_pages(tmp_path))
    assert out["diagnostic_only"] is True
    assert out["commercial_quantity_authority"] is False
    assert out["physical_wall_semantic_authority"]=="UNPROVEN"
    assert out["counts"]=={
        "UNIQUE_CANDIDATE":2,
        "COMPETING_SOURCE_STROKES":1,
        "NO_MATCH":1,
    }
    assert out["room_native_stroke_count"]==4
    assert out["finish_native_stroke_count"]==5
    assert out["unmatched_finish_source_path_ids"]


def test_real_source_rival_strokes_are_not_first_match_selected(tmp_path):
    out=_census(_original_two_pages(tmp_path))
    contender=[r for r in out["room_original_source_strokes"]
               if r["match_status"]=="COMPETING_SOURCE_STROKES"]
    assert len(contender)==1
    assert len(contender[0]["finish_source_path_matches"])==2
    assert len(set(contender[0]["finish_source_path_matches"]))==2


def test_wrong_source_sheet_translation_never_retypes_wall_scope(tmp_path):
    original=_original_two_pages(tmp_path)
    wrong=_census(original,candidate_dx_pt=78.8)
    assert wrong["counts"]["UNIQUE_CANDIDATE"]==0
    assert wrong["counts"]["COMPETING_SOURCE_STROKES"]==0
    assert wrong["counts"]["NO_MATCH"]==4
    assert wrong["physical_wall_semantic_authority"]=="UNPROVEN"


def test_unrelated_grid_line_does_not_become_structural_black_ink(tmp_path):
    out=_census(_original_two_pages(tmp_path))
    assert out["room_native_stroke_count"]==4
    assert all(s["native_source_color"]==(0.0,0.0,0.0)
               for s in out["room_original_source_strokes"])


@pytest.mark.parametrize("override",[
    {"room_page_number":True},
    {"finish_page_number":1},
    {"candidate_dx_pt":float("nan")},
    {"endpoint_tolerance_pt":.2},
    {"room_window_pdf_pt":(1,2,2,1)},
    {"room_window_pdf_pt":(1,2,"3",4)},
])
def test_untrusted_native_source_requests_are_rejected(tmp_path,override):
    with pytest.raises(ValueError):
        _census(_original_two_pages(tmp_path),**override)
