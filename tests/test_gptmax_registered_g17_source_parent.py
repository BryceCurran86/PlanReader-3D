"""Registered G17 source receipts must authenticate before any W4 host test."""
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import pb_source_visibility_authority as visibility
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_raster_unchanged_band_segments import (
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
)
from test_raster_unchanged_band_segments import _pdf
from test_raster_source_visibility_v1 import _selector

FAMILIES = (
    UNCHANGED_BAND_IDENTITY_VERSION,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
    ORIGINAL_G17_JAMB_PARTIAL_IDENTITY_VERSION,
)


def registration_pair(family, *, pixels=(23.5, 30.0, 40.5, 30.0)):
    geometry = tuple(round(v * 72 / 300, 6) for v in pixels)
    fields = dict(
        document_id="synthetic-document", revision_id="synthetic-revision",
        source_sha256="a" * 64, page_id="1", source_partition_id="page:1",
        image_sha256="b" * 64, dpi=300, pixel_geometry=pixels,
        geometry=geometry, visibility_render_sha256="c" * 64,
        detector_version=family, page_parent_observation_id="original-page",
    )
    parent_id = visibility._raster_segment_observation_id(
        document_id=fields["document_id"], revision_id=fields["revision_id"],
        page_id=fields["page_id"], partition_id=fields["source_partition_id"],
        image_sha256=fields["image_sha256"], identity_version=family,
        pixel_geometry=pixels, geometry=geometry, index=0,
        visibility_render_sha256=fields["visibility_render_sha256"],
    )
    receipt = visibility.RasterSegmentVisibilityReceipt(
        parent_observation_id=parent_id, **fields)
    parent = SimpleNamespace(
        observation_id=parent_id,
        source_primitive_ref=f"raster_segment:{'b'*64}:{family}:{'c'*64}:0",
    )
    return receipt, parent


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("pixels", [
    (23.5, 30.0, 40.5, 30.0),       # genuine half-cell extent
    (123.5, 230.0, 140.5, 230.0),   # translated source
    (30.0, 23.5, 30.0, 40.5),       # rotated source
    (47.0, 60.0, 81.0, 60.0),       # different source span
])
def test_exact_registered_family_parent_is_reproducible(family, pixels):
    receipt, parent = registration_pair(family, pixels=pixels)
    assert visibility._raster_segment_receipt_matches_parent(receipt, parent)
    assert visibility._raster_segment_receipt_matches_parent(receipt, parent)


@pytest.mark.parametrize("family", [
    "unknown_g17_v1", "prefix_original_g17_one_end_paint_v1",
    "original_g17_one_end_paint_v1_suffix", "original_g17_one_end_paint_v2",
])
def test_even_self_consistent_unknown_or_similar_family_is_rejected(family):
    receipt, parent = registration_pair(family)
    assert not visibility._raster_segment_receipt_matches_parent(receipt, parent)


@pytest.mark.parametrize("family", FAMILIES)
@pytest.mark.parametrize("damage", [
    {"image_sha256": "d"*64}, {"visibility_render_sha256": "d"*64},
    {"dpi": 144}, {"pixel_geometry": (0.0, 0.0, 1.0, 0.0)},
    {"geometry": (0.0, 0.0, 1.0, 0.0)}, {"document_id": "another-document"},
    {"revision_id": "another-revision"}, {"page_id": "2"},
    {"source_partition_id": "page:2"},
])
def test_new_families_cannot_borrow_existing_parent_registration(family, damage):
    receipt, parent = registration_pair(family)
    assert not visibility._raster_segment_receipt_matches_parent(
        replace(receipt, **damage), parent)


def original_one_ended_source():
    source = visibility.SourceVisibilityProducer(
        producer_method="synthetic-g17-registration", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-g17-registration", source_bytes=_pdf(),
        source_locator="memory://synthetic-g17-registration.pdf")
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id)
    # Exercise the real one-ended publisher independently of older detectors.
    # No source coordinates, receipts, or physical-existence results are supplied.
    with patch.object(visibility, "detect_axis_aligned_raster_segments", return_value=()), \
            patch.object(visibility, "detect_unchanged_terminal_band_segments", return_value=()):
        published = source.augment_with_unmeasured_g17_flanks_source_shadow(
            published.revision.revision_id, page_ids=("1",))
    return source, published


def test_real_one_ended_publisher_reaches_both_source_readers():
    source, published = original_one_ended_source()
    authority = source.authority()
    rows = authority.authenticated_visible_observations(published)
    selected = [oid for oid, row in rows
                if ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION in row.source_primitive_ref]
    assert selected
    for oid in selected:
        assert authority.resolve_visible(_selector(published, oid)).status is Status.CORROBORATED


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("damage", [
    {"image_sha256": "d"*64}, {"visibility_render_sha256": "d"*64},
    {"dpi": 144}, {"pixel_geometry": (0.0, 0.0, 1.0, 0.0)},
])
def test_real_new_receipt_tampering_rejected_even_after_verified_read(warm, damage):
    source, published = original_one_ended_source()
    authority = source.authority()
    ids = [oid for oid, row in authority.authenticated_visible_observations(published)
           if ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION in row.source_primitive_ref]
    assert ids
    oid = ids[0]
    selector = _selector(published, oid)
    if warm:
        assert authority.resolve_visible(selector).status is Status.CORROBORATED
    key = (published.snapshot.snapshot_id, oid)
    source._raster_visibility_receipts[key] = replace(
        source._raster_visibility_receipts[key], **damage)
    assert authority.resolve_visible(selector).status in (Status.ABSTAINED, Status.CONFLICT)
    with pytest.raises(RuntimeError):
        authority.authenticated_visible_observations(published)

