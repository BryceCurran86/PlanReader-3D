from copy import deepcopy
from dataclasses import replace
import cv2
import numpy as np
import pytest

import pb_raster_terminal_wall_band_segments as terminal
from pb_raster_compact_wall_band_segments import compact_band_has_same_visible_paint


def _png(image):
    ok, encoded = cv2.imencode('.png', image)
    assert ok
    return encoded.tobytes()


def _image(defect=None):
    image = np.full((200, 300), 255, np.uint8)
    cv2.rectangle(image, (40, 60), (200, 74), 0, -1)
    if defect != 'solid':
        image[60:65, 40:91] = 255
    if defect == 'gap':
        image[62, 130:135] = 255
    elif defect == 'hollow':
        image[62:73, 42:199] = 255
    elif defect == 'short':
        image[60:65, 40:190] = 255
    elif defect == 'interior':
        image[60:65, 170:201] = 255
    elif defect == 'thin':
        image[62:75, 40:201] = 255
    return image


def _detect(image):
    return terminal.detect_terminal_raster_wall_band_segments(_png(image), dpi=300)


def test_maximal_source_painted_terminal_has_exact_geometry_and_replays_without_mutation():
    image = _image()
    before = image.copy()
    line, = _detect(image)
    assert line.pixel_geometry == (91., 67., 200., 67.)
    assert line.geometry_pt == (21.84, 16.08, 48., 16.08)
    assert line.pixel_support_bounds == (91, 60, 200, 74)
    assert _detect(image) == (line,)
    assert np.array_equal(image, before)
    assert compact_band_has_same_visible_paint(line, image, image.copy())


@pytest.mark.parametrize('defect', ['solid', 'hollow', 'short', 'interior', 'thin'])
def test_no_duplicate_full_band_or_incomplete_short_interior_candidate(defect):
    assert _detect(_image(defect)) == ()


def test_a_core_gap_cannot_be_interpolated_to_the_original_terminal():
    image = _image('gap')
    line, = _detect(image)
    assert line.pixel_geometry == (135., 67., 200., 67.)
    assert all(s.pixel_geometry[0] > 130. for s in _detect(image))


def test_both_terminal_runs_are_retained_without_ranking():
    image = _image('solid')
    image[62, 110:115] = 255
    lines = _detect(image)
    assert [s.pixel_geometry for s in lines] == [(40., 67., 109., 67.), (115., 67., 200., 67.)]


@pytest.mark.parametrize('rotation', [1, 2, 3])
def test_pixel_rotations_preserve_source_terminal_geometry(rotation):
    image = _image()
    lines = _detect(np.rot90(image, rotation).copy())
    points = ((91., 67.), (200., 67.))
    height, width = image.shape
    for _ in range(rotation):
        points = tuple((y, width - 1 - x) for x, y in points)
        height, width = width, height
    first, last = sorted(points)
    assert len(lines) == 1 and lines[0].pixel_geometry == (*first, *last)


def test_translation_scaling_and_unrelated_ink_preserve_exact_paint():
    image = np.full((440, 700), 255, np.uint8)
    enlarged = np.repeat(np.repeat(_image(), 2, axis=0), 2, axis=1)
    image[20:420, 30:630] = enlarged
    cv2.line(image, (20, 430), (180, 430), 0, 1)
    line, = _detect(image)
    assert line.pixel_geometry == (212., 154.5, 431., 154.5)


def test_primitive_order_duplicates_and_split_source_paint_are_stable(monkeypatch):
    image = _image()
    primitives = terminal.detect_raster_opening_source_primitives(_png(image), dpi=300)
    before = deepcopy(primitives)
    expected = _detect(image)
    monkeypatch.setattr(terminal, 'detect_raster_opening_source_primitives', lambda *a, **k: tuple(reversed(primitives)) * 2)
    assert _detect(image) == expected and primitives == before
    split = _image('solid')
    split[60:65, 40:65] = 255
    split[60:65, 65:91] = 255
    assert np.array_equal(split, image) and _detect(split) == expected


@pytest.mark.parametrize('kind', ['raster_wall_band_end', 'raster_wall_band_face'])
def test_missing_source_edge_does_not_create_a_band(monkeypatch, kind):
    image = _image()
    primitives = terminal.detect_raster_opening_source_primitives(_png(image), dpi=300)
    removed = next(p for p in primitives if p.primitive_kind == kind)
    monkeypatch.setattr(terminal, 'detect_raster_opening_source_primitives', lambda *a, **k: tuple(p for p in primitives if p != removed))
    assert _detect(image) == ()


def test_safety_bound_failure_propagates_without_partial_candidates(monkeypatch):
    def bounded(*a, **k):
        raise ValueError('raster opening primitive count exceeds safety bound')
    monkeypatch.setattr(terminal, 'detect_raster_opening_source_primitives', bounded)
    with pytest.raises(ValueError, match='safety bound'):
        _detect(_image())


