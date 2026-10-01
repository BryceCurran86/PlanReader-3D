from __future__ import annotations

from copy import deepcopy
import random
from typing import Mapping, Optional

import fitz

from pb_pdf_exact_fill_geometry import (
    EXACT_FILL_GEOMETRY_OVERLAPPING,
    EXACT_FILL_GEOMETRY_RESOLVED,
    EXACT_FILL_GEOMETRY_UNSUPPORTED,
    exact_disjoint_rectangle_fill_coverage,
    index_drawings_by_seqno,
)
from pb_pdf_text_integrity_authority import (
    TEXT_OCCLUDED_BY_LATER_PAINT,
    _intersection_ratio,
    _later_paint_occlusion_reasons,
    classify_native_word_integrity,
)


class FakePage:
    def __init__(self, drawings):
        self.drawings = deepcopy(drawings)

    def get_drawings(self, *, extended=False):
        assert extended is True
        return deepcopy(self.drawings)


class MissingDrawingPage:
    def get_drawings(self, *, extended=False):
        assert extended is True
        raise RuntimeError("drawing state unavailable")


def _fill_rectangles(
    seqno: int,
    rectangles,
    *,
    drawing_type: str = "f",
    fill=(0.0, 0.0, 0.0),
):
    return {
        "seqno": seqno,
        "type": drawing_type,
        "fill": fill,
        "items": tuple(("re", rect, 1) for rect in rectangles),
    }


def test_neutral_exact_fill_geometry_resolves_only_disjoint_rectangles():
    subject = (40.0, 40.0, 60.0, 50.0)
    resolved = exact_disjoint_rectangle_fill_coverage(
        _fill_rectangles(
            1,
            (
                (0.0, 0.0, 10.0, 10.0),
                (90.0, 90.0, 100.0, 100.0),
            ),
        ),
        subject,
    )
    assert resolved.status == EXACT_FILL_GEOMETRY_RESOLVED
    assert resolved.coverage_ratio == 0.0

    overlap = exact_disjoint_rectangle_fill_coverage(
        _fill_rectangles(
            1,
            (
                (0.0, 0.0, 70.0, 50.0),
                (30.0, 0.0, 100.0, 50.0),
            ),
        ),
        subject,
    )
    assert overlap.status == EXACT_FILL_GEOMETRY_OVERLAPPING
    assert overlap.coverage_ratio is None

    mixed = _fill_rectangles(1, ((0.0, 0.0, 10.0, 10.0),))
    mixed["items"] = (
        ("re", (0.0, 0.0, 10.0, 10.0), 1),
        ("l", (10.0, 10.0), (20.0, 20.0)),
    )
    unsupported = exact_disjoint_rectangle_fill_coverage(mixed, subject)
    assert unsupported.status == EXACT_FILL_GEOMETRY_UNSUPPORTED
    assert unsupported.coverage_ratio is None


def test_drawing_sequence_index_preserves_duplicate_ownership():
    first = _fill_rectangles(7, ((0.0, 0.0, 10.0, 10.0),))
    second = deepcopy(first)
    index = index_drawings_by_seqno((first, second))
    assert tuple(index) == (7,)
    assert len(index[7]) == 2


def test_live_occlusion_clears_only_exact_disconnected_fill_path():
    subject = (40.0, 40.0, 60.0, 50.0)
    bboxlog = (
        ("fill-text", subject),
        ("fill-path", (0.0, 0.0, 100.0, 100.0)),
    )
    page = FakePage(
        (
            _fill_rectangles(
                1,
                (
                    (0.0, 0.0, 10.0, 10.0),
                    (90.0, 90.0, 100.0, 100.0),
                ),
            ),
        )
    )
    assert _later_paint_occlusion_reasons(
        page,
        subject,
        0,
        bboxlog,
    ) == ()


def test_live_occlusion_keeps_real_rectangle_covering_word_blocked():
    subject = (0.0, 0.0, 100.0, 20.0)
    bboxlog = (
        ("fill-text", subject),
        ("fill-path", subject),
    )
    page = FakePage(
        (
            _fill_rectangles(
                1,
                (
                    (0.0, 0.0, 40.0, 20.0),
                    (40.0, 0.0, 70.0, 20.0),
                ),
            ),
        )
    )
    assert _later_paint_occlusion_reasons(
        page,
        subject,
        0,
        bboxlog,
    ) == (TEXT_OCCLUDED_BY_LATER_PAINT,)


def test_live_occlusion_fails_closed_on_overlapping_or_mixed_geometry():
    subject = (0.0, 0.0, 100.0, 20.0)
    bboxlog = (
        ("fill-text", subject),
        ("fill-path", subject),
    )

    overlap = FakePage(
        (
            _fill_rectangles(
                1,
                (
                    (0.0, 0.0, 70.0, 20.0),
                    (30.0, 0.0, 100.0, 20.0),
                ),
            ),
        )
    )
    assert _later_paint_occlusion_reasons(
        overlap,
        subject,
        0,
        bboxlog,
    ) == (TEXT_OCCLUDED_BY_LATER_PAINT,)

    mixed = _fill_rectangles(1, ((0.0, 0.0, 20.0, 20.0),))
    mixed["items"] = (
        ("re", (0.0, 0.0, 20.0, 20.0), 1),
        ("l", (20.0, 0.0), (80.0, 20.0)),
    )
    assert _later_paint_occlusion_reasons(
        FakePage((mixed,)),
        subject,
        0,
        bboxlog,
    ) == (TEXT_OCCLUDED_BY_LATER_PAINT,)


