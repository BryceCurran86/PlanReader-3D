"""An extracted PDF path is not evidence of a visible physical frame."""
from dataclasses import asdict

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_opening_elevation_frame_area_authority import (
    OpeningElevationFrameAreaProducer, _source_painted_geometry_ids,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_opening_elevation_frame_area_authority import _elevation_pdf, _selector


def _payload(mode="stroke", *, rotation=0):
    doc = fitz.open(stream=_elevation_pdf(), filetype="pdf")
    page = doc[0]
    frame = [xref for xref in page.get_contents() if b" re" in doc.xref_stream(xref)]
    assert len(frame) == 1
    stream = doc.xref_stream(frame[0])
    assert b"0 G S" in stream
    replacements = {
        "white-fill": b"1 g f", "black-fill": b"0 g f",
        "white-stroke": b"1 G S", "dashed": b"[4 4] 0 d\n0 G S",
    }
    if mode in replacements:
        stream = stream.replace(b"0 G S", replacements[mode])
    if mode == "split-edges":
        stream = (b"q\n0 G\n150 160 m 300 160 l S\n300 160 m 300 280 l S\n"
                  b"300 280 m 150 280 l S\n150 280 m 150 160 l S\nQ\n")
    if mode.startswith("opacity-"):
        opacity = float(mode.removeprefix("opacity-"))
        resources = int(doc.xref_get_key(page.xref, "Resources")[1].split()[0])
        doc.xref_set_key(resources, "ExtGState", f"<< /FrameOpacity << /CA {opacity} >> >>")
        stream = stream.replace(b"q\n", b"q\n/FrameOpacity gs\n", 1)
    clips = {
        "contained-clip": b"140 150 170 140 re W n\n",
        "excluding-clip": b"150 150 50 140 re W n\n",
        "irregular-clip": b"0 0 m 500 0 l 0 400 l h W n\n",
    }
    if mode in clips:
        stream = stream.replace(b"q\n", b"q\n" + clips[mode], 1)
    doc.update_stream(frame[0], stream)
    if mode == "later-white-mask":
        page.draw_rect(fitz.Rect(149, 119, 151, 241), color=None, fill=(1, 1, 1))
    elif mode == "later-image":
        pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 2, 2), False)
        pix.clear_with(255)
        page.insert_image(fitz.Rect(149, 119, 151, 241), pixmap=pix)
    elif mode == "unrelated-fill":
        page.draw_rect(fitz.Rect(400, 300, 410, 310), color=None, fill=(1, 1, 1))
    elif mode == "same-black-retrace":
        page.draw_rect(fitz.Rect(150, 120, 300, 240), color=(0, 0, 0), width=1)
    page.set_rotation(rotation)
    payload = doc.tobytes()
    doc.close()
    return payload


def _resolve(payload):
    source = SourceVisibilityProducer(producer_method="elevation-paint-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="elevation", source_bytes=payload, source_locator="memory://elevation.pdf",
    )
    producer = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source)
    result = producer.authority().resolve(_selector(published, "W1"))
    return source, published, result


@pytest.mark.parametrize("mode", [
    "white-fill", "black-fill", "white-stroke", "dashed", "opacity-0", "opacity-0.5",
    "excluding-clip", "irregular-clip", "later-white-mask", "later-image",
])
def test_unproved_or_erased_frame_cannot_publish_area(mode):
    _, _, positive = _resolve(_payload())
    assert positive.status is S.CORROBORATED and positive.record.area_m2 == pytest.approx(7.2)
    _, _, result = _resolve(_payload(mode))
    assert result.status is S.ABSTAINED and result.record is None


@pytest.mark.parametrize("mode", ["stroke", "contained-clip", "unrelated-fill", "same-black-retrace", "split-edges"])
@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_source_stroked_frame_and_non_erasing_content_preserve_metric(mode, rotation):
    payload = _payload(mode, rotation=rotation)
    source, published, result = _resolve(payload)
    if mode == "contained-clip" and rotation:
        # The existing native clip authority cannot authenticate the rotated
        # clip/geometry association; a visually plausible box cannot replace it.
        assert result.status is S.ABSTAINED and result.record is None
        return
    assert result.status is S.CORROBORATED, result.reason_codes
    assert result.record.area_m2 == pytest.approx(7.2)
    assert sorted((result.record.axis_x_mm, result.record.axis_y_mm)) == [2400., 3000.]
    before = asdict(source.published_snapshot_for_revision(published.revision.revision_id))
    again = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source).authority().resolve(_selector(published, "W1"))
    assert again == result
    assert asdict(source.published_snapshot_for_revision(published.revision.revision_id)) == before


@pytest.mark.parametrize("offset,scale", [((40, 20), 1.), ((0, 0), 1.2), ((30, 30), 0.75)])
def test_translation_and_uniform_scale_preserve_source_figured_area(offset, scale):
    with fitz.open(stream=_payload(), filetype="pdf") as original:
        doc = fitz.open()
        page = doc.new_page(width=700, height=600)
        dx, dy = offset
        page.show_pdf_page(fitz.Rect(dx, dy, dx + 500 * scale, dy + 400 * scale), original, 0)
        payload = doc.tobytes()
        doc.close()
    _, _, result = _resolve(payload)
    assert result.status is S.CORROBORATED, result.reason_codes
    assert result.record.area_m2 == pytest.approx(7.2)


def test_fill_boundary_remains_in_raw_source_but_never_painted_support():
    payload = _payload("white-fill")
    with fitz.open(stream=payload, filetype="pdf") as doc:
        page = doc[0]
        assert any(d["type"] == "f" and d["fill"] == (1., 1., 1.) for d in page.get_drawings())
        assert not any(i.startswith("vec_p1_0_0_e") for i in _source_painted_geometry_ids(page, "1"))
