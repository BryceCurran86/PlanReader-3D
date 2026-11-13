"""Original Maryborough D09 painted upper wall source proof, shadow-only."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_maryborough_wc_d09_header_source import (
    authenticate_original_maryborough_d09_painted_header,
)

_SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_missing_original_source_does_not_create_header():
    source=SourceVisibilityProducer(
        producer_method="d09-wall-header-missing",
        producer_version="1",
    )
    for obj,revision in ((None,"not_real"),(source,"not_real")):
        result=authenticate_original_maryborough_d09_painted_header(
            source=obj,revision_id=revision,
        )
        assert result.status=="ABSTAIN"
        assert result.record is None
        assert not result.customer_quantity_allowed
        assert not result.benchmark_credit


def test_real_d09_source_painted_header_visible_but_no_customer():
    path_name=os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH")
    if not path_name:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private PDF not provisioned")
    path=Path(path_name)
    assert path.is_file() and not path.is_symlink()
    raw=path.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==_SHA
    source=SourceVisibilityProducer(
        producer_method="d09-original-authenticated-source-paint-test",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    published=source.ingest_native_pdf_bytes(
        document_id="d09-original-authenticated-source-paint-test",
        source_bytes=raw,
        source_locator=str(path),
        page_ids=("9","24","28"),
    )
    result=authenticate_original_maryborough_d09_painted_header(
        source=source,revision_id=published.revision.revision_id,
    )
    assert result.status=="ORIGINAL_D09_ELEVATION_PAINTED_HEADER_AUTHENTIC"
    assert result.reason_codes==("d09_original_visible_black_wall_above_scheduled_door",)
    record=result.record
    assert record is not None
    assert record.door_tag=="D09"
    assert record.source_sha256==_SHA
    assert record.snapshot_id==published.snapshot.snapshot_id
    assert record.door_leaf_height_mm==2040
    assert record.rcp_ceiling_height_mm==2400
    assert len(record.visible_black_header_observation_ids)==4
    assert record.visible_black_header_bbox_pdf_pts[0]<record.visible_black_header_bbox_pdf_pts[2]
    assert record.visible_black_header_bbox_pdf_pts[1]<record.visible_black_header_bbox_pdf_pts[3]
    assert not record.other_wc_headers_authenticated
    assert not record.complete_physical_ceiling_zone_authenticated
    assert not record.customer_quantity_allowed
    assert not record.benchmark_credit
    assert not result.customer_quantity_allowed
    assert not result.benchmark_credit
    # Multiple identical independent reads must not mint competing evidence.
    again=authenticate_original_maryborough_d09_painted_header(
        source=source,revision_id=published.revision.revision_id,
    )
    assert again==result
    invalid=authenticate_original_maryborough_d09_painted_header(
        source=source,revision_id=published.revision.revision_id+"-fake",
    )
    assert invalid.status=="ABSTAIN" and invalid.record is None
