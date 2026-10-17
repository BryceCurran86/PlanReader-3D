"""Fixture-independent room-ink pairing checks; original source is separate."""
import hashlib
import fitz
import pytest
from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_enclosure_correspondence as audit,
)

SIDE={role:(f"d{i}i0",f"d{i}i0") for i,role in enumerate(
    ("left","right","bottom","top_partial"))}


def _pdf():
    d=fitz.open()
    for offset in (0,78):
        d.new_page(width=320,height=220)
        p=d[-1]
        sides=[
            ((20+offset,30),(20+offset,150)),
            ((130+offset,30),(130+offset,150)),
            ((20+offset,150),(130+offset,150)),
            ((65+offset,30),(130+offset,30)),
        ]
        for start,end in sides:p.draw_line(start,end,color=(0,0,0),width=.48)
    b=d.tobytes();d.close();return b


def test_unchanged_source_four_sides_and_open_top_pass_as_candidate_only():
    data=_pdf()
    out=audit(data,expected_sha256=hashlib.sha256(data).hexdigest(),
            floor_page_1_based=1,finish_page_1_based=2,
            original_side_pairs=SIDE,expected_translation_pdf_pts=(78.,0.))
    assert out["status"]=="original_four_edge_ink_correspondence_with_unclosed_doorway"
    assert out["original_top_gap_pdf_pts"]==[[20.,30.],[65.,30.]]
    assert not out["physical_wall_roles_verified"]
    assert not out["canonical_cross_sheet_physical_room_equality_granted"]


def test_foreign_side_source_and_rival_transform_abstain():
    data=_pdf()
    args=dict(expected_sha256=hashlib.sha256(data).hexdigest(),
              floor_page_1_based=1,finish_page_1_based=2,
              original_side_pairs=SIDE,expected_translation_pdf_pts=(78.,0.))
    with pytest.raises(ValueError,match="source_side_ink_or_translation_conflict"):
        audit(data,**{**args,"expected_translation_pdf_pts":(69.36,0.)})
    with pytest.raises(ValueError,match="distinct_source_path_item_owners_required"):
        audit(data,**{**args,"original_side_pairs":{**SIDE,"right":SIDE["left"]}})
