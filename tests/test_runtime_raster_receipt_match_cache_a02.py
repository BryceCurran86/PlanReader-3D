"""A02: the memoized receipt/parent binding check must equal the uncached check exactly."""
from __future__ import annotations

from dataclasses import replace

import pb_source_visibility_authority as vis
from pb_source_visibility_authority import (
    RASTER_RENDER_DPI,
    RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION,
    _RASTER_RECEIPT_MATCH_CACHE,
    _raster_segment_observation_id,
    _raster_segment_receipt_matches_parent,
    _raster_segment_receipt_matches_parent_uncached,
)


class _Receipt:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Parent:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def _pair():
    sha = "ab" * 32
    pixel = (10.0, 20.0, 110.0, 20.0)
    dpi = RASTER_RENDER_DPI
    geom = tuple(round(v * 72.0 / dpi, 6) for v in pixel)
    receipt = _Receipt(
        dpi=dpi, visibility_render_sha256=None, image_sha256=sha,
        pixel_geometry=pixel, geometry=geom, document_id="d", revision_id="r",
        page_id="1", source_partition_id="p",
    )
    oid = _raster_segment_observation_id(
        document_id="d", revision_id="r", page_id="1", partition_id="p",
        image_sha256=sha, identity_version=RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION,
        pixel_geometry=pixel, geometry=geom, index=3, visibility_render_sha256=None,
    )
    parent = _Parent(
        source_primitive_ref=f"raster_segment:{sha}:{RASTER_VISIBLE_SEGMENT_IDENTITY_VERSION}:3",
        observation_id=oid,
    )
    return receipt, parent


def test_cached_equals_uncached_for_valid_and_every_single_field_tamper():
    _RASTER_RECEIPT_MATCH_CACHE.clear()
    receipt, parent = _pair()
    assert _raster_segment_receipt_matches_parent_uncached(receipt, parent) is True
    # Twice: second call is a cache hit and must still be True.
    assert _raster_segment_receipt_matches_parent(receipt, parent) is True
    assert _raster_segment_receipt_matches_parent(receipt, parent) is True

    tampers = [
        (receipt, _Parent(source_primitive_ref=parent.source_primitive_ref, observation_id="x")),
        (receipt, _Parent(source_primitive_ref=parent.source_primitive_ref.replace(":3", ":4"), observation_id=parent.observation_id)),
        (receipt, _Parent(source_primitive_ref="garbage", observation_id=parent.observation_id)),
    ]
    for field, value in (
        ("dpi", receipt.dpi + 1), ("image_sha256", "cd" * 32),
        ("pixel_geometry", (11.0, 20.0, 110.0, 20.0)),
        ("geometry", (0.0, 0.0, 1.0, 1.0)), ("document_id", "other"),
        ("revision_id", "other"), ("page_id", "2"),
        ("source_partition_id", "q"), ("visibility_render_sha256", "ef" * 32),
    ):
        altered = _Receipt(**{**receipt.__dict__, field: value})
        tampers.append((altered, parent))
    for r, p in tampers:
        expected = _raster_segment_receipt_matches_parent_uncached(r, p)
        assert expected is False
        assert _raster_segment_receipt_matches_parent(r, p) is expected
        assert _raster_segment_receipt_matches_parent(r, p) is expected
    # The valid pair is unaffected by the tampered entries.
    assert _raster_segment_receipt_matches_parent(receipt, parent) is True


def test_unhashable_fields_fall_back_to_uncached_and_cache_is_bounded(monkeypatch):
    _RASTER_RECEIPT_MATCH_CACHE.clear()
    receipt, parent = _pair()
    listy = _Receipt(**{**receipt.__dict__, "pixel_geometry": list(receipt.pixel_geometry)})
    assert (_raster_segment_receipt_matches_parent(listy, parent)
            is _raster_segment_receipt_matches_parent_uncached(listy, parent))
    monkeypatch.setattr(vis, "_RASTER_RECEIPT_MATCH_CACHE_MAX", 4)
    for i in range(20):
        r = _Receipt(**{**receipt.__dict__, "page_id": str(i)})
        _raster_segment_receipt_matches_parent(r, parent)
    assert len(_RASTER_RECEIPT_MATCH_CACHE) <= 4
