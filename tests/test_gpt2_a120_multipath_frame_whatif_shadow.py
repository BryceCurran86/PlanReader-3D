"""Test exact source what-if without publishing a corrected F.07 viewport."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

from tools.diag_gpt2_a120_multipath_frame_whatif_shadow import (
    audit_original_multipath_semantic_table_what_if as audit,
    _contains,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_native_frame_containment_is_not_nearest_title():
    assert _contains((1,1,10,10),(2,2,9,9))
    assert not _contains((1,1,10,10),(9,9,12,12))
    assert not _contains((1,1,10,10),(12,2,15,9))


def test_source_original_a120_candidates_preserve_both_false_and_real_frames():
    source=ORIGINAL.read_bytes()
    assert hashlib.sha256(source).hexdigest()==SHA
    with fitz.open(stream=source,filetype="pdf") as document:
        source_page=document[8]
        baseline_model_before=source_page.rotation
        result=audit(source_page,page_number=9)
        print("A120_ORIGINAL_F07_MULTIPATH_COUNTERFACTUAL",
              json.dumps({
                  "baseline":[(r["reported_source_viewport_id"],
                               r["status"],
                               r["source_native_bbox_pdf_pts"])
                              for r in result["original_f07_viewports"]],
                  "shadow":[(r["reported_source_viewport_id"],
                             r["status"],
                             r["source_native_bbox_pdf_pts"])
                            for r in result["optin_simulated_f07_viewports"]],
                  "positive_grid_count":result["candidate_source_grid_frame_count"],
                  "candidate_grid_frames":[
                      x["original_connected_line_grid_bbox_pdf_pts"]
                      for x in result["candidate_native_schedule_grids"]
                  ],
              },sort_keys=True))
        assert result["status"]=="read_only_source_f07_counterfactual_not_production"
        assert result["simulation_universe_complete"]
        assert result["simulated_result_does_not_replace_original_f07"]
        assert not result["new_authoritative_viewports"]
        assert not result["new_ceiling_material_or_m2"]
        assert result["candidate_source_grid_frame_count"]>=1
        true_table=[
            r for r in result["candidate_native_schedule_grids"]
            if all(abs(a-b)<.01 for a,b in zip(
                r["original_connected_line_grid_bbox_pdf_pts"],
                (1393.68,416.,1496.4,991.04)
            ))
        ]
        assert len(true_table)==1
        assert len(true_table[0]["original_native_path_item_ids"])==25
        assert true_table[0]["same_original_grid_title_owner_unambiguous_candidate_only"]
        assert not true_table[0]["no_view_or_material_authority_granted"] is False
        base_by_id={r["reported_source_viewport_id"]:r
                    for r in result["original_f07_viewports"]}
        assert base_by_id["view_p9_4"]["status"]=="resolved"
        assert (base_by_id["view_p9_4"]["source_native_bbox_pdf_pts"][2]
                < 1400) # the incorrect frame does NOT enclose title
        counter_by_id={r["reported_source_viewport_id"]:r
                       for r in result["optin_simulated_f07_viewports"]}
        assert "view_p9_4" in counter_by_id
        # The actual grid/title owner may remain ABSTAIN due to additional F07
        # frame rivals. This diagnostic must not force a resolved outcome.
        assert counter_by_id["view_p9_4"]["view_is_a_new_source_authority"] is False
        assert all(not r["quantity_or_material_granted"]
                   for r in result["optin_simulated_f07_viewports"])
        assert source_page.rotation==baseline_model_before
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_false_bare_dense_lines_without_schedule_title_mint_no_claim():
    document=fitz.open()
    page=document.new_page(width=500,height=400)
    for k in range(6):
        page.draw_line((40+k*20,40),(40+k*20,340))
        page.draw_line((40,40+k*20),(340,40+k*20))
    result=audit(page,page_number=1)
    assert result["new_authoritative_viewports"]==0
    assert result["new_ceiling_material_or_m2"]==0
    assert result["candidate_source_grid_frame_count"]==0
    document.close()