@pytest.mark.parametrize('damage', ['core', 'endpoint', 'size'])
def test_visible_paint_cannot_be_replaced_or_occluded(damage):
    image = _image()
    line, = _detect(image)
    full = image.copy()
    if damage == 'core':
        full[62, 120] = 255
    elif damage == 'endpoint':
        full[67, 200] = 255
    else:
        full = full[:-1]
    assert not compact_band_has_same_visible_paint(line, image, full)


def _source(*, rotation=0, occluded=False, raw_bytes=None):
    import fitz
    from pb_source_visibility_authority import SourceVisibilityProducer
    image = _image()
    cv2.rectangle(image, (230, 140), (250, 150), 0, -1)
    doc = fitz.open()
    page = doc.new_page(width=72., height=48.)
    page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
    if occluded:
        page.draw_rect(fitz.Rect(21., 14., 49., 18.), color=(1, 1, 1), fill=(1, 1, 1), overlay=True)
    page.set_rotation(rotation)
    raw = doc.tobytes(); doc.close()
    if raw_bytes is not None:
        raw = raw_bytes
    source = SourceVisibilityProducer(producer_method='terminal-source-test', producer_version='1')
    initial = source.ingest_native_pdf_bytes(document_id='terminal-source-test', source_bytes=raw,
        source_locator='memory://terminal-band.pdf', page_ids=('1',))
    return source, initial


def _rows(source, snapshot):
    from test_raster_compact_wall_band_segments import _published_rows
    return _published_rows(source, snapshot)


def test_source_bridge_keeps_every_ordinary_and_compact_identity_and_replays(monkeypatch):
    import pb_source_visibility_authority as visibility
    original = visibility.detect_terminal_raster_wall_band_segments
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', lambda *a, **k: ())
    old, old_initial = _source()
    old_snapshot = old.augment_with_raster_visible_segments(old_initial.revision.revision_id, page_ids=('1',))
    old_rows = {r.source_primitive_ref: s.observation_id for s, r in _rows(old, old_snapshot)}
    assert any(':compact_solid_wall_band_v1:' in key for key in old_rows)
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', original)
    raw = old._producer._store.source_bytes_by_revision[old_initial.revision.revision_id]
    source, initial = _source(raw_bytes=raw)
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    rows = {r.source_primitive_ref: s.observation_id for s, r in _rows(source, snapshot)}
    assert all(rows[key] == value for key, value in old_rows.items())
    additions = set(rows) - set(old_rows)
    assert len(additions) == 1 and all(':terminal_solid_wall_band_v1:' in key for key in additions)
    assert source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',)) == snapshot


def test_terminal_text_role_request_cannot_hide_damaged_ordinary_receipt():
    source, initial = _source()
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    rows = _rows(source, snapshot)
    assert any(':terminal_solid_wall_band_v1:' in r.source_primitive_ref for _, r in rows)
    selector, ordinary = next((s, r) for s, r in rows if ':1.0.0:' in r.source_primitive_ref)
    key = (selector.snapshot_id, selector.observation_id)
    source._raster_visibility_receipts[key] = replace(source._raster_visibility_receipts[key], dpi=999)
    with pytest.raises(RuntimeError):
        source.raster_text_overlay_evidence(selector,
            source_primitive_ids=tuple(r.source_primitive_ref.removeprefix('visible:') for _, r in rows))


@pytest.mark.parametrize('rotation', [90, 180, 270])
def test_unpromoted_page_frame_retains_ordinary_visibility(rotation):
    source, initial = _source(rotation=rotation)
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    rows = _rows(source, snapshot)
    assert rows and all(':terminal_solid_wall_band_v1:' not in r.source_primitive_ref for _, r in rows)


def test_native_opaque_overlay_keeps_hidden_terminal_out_of_visibility():
    source, initial = _source(occluded=True)
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    assert all(':terminal_solid_wall_band_v1:' not in r.source_primitive_ref for _, r in _rows(source, snapshot))


