"""Original opening pixels must stay bound to their authenticated source parent."""
from dataclasses import replace

import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_raster_framed_opening_g17_contract import (
    _closure_source, _prepare, _selector, _sheet,
)


@pytest.mark.parametrize("damage", [
    {"render_sha256": "0" * 64},
    {"render_sha256": "not-a-render"},
    {"dpi": 144},
    {"dpi": 0},
    {"dpi": True},
    {"dpi": 300.0},
    {"pixel_geometry": (1.0, 2.0, 3.0, 4.0)},
    {"pixel_geometry": (float("nan"), 2.0, 3.0, 4.0)},
    {"pixel_geometry": (float("inf"), 2.0, 3.0, 4.0)},
    {"pixel_geometry": (1.0, 2.0, 3.0)},
    {"pixel_geometry": (True, 2.0, 3.0, 4.0)},
    {"pixel_geometry": ("1", 2.0, 3.0, 4.0)},
])
def test_changed_registration_cannot_borrow_original_source_parent(damage):
    source, published = _prepare(frame_lines=2)
    selector = _selector(published, published.raster_opening_primitive_observation_ids[0])
    authority = source.authority()
    baseline = authority.resolve_raster_opening_primitive(selector)
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    key = (selector.snapshot_id, selector.observation_id)
    receipt = source._raster_opening_primitive_receipts[key]
    source._raster_opening_primitive_receipts[key] = replace(receipt, **damage)
    changed = authority.resolve_raster_opening_primitive(selector)
    assert changed.status is EvidenceResolutionStatus.CONFLICT
    assert changed.observation is None
    # Opening primitives remain excluded from the ordinary W4 visible reader.
    assert authority.resolve_visible(selector).status is EvidenceResolutionStatus.ABSTAINED
    source._raster_opening_primitive_receipts[key] = receipt
    assert authority.resolve_raster_opening_primitive(selector) == baseline


@pytest.mark.parametrize("turns,scale,pad", [
    (0, 1, 0), (1, 1, 0), (2, 1, 0), (3, 1, 0),
    (0, 0.5, 0), (0, 2, 0), (0, 1, 30),
])
def test_original_transformed_pixel_receipts_replay_without_identity_mutation(turns, scale, pad):
    gray = np.ascontiguousarray(np.rot90(_sheet(frame_lines=2), turns))
    gray = np.pad(gray, ((pad, pad), (pad, pad)), constant_values=255)
    source, published = _closure_source(gray, scale=scale)
    authority = source.authority()
    receipts = dict(source._raster_opening_primitive_receipts)
    ids = published.raster_opening_primitive_observation_ids
    assert ids
    first = {
        oid: authority.resolve_raster_opening_primitive(_selector(published, oid))
        for oid in ids
    }
    assert all(r.status is EvidenceResolutionStatus.CORROBORATED for r in first.values())
    assert first == {
        oid: authority.resolve_raster_opening_primitive(_selector(published, oid))
        for oid in reversed(ids)
    }
    assert source.published_snapshot_for_revision(published.revision.revision_id) == published
    assert source._raster_opening_primitive_receipts == receipts


def test_reversed_pixel_coordinates_cannot_change_source_direction():
    source, published = _prepare(frame_lines=2)
    selector = _selector(published, published.raster_opening_primitive_observation_ids[0])
    key = (selector.snapshot_id, selector.observation_id)
    receipt = source._raster_opening_primitive_receipts[key]
    a, b, c, d = receipt.pixel_geometry
    source._raster_opening_primitive_receipts[key] = replace(receipt, pixel_geometry=(c, d, a, b))
    assert source.authority().resolve_raster_opening_primitive(selector).status is EvidenceResolutionStatus.CONFLICT


def test_other_primitive_pixel_receipt_does_not_authenticate_same_page():
    source, published = _prepare(frame_lines=2)
    first, second = published.raster_opening_primitive_observation_ids[:2]
    key = (published.snapshot.snapshot_id, first)
    receipt = source._raster_opening_primitive_receipts[key]
    other = source._raster_opening_primitive_receipts[(published.snapshot.snapshot_id, second)]
    assert receipt.geometry != other.geometry
    source._raster_opening_primitive_receipts[key] = replace(receipt, pixel_geometry=other.pixel_geometry)
    assert source.authority().resolve_raster_opening_primitive(_selector(published, first)).status is EvidenceResolutionStatus.CONFLICT


def test_subpixel_change_cannot_borrow_rounded_pdf_geometry():
    source, published = _prepare(frame_lines=2)
    selector = _selector(published, published.raster_opening_primitive_observation_ids[0])
    key = (selector.snapshot_id, selector.observation_id)
    receipt = source._raster_opening_primitive_receipts[key]
    pixels = tuple(v + 1e-8 for v in receipt.pixel_geometry)
    assert tuple(round(v * 72 / receipt.dpi, 6) for v in pixels) == receipt.geometry
    source._raster_opening_primitive_receipts[key] = replace(receipt, pixel_geometry=pixels)
    assert source.authority().resolve_raster_opening_primitive(selector).status is EvidenceResolutionStatus.CONFLICT
