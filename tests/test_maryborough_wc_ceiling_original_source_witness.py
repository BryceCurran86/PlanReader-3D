"""SHA-verified original Maryborough WC/Shower benchmark-source preflight tests."""
from __future__ import annotations
import hashlib, os
from pathlib import Path
import pytest
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_maryborough_wc_ceiling_source_witness import (
    source_witnesses_for_three_maryborough_wc_ceilings,
)

_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

def test_bad_source_selector_fails_closed():
    result=source_witnesses_for_three_maryborough_wc_ceilings(source=None,revision_id="not-issue")
    assert result.status=="ABSTAIN" and not result.records
    assert not result.customer_issuance_allowed and not result.benchmark_credit

def test_empty_original_source_receipts_cannot_promote():
    producer=SourceVisibilityProducer(producer_method="wc-shower-missing-source",producer_version="1")
    res=source_witnesses_for_three_maryborough_wc_ceilings(source=producer,revision_id="missing")
    assert res.status=="ABSTAIN" and not res.records
    assert not res.customer_issuance_allowed

def test_original_sha_maryborough_three_wc_shower_detail_to_rcp_source_if_provisioned():
    val=os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH")
    if not val: pytest.skip("ORIGINAL_SOURCE_NOT_RUN: no private original provided")
    p=Path(val)
    assert p.is_file() and not p.is_symlink()
    raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==_SHA
    source=SourceVisibilityProducer(
        producer_method="gptmax-original-frozen-wc-shower-pair-test",
        producer_version="1",source_native_finish_text_shadow=True,
    )
    published=source.ingest_native_pdf_bytes(
        document_id="maryborough-wc-shower-original-source-pair-test",
        source_bytes=raw,source_locator=str(p),page_ids=("9","24"),
    )
    res=source_witnesses_for_three_maryborough_wc_ceilings(
        source=source,revision_id=published.revision.revision_id,
    )
    assert res.status=="SOURCE_WITNESSES_AUTHENTIC_ZONE_UNRESOLVED"
    assert len(res.records)==3
    assert [r.door_tag for r in res.records]==["D07","D08","D09"]
    assert len({r.record_id for r in res.records})==3
    assert len({r.rcp_height_material_pair_id for r in res.records})==3
    assert len({r.detail_width_word_id for r in res.records})==3
    assert len({r.detail_length_word_id for r in res.records})==1
    assert all(r.source_sha256==_SHA and r.ceiling_material_code=="WFPB" and r.ceiling_height_mm==2400 for r in res.records)
    assert all(r.floor_finish_code=="FT2" and r.figured_width_mm==1620 and r.figured_length_mm==2935 for r in res.records)
    assert all(not r.physical_ceiling_zone_authenticated and not r.cross_sheet_metric_area_authenticated for r in res.records)
    assert all(not r.customer_issuance_allowed and not r.benchmark_credit for r in res.records)
    assert not res.customer_issuance_allowed and not res.benchmark_credit
    repeated=source_witnesses_for_three_maryborough_wc_ceilings(
        source=source,revision_id=published.revision.revision_id,
    )
    assert repeated==res
    fake=source_witnesses_for_three_maryborough_wc_ceilings(
        source=source,revision_id=published.revision.revision_id+"-changed",
    )
    assert fake.status=="ABSTAIN" and not fake.records
