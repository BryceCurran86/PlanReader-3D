"""Fixture-independent room-ink pairing checks; original source is separate."""
import hashlib
import fitz
import pytest
from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_enclosure_correspondence as audit,
)

# Source path/item identities are LOCAL to each original page. These older
# fixture pages happen to use eight distinct path names because p2 contains
# four unrelated native strokes. That is not a requirement for source proof.
SIDE={role:(f"d{i}i0",f"d{i+4}i0") for i,role in enumerate(
    ("left","right","bottom","top_partial"))}

def _unrelated_source_paths(page):
    for x in (2,4,6,8):
        page.draw_line((x,2),(x+1,2),color=(.5,.5,.5),width=.18)


def _pdf():
    d=fitz.open()
    for offset in (0,78):
        d.new_page(width=320,height=220)
        p=d[-1]
        if offset:
            _unrelated_source_paths(p)
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

def test_competing_native_cross_sheet_registrations_keep_first_failures():
    source=_pdf()
    expected=hashlib.sha256(source).hexdigest()
    result=__import__("tools.diag_original_room_four_edge_source_ink_shadow",fromlist=[
        "audit_competing_original_enclosure_registrations"
    ]).audit_competing_original_enclosure_registrations(
        source,expected_sha256=expected,floor_page_1_based=1,
        finish_page_1_based=2,candidates=(
            {"side_pairs":SIDE,"translation":(78.,0.)},
            {"side_pairs":SIDE,"translation":(69.36,0.)},
        ),
    )
    assert result["source_ink_positive_candidate_count"]==1
    assert len(result["all_original_registration_evidence"])==2
    assert result["all_original_registration_evidence"][1]["source_evidence"]["status"]=="source_registration_rejected"
    assert not result["cross_sheet_physical_room_identity_issued"]
    assert result["new_firm_quantities"]==0


def test_stroke_style_mismatch_between_source_sheets_never_publishes_room_link():
    doc=fitz.open()
    for offset, opacity in ((0,1.),(78,.5)):
        page=doc.new_page(width=400,height=220)
        if offset:
            _unrelated_source_paths(page)
        for a,b in [((20,30),(20,150)),((130,30),(130,150)),
                    ((20,150),(130,150)),((65,30),(130,30))]:
            page.draw_line((a[0]+offset,a[1]),(b[0]+offset,b[1]),
                           color=(0,0,0),width=.48,stroke_opacity=opacity)
    source=doc.tobytes();doc.close()
    with pytest.raises(ValueError,match="source_side_ink_or_translation_conflict"):
        audit(source,expected_sha256=hashlib.sha256(source).hexdigest(),
              floor_page_1_based=1,finish_page_1_based=2,
              original_side_pairs=SIDE,expected_translation_pdf_pts=(78.,0.))

def test_competing_registration_cannot_swallow_global_original_pdf_tampering():
    from tools.diag_original_room_four_edge_source_ink_shadow import (
        audit_competing_original_enclosure_registrations as compare,
    )
    source=_pdf()
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        compare(source+b"forged-original-pdf",
                expected_sha256=hashlib.sha256(source).hexdigest(),
                floor_page_1_based=1,finish_page_1_based=2,
                candidates=({"side_pairs":SIDE,"translation":(78.,0.)},))
    with pytest.raises(ValueError,match="duplicate_original_registration_candidate"):
        compare(source,expected_sha256=hashlib.sha256(source).hexdigest(),
                floor_page_1_based=1,finish_page_1_based=2,
                candidates=({"side_pairs":SIDE,"translation":(78.,0.)},
                            {"side_pairs":SIDE,"translation":(78,0)}))


def test_left_anchored_original_top_partial_has_gap_on_right_not_false_wall():
    d=fitz.open()
    for offset in (0,78):
        p=d.new_page(width=320,height=220)
        if offset:
            _unrelated_source_paths(p)
        for a,b in (
            ((20,30),(20,150)),
            ((130,30),(130,150)),
            ((20,150),(130,150)),
            ((20,30),(65,30)),
        ):
            p.draw_line((a[0]+offset,a[1]),
                        (b[0]+offset,b[1]),color=(0,0,0),width=.48)
    raw=d.tobytes();d.close()
    r=audit(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
            floor_page_1_based=1,finish_page_1_based=2,
            original_side_pairs=SIDE,expected_translation_pdf_pts=(78.,0.))
    assert r["status"]=="original_four_edge_ink_correspondence_with_unclosed_doorway"
    assert r["original_top_partial_wall_anchor"]=="left"
    assert r["original_top_gap_pdf_pts"]==[[65.,30.],[130.,30.]]
    assert not r["canonical_cross_sheet_physical_room_equality_granted"]
    assert r["new_firm_quantities"]==0


def test_source_native_path_names_may_repeat_on_independent_original_pages():
    # A real CAD export can start at d0i0 on BOTH original pages. Only a
    # (SHA,page,path,item) tuple, never the bare path string, identifies ink.
    doc=fitz.open()
    for offset in (0,78):
        page=doc.new_page(width=320,height=220)
        for start,end in (
            ((20,30),(20,150)),
            ((130,30),(130,150)),
            ((20,150),(130,150)),
            ((65,30),(130,30)),
        ):
            page.draw_line((start[0]+offset,start[1]),
                           (end[0]+offset,end[1]),
                           color=(0,0,0),width=.48)
    raw=doc.tobytes()
    doc.close()
    side_names={role:(f"d{i}i0",f"d{i}i0")
                for i,role in enumerate(
                    ("left","right","bottom","top_partial"))}
    result=audit(
        raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
        floor_page_1_based=1,finish_page_1_based=2,
        original_side_pairs=side_names,
        expected_translation_pdf_pts=(78.,0.))
    assert result["status"]=="original_four_edge_ink_correspondence_with_unclosed_doorway"
    assert result["original_top_gap_pdf_pts"]==[[20.,30.],[65.,30.]]
    assert all(value["physical_wall_role_proven"] is False
               for value in result["original_witnesses"].values())
    assert result["new_firm_quantities"]==0


def test_same_native_line_cannot_own_two_different_sides_on_either_page():
    doc=fitz.open()
    for offset in (0,78):
        page=doc.new_page(width=320,height=220)
        for start,end in (
            ((20,30),(20,150)),
            ((130,30),(130,150)),
            ((20,150),(130,150)),
            ((65,30),(130,30)),
        ):
            page.draw_line((start[0]+offset,start[1]),
                           (end[0]+offset,end[1]),
                           color=(0,0,0),width=.48)
    raw=doc.tobytes()
    doc.close()
    sides={role:(f"d{i}i0",f"d{i}i0") for i,role in enumerate(
        ("left","right","bottom","top_partial"))}
    for repeat_side in ("floor","finish"):
        forged={key:list(value) for key,value in sides.items()}
        index=0 if repeat_side=="floor" else 1
        forged["right"][index]=forged["left"][index]
        with pytest.raises(ValueError,match="distinct_source_path_item_owners_required"):
            audit(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),
                  floor_page_1_based=1,finish_page_1_based=2,
                  original_side_pairs={key:tuple(v) for key,v in forged.items()},
                  expected_translation_pdf_pts=(78.,0.))
