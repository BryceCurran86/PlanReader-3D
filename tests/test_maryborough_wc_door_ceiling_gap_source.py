"""Original-source-only D07-D09 ceiling header *candidate* receipts."""
from pathlib import Path
import hashlib
import os

import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_maryborough_wc_door_ceiling_gap import (
    authenticate_original_maryborough_wc_door_ceiling_gaps,
)

_ORIGINAL_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_no_original_source_can_authorize_door_header_or_benchmark():
    producer=SourceVisibilityProducer(producer_method="wc-schedule-nonexistent",producer_version="1")
    for source,rev in ((None,"none"),(producer,"none")):
        result=authenticate_original_maryborough_wc_door_ceiling_gaps(
            source=source,revision_id=rev,
        )
        assert result.status=="ABSTAIN"
        assert result.records==()
        assert not result.customer_quantity_allowed
        assert not result.benchmark_credit


def test_genuine_maryborough_wc_door_schedule_gap_is_not_an_invented_header():
    raw_path=os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH")
    if not raw_path:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private Maryborough PDF absent")
    path=Path(raw_path)
    assert path.is_file() and not path.is_symlink()
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==_ORIGINAL_SHA
    producer=SourceVisibilityProducer(
        producer_method="wc-schedule-height-source-integration",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    published=producer.ingest_native_pdf_bytes(
        document_id="wc-schedule-height-source-integration",
        source_bytes=raw,
        source_locator=str(path),
        page_ids=("9","24","28"),
    )
    result=authenticate_original_maryborough_wc_door_ceiling_gaps(
        source=producer,
        revision_id=published.revision.revision_id,
    )
    assert result.status=="SOURCE_SCHEDULED_DOOR_HEIGHT_BELOW_RCP_HEADER_UNPROVEN"
    assert len(result.records)==3
    assert [r.door_tag for r in result.records]==["D07","D08","D09"]
    assert len({r.record_id for r in result.records})==3
    assert len({r.physical_ceiling_source_witness_id for r in result.records})==3
    for row in result.records:
        assert row.source_sha256==_ORIGINAL_SHA
        assert row.ceiling_height_mm==2400
        assert row.door_leaf_width_mm==920
        assert row.door_leaf_height_mm==2040
        assert row.leaf_height_to_ceiling_difference_mm==360
        assert row.status=="SOURCE_DOOR_HEIGHT_BELOW_CEILING_HEADER_NOT_AUTHENTICATED"
        assert not row.source_ceil_wall_header_authenticated
        assert not row.physical_ceiling_perimeter_authenticated
        assert not row.customer_quantity_allowed
        assert not row.benchmark_credit
    assert result==authenticate_original_maryborough_wc_door_ceiling_gaps(
        source=producer,revision_id=published.revision.revision_id,
    )
    invalid=authenticate_original_maryborough_wc_door_ceiling_gaps(
        source=producer,revision_id=published.revision.revision_id+"-wrong",
    )
    assert invalid.status=="ABSTAIN" and not invalid.records
