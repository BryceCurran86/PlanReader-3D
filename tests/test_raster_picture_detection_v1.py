"""Picture walls from the picture alone on pages that mix pictures and line work, default off (MAX 7230726656).

Synthetic only."""
from __future__ import annotations

import hashlib

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_raster_visible_segment_detector import detect_axis_aligned_raster_segments
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector, _decision_scope_id
from pb_source_visibility_authority import (
    RASTER_PICTURE_SEGMENT_IDENTITY_VERSION, RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION, SourceVisibilityProducer,
)
from pb_source_observation_authority import ObservationSelector


def _picture():
    pixels = np.full((400, 400), 255, dtype=np.uint8)
    pixels[198:202, 40:240] = 0  # the picture's own line: page y = 100, x 30..180 when placed at (0, 0, 300, 200)
    return fitz.Pixmap(fitz.csGRAY, 400, 400, pixels.tobytes(), False)


def _page(*, picture=True, lines=True, text=True):
    document = fitz.open()
    page = document.new_page(width=300, height=300)
    if picture:
        page.insert_image(fitz.Rect(0, 0, 300, 200), pixmap=_picture(), keep_proportion=False)
    if lines:
        page.draw_line((100, 100), (260, 100), color=(0, 0, 0), width=1.0)  # continues the picture line past it
        page.draw_line((20, 140), (180, 140), color=(0, 0, 0), width=1.0)  # drawn over the picture
    if text:
        page.insert_text((40, 60), "IIIIIIIIIIIIIIIIIIIIII", fontsize=18)
    data = document.tobytes()
    document.close()
    return data


def _capture(data, **options):
    source = SourceVisibilityProducer(producer_method="picture-detect-test", producer_version="1", **options)
    published = source.ingest_native_pdf_bytes(document_id="picture", source_bytes=data, source_locator="memory://p.pdf")
    published = source.augment_with_raster_visible_segments(published.revision.revision_id)
    snapshot = published.snapshot.snapshot_id
    segments = {record.observation_id: record for (sid, _o), record in source._producer._store.observations.items()
                if sid == snapshot and str(record.source_primitive_ref).startswith("raster_segment:")}
    return source, published, segments


def _horizontal(segments):
    return sorted((round(g[1]), round(min(g[0], g[2])), round(max(g[0], g[2])))
                  for g in (r.geometry for r in segments.values()) if abs(g[3] - g[1]) < 1)


def test_the_picture_line_stays_whole_and_nothing_drawn_over_it_is_seen():
    data = _page()
    _s, _p, off = _capture(data)
    _s, _p, on = _capture(data, raster_picture_detection_shadow=True)
    # today the full render joins the picture line with the drawn continuation and sees the drawn line and letters
    assert any(y == 100 and x1 > 250 for y, _x0, x1 in _horizontal(off))
    assert any(y == 140 for y, _x0, _x1 in _horizontal(off))
    assert _horizontal(on) == [(100, 30, 180)]
    assert not any(r.geometry[1] < 80 for r in on.values())


def test_every_picture_segment_is_bound_to_the_images_only_render_and_verifies():
    data = _page()
    source, published, on = _capture(data, raster_picture_detection_shadow=True)
    png = source._producer.render_native_page_png(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id, page_id="1",
        dpi=144.0, images_only=True)[0]
    sha = hashlib.sha256(png).hexdigest()
    parts = [str(r.source_primitive_ref).split(":") for r in on.values()]
    assert parts and all(p[1] == sha and p[2] == RASTER_PICTURE_SEGMENT_IDENTITY_VERSION for p in parts)
    authority = source.authority()
    visible = [record.observation_id for (sid, _o), record in source._producer._store.observations.items()
               if sid == published.snapshot.snapshot_id
               and str(record.source_primitive_ref).startswith("visible:raster_segment:")]
    assert visible
    for observation_id in visible:
        resolved = authority.resolve_visible(ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id))
        assert resolved.status is EvidenceResolutionStatus.CORROBORATED


