"""Source candidates and local bindings cannot replace missing proof."""
from types import SimpleNamespace as Obj

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from test_raster_opening_source_band_host import _fixture, _resolve
from test_raster_opening_split_centerline_host import _record
from test_raster_opening_whole_wall_frame import (
    GEOMETRY, _binding, _opening, _producer, _scope,
)
from pb_physical_opening_authority import _raster_swing_perpendicular_scale_ratio
from pb_opening_host_frame_authority import OpeningHostFrameProducer


@pytest.mark.parametrize("usable", [False, True])
@pytest.mark.parametrize("reverse", [False, True])
def test_unmapped_perpendicular_candidate_cannot_replace_missing_flank(usable, reverse):
    records, lines = _fixture()
    records[0].physical_identity.source_primitive_ids = ("unmapped:left",)
    baseline = _resolve(records, lines)
    assert baseline.bands == ()
    assert baseline.reason_codes == ("raster_source_band_left_source_primitive_unmapped",)

    corner = _record("unproved-return", start=0., end=10.,
                     source_ids=("unmapped:return",))
    corner.wall_candidate.centerline_pts = ((100., 45.), (100., 65.))
    corner.physical_identity.usable = usable
    candidates = (*records, corner)
    if reverse:
        candidates = tuple(reversed(candidates))
    result = _resolve(candidates, lines)
    assert result.bands == (), result


def _frame(points):
    piece = _record("wall:host", start=20., end=100.,
                    source_ids=("source:left-flank",))
    piece.wall_candidate.centerline_pts = points
    producer = _producer(_scope((piece,)))
    producer._supplemental_walls = None
    binding, opening = _binding(), _opening()
    binding.opening_identity_id = opening.record_id
    producer._host = Obj(resolve=lambda selector: Obj(
        status=Status.CORROBORATED, record=binding))
    return producer._raster_whole_wall_frame(
        binding=binding, opening=opening, geometry=GEOMETRY)


def test_local_binding_cannot_extend_frame_beyond_source_wall():
    result = _frame(((20., 55.), (100., 55.)))
    assert result is None, result


def test_local_binding_cannot_move_frame_to_unrelated_parallel_wall():
    result = _frame(((20., 155.), (220., 155.)))
    assert result is None, result


def test_authentic_containing_wall_control_still_frames():
    result = _frame(((20., 55.), (220., 55.)))
    assert result is not None
    assert (result.u0, result.u1, result.whole_wall_length) == (80., 120., 200.)


def test_partial_image_overlap_cannot_prove_transform_for_uncovered_gap():
    left = Obj(bbox_pt=(0., 0., 50., 100.), pixel_width=50, pixel_height=100)
    result = _raster_swing_perpendicular_scale_ratio(
        (40., 40., 60., 60.), "horizontal", (left,))
    assert result is None, result


def test_two_covering_image_tiles_can_prove_same_transform_control():
    left = Obj(bbox_pt=(0., 0., 50., 100.), pixel_width=50, pixel_height=100)
    right = Obj(bbox_pt=(50., 0., 100., 100.), pixel_width=50, pixel_height=100)
    result = _raster_swing_perpendicular_scale_ratio(
        (40., 40., 60., 60.), "horizontal", (left, right), tiled_gap_shadow=True)
    assert result == 1.
    assert _raster_swing_perpendicular_scale_ratio(
        (40., 40., 60., 60.), "horizontal", (left, right)) is None


@pytest.mark.parametrize("gap", [(.01, 0.), (0., .01), (.01, .01)])
def test_tiled_shadow_cannot_bridge_uncovered_strips(gap):
    dx, dy = gap
    boxes = ((0., 0., 50.-dx, 50.-dy), (50., 0., 100., 50.-dy),
             (0., 50., 50.-dx, 100.), (50., 50., 100., 100.))
    tiles = tuple(Obj(bbox_pt=b, pixel_width=b[2]-b[0], pixel_height=b[3]-b[1])
                  for b in boxes)
    assert _raster_swing_perpendicular_scale_ratio(
        (40., 40., 60., 60.), "horizontal", tiles, tiled_gap_shadow=True) is None


@pytest.mark.parametrize("flag", [1, "yes", None])
def test_tiled_capture_policy_is_explicit_and_not_truthiness(flag):
    with pytest.raises(TypeError):
        _raster_swing_perpendicular_scale_ratio(
            (40., 40., 60., 60.), "horizontal", (), tiled_gap_shadow=flag)


def test_complete_tile_grid_is_order_and_translation_invariant():
    for dx, dy in ((0., 0.), (73., -42.)):
        tiles = tuple(Obj(bbox_pt=(x+dx,y+dy,x+50.+dx,y+50.+dy),
                          pixel_width=50, pixel_height=50)
                      for x in (0., 50.) for y in (0., 50.))
        for ordered in (tiles, tiles[::-1], (*tiles, tiles[0])):
            assert _raster_swing_perpendicular_scale_ratio(
                (40.+dx,40.+dy,60.+dx,60.+dy), "horizontal", ordered,
                tiled_gap_shadow=True) == 1.


@pytest.mark.parametrize("points", [((20.,55.),(100.,75.),(220.,55.)),
                                  ((20.,55.),(100.,55.01),(220.,55.))])
def test_monotone_bent_wall_cannot_be_flattened_to_average_offset(points):
    record = _record("bent", start=20., end=220.)
    record.wall_candidate.centerline_pts = points
    assert OpeningHostFrameProducer._record_projection(record, GEOMETRY.axis, GEOMETRY.normal,
        strict_collinearity_shadow=True) is None


def test_negative_policy_fork_preserves_original_and_cannot_change_cached_reader():
    from test_gptmax_source_geometry_recovery_batch import source
    from pb_source_observation_authority import ObservationSelector
    producer, published = source()
    original = producer.published_snapshot_for_revision(published.revision.revision_id)
    authority = producer.physical_opening_authority()
    fork, replay = producer.fork_native_source_shadow(published.revision.revision_id,
        raster_double_face_negative_shadow=True)
    assert fork._raster_double_face_negative_shadow is True
    assert producer._raster_double_face_negative_shadow is False
    assert replay.revision.source_sha256 == published.revision.source_sha256
    assert producer.published_snapshot_for_revision(published.revision.revision_id) is original
    producer._raster_double_face_negative_shadow = True
    selector = ObservationSelector(published.revision.document_id,
        published.revision.revision_id, published.revision.source_sha256,
        published.snapshot.snapshot_id, published.visible_observation_ids[0])
    with pytest.raises(RuntimeError, match="policy changed"):
        authority.prove_existence(selector)
    with pytest.raises(RuntimeError, match="policy changed"):
        producer.physical_opening_authority()


@pytest.mark.parametrize("flag", [1, "yes", None])
def test_negative_policy_rejects_non_boolean_before_source_construction(flag):
    from pb_source_visibility_authority import SourceVisibilityProducer
    with pytest.raises(ValueError):
        SourceVisibilityProducer(producer_method="negative", producer_version="1",
            raster_double_face_negative_shadow=flag)
