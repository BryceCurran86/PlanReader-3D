"""Generic original-source closed tiled face positives and adversarial abstentions.

All fixtures are synthetic. No Q5446 coordinates, PDF bytes, benchmark answers
or gold filenames are present. Private original replay is a separate test.
"""
from __future__ import annotations

import fitz
import pytest

import pb_source_native_tiled_room_face_authority as a


def _path(points, width=0.24):
    segs = [
        ("l", fitz.Point(*u), fitz.Point(*v))
        for u, v in zip(points[:-1], points[1:])
    ]
    x = [p[0] for p in points]
    y = [p[1] for p in points]
    return {
        "type": "s", "width": width, "color": (0.0, 0.0, 0.0),
        "rect": fitz.Rect(min(x), min(y), max(x), max(y)),
        "items": segs,
    }


def _fixture(include_hatch=True, include_wall=True, duplicate=False):
    # Full finished-face rectangle with a small door threshold return and
    # an inset fixture, all owned by a single genuinely closed source path.
    ring = [(50, 100), (50, 77), (60, 77), (60, 65), (50, 65),
            (50, 50), (110, 50), (110, 70), (111, 70), (111, 87),
            (110, 87), (110, 100), (50, 100)]
    drawings = [_path(ring)]
    if include_wall:
        drawings += [
            _path([(50, 50), (50, 100)], width=.96),
            _path([(110, 50), (110, 74)], width=.96),
            _path([(110, 80), (110, 100)], width=.96),
            _path([(50, 50), (110, 50)], width=.96),
            _path([(50, 100), (110, 100)], width=.96),
        ]
    if include_hatch:
        for n in range(13):
            x, y = 66 + 3 * n, 56 + 3 * n
            drawings.append(_path([(x, 59), (x, 69)]))
            drawings.append(_path([(65, y), (75, y)]))
    if duplicate:
        drawings.append(_path(ring))
    return drawings


class _Page:
    def __init__(self, drawings):
        self._doc = fitz.open()
        self._page = self._doc.new_page(width=200, height=200)
        self.drawings = drawings

    def get_drawings(self):
        return self.drawings

    def get_pixmap(self, **kwargs):
        return self._page.get_pixmap(**kwargs)

    def close(self):
        self._doc.close()


class _OCR:
    token = "ENS'"
    low_confidence = False
    mismatch_at_288 = False
    extra_match = False
    low_confidence_at_288 = False
    conflict_position_at_360 = False

    def is_available(self):
        return True

    def extract_lines(self, image, dpi=150):
        from pb_portable_raster_ocr_authority import OCRLine
        token = "BED" if self.mismatch_at_288 and dpi == 288 else self.token
        conf = .7 if self.low_confidence else (.88 if self.low_confidence_at_288 and dpi == 288 else .99)
        witness = OCRLine(
            text=token, confidence=conf,
            bbox_px=(100, 80, 160, 132),
            bbox_pt=(55, 22, 70, 34) if self.conflict_position_at_360 and dpi == 360 else (25, 22, 40, 34),
        )
        if self.extra_match:
            return (witness, witness)
        return (witness,)


@pytest.fixture
def ocr(monkeypatch):
    class Configured(_OCR):
        pass
    monkeypatch.setattr(a, "RapidOCRBackend", Configured)
    return Configured


def test_closed_original_source_tiled_face_is_recovered_but_not_commercial(ocr):
    page = _Page(_fixture())
    try:
        result = a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        )
        assert isinstance(result, a.NativeTiledRoomFace)
        assert result.source_boundary_path_id == 0
        assert result.source_bbox_pts == (50, 50, 110, 100)
        assert result.finished_width_pts == 60
        assert result.finished_depth_pts == 50
        assert result.room_label == "ENS"
        assert len(result.wall_support_source_path_ids) >= 4
        assert len(result.hatch_support_source_path_ids) >= 20
        assert result.raster_ocr_render_dpis == (216, 288, 360)
        assert result.physical_source_verified
        assert result.commercial_permission is False
    finally:
        page.close()


@pytest.mark.parametrize("kwargs", [
    {"include_hatch": False},
    {"include_wall": False},
    {"duplicate": True},
])
def test_unowned_or_duplicate_tiled_face_never_promotes(kwargs, ocr):
    page = _Page(_fixture(**kwargs))
    try:
        assert a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        ) is None
    finally:
        page.close()


@pytest.mark.parametrize("config", [
    {"token": "BED"},
    {"low_confidence": True},
    {"mismatch_at_288": True},
    {"extra_match": True},
])
def test_missing_conflicted_or_low_confidence_ocr_cannot_name_face(config, ocr):
    for key, value in config.items():
        setattr(ocr, key, value)
    page = _Page(_fixture())
    try:
        assert a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        ) is None
    finally:
        page.close()


def test_unbounded_foreign_page_and_non_room_labels_abstain(ocr):
    page = _Page(_fixture())
    try:
        for n, label in ((0, "ENS"), (1, ""), (1, " " * 10),
                         (1, "X" * 50)):
            assert a.find_unique_native_tiled_room_face(
                page=page, page_number=n, room_label=label,
            ) is None
    finally:
        page.close()


def test_open_ring_and_crossing_source_ink_abstain():
    ring = _fixture()[0]
    assert a._candidate_ring(ring) is not None
    broken = {**ring, "items": ring["items"][:-1]}
    assert a._candidate_ring(broken) is None
    crossed = _path([
        (50, 50), (110, 50), (110, 100), (50, 100), (50, 75),
        (115, 75), (50, 50),
    ])
    assert a._candidate_ring(crossed) is None


def test_two_source_local_confident_renders_recover_an_ambiguous_middle_view(ocr):
    ocr.low_confidence_at_288 = True
    page = _Page(_fixture())
    try:
        result = a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        )
        assert result is not None
        assert result.raster_ocr_render_dpis == (216, 360)
        assert result.commercial_permission is False
    finally:
        page.close()


def test_conflicting_raster_position_abstains_even_when_two_others_match(ocr):
    ocr.conflict_position_at_360 = True
    page = _Page(_fixture())
    try:
        assert a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        ) is None
    finally:
        page.close()


def test_confident_different_room_label_blocks_majority_promotion(ocr):
    ocr.mismatch_at_288 = True
    page = _Page(_fixture())
    try:
        assert a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        ) is None
    finally:
        page.close()


def test_native_source_float_tolerances_do_not_reject_exact_closed_face():
    """Original Q5446 p2 1982 had rounded bounds 0.000018pt too tall."""
    # These numbers are a synthetic float-representation example, not a
    # benchmark target or a source PDF copy. Ring geometry remains unmodified.
    points = [(50, 60.00002), (110, 60.00002), (110, 75),
              (112, 75), (112, 80), (110, 80), (110, 120.0),
              (50, 120.0), (50, 60.00002)]
    source_ring = _path(points)
    candidate = a._candidate_ring(source_ring)
    assert candidate is not None
    polygon, box = candidate
    assert polygon.is_valid and polygon.is_simple
    assert box == (50.0, 60.00002, 110.0, 120.0)
    assert box[3] - box[1] <= polygon.bounds[3] - polygon.bounds[1]
    # A ring candidate is only ink geometry: still cannot publish a floor.
    page = _Page([source_ring])
    try:
        assert a.find_unique_native_tiled_room_face(
            page=page, page_number=1, room_label="ENS",
        ) is None
    finally:
        page.close()
