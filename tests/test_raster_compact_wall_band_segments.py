from copy import deepcopy
import cv2
import numpy as np
import pytest

import pb_raster_compact_wall_band_segments as compact
from pb_raster_visible_segment_detector import detect_axis_aligned_raster_segments


def _png(image):
    ok, encoded = cv2.imencode('.png', image)
    assert ok
    return encoded.tobytes()


def _image(*, defect=None):
    image = np.full((200, 300), 255, np.uint8)
    size = {'long': (70, 10), 'thin': (20, 2), 'square': (20, 20),
            'short': (10, 7)}.get(defect, (20, 10))
    cv2.rectangle(image, (40, 60), (40 + size[0], 60 + size[1]),
                  0, 1 if defect == 'hollow' else -1)
    if defect == 'hole':
        image[64:67, 49:52] = 255
    return image


def _detect(image):
    return compact.detect_compact_raster_wall_band_segments(_png(image), dpi=300)


def test_compact_filled_source_has_exact_candidate_geometry():
    image = _image()
    before = image.copy()
    result = _detect(image)
    assert len(result) == 1
    line = result[0]
    assert line.pixel_geometry == (40., 65., 60., 65.)
    assert line.geometry_pt == (9.6, 15.6, 14.4, 15.6)
    assert detect_axis_aligned_raster_segments(_png(image), dpi=300) == ()
    assert np.array_equal(before, image)
    assert _detect(image) == result


def test_antialiased_corner_keeps_complete_centerline_but_core_or_endpoint_gap_rejects():
    image = _image()
    image[70, 60] = 252
    assert _detect(image)
    image[65, 50] = 252
    assert _detect(image) == ()
    image = _image()
    image[65, 40] = 252
    assert all(line.pixel_geometry[0] > 40. for line in _detect(image))


def _source(rotation=0, occluded=False):
    import fitz
    from pb_source_visibility_authority import SourceVisibilityProducer
    image = _image()
    cv2.line(image, (100, 130), (240, 130), 0, 3)
    doc = fitz.open()
    page = doc.new_page(width=72., height=48.)
    page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
    if occluded:
        page.draw_rect(fitz.Rect(9., 14., 15., 17.), color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
    page.set_rotation(rotation)
    raw = doc.tobytes(); doc.close()
    source = SourceVisibilityProducer(producer_method='compact-band-test', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='compact-band-test', source_bytes=raw,
        source_locator='memory://compact-band.pdf', page_ids=('1',))
    return source, published


def _published_rows(source, published):
    from pb_source_observation_authority import ObservationSelector
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    rows = []
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id, observation_id=observation_id)
        result = source.authority().resolve_visible(selector)
        assert result.status is Status.CORROBORATED
        rows.append((selector, result.observation))
    return rows


def test_live_source_bridge_preserves_all_ordinary_indices_and_is_idempotent():
    import hashlib
    from pb_source_visibility_authority import RASTER_RENDER_DPI, RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION
    source, initial = _source()
    png, _ = source._producer.render_native_page_png(document_id=initial.revision.document_id,
        revision_id=initial.revision.revision_id, source_sha256=initial.revision.source_sha256,
        snapshot_id=initial.snapshot.snapshot_id, page_id='1', dpi=RASTER_RENDER_DPI)
    normal = sorted(detect_axis_aligned_raster_segments(png, dpi=RASTER_RENDER_DPI),
        key=lambda s: (s.orientation, s.geometry_pt, s.pixel_geometry))
    expected = {f'visible:raster_segment:{hashlib.sha256(png).hexdigest()}:{RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION}:{i}'
                for i in range(len(normal))}
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    rows = _published_rows(source, published)
    ordinary = {r.source_primitive_ref for _, r in rows
                if f':{compact.COMPACT_WALL_BAND_IDENTITY_VERSION}:' not in r.source_primitive_ref}
    additions = [r for _, r in rows if r.source_primitive_ref not in ordinary]
    assert ordinary == expected and expected
    assert len(additions) == 1
    assert additions[0].geometry == (9.6, 15.6, 14.4, 15.6)
    before = deepcopy(source._producer._store.observations)
    assert source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',)) == published
    assert source._producer._store.observations == before


def test_native_opaque_paint_cannot_reveal_a_hidden_image_band_as_visible():
    source, initial = _source(occluded=True)
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    assert all(f':{compact.COMPACT_WALL_BAND_IDENTITY_VERSION}:' not in r.source_primitive_ref
               for _, r in _published_rows(source, published))


