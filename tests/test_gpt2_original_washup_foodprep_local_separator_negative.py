"""Open labels cannot be converted into a physical wall or room by a probe."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_open_plan_label_separator_shadow import (
    audit_original_label_between_ink_probe as audit,
)

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _sample(with_separator=False, with_partial=False):
    pdf=fitz.open()
    page=pdf.new_page(width=300,height=120)
    page.insert_text((20,54),"WASH UP",fontsize=12)
    page.insert_text((185,54),"FOOD PREP",fontsize=12)
    if with_separator:
        page.draw_line((120,35),(120,60),color=(0,0,0),width=.48)
    if with_partial:
        page.draw_line((120,43),(120,49),color=(0,0,0),width=.48)
    words=page.get_text("words",sort=False)
    label_ids={
        token: (w[5],w[6],w[7])
        for w in words for token in (w[4],)
    }
    raw=pdf.tobytes()
    pdf.close()
    return raw, ((label_ids["WASH"],label_ids["UP"]),
                 (label_ids["FOOD"],label_ids["PREP"]))


def _run(with_separator=False,with_partial=False,**changes):
    raw, labels=_sample(with_separator,with_partial)
    opts={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "page_1_based":1,
        "first_label_native_word_addresses":labels[0],
        "second_label_native_word_addresses":labels[1],
        "probe_line_pdf_pts":((120.,35.),(120.,60.)),
    }
    opts.update(changes)
    return audit(raw,**opts)


def test_original_open_plan_local_probe_no_wall_does_not_mint_a_room():
    result=_run()
    assert result["no_qualifying_original_black_ink_on_this_probe"] is True
    assert result["probe_fully_covered_by_black_ink"] is False
    assert result["original_probe_is_source_authentic_structural_separator"] is False
    assert result["two_original_labels_same_physical_room_proven"] is False
    assert result["new_firm_quantities"]==0


def test_genuine_source_ink_on_local_probe_is_retained_but_not_wall_authority():
    row=_run(with_separator=True)
    assert row["probe_fully_covered_by_black_ink"] is True
    assert row["original_opaque_black_collinear_ink_candidates"][0][
        "original_native_path_item_id"]=="d0i0"
    assert row["original_probe_is_source_authentic_structural_separator"] is False
    assert row["new_firm_quantities"]==0


def test_partial_hatch_or_drafting_ink_does_not_fake_complete_separator():
    row=_run(with_partial=True)
    assert len(row["original_opaque_black_collinear_ink_candidates"])==1
    assert row["probe_fully_covered_by_black_ink"] is False


@pytest.mark.parametrize("changes",[
    {"expected_sha256":"0"*64},
    {"first_label_native_word_addresses":((999,0,0),)},
    {"first_label_native_word_addresses":((0,0,0),(0,0,0))},
    {"probe_line_pdf_pts":((120,35),(120,35))},
    {"probe_line_pdf_pts":((120,35),(140,60))},
    {"probe_line_pdf_pts":((30,35),(30,60))},
    {"minium_stroke_width_pdf_pts":float("nan")},
])
def test_invalid_original_source_or_probe_never_claims_a_room(changes):
    if "minium_stroke_width_pdf_pts" in changes:
        changes={"minimum_stroke_width_pdf_pts":changes[
            "minium_stroke_width_pdf_pts"]}
    with pytest.raises(ValueError):
        _run(**changes)


@pytest.mark.skipif(not SOURCE.is_file(),reason="private owner source not provisioned")
def test_original_page7_wash_up_to_food_prep_local_probes_have_no_black_partition():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    for x in (270.,275.04,280.,290.,300.,310.,315.):
        result=audit(
            raw,expected_sha256=SHA,page_1_based=7,
            first_label_native_word_addresses=((168,0,0),(168,0,1)),
            second_label_native_word_addresses=((138,0,0),(138,0,1)),
            probe_line_pdf_pts=((x,640.),(x,715.)),
            minimum_stroke_width_pdf_pts=.45,
        )
        assert result["no_qualifying_original_black_ink_on_this_probe"] is True
        assert result["two_original_labels_same_physical_room_proven"] is False
        assert result["new_firm_quantities"]==0
