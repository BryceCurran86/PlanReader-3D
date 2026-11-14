"""Exact rendering/lineage and bounded reuse for original-source text crops."""
from __future__ import annotations

from dataclasses import replace

import fitz
import pytest

from pb_source_observation_authority import ProducerIntegrityError
from tests.test_source_observation_render_clip_v1 import _ingest, _kwargs


def _source_bytes(*, rotation=0, pages=1, annotation=False, text="SOURCE"):
    with fitz.open() as doc:
        for index in range(pages):
            page = doc.new_page(width=300, height=220)
            page.insert_text((45, 95), f"{text} {index + 1}", fontsize=18)
            page.draw_rect((25, 30, 140, 130), color=(0.1, 0.2, 0.3))
            if annotation:
                annot = page.add_rect_annot((35, 70, 125, 105))
                annot.set_colors(stroke=(1, 0, 0))
                annot.update()
            page.set_rotation(rotation)
        return doc.tobytes()


def _count_builds(monkeypatch):
    count = []
    original = fitz.mupdf.fz_new_display_list_from_page

    def counted(*args, **kwargs):
        count.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(fitz.mupdf, "fz_new_display_list_from_page", counted)
    return count


@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("dpi", [144.0, 300.0, 450.0])
@pytest.mark.parametrize("annotation", [False, True])
def test_cached_crop_matches_direct_renderer_bytes_and_parent(rotation, dpi, annotation):
    payload = _source_bytes(rotation=rotation, annotation=annotation)
    producer, published = _ingest(payload)
    clip = (31.25, 67.5, 151.75, 110.25)
    with fitz.open(stream=payload, filetype="pdf") as doc:
        page = doc[0]
        display_clip = fitz.Rect(clip) * page.rotation_matrix
        expected = page.get_pixmap(
            matrix=fitz.Matrix(dpi / 72, dpi / 72), clip=display_clip, alpha=False,
        ).tobytes("png")
    first, parent = producer.render_native_page_png(**_kwargs(published), dpi=dpi, clip_pt=clip)
    again, parent_again = producer.render_native_page_png(**_kwargs(published), dpi=dpi, clip_pt=clip)
    assert first == again == expected
    assert parent == parent_again and parent is not parent_again
    assert parent.source_sha256 == published.revision.source_sha256


@pytest.mark.parametrize("rotation", [180, 270])
@pytest.mark.parametrize("dpi", [144.0, 300.0, 450.0])
@pytest.mark.parametrize("annotation", [False, True])
def test_unresolved_native_rotation_keeps_existing_clip_rejection(rotation, dpi, annotation):
    producer, published = _ingest(_source_bytes(rotation=rotation, annotation=annotation))
    with pytest.raises(ValueError, match="invalid_render_clip: native page frame unresolved"):
        producer.render_native_page_png(
            **_kwargs(published), dpi=dpi, clip_pt=(31.25, 67.5, 151.75, 110.25),
        )


def test_each_dpi_renders_independently_but_builds_native_page_only_once(monkeypatch):
    producer, published = _ingest(_source_bytes())
    builds = _count_builds(monkeypatch)
    results = [producer.render_native_page_png(
        **_kwargs(published), dpi=dpi, clip_pt=(30, 65, 160, 115),
    )[0] for dpi in [300, 450, 300]]
    assert len(builds) == 1
    assert results[0] == results[2] and results[0] != results[1]


def test_display_list_cache_is_bounded_and_evicted_page_is_rebuilt(monkeypatch):
    producer, published = _ingest(_source_bytes(pages=3))
    builds = _count_builds(monkeypatch)
    for page in [1, 2, 1, 3, 2]:
        producer.render_native_page_png(
            **_kwargs(published, page_id=str(page)), dpi=144, clip_pt=(30, 65, 160, 115),
        )
    assert len(builds) == 4


def test_independent_producers_do_not_share_page_cache(monkeypatch):
    payload = _source_bytes()
    first, a = _ingest(payload, "first-source")
    second, b = _ingest(payload, "second-source")
    builds = _count_builds(monkeypatch)
    for producer, published in [(first, a), (second, b), (first, a)]:
        producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))
    assert len(builds) == 2


@pytest.mark.parametrize("method", ["get_pixmap", "get_displaylist"])
def test_changed_render_hooks_are_respected_even_after_warming_cache(monkeypatch, method):
    producer, published = _ingest(_source_bytes())
    producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))

    def fail(*args, **kwargs):
        raise RuntimeError("render-hook-unavailable")

    monkeypatch.setattr(fitz.Page, method, fail)
    with pytest.raises(RuntimeError, match="render-hook-unavailable"):
        producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))


def test_cached_pixels_do_not_skip_source_integrity_checks():
    producer, published = _ingest(_source_bytes())
    producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))
    producer._store.source_bytes_by_revision[published.revision.revision_id] = _source_bytes(text="REPLACEMENT")
    with pytest.raises(ProducerIntegrityError, match="immutable source hash changed"):
        producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))


def test_new_revision_renders_new_pixels_and_old_revision_still_fails():
    producer, old = _ingest(_source_bytes(text="OLD"))
    before, _ = producer.render_native_page_png(**_kwargs(old), clip_pt=(30, 65, 160, 115))
    new = producer.ingest_native_pdf_bytes(
        document_id=old.revision.document_id, source_bytes=_source_bytes(text="NEW"),
        source_locator="memory://new-render-source.pdf",
    )
    after, parent = producer.render_native_page_png(**_kwargs(new), clip_pt=(30, 65, 160, 115))
    assert before != after and parent.source_sha256 == new.revision.source_sha256
    with pytest.raises(ValueError, match="stale_revision"):
        producer.render_native_page_png(**_kwargs(old), clip_pt=(30, 65, 160, 115))


def test_cache_hit_uses_current_snapshot_parent_defensive_copy():
    producer, published = _ingest(_source_bytes())
    pixels, parent = producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))
    returned = replace(parent, page_id="caller-mutated-copy")
    again, genuine = producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 65, 160, 115))
    assert returned.page_id != genuine.page_id
    assert pixels == again and parent == genuine and parent is not genuine


def test_mutable_retained_page_uses_live_renderer_instead_of_cached_pixels():
    producer, published = _ingest(_source_bytes())
    clip = (30, 65, 160, 115)
    before, _ = producer.render_native_page_png(**_kwargs(published), dpi=144, clip_pt=clip)
    payload = producer._store.source_bytes_by_revision[published.revision.revision_id]
    doc = producer._retained_source_pdf(payload)
    page = doc[0]
    page.draw_rect(clip, fill=(1, 0, 0), overlay=True)
    assert doc.is_dirty
    expected = page.get_pixmap(matrix=fitz.Matrix(2, 2), clip=fitz.Rect(clip), alpha=False).tobytes("png")
    after, _ = producer.render_native_page_png(**_kwargs(published), dpi=144, clip_pt=clip)
    assert after == expected and after != before
