"""Producer-owned native-line ceiling-finish evidence tests."""
from __future__ import annotations

import fitz

from pb_migration_contracts import ViewportEvidence, ViewportResolutionStatus
from pb_migration_provider_envelope import ProviderContext
from pb_source_ceiling_finish_evidence import (
    SOURCE_CEILING_FINISH_METHOD,
    collect_source_owned_ceiling_finish_candidates,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_vector_geometry_v130 import extract_native_page


def _pdf_bytes(
    *,
    first: str,
    second: str | None = None,
    first_color=(0, 0, 0),
    second_color=(0, 0, 0),
) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300, height=200)
        page.insert_text(
            fitz.Point(40, 70),
            first,
            fontsize=10,
            color=first_color,
        )
        if second is not None:
            page.insert_text(
                fitz.Point(40, 90),
                second,
                fontsize=10,
                color=second_color,
            )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _ingest(payload: bytes):
    producer = SourceVisibilityProducer(
        producer_method="source-ceiling-finish-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="source-ceiling-finish-doc",
        source_bytes=payload,
        source_locator="memory://source-ceiling-finish.pdf",
    )
    return producer, published


def _context(published) -> ProviderContext:
    return ProviderContext(
        run_id="run-source-ceiling-finish",
        workspace_id="workspace-source-ceiling-finish",
        project_id="project-source-ceiling-finish",
        document_id=published.revision.document_id,
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        current_revision_id=published.revision.revision_id,
        selected_pages=(0,),
        owned_viewport_ids=("vp-source-ceiling-finish",),
        evidence_snapshot_id=published.snapshot.snapshot_id,
        owned_page_numbers=(1,),
        viewport_page_ownership=(("vp-source-ceiling-finish", 1),),
    )


def _viewport(published, bbox=(0.0, 0.0, 300.0, 200.0)) -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="vp-source-ceiling-finish",
        document_id=published.revision.document_id,
        page_id="1",
        bbox=bbox,
        view_type="floor_plan",
        status=ViewportResolutionStatus.RESOLVED,
        evidence_ids=(),
        confidence=1.0,
    )


def test_native_word_extraction_preserves_block_line_word_numbers() -> None:
    doc = fitz.open(
        stream=_pdf_bytes(first="CEILING FINISH: 12mm gypsum plasterboard"),
        filetype="pdf",
    )
    try:
        native = extract_native_page(doc.load_page(0))
    finally:
        doc.close()

    assert native["words"]
    for word in native["words"]:
        assert isinstance(word["block_no"], int)
        assert isinstance(word["line_no"], int)
        assert isinstance(word["word_no"], int)


def test_same_native_line_builds_source_owned_finish_candidate() -> None:
    producer, published = _ingest(
        _pdf_bytes(first="CEILING FINISH: 12mm gypsum plasterboard")
    )
    atoms = collect_source_owned_ceiling_finish_candidates(
        source_visibility_producer=producer,
        context=_context(published),
        viewport=_viewport(published),
        page_no=1,
    )

    assert len(atoms) == 1
    atom = atoms[0]
    assert atom.method == SOURCE_CEILING_FINISH_METHOD
    assert atom.raw_text.lower().startswith("ceiling finish")
    assert atom.bbox is not None
    assert atom.metadata["producer_owned_text_line"] is True
    assert isinstance(atom.metadata["native_block_no"], int)
    assert isinstance(atom.metadata["native_line_no"], int)
    assert atom.metadata["source_text_observation_ids"]
    assert atom.metadata["text_integrity_receipt_ids"]


def test_split_native_lines_are_never_concatenated_into_finish_phrase() -> None:
    producer, published = _ingest(
        _pdf_bytes(
            first="CEILING",
            second="FINISH: 12mm gypsum plasterboard",
        )
    )
    atoms = collect_source_owned_ceiling_finish_candidates(
        source_visibility_producer=producer,
        context=_context(published),
        viewport=_viewport(published),
        page_no=1,
    )
    assert atoms == ()


def test_untrusted_hidden_text_cannot_create_finish_candidate() -> None:
    producer, published = _ingest(
        _pdf_bytes(
            first="CEILING FINISH: 12mm gypsum plasterboard",
            first_color=(1, 1, 1),
        )
    )
    atoms = collect_source_owned_ceiling_finish_candidates(
        source_visibility_producer=producer,
        context=_context(published),
        viewport=_viewport(published),
        page_no=1,
    )
    assert atoms == ()


def test_finish_line_outside_owned_viewport_is_ignored() -> None:
    producer, published = _ingest(
        _pdf_bytes(first="CEILING FINISH: 12mm gypsum plasterboard")
    )
    atoms = collect_source_owned_ceiling_finish_candidates(
        source_visibility_producer=producer,
        context=_context(published),
        viewport=_viewport(published, bbox=(0.0, 0.0, 25.0, 25.0)),
        page_no=1,
    )
    assert atoms == ()
