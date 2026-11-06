"""Source pixel border support, never a heuristic furniture/wall classifier."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace as Obj

import cv2
import numpy as np
import pytest

from pb_raster_source_wall_frame_projection import (
    exact_raster_rectangle_holes, source_equipment_border_support,
)
from test_gptmax_source_closed_pier_face_chain import _fragment_record


def _fixture():
    image = np.full((100, 150), 255, np.uint8)
    cv2.rectangle(image, (40, 18), (120, 22), 0, -1)
    cv2.rectangle(image, (60, 25), (88, 45), 0, 1)
    geometry = Obj(origin=(20., 20.), axis=(1., 0.), normal=(0., 1.),
                   length=20., thickness=4.)
    record, parent, line = _fragment_record('equipment', 61, 87, 25)
    words = [dict(id='word-ac', text='AC', bbox=(64., 29., 72., 39.),
                  trusted=True, receipt='receipt-ac', block=2, line=0, word=0),
             dict(id='word-unit', text='Unit', bbox=(73., 29., 85., 39.),
                  trusted=True, receipt='receipt-unit', block=2, line=0, word=1)]
    return dict(record=record, geometry=geometry, source_lines={parent:line},
        flanks={'right':(20., 100., -2., 2., 20.)},
        words=words, image=image, full=image.copy())


def _png(image):
    ok, png = cv2.imencode('.png', image)
    assert ok
    return png.tobytes()


def _proof(fixture, *, rectangles=None):
    image, full = _png(fixture['image']), _png(fixture['full'])
    return source_equipment_border_support(
        fixture['record'], fixture['geometry'], fixture['source_lines'],
        fixture['flanks'], words=fixture['words'],
        rectangles=(exact_raster_rectangle_holes(image, dpi=72)
                    if rectangles is None else rectangles),
        image_png=image, full_png=full, dpi=72, source_equality_tolerance=.74,
    )


def test_exact_original_closed_box_and_complete_label_supply_only_local_support():
    f = _fixture()
    before = deepcopy(f)
    proof = _proof(f)
    assert proof is not None
    box, words, receipts = proof
    assert box == (60., 25., 88., 45.)
    assert words == ('word-ac', 'word-unit')
    assert receipts == ('receipt-ac', 'receipt-unit')
    assert f['words'] == before['words']
    assert f['source_lines'] == before['source_lines']
    assert np.array_equal(f['image'], before['image'])
    # Merely another source/graph address, not a physical-wall relation.
    assert not hasattr(proof, 'whole_wall_frame_id')


@pytest.mark.parametrize('damage', [
    'broken_box', 'unknown_label', 'untrusted_word', 'extra_unknown_word',
    'missing_label_word', 'duplicate_address', 'second_line', 'word_gap',
    'word_crosses_box', 'missing_parent', 'foreign_fragment', 'curve',
    'snapped_into_wall', 'bent_snapped_path', 'source_separator_painted',
    'native_separator_painted', 'outside_flank', 'overlapping_wall_box',
])
def test_opposing_role_requires_every_independent_original_proposition(damage):
    f = _fixture()
    if damage == 'broken_box':
        f['image'][25, 70:75] = 255
        f['full'] = f['image'].copy()
    elif damage == 'unknown_label':
        f['words'][1]['text'] = 'STORE'
    elif damage == 'untrusted_word':
        f['words'][0]['trusted'] = False
    elif damage == 'extra_unknown_word':
        f['words'].append(dict(f['words'][0], id='unknown', trusted=False,
                               bbox=(65., 40., 70., 43.), word=3))
    elif damage == 'missing_label_word':
        f['words'].pop()
    elif damage == 'duplicate_address':
        f['words'].append(dict(f['words'][0], id='duplicate'))
    elif damage == 'second_line':
        f['words'][1]['line'] = 1
    elif damage == 'word_gap':
        f['words'][1]['word'] = 2
    elif damage == 'word_crosses_box':
        f['words'][0]['bbox'] = (59., 29., 72., 39.)
    elif damage == 'missing_parent':
        f['source_lines'].clear()
    elif damage == 'foreign_fragment':
        fragment = f['record'].source_edge_fragments[0]
        f['record'].source_edge_fragments = (replace(fragment,
            source_primitive_ids=('foreign',)),)
    elif damage == 'curve':
        f['record'].wall_candidate.is_curved = True
    elif damage == 'snapped_into_wall':
        f['record'].wall_candidate.centerline_pts = ((61., 22.), (87., 22.))
    elif damage == 'bent_snapped_path':
        f['record'].wall_candidate.centerline_pts = ((61., 25.), (70., 25.5), (87., 25.))
    elif damage == 'source_separator_painted':
        f['image'][23:25, 61:88] = 0
        f['full'] = f['image'].copy()
    elif damage == 'native_separator_painted':
        f['full'][23:25, 61:88] = 0
    elif damage == 'outside_flank':
        f['flanks']['right'] = (20., 50., -2., 2., 20.)
    elif damage == 'overlapping_wall_box':
        f['flanks']['right'] = (20., 100., -2., 7., 20.)
    assert _proof(f) is None


def test_competing_boxes_are_not_ranked_by_size_or_input_order():
    f = _fixture()
    boxes = exact_raster_rectangle_holes(_png(f['image']), dpi=72)
    assert _proof(f, rectangles=boxes+boxes) is None
    assert _proof(f, rectangles=tuple(reversed(boxes+boxes))) is None


def test_producer_requires_explicit_typed_opt_in_and_original_g17_owner():
    from pb_opening_host_frame_authority import OpeningHostFrameProducer
    from test_gptmax_g17_face_to_w2_centreline_owner import _source
    _source_visibility, comp, _producer, _bound = _source(clean_supplement=False)
    base = dict(physical_opening_authority=comp.physical_opening_authority,
        host_binding_authority=comp.opening_host_binding_authority,
        physical_wall_candidate_authority=comp.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=comp.supplemental_physical_wall_candidate_authority)
    for value in (None, 0, 1, 'true', {}, ()):
        with pytest.raises(TypeError, match='source_equipment_border_shadow must be a bool'):
            OpeningHostFrameProducer.from_authorities(
                **base, source_equipment_border_shadow=value)
    with pytest.raises(ValueError, match='requires original G17 W2 owner'):
        OpeningHostFrameProducer.from_authorities(**base, source_equipment_border_shadow=True)
    default = OpeningHostFrameProducer.from_authorities(**base)
    assert default._source_equipment_border_shadow is False
    assert dict(default.source_negative_evidence()) == {}
    with pytest.raises(TypeError, match='exact original selectors'):
        default.source_equipment_border_negative_shadow(
            opening_selector=object(), host_binding_selector=object(), wall_candidate_id='fake')


def test_disabled_shadow_preserves_actual_synthetic_frame_publisher_and_quantity_boundary():
    from test_gptmax_source_face_frame import _fixture
    from test_raster_connected_host_frame import _publish
    from pb_opening_host_frame_authority import OpeningHostFrameProducer
    _source, comp, original, bound = _fixture()
    before = _publish(original, bound)
    assert all(row.evidence is not None for row in before)
    default = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=comp.physical_opening_authority,
        host_binding_authority=comp.opening_host_binding_authority,
        physical_wall_candidate_authority=comp.physical_wall_candidate_authority,
        supplemental_wall_candidate_authority=comp.supplemental_physical_wall_candidate_authority,
        source_fragment_roles_shadow=True,
    )
    assert _publish(default, bound) == before
    assert dict(default.source_negative_evidence()) == {}


@pytest.mark.parametrize('rotation', [0, 1, 2, 3])
@pytest.mark.parametrize('scale', [1, 2])
def test_pixel_source_transform_and_source_order_preserve_support(rotation, scale):
    f = _fixture()
    h, w = f['image'].shape
    # Use one homogeneous affine operation for each quarter turn.
    def transform(p):
        x, y = p
        width, height = w, h
        for _ in range(rotation):
            x, y, width, height = y, width-1-x, height, width
        # Nearest-neighbour image enlargement maps each original cell to
        # a block whose centre is (scale-1)/2 beyond its first sample.
        return (x*scale+(scale-1)/2., y*scale+(scale-1)/2.)
    g = f['geometry']
    origin = transform(g.origin)
    end = transform((g.origin[0]+1., g.origin[1]))
    axis = ((end[0]-origin[0])/scale, (end[1]-origin[1])/scale)
    g.origin, g.axis, g.normal = origin, axis, (-axis[1], axis[0])
    g.length *= scale
    g.thickness *= scale
    f['flanks'] = {key:tuple(v*scale for v in values)
                    for key, values in f['flanks'].items()}
    record = f['record']
    record.wall_candidate.centerline_pts = tuple(transform(p) for p in record.wall_candidate.centerline_pts)
    fragment = record.source_edge_fragments[0]
    transformed = (*transform(fragment.geometry[:2]), *transform(fragment.geometry[2:]))
    record.source_edge_fragments = (replace(fragment, geometry=transformed),)
    f['source_lines'] = {key:transformed for key in f['source_lines']}
    for word in f['words']:
        x0, y0, x1, y1 = word['bbox']
        corners = [transform(p) for p in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
        xs, ys = zip(*corners)
        word['bbox'] = (min(xs), min(ys), max(xs), max(ys))
    # Scale the actual original cells together with their centre geometry.
    f['image'] = cv2.resize(np.ascontiguousarray(np.rot90(f['image'], rotation)),
        None, fx=scale, fy=scale, interpolation=cv2.INTER_NEAREST)
    f['full'] = f['image'].copy()
    proof = _proof(f)
    assert proof is not None
    f['words'].reverse()
    f['source_lines'] = dict(reversed(tuple(f['source_lines'].items())))
    assert _proof(f) == proof
