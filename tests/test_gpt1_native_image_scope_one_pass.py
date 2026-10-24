"""Original PDF XObject registration: one verified pass, no stale cache authority."""
import fitz
import pytest
from pb_source_observation_authority import SourceObservationProducer, ProducerIntegrityError


def _source():
    document = fitz.open()
    page = document.new_page(width=220, height=180)
    image = fitz.Pixmap(fitz.csGRAY, fitz.IRect(0, 0, 40, 20), False)
    image.clear_with(170)
    page.insert_image(fitz.Rect(20, 30, 100, 70), pixmap=image)
    page.insert_image(fitz.Rect(120, 80, 200, 120), pixmap=image)
    pdf = document.tobytes()
    document.close()
    producer = SourceObservationProducer(
        producer_method="image-scope-cache-test", producer_version="1"
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="img-doc", source_bytes=pdf, source_locator="memory://image"
    )
    selector = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id="1",
    )
    return producer, selector


def test_original_image_regions_and_placements_share_one_xobject_pass(monkeypatch):
    source, selector = _source()
    original = fitz.Page.get_image_rects
    calls = []
    def measured(self, *args, **kwargs):
        calls.append(None)
        return original(self, *args, **kwargs)
    monkeypatch.setattr(fitz.Page, "get_image_rects", measured)
    regions = source.native_page_image_regions(**selector)
    placements = source.native_page_image_placements(**selector)
    assert len(regions) == len(placements) == 2
    assert len(calls) == 1
    assert {p.bbox_pt for p in placements} == {
        tuple(round(v, 6) for v in region) for region in regions
    }
    assert {(p.pixel_width, p.pixel_height) for p in placements} == {(40, 20)}
    assert source.native_page_image_regions(**selector) == regions
    assert source.native_page_image_placements(**selector) == placements
    assert len(calls) == 1


def test_valid_cached_image_cannot_hide_original_sha_mutation():
    source, selector = _source()
    assert len(source.native_page_image_placements(**selector)) == 2
    source._store.source_bytes_by_revision[selector["revision_id"]] = b"modified"
    with pytest.raises((ProducerIntegrityError, ValueError)):
        source.native_page_image_regions(**selector)
    with pytest.raises((ProducerIntegrityError, ValueError)):
        source.native_page_image_placements(**selector)


def test_original_image_cache_does_not_accept_foreign_snapshot():
    source, selector = _source()
    source.native_page_image_placements(**selector)
    with pytest.raises(ValueError):
        source.native_page_image_placements(
            **{**selector, "snapshot_id": "unrelated-snapshot"}
        )
