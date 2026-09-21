from __future__ import annotations

import fitz

from pb_generic_opening_count_authority import _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
from pb_opening_universe_completeness_source_adapter import (
    build_semantic_opening_inventory_completeness,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    for first, second in (
        ((25.0, 60.0), (110.0, 60.0)),
        ((150.0, 60.0), (275.0, 60.0)),
        ((25.0, 75.0), (110.0, 75.0)),
        ((150.0, 75.0), (275.0, 75.0)),
        ((110.0, 60.0), (110.0, 75.0)),
        ((150.0, 60.0), (150.0, 75.0)),
        ((320.0, 20.0), (380.0, 20.0)),
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


def test_registered_path_universe_proof_receives_commercial_seal() -> None:
    source = SourceVisibilityProducer(
        producer_method="commercial-seal-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="commercial-seal",
        source_bytes=_pdf(),
        source_locator="memory://commercial-seal.pdf",
    )
    authority = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        decision_scope_id="scope:page:1",
        page_ids=("1",),
        optional_content_known_visible=True,
    )
    assert (
        getattr(authority, "_source_authentication_seal", None)
        is _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL
    )
