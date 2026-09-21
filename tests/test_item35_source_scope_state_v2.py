from __future__ import annotations

import fitz

from pb_generic_opening_count_authority import _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _simple_opening_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    for first, second in (
        ((25.0, 60.0), (110.0, 60.0)),
        ((150.0, 60.0), (275.0, 60.0)),
        ((25.0, 75.0), (110.0, 75.0)),
        ((150.0, 75.0), (275.0, 75.0)),
        ((110.0, 60.0), (110.0, 75.0)),
        ((150.0, 60.0), (150.0, 75.0)),
    ):
        page.draw_line(
            fitz.Point(*first),
            fitz.Point(*second),
            color=(0, 0, 0),
            width=1,
        )
    payload = doc.tobytes()
    doc.close()
    return payload


def _form_xobject_pdf() -> bytes:
    source = fitz.open()
    src_page = source.new_page(width=200, height=100)
    src_page.draw_line(
        fitz.Point(20, 50), fitz.Point(180, 50), color=(0, 0, 0), width=1
    )

    target = fitz.open()
    page = target.new_page(width=400, height=250)
    page.show_pdf_page(fitz.Rect(20, 20, 220, 120), source, 0)
    payload = target.tobytes()
    target.close()
    source.close()
    return payload


def test_producer_derives_normal_scope_as_no_ocg_no_unresolved_form_xobject() -> None:
    source = SourceVisibilityProducer(
        producer_method="source-state-test",
        producer_version="2.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-state-normal",
        source_bytes=_simple_opening_pdf(),
        source_locator="memory://source-state-normal.pdf",
    )

    assert (
        source.optional_content_state_for_scope(
            published.revision.revision_id,
            page_ids=("1",),
        )
        == "known_visible"
    )
    assert (
        source.xobject_traversal_truncated_for_scope(
            published.revision.revision_id,
            page_ids=("1",),
        )
        is False
    )


def test_form_xobject_scope_fails_closed_even_when_caller_claims_safe_flags() -> None:
    source = SourceVisibilityProducer(
        producer_method="source-state-test",
        producer_version="2.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="source-state-form",
        source_bytes=_form_xobject_pdf(),
        source_locator="memory://source-state-form.pdf",
    )

    assert (
        source.xobject_traversal_truncated_for_scope(
            published.revision.revision_id,
            page_ids=("1",),
        )
        is True
    )

    authority = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        decision_scope_id="scope:page:1",
        page_ids=("1",),
        optional_content_known_visible=True,
        xobject_traversal_truncated=False,
    )
    assert (
        getattr(authority, "_source_authentication_seal", None)
        is not _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )
