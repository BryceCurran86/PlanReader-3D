"""Original A120 F07 RCP material producer page-scope integration (private source).

The tests cannot certify original source on public CI without the owner's
SHA-pinned PDF. They do not publish metric areas or customer quantities.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

import pb_source_material_semantic_authority as material
import pb_viewport_segmentation as f07
from pb_source_visibility_authority import SourceVisibilityProducer


ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.fixture(scope="module")
def source():
    if not ORIGINAL.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: exact F07 material acceptance NOT VERIFIED")
    data=ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    with fitz.open(stream=data,filetype="pdf") as doc:
        assert len(doc)==31
        assert doc[8].rotation==90
        selected=f07.segment_page_viewports(
            doc[8], page_number=9,
            source_connected_table_cell_shadow=True,
            source_native_multipath_semantic_frame_shadow=True,
            source_connected_text_cell_plan_frame_shadow=True,
        )
        by_id={v.view_id:v for v in selected}
        assert by_id["view_p9_5"].status == f07.ViewportSegmentationStatus.RESOLVED.value
        assert by_id["view_p9_4"].status == f07.ViewportSegmentationStatus.RESOLVED.value
        assert f07.validate_non_overlapping_viewports(selected)
        # Positive source view EXTENT only; never a structural wall.
        ink=by_id["view_p9_5"].provenance.get(
            "source_connected_text_cell_plan_frame_shadow"
        )
        assert ink is not None
    source=SourceVisibilityProducer(
        producer_method="gpt2-private-F07-rcp-material",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="private-source-test-only",
        source_bytes=data,
        source_locator="memory:original-a120-source",
        page_ids=("9",),
    )
    assert published.revision.source_sha256==SHA
    return source,published


def test_original_page9_rcp_material_factory_consumes_source_owned_plan_scope(source):
    upstream,published=source
    producer=material.SourceMaterialSemanticProducer.for_source_connected_original_rcp_plan_shadow(
        upstream,page_ids=("9",),
    )
    auth=producer.publish(published.revision.revision_id)
    assert auth is not None
    scopes=producer.published_occurrence_results()
    assert isinstance(scopes,tuple)
    assert all(scope.status is not None for scope in scopes)
    assert all(not hasattr(scope,"commercial_projection_allowed") for scope in scopes)
    assert producer._source_connected_rcp_plan_page_ids==frozenset({"9"})
    assert producer._source_native_schedule_page_ids==frozenset({"9"})


def test_original_rcp_material_optin_does_not_change_default_producer_mode(source):
    upstream,published=source
    default=material.SourceMaterialSemanticProducer.from_source_visibility_producer(
        upstream,
    )
    assert default._source_connected_rcp_plan_page_ids==frozenset()
    assert default._source_native_schedule_page_ids==frozenset()
    default.publish(published.revision.revision_id)
    assert default._source_connected_rcp_plan_page_ids==frozenset()
