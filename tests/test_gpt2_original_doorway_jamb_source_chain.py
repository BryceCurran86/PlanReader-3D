"""Original A110 D15 source jamb witness vs nonstructural drafting rivals."""
import hashlib
from pathlib import Path
import fitz
import pytest
from pb_source_doorway_jamb_authority import audit_native_source_doorway_jamb_chain as audit

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_original_office_d15_exact_jamb_chain_not_physical_room_or_door_count():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        r=audit(doc[6],left_wall_id="d52622i0",right_wall_id="d52625i0",
                left_jamb_id="d69419i0",right_jamb_id="d69421i0")
        assert r["status"]=="exact_original_native_jamb_endpoint_chain_candidate"
        assert r["native_ink_contact_proved"]
        assert r["source_native_unbridged_wall_gap_pdf_pts"]==[177.12,233.76]
        assert r["source_native_jamb_crosswall_interval_pdf_pts"]==[1376.72,1383.2]
        assert abs(r["source_native_jamb_separation_pdf_pt"]-56.64)<.001
        assert not r["original_structural_host_authenticated"]
        assert not r["source_door_schedule_size_binding_granted"]
        assert not r["source_physical_floor_ring_closed"]
        assert r["new_quantities"]==r["new_physical_opening_count"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def _fixture(*,right_jamb_x=150.,gray=False,right_wall_start=150.,
             right_wall_width=.48,right_jamb_width=.96, left_wall_opacity=1.,
             right_wall_opacity=1., left_jamb_opacity=1.,right_jamb_opacity=1.,
             right_jamb_dashes=None):
    doc=fitz.open()
    page=doc.new_page(width=400,height=300)
    page.draw_line((20,100),(50,100),color=(0,0,0),width=.48,stroke_opacity=left_wall_opacity)
    page.draw_line((right_wall_start,100),(280,100),color=(0,0,0),width=right_wall_width,stroke_opacity=right_wall_opacity)
    page.draw_line((50,92),(50,100),color=(.5,.5,.5) if gray else (0,0,0),width=.96,stroke_opacity=left_jamb_opacity)
    page.draw_line((right_jamb_x,92),(right_jamb_x,100),color=(0,0,0),width=right_jamb_width,stroke_opacity=right_jamb_opacity,dashes=right_jamb_dashes)
    return doc,page


def test_synthetic_jamb_source_positive_and_no_guessed_door_dimensions():
    doc,p=_fixture()
    r=audit(p,left_wall_id="d0i0",right_wall_id="d1i0",
        left_jamb_id="d2i0",right_jamb_id="d3i0")
    assert r["native_ink_contact_proved"]
    assert r["source_native_jamb_separation_pdf_pt"]==100.
    assert not r["source_door_schedule_size_binding_granted"]
    doc.close()


@pytest.mark.parametrize("kwargs,reason",[
    ({"right_jamb_x":151.},"native_jamb_not_exact_wall_terminator"),
    ({"right_wall_start":149.},"native_jamb_not_exact_wall_terminator"),
    ({"gray":True},"competing_nonstructural_paint_ink"),
    ({"right_wall_width":.24},"competing_source_stroke_role_mismatch"),
    ({"right_jamb_width":.48},"competing_source_stroke_role_mismatch"),
])
def test_competing_source_strokes_do_not_become_doorway(kwargs,reason):
    doc,p=_fixture(**kwargs)
    r=audit(p,left_wall_id="d0i0",right_wall_id="d1i0",
            left_jamb_id="d2i0",right_jamb_id="d3i0")
    assert r["status"]==reason
    assert r["new_quantities"]==0
    doc.close()


def test_repeat_wall_as_jamb_and_loose_tolerance_fail_closed():
    doc,p=_fixture()
    with pytest.raises(ValueError,match="independent_original_wall_and_jamb_paths_required"):
        audit(p,left_wall_id="d0i0",right_wall_id="d1i0",
            left_jamb_id="d0i0",right_jamb_id="d3i0")
    with pytest.raises(ValueError,match="strict_native_float_equality_scope_required"):
        audit(p,left_wall_id="d0i0",right_wall_id="d1i0",
            left_jamb_id="d2i0",right_jamb_id="d3i0",
            exact_native_tolerance_pt=2.5)
    doc.close()


def test_original_pwd_d13_independent_native_jamb_source_chain():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        r=audit(doc[6],left_wall_id="d52626i0",right_wall_id="d52631i0",
                left_jamb_id="d69501i0",right_jamb_id="d69499i0")
        assert r["status"]=="exact_original_native_jamb_endpoint_chain_candidate"
        assert r["native_ink_contact_proved"]
        assert r["source_native_unbridged_wall_gap_pdf_pts"]==[386.64,443.28]
        assert abs(r["source_native_jamb_separation_pdf_pt"]-56.64)<.001
        assert r["source_native_jamb_crosswall_interval_pdf_pts"]==[1376.72,1383.2]
        assert r["source_door_schedule_size_binding_granted"] is False
        assert r["source_physical_floor_ring_closed"] is False
        assert r["new_quantities"]==0

@pytest.mark.parametrize("kwargs,reason", [
    ({"left_wall_opacity":0.}, "invisible_or_invalid_original_stroke_opacity"),
    ({"right_jamb_opacity":0.}, "invisible_or_invalid_original_stroke_opacity"),
    ({"right_wall_opacity":.5}, "competing_original_stroke_opacity_roles"),
    ({"right_jamb_opacity":.5}, "competing_original_stroke_opacity_roles"),
])
def test_source_black_but_invisible_or_unequally_painted_doorways_abstain(kwargs, reason):
    doc, page = _fixture(**kwargs)
    evidence = audit(page, left_wall_id="d0i0", right_wall_id="d1i0",
                     left_jamb_id="d2i0", right_jamb_id="d3i0")
    assert evidence["status"] == reason
    assert evidence["new_quantities"] == 0
    assert not evidence["native_ink_contact_proved"]
    doc.close()

def test_dashed_dimensional_ink_cannot_counterfeit_original_source_doorway():
    doc, page = _fixture(right_jamb_dashes="[2 2] 0")
    evidence = audit(page, left_wall_id="d0i0", right_wall_id="d1i0",
                     left_jamb_id="d2i0", right_jamb_id="d3i0")
    assert evidence["status"] == "competing_dashed_drafting_line"
    assert not evidence["native_ink_contact_proved"]
    assert evidence["new_quantities"] == 0
    doc.close()

def test_vertical_native_wall_and_horizontal_jambs_preserve_exact_source_contact():
    # Reflection in the diagonal is a metamorhic 90-degree wall-axis test:
    # source intervals change axes, but no physical wall is guessed.
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_line((100,20),(100,50),color=(0,0,0),width=.48)
    page.draw_line((100,150),(100,280),color=(0,0,0),width=.48)
    page.draw_line((92,50),(100,50),color=(0,0,0),width=.96)
    page.draw_line((92,150),(100,150),color=(0,0,0),width=.96)
    result = audit(page, left_wall_id="d0i0", right_wall_id="d1i0",
                   left_jamb_id="d2i0", right_jamb_id="d3i0")
    assert result["status"] == "exact_original_native_jamb_endpoint_chain_candidate"
    assert result["source_native_wall_run_axis"] == "native_y"
    assert result["source_native_unbridged_wall_gap_pdf_pts"] == [50., 150.]
    assert result["source_native_jamb_separation_pdf_pt"] == 100.
    assert not result["source_door_schedule_size_binding_granted"]
    assert result["new_quantities"] == 0
    doc.close()


def test_jamb_return_on_opposite_side_is_still_exact_but_not_extra_authority():
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_line((20,100),(50,100),color=(0,0,0),width=.48)
    page.draw_line((150,100),(280,100),color=(0,0,0),width=.48)
    page.draw_line((50,100),(50,108),color=(0,0,0),width=.96)
    page.draw_line((150,100),(150,108),color=(0,0,0),width=.96)
    result = audit(page, left_wall_id="d0i0",right_wall_id="d1i0",
                   left_jamb_id="d2i0",right_jamb_id="d3i0")
    assert result["native_ink_contact_proved"]
    assert result["source_native_jamb_crosswall_interval_pdf_pts"] == [100.,108.]
    assert result["new_quantities"] == 0
    doc.close()