def test_the_wall_candidates_cover_the_picture_part_and_the_drawn_part():
    data = _page(text=False)
    source, published, _on = _capture(data, raster_picture_detection_shadow=True)
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    scope = authority.resolve_scope(PhysicalWallCandidateSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        page_id="1", decision_scope_id=_decision_scope_id("1")))
    spans = [(min(p[0] for p in r.wall_candidate.centerline_pts), max(p[0] for p in r.wall_candidate.centerline_pts))
             for r in scope.records if all(abs(p[1] - 100) < 2 for p in r.wall_candidate.centerline_pts)]
    assert min(lo for lo, _hi in spans) <= 32 and max(hi for _lo, hi in spans) >= 258


def test_default_off_is_exactly_the_historical_capture():
    data = _page()
    off = _capture(data)[2]
    explicit = _capture(data, raster_picture_detection_shadow=False)[2]
    assert sorted(off) == sorted(explicit)
    assert {str(r.source_primitive_ref).split(":")[2] for r in off.values()} == {RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION}


@pytest.mark.parametrize("kwargs", [dict(lines=False, text=False), dict(picture=False)], ids=["scan", "no-picture"])
def test_pure_pictures_and_pages_without_pictures_are_not_affected(kwargs):
    data = _page(**kwargs)
    assert sorted(_capture(data)[2]) == sorted(_capture(data, raster_picture_detection_shadow=True)[2])


def _faint_and_dark_picture():
    pixels = np.full((400, 400), 255, dtype=np.uint8)
    pixels[10:50, 20:380] = 0  # a dark block in the picture
    pixels[200:202, 40:360] = 150  # and a faint wall line: page y = 100
    return fitz.Pixmap(fitz.csGRAY, 400, 400, pixels.tobytes(), False)


def test_a_faint_picture_line_keeps_the_full_pages_threshold():
    document = fitz.open()
    page = document.new_page(width=200, height=200)
    page.insert_image(fitz.Rect(0, 0, 200, 200), pixmap=_faint_and_dark_picture())
    grey = (150 / 255,) * 3
    page.draw_rect(fitz.Rect(10, 110, 190, 170), color=None, fill=grey)  # grey drawn work elsewhere on the page
    page.draw_line((10, 190), (190, 190), color=(0, 0, 0), width=1.0)
    data = document.tobytes()
    document.close()
    _s, _p, off = _capture(data)
    _s, _p, on = _capture(data, raster_picture_detection_shadow=True)
    faint = lambda found: [g for g in _horizontal(found) if g[0] == 100]
    assert faint(off) and faint(on) == faint(off)  # the faint line survives with the option
    assert not any(y == 190 for y, _x0, _x1 in _horizontal(on))


def test_the_detector_default_is_unchanged_and_the_reference_decides_the_threshold():
    image = np.full((400, 400), 255, dtype=np.uint8)
    image[10:50, 20:380] = 0
    image[200:202, 40:360] = 150
    reference = image.copy()
    reference[220:340, 20:380] = 150
    png = lambda a: cv2.imencode(".png", a)[1].tobytes()
    plain = detect_axis_aligned_raster_segments(png(image), dpi=144)
    with_reference = detect_axis_aligned_raster_segments(png(image), dpi=144, threshold_reference_png=png(reference))
    level = lambda found: sorted({round(s.pixel_geometry[1]) for s in found if s.orientation == "horizontal"})
    assert not any(195 <= y <= 206 for y in level(plain)) and any(195 <= y <= 206 for y in level(with_reference))
    assert plain == detect_axis_aligned_raster_segments(png(image), dpi=144, threshold_reference_png=png(image))
    with pytest.raises(ValueError):
        detect_axis_aligned_raster_segments(png(image), dpi=144, threshold_reference_png=png(image[:200]))


def test_the_option_must_be_a_boolean():
    with pytest.raises(ValueError):
        SourceVisibilityProducer(producer_method="m", producer_version="1", raster_picture_detection_shadow="yes")
