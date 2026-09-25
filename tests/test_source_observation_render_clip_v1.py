"""render_native_page_png(clip_pt=...) contract tests.

``clip_pt`` is an optional PDF page-space region rendered with the PDF
renderer's own clip. ``None`` must preserve existing full-page behaviour
exactly; an invalid or out-of-page clip is rejected, never clamped; every
lineage check is unchanged.
"""
from __future__ import annotations

import io
import math

import fitz
import pytest
from PIL import Image

from pb_source_observation_authority import (
    INVALID_RENDER_CLIP,
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    STALE_REVISION,
    SourceObservationProducer,
)

DOC = "doc-render-clip"


def _pdf(text: str = "Alpha 900", *, width: float = 300.0, height: float = 200.0) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    page.insert_text((40, 100), text, fontsize=14)
    page.draw_rect(fitz.Rect(20, 20, 120, 60), width=1)
    data = doc.tobytes()
    doc.close()
    return data


def _ingest(payload: bytes | None = None, document_id: str = DOC):
    producer = SourceObservationProducer(producer_method="render-clip-test", producer_version="1")
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload or _pdf(),
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published


def _kwargs(published, **overrides):
    args = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
    )
    args.update(overrides)
    return args


def _image(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png)).convert("RGB")


def test_none_clip_is_byte_identical_to_the_previous_full_page_behaviour() -> None:
    producer, published = _ingest()
    baseline, parent = producer.render_native_page_png(**_kwargs(published), dpi=200.0)
    explicit, parent2 = producer.render_native_page_png(**_kwargs(published), dpi=200.0, clip_pt=None)
    assert baseline == explicit
    assert parent == parent2
    # and identical to rendering the same immutable bytes directly
    doc = fitz.open(stream=_pdf(), filetype="pdf")
    s = 200.0 / 72.0
    expected = doc[0].get_pixmap(matrix=fitz.Matrix(s, s), alpha=False).tobytes("png")
    assert baseline == expected


def test_valid_clip_renders_only_the_region_and_matches_the_full_render_pixels() -> None:
    producer, published = _ingest()
    clip = (36.0, 72.0, 108.0, 108.0)  # integer-aligned at 144 dpi (scale 2)
    png, parent = producer.render_native_page_png(**_kwargs(published), dpi=144.0, clip_pt=clip)
    full, full_parent = producer.render_native_page_png(**_kwargs(published), dpi=144.0)
    cropped = _image(png)
    assert cropped.size == (int((108 - 36) * 2), int((108 - 72) * 2))
    assert _image(full).size == (600, 400)
    reference = _image(full).crop((72, 144, 216, 216))
    assert cropped.tobytes() == reference.tobytes()
    assert parent == full_parent  # page-parent lineage is unchanged by the clip


def test_clip_uses_the_renderer_clip_facility_not_a_full_render_then_crop(monkeypatch) -> None:
    producer, published = _ingest()
    seen: list[dict] = []
    original = fitz.Page.get_pixmap

    def spy(self, *args, **kwargs):
        seen.append(dict(kwargs))
        return original(self, *args, **kwargs)

    monkeypatch.setattr(fitz.Page, "get_pixmap", spy)
    producer.render_native_page_png(**_kwargs(published), dpi=300.0, clip_pt=(30, 30, 90, 70))
    assert len(seen) == 1
    assert "clip" in seen[0] and tuple(seen[0]["clip"]) == (30.0, 30.0, 90.0, 70.0)


