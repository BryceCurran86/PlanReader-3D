"""Regression tests for indexed later-paint text occlusion candidates."""
from __future__ import annotations

import pb_pdf_text_integrity_authority as text_auth


class _Page:
    pass


_RELEVANT = {"fill-path", "fill-image", "fill-shade", "fill-text"}


def _reference_later_paint(
    subject_bbox,
    text_sequence_number: int,
    bboxlog,
    *,
    threshold: float = 0.65,
):
    for seqno, item in enumerate(bboxlog):
        if seqno <= text_sequence_number:
            continue
        try:
            kind, bbox = str(item[0]), item[1]
        except (IndexError, TypeError):
            continue
        if kind not in _RELEVANT:
            continue
        if text_auth._intersection_ratio(subject_bbox, bbox) < threshold:
            continue
        if kind == "fill-path":
            # This reference is used only by tests that monkeypatch exact
            # coverage identically for production and reference paths.
            coverage = _REFERENCE_COVERAGE.get(seqno)
            if coverage is not None and coverage < threshold:
                continue
        return (text_auth.TEXT_OCCLUDED_BY_LATER_PAINT,)
    return ()

_REFERENCE_COVERAGE: dict[int, float | None] = {}


def test_indexed_later_paint_matches_tail_scan_on_dense_log(monkeypatch) -> None:
    page = _Page()
    subject = (100.0, 100.0, 120.0, 120.0)
    bboxlog = []
    for index in range(8000):
        x = 1000.0 + float(index % 100) * 20.0
        y = 1000.0 + float(index // 100) * 20.0
        bboxlog.append(("fill-image", (x, y, x + 5.0, y + 5.0)))

    # First plausible fill-path does not cover enough; the later image does.
    bboxlog[6000] = ("fill-path", (99.0, 99.0, 121.0, 121.0))
    bboxlog[7000] = ("fill-image", (99.0, 99.0, 121.0, 121.0))
    _REFERENCE_COVERAGE.clear()
    _REFERENCE_COVERAGE[6000] = 0.20
    monkeypatch.setattr(
        text_auth,
        "_exact_fill_path_coverage",
        lambda _page, _bbox, seqno: _REFERENCE_COVERAGE.get(seqno),
    )

    for text_seqno in (0, 5999, 6000, 6999, 7000):
        expected = _reference_later_paint(
            subject,
            text_seqno,
            bboxlog,
        )
        actual = text_auth._later_paint_occlusion_reasons(
            page,
            subject,
            text_seqno,
            bboxlog,
        )
        assert actual == expected

def test_spatial_index_prunes_non_overlapping_later_paints() -> None:
    page = _Page()
    subject = (10.0, 10.0, 20.0, 20.0)
    bboxlog = [
        (
            "fill-image",
            (
                1000.0 + float(index % 200) * 8.0,
                1000.0 + float(index // 200) * 8.0,
                1004.0 + float(index % 200) * 8.0,
                1004.0 + float(index // 200) * 8.0,
            ),
        )
        for index in range(20000)
    ]
    bboxlog[19000] = ("fill-image", (9.0, 9.0, 21.0, 21.0))

    paint_seqnos, paints = text_auth._cached_occluding_paints(page, bboxlog)
    start = text_auth.bisect_right(paint_seqnos, 100)
    positions = text_auth._candidate_occluding_paint_positions(
        page,
        subject,
        bboxlog,
        start=start,
    )

    assert len(paints) == 20000
    assert positions == (19000,)
    assert text_auth._later_paint_occlusion_reasons(
        page,
        subject,
        100,
        bboxlog,
    ) == (text_auth.TEXT_OCCLUDED_BY_LATER_PAINT,)