@pytest.mark.parametrize('defect', ['core', 'endpoint', 'size'])
def test_visibility_requires_all_core_and_centerline_pixels_even_when_other_paint_agrees(defect):
    image = _image()
    segment, = _detect(image)
    assert compact.compact_band_has_same_visible_paint(segment, image, image.copy())
    full = image.copy()
    if defect == 'core':
        full[63, 45] = 255
    elif defect == 'endpoint':
        full[65, 40] = 255
    else:
        full = full[:-1]
    assert not compact.compact_band_has_same_visible_paint(segment, image, full)


@pytest.mark.parametrize('defect', ['dpi', 'version', 'geometry', 'receipt', 'visibility_hash', 'wrong_visibility_hash'])
def test_compact_source_damage_cannot_be_mistaken_for_native_text_role(defect):
    from dataclasses import replace
    source, initial = _source()
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    selector, record = next((s, r) for s, r in _published_rows(source, published)
        if f':{compact.COMPACT_WALL_BAND_IDENTITY_VERSION}:' in r.source_primitive_ref)
    primitive = record.source_primitive_ref.removeprefix('visible:')
    assert source.raster_text_overlay_evidence(selector, source_primitive_ids=(primitive,)) == ()
    key = (selector.snapshot_id, selector.observation_id)
    if defect == 'receipt':
        del source._raster_visibility_receipts[key]
    elif defect == 'geometry':
        source._producer._store.observations[key] = replace(record, geometry=(0., 0., 10., 0.))
    elif defect in {'visibility_hash', 'wrong_visibility_hash'}:
        receipt = source._raster_visibility_receipts[key]
        source._raster_visibility_receipts[key] = replace(receipt,
            visibility_render_sha256=None if defect == 'visibility_hash' else '0' * 64)
    else:
        receipt = source._raster_visibility_receipts[key]
        source._raster_visibility_receipts[key] = replace(receipt,
            **({'dpi': 144} if defect == 'dpi' else {'detector_version': 'unknown'}))
    with pytest.raises(RuntimeError):
        source.raster_text_overlay_evidence(selector, source_primitive_ids=(primitive,))


def test_mixed_compact_request_still_rejects_damaged_ordinary_receipt():
    from dataclasses import replace
    source, initial = _source()
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    rows = _published_rows(source, published)
    selector, ordinary = next((s, r) for s, r in rows
        if f':{compact.COMPACT_WALL_BAND_IDENTITY_VERSION}:' not in r.source_primitive_ref)
    key = (selector.snapshot_id, selector.observation_id)
    source._raster_visibility_receipts[key] = replace(source._raster_visibility_receipts[key], dpi=999)
    with pytest.raises(RuntimeError):
        source.raster_text_overlay_evidence(selector,
            source_primitive_ids=tuple(r.source_primitive_ref.removeprefix('visible:') for _, r in rows))


@pytest.mark.parametrize('rotation', [90, 180, 270])
def test_unpromoted_page_frame_keeps_ordinary_visibility_and_adds_no_compact_line(rotation):
    source, initial = _source(rotation)
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    rows = _published_rows(source, published)
    assert rows and all(f':{compact.COMPACT_WALL_BAND_IDENTITY_VERSION}:' not in r.source_primitive_ref for _, r in rows)


def test_failed_supplement_does_not_consume_the_source_attempt_or_publish_partial_input(monkeypatch):
    import pb_source_visibility_authority as visibility
    source, initial = _source()
    original = visibility.detect_compact_raster_wall_band_segments
    def failure(*args, **kwargs):
        raise ValueError('raster opening primitive count exceeds safety bound')
    monkeypatch.setattr(visibility, 'detect_compact_raster_wall_band_segments', failure)
    with pytest.raises(ValueError, match='safety bound'):
        source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    assert source.published_snapshot_for_revision(initial.revision.revision_id) == initial
    assert (initial.revision.revision_id, '1') not in source._raster_visibility_attempted_pages
    monkeypatch.setattr(visibility, 'detect_compact_raster_wall_band_segments', original)
    published = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    assert _published_rows(source, published)


@pytest.mark.parametrize('defect', ['thin', 'square', 'short', 'hollow', 'hole', 'long'])
def test_missing_poche_or_ordinary_eligible_lines_do_not_create_compact_bridge(defect):
    assert _detect(_image(defect=defect)) == ()


@pytest.mark.parametrize('rotation', [1, 2, 3])
def test_quarter_turns_preserve_source_centerline(rotation):
    image = _image()
    result = _detect(np.rot90(image, rotation).copy())
    assert len(result) == 1
    points = ((40., 65.), (60., 65.))
    height, width = image.shape
    for _ in range(rotation):
        points = tuple((y, width - 1 - x) for x, y in points)
        height, width = width, height
    first, last = sorted(points)
    assert result[0].pixel_geometry == (*first, *last)


