"""Prove bounded page segmentation cache cannot change physical scale authority."""
from __future__ import annotations

from dataclasses import replace

import pb_physical_scale_authority as scale_module
from pb_physical_scale_authority import PhysicalScaleProducer
from test_physical_scale_page_input_index import _multi_page_scale_pdf, _selector, _source


def test_one_source_page_segmentation_shared_across_viewports(monkeypatch):
    source, published = _source(page_count=2)
    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    original = scale_module.segment_page_viewports
    calls = []

    def observed(page, *, page_number):
        calls.append(page_number)
        return original(page, page_number=page_number)

    monkeypatch.setattr(scale_module, "segment_page_viewports", observed)
    monkeypatch.setattr(scale_module, "segment_source_page_viewports",
                        lambda *a, **kw: ())
    payload = _multi_page_scale_pdf(page_count=2)
    first = _selector(published, "1")
    result = producer._scope_bbox(first, payload)
    second = replace(first, viewport_id="nonexistent-source-viewport")
    producer._scope_bbox(second, payload)
    assert calls == [1]
    assert result == PhysicalScaleProducer.from_source_visibility_producer(
        source,
    )._scope_bbox(first, payload)

    producer._scope_bbox(replace(first, page_id="2"), payload)
    producer._scope_bbox(replace(first, revision_id="different-revision"), payload)
    assert calls == [1, 1, 2, 1]


def test_page_cache_bounded_and_new_page_forces_new_segmentation(monkeypatch):
    source, published = _source(page_count=5)
    producer = PhysicalScaleProducer.from_source_visibility_producer(source)
    data = _multi_page_scale_pdf(5)
    original = scale_module.segment_page_viewports
    seen = []

    def observed(page, *, page_number):
        seen.append(page_number)
        return original(page, page_number=page_number)

    monkeypatch.setattr(scale_module, "segment_page_viewports", observed)
    for number in range(1, 6):
        producer._scope_bbox(_selector(published, str(number)), data)
    assert len(producer._page_viewports_cache) == 4
    assert seen == [1, 2, 3, 4, 5]
    producer._scope_bbox(_selector(published, "1"), data)
    assert seen[-1] == 1