@pytest.mark.parametrize(
    "clip",
    [
        (10.0, 10.0),  # wrong arity
        (10.0, 10.0, 50.0, 50.0, 60.0),
        (float("nan"), 10.0, 50.0, 50.0),
        (10.0, 10.0, float("inf"), 50.0),
        (10.0, 10.0, 10.0, 50.0),  # zero width
        (10.0, 50.0, 40.0, 50.0),  # zero height
        (50.0, 10.0, 10.0, 50.0),  # negative width
        (10.0, 50.0, 40.0, 10.0),  # negative height
        (-0.5, 10.0, 50.0, 50.0),  # left of the page
        (10.0, -0.5, 50.0, 50.0),
        (10.0, 10.0, 300.5, 50.0),  # right of the page
        (10.0, 10.0, 50.0, 200.5),
        (250.0, 150.0, 350.0, 250.0),  # partially outside: rejected, never clamped
        ("10", 10.0, 50.0, 50.0),  # non-numeric
        (True, 10.0, 50.0, 50.0),
        (None, 10.0, 50.0, 50.0),
    ],
)
def test_invalid_or_out_of_page_clips_are_rejected_not_clamped(clip) -> None:
    producer, published = _ingest()
    with pytest.raises(ValueError, match=INVALID_RENDER_CLIP):
        producer.render_native_page_png(**_kwargs(published), clip_pt=clip)


def test_clip_covering_exactly_the_page_is_accepted() -> None:
    producer, published = _ingest()
    png, _parent = producer.render_native_page_png(
        **_kwargs(published), dpi=72.0, clip_pt=(0.0, 0.0, 300.0, 200.0)
    )
    assert _image(png).size == (300, 200)


def test_stale_revision_is_rejected_even_with_a_valid_clip() -> None:
    producer, published = _ingest(_pdf("Old"))
    producer.ingest_native_pdf_bytes(
        document_id=DOC, source_bytes=_pdf("New"), source_locator="memory://new.pdf"
    )
    with pytest.raises(ValueError, match=STALE_REVISION):
        producer.render_native_page_png(**_kwargs(published), clip_pt=(30, 30, 90, 70))


def test_wrong_sha_is_rejected_even_with_a_valid_clip() -> None:
    producer, published = _ingest()
    with pytest.raises(ValueError, match=SOURCE_HASH_MISMATCH):
        producer.render_native_page_png(
            **_kwargs(published, source_sha256="0" * 64), clip_pt=(30, 30, 90, 70)
        )


def test_wrong_snapshot_is_rejected_even_with_a_valid_clip() -> None:
    producer, published = _ingest()
    with pytest.raises(ValueError, match=SNAPSHOT_MISMATCH):
        producer.render_native_page_png(
            **_kwargs(published, snapshot_id="snapshot-that-does-not-exist"), clip_pt=(30, 30, 90, 70)
        )


def test_clipped_rendering_is_deterministic() -> None:
    producer, published = _ingest()
    a, pa = producer.render_native_page_png(**_kwargs(published), dpi=450.0, clip_pt=(38.3, 88.1, 71.9, 104.7))
    b, pb = producer.render_native_page_png(**_kwargs(published), dpi=450.0, clip_pt=(38.3, 88.1, 71.9, 104.7))
    assert a == b and pa == pb


def test_clip_scale_is_proportional_to_dpi() -> None:
    producer, published = _ingest()
    clip = (30.0, 80.0, 90.0, 110.0)
    small = _image(producer.render_native_page_png(**_kwargs(published), dpi=300.0, clip_pt=clip)[0])
    large = _image(producer.render_native_page_png(**_kwargs(published), dpi=450.0, clip_pt=clip)[0])
    assert math.isclose(large.width / small.width, 1.5, rel_tol=0.02)
    assert math.isclose(large.height / small.height, 1.5, rel_tol=0.02)


def test_swapped_page_uses_that_pages_own_pixels_and_parent() -> None:
    doc = fitz.open()
    p1 = doc.new_page(width=300, height=200)
    p1.insert_text((40, 100), "AAAA", fontsize=20)
    p2 = doc.new_page(width=300, height=200)
    p2.insert_text((40, 100), "BBBB", fontsize=20)
    payload = doc.tobytes()
    doc.close()
    producer, published = _ingest(payload)
    clip = (30.0, 80.0, 120.0, 110.0)
    a, parent_a = producer.render_native_page_png(**_kwargs(published, page_id="1"), dpi=150.0, clip_pt=clip)
    b, parent_b = producer.render_native_page_png(**_kwargs(published, page_id="2"), dpi=150.0, clip_pt=clip)
    assert a != b
    assert parent_a.page_id == "1" and parent_b.page_id == "2"
    assert parent_a.observation_id != parent_b.observation_id