def test_translation_unrelated_content_and_scale_preserve_geometry():
    image = np.full((400, 600), 255, np.uint8)
    cv2.rectangle(image, (130, 140), (170, 160), 0, -1)
    cv2.rectangle(image, (300, 250), (440, 270), 0, -1)
    line, = _detect(image)
    assert line.pixel_geometry == (130., 150., 170., 150.)


def test_primitive_order_and_duplicates_do_not_choose_or_mutate(monkeypatch):
    image = _image()
    raw = _png(image)
    primitives = compact.detect_raster_opening_source_primitives(raw, dpi=300)
    before = deepcopy(primitives)
    expected = _detect(image)
    monkeypatch.setattr(compact, 'detect_raster_opening_source_primitives',
                        lambda *args, **kwargs: tuple(reversed(primitives)) * 2)
    assert _detect(image) == expected
    assert primitives == before


@pytest.mark.parametrize('kind', ['raster_wall_band_end', 'raster_wall_band_face'])
def test_missing_one_source_edge_cannot_interpolate_a_closed_band(monkeypatch, kind):
    image = _image()
    primitives = compact.detect_raster_opening_source_primitives(_png(image), dpi=300)
    target = next(p for p in primitives if p.primitive_kind == kind)
    monkeypatch.setattr(compact, 'detect_raster_opening_source_primitives',
                        lambda *args, **kwargs: tuple(p for p in primitives if p != target))
    assert _detect(image) == ()


def test_existing_source_primitive_safety_failure_propagates(monkeypatch):
    def bounded(*args, **kwargs):
        raise ValueError('raster opening primitive count exceeds safety bound')
    monkeypatch.setattr(compact, 'detect_raster_opening_source_primitives', bounded)
    with pytest.raises(ValueError, match='exceeds safety bound'):
        _detect(_image())


def _compact_door_source(*, scale=1., rotation=0, translated=False, leaf=True, arc=True):
    import fitz
    from test_raster_door_swing_g17_contract import _sheet
    from pb_source_visibility_authority import SourceVisibilityProducer
    image = _sheet(leaf=leaf, arc=arc)
    image[150:165, 30:241] = 255
    cv2.rectangle(image, (214, 150), (240, 164), 0, -1)
    if translated:
        image = np.roll(np.roll(image, 10, axis=0), 20, axis=1)
        cv2.line(image, (20, 30), (160, 30), 0, 1)
    image = np.ascontiguousarray(np.rot90(image, rotation))
    doc = fitz.open()
    page = doc.new_page(width=image.shape[1] / 4 * scale, height=image.shape[0] / 4 * scale)
    page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
    raw = doc.tobytes(); doc.close()
    source = SourceVisibilityProducer(producer_method='compact-door-host-test', producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='compact-door-host-test', source_bytes=raw,
        source_locator='memory://compact-door-host.pdf', page_ids=('1',))
    return source, published


@pytest.mark.parametrize('kwargs', [{}, {'scale': 2.}, {'rotation': 1}, {'rotation': 3}, {'translated': True}])
def test_compact_source_flank_reaches_sealed_host_authority_without_metric_or_quantity(kwargs):
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
    from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
    source, initial = _compact_door_source(**kwargs)
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    assert len(composition.opening_bindings) == 1
    trace, = composition.opening_bindings
    assert trace.status is Status.CORROBORATED and trace.host_wall_id
    assert 'raster_source_band_host_resolved' in trace.reason_codes
    voids = compose_live_physical_opening_voids(source_visibility_producer=source,
        wall_opening_composition=composition)
    assert publish_live_opening_area_quantities(voids) == ()
    assert all(o.width_m is None and o.height_m is None for o in voids.canonical_openings)
    again = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    assert again.opening_bindings == composition.opening_bindings


def test_old_source_capture_reproduces_missing_compact_host(monkeypatch):
    import pb_source_visibility_authority as visibility
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    monkeypatch.setattr(visibility, 'detect_compact_raster_wall_band_segments', lambda *a, **k: ())
    source, initial = _compact_door_source()
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    trace, = composition.opening_bindings
    assert trace.host_wall_id is None
    assert 'raster_source_band_left_source_primitive_unmapped' in trace.reason_codes


@pytest.mark.parametrize('kwargs', [{'leaf': False}, {'arc': False}])
def test_source_band_candidate_cannot_mint_opening_or_host_without_required_swing_evidence(kwargs):
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    source, initial = _compact_door_source(**kwargs)
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    assert composition.opening_bindings == ()
