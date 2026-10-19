"""An original 2127 STACKER HHWW callout is dimension syntax, not FIRM."""
from dataclasses import replace
from hashlib import sha256
from pathlib import Path

import fitz
import pytest

from pb_source_plan_opening_callout import extract_source_plan_opening_callouts
from tools.diag_gptmax_original_2127_nominal_source_dimensions import (
    select_unpublished_stacker_2127_callout,
    original_2127_stacker_nominal_dimension_receipt,
)

SOURCE=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")


def _fixture():
    doc=fitz.open()
    page=doc.new_page(width=500,height=300)
    page.insert_text((30,30),"FLOOR PLAN")
    page.insert_text((100,100),"2127 STACKER")
    pdf=doc.tobytes()
    sha=sha256(pdf).hexdigest()
    calls=extract_source_plan_opening_callouts(
        page,source_sha256=sha,source_page=3,
    )
    doc.close()
    candidate=[c for c in calls if c.raw_callout=="2127 STACKER"]
    assert len(candidate)==1
    return sha,candidate[0]


def test_compact_2127_original_source_is_abstained_not_an_extra_opening():
    sha,record=_fixture()
    result=select_unpublished_stacker_2127_callout(
        (record,),source_sha256=sha,
        source_plan_bbox_pdf_pt=record.bbox,
    )
    assert result["status"]=="original_2127_compact_size_source_only"
    assert result["source_nominal_height_mm"]==21*100
    assert result["source_nominal_width_mm"]==27*100
    assert result["source_arithmetic_area_candidate_m2"]==2.1*2.7
    assert result["source_opening_kind_lexical_only"]=="door"
    assert result["underlying_source_quantity_status"]=="abstained"
    assert result["underlying_source_quantity_value"] is None
    assert result["physical_cross_page_instance_binding_proven"] is False
    assert result["unique_structural_host_proven"] is False
    assert result["connected_whole_wall_frame_proven"] is False
    assert result["source_quantity_publication_granted"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("break_candidate", [
    lambda r:replace(r,source_sha256="0"*64),
    lambda r:replace(r,source_page=5),
    lambda r:replace(r,opening_kind="window"),
    lambda r:replace(r,raw_callout="2127 STACKER DIA"),
    lambda r:replace(r,width_mm=2800.),
    lambda r:replace(r,height_mm=2000.),
    lambda r:replace(r,area_m2=0.),
    lambda r:replace(r,quantity_evidence=replace(
        r.quantity_evidence,status="firm")),
    lambda r:replace(r,quantity_evidence=replace(
        r.quantity_evidence,value=5.67)),
    lambda r:replace(r,quantity_evidence=replace(
        r.quantity_evidence,unit="each")),
])
def test_reconstructed_nominal_source_claims_fail_before_any_metric_promotion(
    break_candidate
):
    sha,record=_fixture()
    forged=break_candidate(record)
    with pytest.raises(ValueError):
        select_unpublished_stacker_2127_callout(
            (forged,),source_sha256=sha,
            source_plan_bbox_pdf_pt=record.bbox,
        )


def test_duplicate_code_cannot_elect_a_nearest_stacker_or_default_count():
    sha,record=_fixture()
    with pytest.raises(ValueError,match="exact one original"):
        select_unpublished_stacker_2127_callout(
            (record,record),source_sha256=sha,
            source_plan_bbox_pdf_pt=record.bbox,
        )


def test_foreign_native_original_bbox_cannot_bind_lexical_dimensions():
    sha,record=_fixture()
    foreign=tuple(x+3 for x in record.bbox)
    with pytest.raises(ValueError,match="callout/native text binding"):
        select_unpublished_stacker_2127_callout(
            (record,),source_sha256=sha,
            source_plan_bbox_pdf_pt=foreign,
        )


@pytest.mark.skipif(not SOURCE.is_file(),reason="private original Lot16 PDF unavailable")
def test_owner_original_2127_nominal_source_retains_complete_abstain():
    result=original_2127_stacker_nominal_dimension_receipt(
        SOURCE.read_bytes()
    )
    assert result["source_compact_code"]=="2127"
    assert result["source_descriptor"]=="STACKER"
    assert result["source_plan_evidence_ids"]
    assert result["source_nominal_height_mm"]==21*100
    assert result["source_nominal_width_mm"]==27*100
    assert result["underlying_source_quantity_status"]=="abstained"
    assert result["underlying_source_quantity_value"] is None
    assert [row["page_number"] for row in result[
        "source_native_crossview_label_receipt"]["native_marks"]]==[3,5]
    assert result["new_firm_quantities"]==0
