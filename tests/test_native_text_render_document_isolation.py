"""Native text reads must not dirty the retained immutable raster document."""

import fitz
import pytest

from tests.test_source_observation_clip_display_list_cache import _source_bytes, _count_builds
from tests.test_source_observation_render_clip_v1 import _ingest, _kwargs


@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("warm_render", [False, True])
def test_text_fact_reads_leave_exact_raster_reuse_available(monkeypatch, rotation, warm_render):
    payload = _source_bytes(rotation=rotation, annotation=True)
    producer, published = _ingest(payload)
    with fitz.open(stream=payload, filetype="pdf") as doc:
        page = doc[0]
        expected_raw = page.get_text("rawdict", flags=fitz.TEXTFLAGS_WORDS)
        expected_trace = tuple(page.get_texttrace())
        expected_rotation = tuple(page.rotation_matrix)
        expected_png = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            clip=fitz.Rect(30, 65, 160, 115) * page.rotation_matrix,
            alpha=False,
        ).tobytes("png")
    original = fitz.Page.get_text

    def text_read_that_marks_document_dirty(page, *args, **kwargs):
        result = original(page, *args, **kwargs)
        # Model PyMuPDF's native text read bookkeeping, independent of PDF ink.
        page.parent.set_metadata(dict(page.parent.metadata))
        assert page.parent.is_dirty
        return result

    monkeypatch.setattr(fitz.Page, "get_text", text_read_that_marks_document_dirty)
    builds = _count_builds(monkeypatch)
    render_args = dict(**_kwargs(published), dpi=144, clip_pt=(30, 65, 160, 115))
    if warm_render:
        assert producer.render_native_page_png(**render_args)[0] == expected_png
    facts = producer.page_text_facts(payload, 1)
    assert facts[0] == expected_raw
    assert facts[1] == expected_trace
    assert tuple(facts[2]) == expected_rotation
    assert not producer._retained_source_pdf(payload).is_dirty
    assert producer.page_text_facts(payload, 1) is facts
    first, parent = producer.render_native_page_png(**render_args)
    again, parent_again = producer.render_native_page_png(**render_args)
    assert first == again == expected_png
    assert parent == parent_again and parent is not parent_again
    assert len(builds) == 1


@pytest.mark.parametrize("page_number", [0, 3])
def test_invalid_text_page_closes_temporary_document(monkeypatch, page_number):
    payload = _source_bytes(pages=2)
    producer, _ = _ingest(payload)
    retained = producer._retained_source_pdf(payload)
    opened = []
    original = fitz.open

    def tracked(*args, **kwargs):
        doc = original(*args, **kwargs)
        opened.append(doc)
        return doc

    monkeypatch.setattr(fitz, "open", tracked)
    assert producer.page_text_facts(payload, page_number) is None
    assert len(opened) == 1 and opened[0].is_closed
    assert not retained.is_closed and not retained.is_dirty


def test_failed_text_read_closes_temporary_document_and_preserves_renderer(monkeypatch):
    payload = _source_bytes()
    producer, published = _ingest(payload)
    retained = producer._retained_source_pdf(payload)
    opened = []
    original_open = fitz.open

    def tracked(*args, **kwargs):
        doc = original_open(*args, **kwargs)
        opened.append(doc)
        return doc

    def fail(*args, **kwargs):
        raise RuntimeError("native-text-unavailable")

    with monkeypatch.context() as context:
        context.setattr(fitz, "open", tracked)
        context.setattr(fitz.Page, "get_text", fail)
        with pytest.raises(RuntimeError, match="native-text-unavailable"):
            producer.page_text_facts(payload, 1)
    assert len(opened) == 1 and opened[0].is_closed
    assert not retained.is_closed and not retained.is_dirty
    assert producer.render_native_page_png(
        **_kwargs(published), dpi=144, clip_pt=(30, 65, 160, 115),
    )[0]
