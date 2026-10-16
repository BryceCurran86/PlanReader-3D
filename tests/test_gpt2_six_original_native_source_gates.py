"""Six independent original-source authority blockers, not six guessed areas."""
import hashlib
from pathlib import Path

import fitz
import pytest
from tools.diag_gpt2_six_source_scope_firstgates import (
    audit_floor_finish_mark_scope_candidates,
    audit_ceiling_material_mark_scope_candidates,
    audit_coincident_native_stroke_ancestry,
    audit_shell_versus_room_face_source_conflict,
    audit_shared_figured_dimension_scope,
    audit_cross_sheet_label_identity_candidates,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.fixture(scope="module")
def source_pdf():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as document:
        yield document
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_1_original_ft3_five_plan_marks_plus_one_schedule(source_pdf):
    result=audit_floor_finish_mark_scope_candidates(
        source_pdf[10],source_finish_code="FT3",
        candidate_scopes={
            "unverified_inplan":(251.,471.,1195.,1946.),
            "unverified_schedule":(1370.,2180.,1410.,2230.),
        },
    )
    assert result["count_of_original_raw_words_not_quantity"]==6
    a=result["original_source_mark_candidates"]
    assert sum("unverified_inplan" in r["source_candidate_scopes_containing_word_center"]
               for r in a)==5
    assert sum("unverified_schedule" in r["source_candidate_scopes_containing_word_center"]
               for r in a)==1
    assert not any(r["source_physical_occurrence_owner_proven"] for r in a)
    assert result["authenticated_floor_finish_area_m2"]==0


def test_2_original_a120_grid_ipf1_cld3_schedule_vs_plan_candidates(source_pdf):
    result=audit_ceiling_material_mark_scope_candidates(
        source_pdf[8],source_material_literals=("GRID","IPF1","CLD3"),
        candidate_scopes={
            "claimed_main_ceiling_plan_candidate":(0.,450.,1300.,1946.),
            "source_true_schedule_grid_candidate":(1393.68,416.,1496.4,991.04),
        },
    )
    literal=[r["source_literal_untrusted"] for r
             in result["source_untrusted_ceiling_code_candidates"]]
    assert literal.count("GRID")==3
    assert literal.count("IPF1")==12
    assert literal.count("CLD3")==4
    assert any(
        "source_true_schedule_grid_candidate" in r["source_candidate_scopes_containing_word_center"]
        for r in result["source_untrusted_ceiling_code_candidates"]
    )
    assert result["authentic_ceiling_zone_material_assignments"]==0
    assert result["authentic_ceiling_area_m2"]==0


def test_3_original_food_pos_three_native_paths_one_geometrical_divider(source_pdf):
    result=audit_coincident_native_stroke_ancestry(
        source_pdf[6],original_source_ids=("d86147i0","d86146i0","d84218i0"),
    )
    assert len(result["all_source_line_parents"])==3
    assert len(result["original_coincident_geometry_groups"])==1
    assert set(result["original_coincident_geometry_groups"][0]["original_source_ids"]) == {
        "d86147i0","d86146i0","d84218i0"
    }
    assert not result["source_paths_are_distinct_walls_proven"]
    assert result["wall_count_published"]==0


def test_4_original_freezer_inside_wall_not_external_shell(source_pdf):
    result=audit_shell_versus_room_face_source_conflict(
        source_pdf[6],shell_stroke_id="d86124i0",
        interior_stroke_ids=("d69322i0","d69324i0"),
        old_corner_native_xy=(596.880005,1288.961827),
    )
    distances={r["competing_original_interior_candidate_id"]:
               r["native_parallel_axis_displacement_pdf_pts"]
               for r in result["candidate_parallel_source_displacements"]}
    assert abs(distances["d69324i0"]-8.64)<.001
    assert abs(distances["d69322i0"]-228.24)<.001
    assert not result["physical_closed_room_ring_granted"]
    assert result["new_room_area_m2"]==0


def test_5_original_a501_figured_5044_spans_multiple_named_sections(source_pdf):
    result=audit_shared_figured_dimension_scope(
        source_pdf[24],figured_literal="5044",
        room_name_literals=("LAUNDRY","AIRLOCK"),
        candidate_local_plan_scope=(400.,1600.,600.,2150.),
    )
    assert len(result["original_raw_figure_word_candidates"])==1
    assert len(result["original_competing_room_words"]["LAUNDRY"])==1
    assert len(result["original_competing_room_words"]["AIRLOCK"])==1
    assert not result["one_room_only_dimension_owner_authenticated"]
    assert not result["source_witness_endpoints_to_finished_faces_proven"]
    assert result["new_room_areas"]==0


def test_6_pwd_same_label_p7_p26_is_not_physical_crosssheet_room_join(source_pdf):
    result=audit_cross_sheet_label_identity_candidates(
        (source_pdf[6],source_pdf[25]),room_literal="PWD",
        source_candidate_scopes=((300.,1300.,600.,1700.),
                                 (200.,1400.,650.,2150.)),
    )
    assert result["same_label_word_in_all_scopes"]
    assert all(r["original_same_label_word_candidates"]
               for r in result["independent_original_page_receipts"])
    assert not result["unique_corresponding_physical_room_identity_granted"]
    assert not result["cross_sheet_floor_or_ceiling_quantity_granted"]


def test_all_six_source_gates_refuse_misleading_or_malformed_claims():
    doc=fitz.open()
    doc.new_page(width=500,height=500)
    doc.new_page(width=500,height=500)
    # PyMuPDF invalidates older Page handles when new pages are inserted.
    a=doc[0]
    b=doc[1]
    a.insert_text((40,40),"PWD",fontsize=12)
    b.insert_text((40,40),"PWD",fontsize=12)
    r=audit_cross_sheet_label_identity_candidates(
        (a,b),room_literal="PWD",
        source_candidate_scopes=((0,0,400,400),(0,0,400,400)))
    assert r["same_label_word_in_all_scopes"]
    assert not r["unique_corresponding_physical_room_identity_granted"]

    a.draw_line((20,20),(20,100))
    a.draw_line((20,100),(20,20))
    r=audit_coincident_native_stroke_ancestry(
        a,original_source_ids=("d0i0","d1i0"))
    assert len(r["original_coincident_geometry_groups"])==1
    with pytest.raises(ValueError):
        audit_coincident_native_stroke_ancestry(
            a,original_source_ids=("d0i0","d0i0"))
    with pytest.raises(ValueError):
        audit_shell_versus_room_face_source_conflict(
            a,shell_stroke_id="broken",interior_stroke_ids=("d0i0",))
    with pytest.raises(ValueError):
        audit_shared_figured_dimension_scope(
            a,figured_literal="5000",room_name_literals=("A","A"),
            candidate_local_plan_scope=(0,0,400,400))
    with pytest.raises(ValueError):
        audit_floor_finish_mark_scope_candidates(
            a,source_finish_code="FT3",candidate_scopes={"bad":(0,0,0,9)})
    doc.close()
