"""FT2 PWD exposed floor must stop at INTERNAL finished wall faces.

Synthetic source issuer receipts; original PDF-positive checks stay separate.
This prevents counting wall footprint as tile or subtracting 92mm twice.
"""
from tools.diag_gpt2_original_figured_face_rivals_shadow import (
    audit_original_ft2_internal_wall_face_basis as internal,
)

ROOT="a"*64


def _figure_marks(finish="FT2"):
    return (
        {"original_literal_untrusted":"PWD","original_word_address":[15,0,0]},
        {"original_literal_untrusted":finish,"original_word_address":[14,1,0]},
    )


def _dimension(mm, pair):
    return {
        "source_original_dimension_mm":mm,
        "original_arrowhead_tips_pdf_pts":list(pair),
    }


def _source():
    walls={
        "status":"original_figured_face_source_rivals_only",
        "original_source_sha256":ROOT,
        "original_detail_page_1_based":26,
        "original_room_and_finish_mark_candidates":_figure_marks(),
        "original_source_figured_area_m2_candidate_not_signed":7.854,
        "original_source_candidate_face_families":(
            {
                "source_native_family_id_untrusted":"figure-bound-linework",
                "original_source_native_bbox_pdf_pts":
                    [217.44,1774.64,466.8,2179.52],
            },
            {
                "source_native_family_id_untrusted":"other-inward-source-ink",
                "original_source_native_bbox_pdf_pts":
                    [219.6,1777.04,464.64,2177.36],
            },
        ),
    }
    chain={
        "status":"source_orthogonal_native_figured_chains_candidate_only",
        "original_source_sha256":ROOT,
        "original_detail_page_1_based":26,
        "native_printed_dimension_chains":{
            "horizontal":{
                "original_source_records":{
                    "short_before":_dimension(92,(206.88,217.44)),
                    "main":_dimension(2200,(217.44,466.80)),
                    "short_after":_dimension(92,(466.80,477.36)),
                },
            },
            "vertical":{
                "original_source_records":{
                    "short_before":_dimension(92,(1764.32,1774.64)),
                    "main":_dimension(3570,(1774.64,2179.52)),
                    "short_after":_dimension(92,(2179.52,2189.84)),
                },
            },
        },
    }
    return walls,chain


def test_92_wall_figures_outside_central_pwd_span_not_tiled_and_not_subtracted():
    walls,chain=_source()
    result=internal(walls,chain)
    assert result["status"]=="original_ft2_clear_internal_wall_face_area_candidate"
    assert result["measurement_surface"]=="exposed_ft2_floor_within_internal_finished_wall_faces"
    assert not result["include_area_under_walls"]
    assert not result["deduct_the_92mm_walls_from_clear_room_figures"]
    assert not result["add_the_92mm_walls_to_clear_room_figures"]
    assert result["source_original_figured_internal_length_mm"]==3570
    assert result["source_original_figured_internal_width_mm"]==2200
    assert result["source_wall_notes_outside_clear_dimensions_mm"]==(92,92,92,92)
    assert result["source_ft2_clear_room_rectangle_area_m2_candidate_not_signed"]==7.854
    assert result["source_original_figure_bound_face_family"]=="figure-bound-linework"
    assert len(result["source_all_face_family_candidates"])==2
    assert result["d13_threshold_treatment_requires_source_boundary_proof"]
    assert result["source_finished_wall_face_role_authenticated"] is False
    assert result["source_FT2_floor_finish_m2_signed"] is None
    assert result["new_firm_quantities"]==0


def test_an_arbitrary_more_inward_cad_stroke_is_not_the_finished_face_by_nearness():
    walls,chain=_source()
    result=internal(walls,chain)
    assert result["do_not_elect_further_inset_stroke_as_finished_face_by_proximity"]
    assert result["source_original_figure_bound_face_family"]!="other-inward-source-ink"


def test_wrong_material_mark_or_missing_original_both_axis_figures_abstains():
    walls,chain=_source()
    walls["original_room_and_finish_mark_candidates"]=_figure_marks("FT3")
    assert internal(walls,chain)["status"]=="original_ft2_internal_wall_face_basis_unresolved"
    walls,chain=_source()
    chain["native_printed_dimension_chains"]["vertical"]["original_source_records"]["main"]["original_arrowhead_tips_pdf_pts"]=[1774.64,2178.]
    assert internal(walls,chain)["status"]=="original_ft2_internal_wall_face_basis_unresolved"
    assert internal(None,chain)["new_firm_quantities"]==0


def test_competing_figured_face_boundaries_do_not_auto_elect_which_w4_wall():
    walls,chain=_source()
    duplicate={
        "source_native_family_id_untrusted":"competing-matching-figure",
        "original_source_native_bbox_pdf_pts":[217.44,1774.64,466.8,2179.52],
    }
    walls["original_source_candidate_face_families"]+= (duplicate,)
    output=internal(walls,chain)
    assert output["status"]=="original_ft2_internal_wall_face_basis_unresolved"
    assert output["first_failure"]=="clear_inside_figure_face_missing_or_competing"
    assert output["source_FT2_floor_finish_m2_signed"] is None