@pytest.mark.parametrize('damage', ['dpi', 'version', 'geometry', 'receipt', 'visibility_hash', 'wrong_visibility_hash'])
def test_both_visibility_readers_and_text_role_reject_damaged_terminal_receipts(damage):
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    source, initial = _source()
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    selector, record = next((s, r) for s, r in _rows(source, snapshot) if ':terminal_solid_wall_band_v1:' in r.source_primitive_ref)
    primitive = record.source_primitive_ref.removeprefix('visible:')
    assert source.raster_text_overlay_evidence(selector, source_primitive_ids=(primitive,)) == ()
    key = (selector.snapshot_id, selector.observation_id)
    if damage == 'receipt':
        del source._raster_visibility_receipts[key]
    elif damage == 'geometry':
        source._producer._store.observations[key] = replace(record, geometry=(0., 0., 10., 0.))
    else:
        change = {'dpi': 144} if damage == 'dpi' else {'detector_version': 'unknown'} if damage == 'version' else {
            'visibility_render_sha256': None if damage == 'visibility_hash' else '0' * 64}
        source._raster_visibility_receipts[key] = replace(source._raster_visibility_receipts[key], **change)
    assert source.authority().resolve_visible(selector).status is not Status.CORROBORATED
    with pytest.raises(RuntimeError):
        source.authority().authenticated_visible_observations(snapshot)
    with pytest.raises(RuntimeError):
        source.raster_text_overlay_evidence(selector, source_primitive_ids=(primitive,))


def test_failed_terminal_capture_keeps_snapshot_and_attempt_retryable(monkeypatch):
    import pb_source_visibility_authority as visibility
    original = visibility.detect_terminal_raster_wall_band_segments
    def bounded(*a, **k):
        raise ValueError('raster opening primitive count exceeds safety bound')
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', bounded)
    source, initial = _source()
    with pytest.raises(ValueError, match='safety bound'):
        source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    assert source.published_snapshot_for_revision(initial.revision.revision_id) == initial
    assert (initial.revision.revision_id, '1') not in source._raster_visibility_attempted_pages
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', original)
    snapshot = source.augment_with_raster_visible_segments(initial.revision.revision_id, page_ids=('1',))
    assert any(':terminal_solid_wall_band_v1:' in r.source_primitive_ref for _, r in _rows(source, snapshot))


def _door_source(*, rotation=0, scale=1., translated=False, leaf=True, arc=True):
    import fitz
    from test_raster_door_swing_g17_contract import _sheet
    from pb_source_visibility_authority import SourceVisibilityProducer
    image = _sheet(leaf=leaf, arc=arc)
    image[150:155, 30:100] = 255
    dx, dy = (20, 10) if translated else (0, 0)
    image = np.roll(np.roll(image, dy, axis=0), dx, axis=1)
    if translated:
        cv2.line(image, (20, 30), (160, 30), 0, 1)
    overlay = ((30 + dx, 110 + dy), (240 + dx, 150 + dy))
    height, width = image.shape
    for _ in range(rotation):
        overlay = tuple((y, width - 1 - x) for x, y in overlay)
        image = np.ascontiguousarray(np.rot90(image))
        height, width = width, height
    doc = fitz.open()
    page = doc.new_page(width=width / 4 * scale, height=height / 4 * scale)
    page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
    xs, ys = zip(*overlay)
    page.draw_rect(fitz.Rect(min(xs) / 4 * scale, min(ys) / 4 * scale,
                            max(xs) / 4 * scale, max(ys) / 4 * scale),
                   color=None, fill=(0, 0, 0), overlay=True)
    raw = doc.tobytes(); doc.close()
    source = SourceVisibilityProducer(producer_method='terminal-door-test', producer_version='1')
    initial = source.ingest_native_pdf_bytes(document_id='terminal-door-test', source_bytes=raw,
        source_locator='memory://terminal-door.pdf', page_ids=('1',))
    return source, initial


@pytest.mark.parametrize('kwargs', [{}, {'rotation': 1}, {'rotation': 3}, {'scale': 2.}, {'translated': True}])
def test_terminal_flank_closes_sealed_host_without_dimensions_or_quantity(kwargs):
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
    from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
    source, initial = _door_source(**kwargs)
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    trace, = composition.opening_bindings
    assert trace.host_wall_id and 'raster_source_band_host_resolved' in trace.reason_codes
    voids = compose_live_physical_opening_voids(source_visibility_producer=source, wall_opening_composition=composition)
    assert publish_live_opening_area_quantities(voids) == ()
    assert all(o.width_m is None and o.height_m is None for o in voids.canonical_openings)
    assert compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',)).opening_bindings == composition.opening_bindings


def test_old_capture_reproduces_unmapped_flank_without_terminal_bridge(monkeypatch):
    import pb_source_visibility_authority as visibility
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    monkeypatch.setattr(visibility, 'detect_terminal_raster_wall_band_segments', lambda *a, **k: ())
    source, initial = _door_source()
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    trace, = composition.opening_bindings
    assert trace.host_wall_id is None and 'raster_source_band_left_source_primitive_unmapped' in trace.reason_codes


@pytest.mark.parametrize('kwargs', [{'leaf': False}, {'arc': False}])
def test_terminal_paint_alone_cannot_mint_a_swing_opening(kwargs):
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    source, initial = _door_source(**kwargs)
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=initial.revision.revision_id, page_ids=('1',))
    assert composition.opening_bindings == ()
