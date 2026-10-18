"""Source-native A120 RCP vs floor-plan multiwall correspondence, not m².

Reuses the merged general two-page native source-line candidate census instead
of inventing new wall matching. Exact original stroke identity, length, paint
and both endpoints are required. The genuine p7↔p9 plan correlation is a
candidate source relationship, never automatic RCP bbox, roof footprint,
ceiling zone ownership or FT3 floor correspondence.
"""
import hashlib
from pathlib import Path
import fitz

from tools.diag_original_crosssheet_native_ink_registration_shadow import (
    audit_original_cross_sheet_source_translation as audit,
)

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_original_p7_p9_anchored_source_wall_ink_has_dominant_x_shift():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        receipt=audit(
            doc[6],doc[8],
            native_candidate_bbox_a=(80.,450.,930.,1955.),
            native_candidate_bbox_b=(180.,450.,1400.,1955.),
            native_min_line_length_pt=90.,
            max_offset_pdf_pt=400.,
        )
        assert receipt["source_candidate_universe_complete"]
        groups=receipt["all_competing_translation_groups"]
        assert len(groups)>=2
        primary=next(g for g in groups
                     if g["original_source_translation_pdf_pts"]==[106.32,0.])
        assert primary["original_source_pair_count"]>=100
        assert primary["locally_unique_source_ink_pair_count"]>=50
        others=[g for g in groups
                if g["original_source_translation_pdf_pts"]!=[106.32,0.]]
        assert max(g["original_source_pair_count"] for g in others)<primary["original_source_pair_count"]
        # These are original CAD source ink matches, not 100 physical walls.
        assert not primary["structural_wall_identity_granted"]
        assert not primary["page7_to_page11_physical_room_join_granted"]
        assert not primary["global_source_registration_authority_granted"]
        assert receipt["new_quantities"]==receipt["new_floor_finish_quantities"]==0
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA


def test_original_p7_p9_retains_freezer_and_other_independent_native_ink():
    raw=SOURCE.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as doc:
        receipt=audit(doc[6],doc[8],
            native_candidate_bbox_a=(80.,450.,930.,1955.),
            native_candidate_bbox_b=(180.,450.,1400.,1955.),
            native_min_line_length_pt=90.,
            max_offset_pdf_pt=400.)
        group=next(g for g in receipt["all_competing_translation_groups"]
                   if g["original_source_translation_pdf_pts"]==[106.32,0.])
        ids={p["source_original_a_path_item_id"]
             for p in group["all_original_candidate_pairs"]}
        assert "d51615i0" in ids
        assert "d52155i0" in ids
        assert len(ids)>=70
        assert receipt["first_remaining_gate"]=="unique_structural_wall_ancestry_and_same_physical_floor_identity"
        assert receipt["newly_authenticated_physical_walls"]==0


def test_source_rivals_include_opposite_wall_faces_not_merge_authority():
    raw=SOURCE.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as doc:
        receipt=audit(doc[6],doc[8],
            native_candidate_bbox_a=(80.,450.,930.,1955.),
            native_candidate_bbox_b=(180.,450.,1400.,1955.),
            native_min_line_length_pt=90.,
            max_offset_pdf_pt=400.)
        offsets={tuple(g["original_source_translation_pdf_pts"])
                 for g in receipt["all_competing_translation_groups"]}
        assert (106.32,0.) in offsets
        assert (112.08,0.) in offsets
        # The exact original native candidate census has no zero-offset
        # same-ink pair in this bounded comparison. Never invent a rival
        # translation to make the plan-registration test appear complete.
        assert (0.,0.) not in offsets
        assert not any(g["global_source_registration_authority_granted"]
                       for g in receipt["all_competing_translation_groups"])
