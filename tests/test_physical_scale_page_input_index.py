from __future__ import annotations

import fitz

import pb_physical_wall_candidate_authority as wall_module
from pb_pdf_text_integrity_authority import PdfTextIntegrityAuthority
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_source_visibility_authority import SourceVisibilityAuthority, SourceVisibilityProducer


def _multi_page_scale_pdf(page_count=4):
    doc = fitz.open()
    try:
        for index in range(page_count):
            page = doc.new_page(width=420.0, height=260.0)
            x0, x1 = 60.0, 88.3464567
            y = 90.0 + index
            shape = page.new_shape()
            shape.draw_line((x0, y), (x1, y))
            shape.draw_line((x0, y - 8), (x0, y + 8))
            shape.draw_line((x1, y - 8), (x1, y + 8))
            shape.finish(width=1)
            shape.commit()
            page.insert_text((x0 - 2, y + 24), "0")
            page.insert_text((x1 - 4, y + 24), "1m")
            page.insert_text((250, 60), "SCALE 1:100")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _source(page_count=4):
    source = SourceVisibilityProducer(
        producer_method="scale-page-input-index-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="scale-page-input-index-test",
        source_bytes=_multi_page_scale_pdf(page_count),
        source_locator="memory://scale-page-input-index-test.pdf",
    )
    return source, published


def _selector(published, page_id):
    return PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=str(page_id),
    )


def test_shared_scale_producer_matches_fresh_producer_per_page():
    source, published = _source(page_count=4)
    shared = PhysicalScaleProducer.from_source_visibility_producer(source)

    for page_id in ("1", "2", "3", "4"):
        selector = _selector(published, page_id)
        expected = PhysicalScaleProducer.from_source_visibility_producer(
            source
        ).publish_scope(selector)
        actual = shared.publish_scope(selector)
        assert actual == expected


def test_scale_snapshot_inputs_are_authenticated_once(monkeypatch):
    source, published = _source(page_count=5)
    visible_original = SourceVisibilityAuthority.resolve_visible
    text_original = PdfTextIntegrityAuthority.resolve_text
    visible_calls = 0
    text_calls = 0

    def counted_visible(self, selector):
        nonlocal visible_calls
        visible_calls += 1
        return visible_original(self, selector)

    def counted_text(self, selector):
        nonlocal text_calls
        text_calls += 1
        return text_original(self, selector)

    monkeypatch.setattr(SourceVisibilityAuthority, "resolve_visible", counted_visible)
    monkeypatch.setattr(PdfTextIntegrityAuthority, "resolve_text", counted_text)

    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    for page_id in ("1", "2", "3", "4", "5"):
        producer.publish_scope(_selector(published, page_id))

    assert visible_calls == len(published.visible_observation_ids)
    assert text_calls == len(published.text_observation_ids)


def test_wall_candidate_build_constructs_one_scale_producer_per_revision(monkeypatch):
    source, _published = _source(page_count=3)
    original = wall_module.PhysicalScaleProducer.from_source_visibility_producer
    constructions = 0

    def counted(source_producer):
        nonlocal constructions
        constructions += 1
        return original(source_producer)

    monkeypatch.setattr(
        wall_module.PhysicalScaleProducer,
        "from_source_visibility_producer",
        counted,
    )

    wall_module.PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1", "2", "3"),
    )

    assert constructions == 1