def test_live_occlusion_fails_closed_on_missing_or_duplicate_ownership():
    subject = (0.0, 0.0, 100.0, 20.0)
    bboxlog = (
        ("fill-text", subject),
        ("fill-path", subject),
    )
    drawing = _fill_rectangles(1, ((0.0, 0.0, 20.0, 20.0),))

    assert _later_paint_occlusion_reasons(
        MissingDrawingPage(),
        subject,
        0,
        bboxlog,
    ) == (TEXT_OCCLUDED_BY_LATER_PAINT,)

    assert _later_paint_occlusion_reasons(
        FakePage((drawing, deepcopy(drawing))),
        subject,
        0,
        bboxlog,
    ) == (TEXT_OCCLUDED_BY_LATER_PAINT,)


def test_clear_exact_fill_does_not_hide_later_non_path_occluder():
    subject = (0.0, 0.0, 100.0, 20.0)
    bboxlog = (
        ("fill-text", subject),
        ("fill-path", subject),
        ("fill-image", subject),
    )
    page = FakePage(
        (
            _fill_rectangles(1, ((0.0, 40.0, 10.0, 50.0),)),
        )
    )
    assert _later_paint_occlusion_reasons(
        page,
        subject,
        0,
        bboxlog,
    ) == (TEXT_OCCLUDED_BY_LATER_PAINT,)


def _pdf_bytes(objects: Mapping[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    position = len(header)
    for number in sorted(objects):
        offsets[number] = position
        chunk = (
            f"{number} 0 obj\n".encode("ascii")
            + objects[number].encode("latin1")
            + b"\nendobj\n"
        )
        chunks.append(chunk)
        position += len(chunk)
    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        xref.append(
            f"{offsets[number]:010d} 00000 n \n"
            if number in offsets
            else "0000000000 00000 f \n"
        )
    trailer = (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{position}\n%%EOF\n"
    )
    return (
        b"".join(chunks)
        + "".join(xref).encode("ascii")
        + trailer.encode("ascii")
    )


def _pdf(stream: str) -> bytes:
    font = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
            "/Resources << /Font << /F1 5 0 R >> >> "
            "/Contents 4 0 R >>"
        ),
        4: (
            f"<< /Length {len(stream.encode('latin1'))} >>\n"
            f"stream\n{stream}\nendstream"
        ),
        5: font,
    }
    return _pdf_bytes(objects)


def _classify(pdf: bytes):
    doc = fitz.open(stream=pdf, filetype="pdf")
    page = doc[0]
    words = page.get_text("words")
    assert len(words) == 1
    word = words[0]
    decision = classify_native_word_integrity(
        page,
        {"text": word[4], "bbox": tuple(word[:4])},
    )
    return page, tuple(word[:4]), decision


def test_real_pdf_disconnected_compound_fill_no_longer_false_occludes():
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (900) Tj ET "
        "0 0 10 10 re 290 190 10 10 re f"
    )
    page, word_bbox, decision = _classify(pdf)

    later_fills = [
        item
        for item in page.get_bboxlog()
        if str(item[0]) == "fill-path"
    ]
    assert len(later_fills) == 1
    assert _intersection_ratio(word_bbox, later_fills[0][1]) >= 0.65
    assert decision.trusted, decision.reason_codes
    assert TEXT_OCCLUDED_BY_LATER_PAINT not in decision.reason_codes


def test_real_pdf_opaque_rectangle_over_word_remains_blocked():
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (900) Tj ET "
        "30 105 100 35 re f"
    )
    page, word_bbox, decision = _classify(pdf)

    later_fills = [
        item
        for item in page.get_bboxlog()
        if str(item[0]) == "fill-path"
    ]
    assert len(later_fills) == 1
    assert _intersection_ratio(word_bbox, later_fills[0][1]) >= 0.65
    assert not decision.trusted
    assert TEXT_OCCLUDED_BY_LATER_PAINT in decision.reason_codes


def test_later_paint_spatial_index_matches_exhaustive_scan_randomized():
    rng = random.Random(20261002)
    kinds = ("fill-image", "fill-shade", "fill-text", "stroke-path", "stroke-text")

    for case in range(40):
        bboxlog = []
        for _ in range(350):
            x0 = rng.uniform(-200.0, 1800.0)
            y0 = rng.uniform(-200.0, 1200.0)
            width = rng.uniform(1.0, 300.0)
            height = rng.uniform(1.0, 180.0)
            bboxlog.append((rng.choice(kinds), (x0, y0, x0 + width, y0 + height)))

        sx0 = rng.uniform(0.0, 1500.0)
        sy0 = rng.uniform(0.0, 900.0)
        subject = (sx0, sy0, sx0 + rng.uniform(5.0, 120.0), sy0 + rng.uniform(5.0, 60.0))
        text_seqno = rng.randrange(0, len(bboxlog) - 1)
        threshold = rng.choice((0.1, 0.35, 0.65, 0.9))

        expected = ()
        for item in bboxlog[text_seqno + 1 :]:
            kind, paint_bbox = item
            if kind not in {"fill-image", "fill-shade", "fill-text"}:
                continue
            if _intersection_ratio(subject, paint_bbox) >= threshold:
                expected = (TEXT_OCCLUDED_BY_LATER_PAINT,)
                break

        actual = _later_paint_occlusion_reasons(
            FakePage(()),
            subject,
            text_seqno,
            tuple(bboxlog),
            threshold=threshold,
        )
        assert actual == expected, f"random case {case} diverged"
