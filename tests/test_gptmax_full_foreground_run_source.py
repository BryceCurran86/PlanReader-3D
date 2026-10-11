"""Full-pixel shadow extraction must preserve literal foreground and authority boundaries."""
from dataclasses import replace
from hashlib import sha256

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector, SOURCE_OBSERVATION_EXISTS
from pb_source_visibility_authority import SourceVisibilityProducer, RASTER_RENDER_DPI
from tools import gptmax_full_foreground_run_source as full
from tools import gptmax_raster_positive_pixel_source as rejected


def png(image):
    ok, data = cv2.imencode(".png", image)
    assert ok
    return data.tobytes()


def image():
    pixels = np.full((120, 160), 255, np.uint8)
    pixels[30, 20:90] = 0       # Accepted long ordinary component.
    pixels[65:84, 110:129] = 0  # Rejected thick component.
    pixels[72, 116:120] = 255   # Genuine hole must break the scanline.
    return pixels


def pdf(*, rotation=0):
    pixels = image()
    with fitz.open() as doc:
        page = doc.new_page(width=pixels.shape[1] / 2, height=pixels.shape[0] / 2)
        page.insert_image(page.rect, stream=png(pixels))
        page.draw_line((4, 5), (17, 5))
        page.set_rotation(rotation)
        return doc.tobytes()


def producer(data=None):
    data = pdf() if data is None else data
    return full.FullForegroundSourceProducer(
        data, expected_source_sha=sha256(data).hexdigest(), page_id="1")


def test_all_original_foreground_runs_without_detector_component_selection():
    pixels = image()
    raw = full._inventory(png(pixels))
    assert raw
    assert raw == full._inventory(png(pixels))
    assert len({(r.orientation, r.pixel_geometry) for r in raw}) == len(raw)
    assert all(r.run_pixel_count == max(
        abs(r.pixel_geometry[2] - r.pixel_geometry[0]),
        abs(r.pixel_geometry[3] - r.pixel_geometry[1])) + 1 for r in raw)
    assert all(r.geometry == tuple(q / (RASTER_RENDER_DPI / 72.) for q in r.pixel_geometry) for r in raw)
    long_source = next(r for r in raw if r.pixel_geometry == (20, 30, 89, 30))
    assert long_source.orientation == "horizontal"
    assert all(r.pixel_geometry != long_source.pixel_geometry for r in rejected._inventory(png(pixels)))
    # Complete scan never bridges the source-owned white void.
    assert (110, 72, 115, 72) not in {r.pixel_geometry for r in raw}
    assert all(not (r.pixel_geometry[1] == r.pixel_geometry[3] == 72
                    and r.pixel_geometry[0] <= 116 < 120 <= r.pixel_geometry[2])
               for r in raw)


def test_producer_owned_source_exists_only_and_published_snapshot_is_append_only():
    shadow = producer()
    previous = shadow.base_snapshot
    published = shadow.nominate()
    selectors = shadow.selectors()
    assert selectors
    results = shadow.authority().resolve_many(selectors)
    assert all(r.status is EvidenceResolutionStatus.CORROBORATED
               and r.proposition == SOURCE_OBSERVATION_EXISTS for r in results)
    assert all(r.observation.observation_kind == full.FULL_RUN_KIND
               and r.observation.viewport_id is None for r in results)
    assert all(not r.semantic_enumeration_complete and not r.decision_scope_complete for r in results)
    assert previous == shadow.base_snapshot
    assert set(previous.snapshot.observation_ids) <= set(published.snapshot.observation_ids)
    assert shadow.nominate() == published


def test_ordinary_source_visibility_cannot_consume_shadow_run():
    data = pdf()
    shadow = producer(data)
    selector = shadow.selectors()[0]
    source = SourceVisibilityProducer(producer_method="positive-control", producer_version="1")
    original = source.ingest_native_pdf_bytes(document_id="original", source_bytes=data,
        source_locator="memory://full-source.pdf", page_ids=("1",))
    original = source.augment_with_raster_visible_segments(original.revision.revision_id, page_ids=("1",))
    assert source.authority().resolve_visible(selector).status is not EvidenceResolutionStatus.CORROBORATED
    assert original.revision.source_sha256 == sha256(data).hexdigest()


@pytest.mark.parametrize("bad", [None, 1, True, "", "01", "-1", "0", "1.0"])
def test_noncanonical_page_rejected(bad):
    data = pdf()
    with pytest.raises((ValueError, TypeError)):
        full.FullForegroundSourceProducer(data, expected_source_sha=sha256(data).hexdigest(), page_id=bad)


def test_bad_source_sha_and_foreign_selector_fail_closed():
    data = pdf()
    with pytest.raises(ValueError, match="SHA"):
        full.FullForegroundSourceProducer(data, expected_source_sha="0" * 64, page_id="1")
    shadow = producer(data)
    selector = shadow.selectors()[0]
    result = shadow.authority().resolve(replace(selector, source_sha256="0" * 64))
    assert result.status is not EvidenceResolutionStatus.CORROBORATED


def test_factory_enforces_original_source_authority_seal():
    with pytest.raises(TypeError):
        full.FullForegroundSourceAuthority(producer())


def test_nonzero_page_rotation_abstains_before_append():
    shadow = producer(pdf(rotation=90))
    with pytest.raises(ValueError, match="rotation"):
        shadow.nominate()


def test_source_primitive_cap_is_atomic_and_never_truncates(monkeypatch):
    monkeypatch.setattr(full, "MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS", 1)
    shadow = producer()
    with pytest.raises(ValueError, match="safety bound"):
        shadow.nominate()
    assert shadow._published is None
    assert not shadow._proofs


def test_repeat_run_ids_and_polarity_are_deterministic_and_source_owned():
    forward = full._inventory(png(image()))
    inverted = full._inventory(png(255 - image()))
    assert [(p.orientation, p.pixel_geometry) for p in forward] == [
        (p.orientation, p.pixel_geometry) for p in inverted]
    assert [full._reference("f" * 64, p) for p in forward] == [
        full._reference("f" * 64, p) for p in inverted]
    assert all(full.FULL_RUN_KIND in full._reference("f" * 64, p) for p in forward)


def test_no_foreground_and_bad_png_have_explicit_distinct_results():
    assert full._inventory(png(np.full((80, 100), 255, np.uint8))) == ()
    with pytest.raises(ValueError, match="decode"):
        full._inventory(b"not-an-image")
