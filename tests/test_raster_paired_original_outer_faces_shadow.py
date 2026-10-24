"""Internal endpoint-coverage rows are not original paired band faces."""

from copy import deepcopy
from dataclasses import replace

import cv2
import fitz
import numpy as np
import pytest

from pb_physical_opening_authority import _RasterBandPair, _raster_wall_face_continues
from pb_source_visibility_authority import SourceVisibilityProducer


def pair():
    return _RasterBandPair(
        a=(5, 10, 20, 25),
        b=(50, 10, 70, 25),
        gap_x0=21,
        gap_x1=49,
        row0=11,
        row1=24,
        thickness_a=16,
        thickness_b=14,
        reasons=(),
    )


def source_mask(p):
    mask = np.zeros((120, 200), dtype=np.uint8)
    for x0, y0, x1, y1 in (p.a, p.b):
        mask[y0 : y1 + 1, x0 : x1 + 1] = 1
    for y in (p.row0, p.row1):
        mask[y, p.gap_x0 : p.gap_x1 + 1] = 1
    return mask


def test_exact_matching_outer_faces_separate_tracks_from_source_wall_continuation():
    p = pair()
    mask = source_mask(p)
    before = mask.copy()
    original = deepcopy(p)
    assert _raster_wall_face_continues(mask, p)
    assert not _raster_wall_face_continues(mask, p, paired_original_faces_shadow=True)
    assert _raster_wall_face_continues(mask, p, paired_original_faces_shadow=False)
    assert np.array_equal(mask, before) and p == original


@pytest.mark.parametrize("face", ["top", "bottom", "both"])
def test_actual_source_outer_face_continuation_remains_opposing_evidence(face):
    p = pair()
    mask = source_mask(p)
    for y in (
        (p.a[1], p.a[3])
        if face == "both"
        else (p.a[1],)
        if face == "top"
        else (p.a[3],)
    ):
        mask[y, p.gap_x0 : p.gap_x1 + 1] = 1
    assert _raster_wall_face_continues(mask, p, paired_original_faces_shadow=True)


@pytest.mark.parametrize(
    "other", [(50, 9, 70, 25), (50, 10, 70, 26), (50, 11, 70, 24), (50, 8, 70, 28)]
)
def test_nonidentical_source_band_bounds_retain_the_original_conservative_test(other):
    p = replace(pair(), b=other)
    mask = source_mask(p)
    assert _raster_wall_face_continues(mask, p, paired_original_faces_shadow=True)


@pytest.mark.parametrize(
    "scale,offset,transpose",
    [(1, (0, 0), False), (2, (11, 7), False), (3, (4, 3), True)],
)
def test_exact_source_translation_scale_quarter_turn_replay(scale, offset, transpose):
    p = pair()
    dx, dy = offset

    def box(b):
        return (
            scale * b[0] + dx,
            scale * b[1] + dy,
            scale * b[2] + dx,
            scale * b[3] + dy,
        )

    p = replace(
        p,
        a=box(p.a),
        b=box(p.b),
        gap_x0=scale * p.gap_x0 + dx,
        gap_x1=scale * p.gap_x1 + dx,
        row0=scale * p.row0 + dy,
        row1=scale * p.row1 + dy,
        thickness_a=scale * (p.thickness_a - 1) + 1,
        thickness_b=scale * (p.thickness_b - 1) + 1,
    )
    mask = np.zeros((300, 350), dtype=np.uint8)
    for b in (p.a, p.b):
        mask[b[1] : b[3] + 1, b[0] : b[2] + 1] = 1
    mask[p.row0, p.gap_x0 : p.gap_x1 + 1] = 1
    mask[p.row1, p.gap_x0 : p.gap_x1 + 1] = 1
    if transpose:
        page = np.ascontiguousarray(mask.T)
        mask = np.ascontiguousarray(page.T)  # Existing vertical-axis normalization.
    before = mask.copy()
    assert _raster_wall_face_continues(mask, p)
    assert not _raster_wall_face_continues(mask, p, paired_original_faces_shadow=True)
    assert np.array_equal(mask, before)
    assert not _raster_wall_face_continues(mask, p, paired_original_faces_shadow=True)


def test_source_splitting_direction_and_unrelated_ink_do_not_change_the_face_question():
    p = pair()
    mask = source_mask(p)
    for ordering in (
        ((0, 0, 4, 4), (80, 80, 100, 85)),
        ((80, 80, 100, 85), (0, 0, 4, 4)),
    ):
        changed = mask.copy()
        for x0, y0, x1, y1 in ordering:
            changed[y0 : y1 + 1, x0 : x1 + 1] = 1
        assert not _raster_wall_face_continues(
            changed, p, paired_original_faces_shadow=True
        )
    # A different crop/split of each band's along direction retains its exact
    # original common outer faces; no endpoint ownership is elected here.
    assert not _raster_wall_face_continues(
        mask,
        replace(p, a=(15, 10, 20, 25), b=(50, 10, 60, 25)),
        paired_original_faces_shadow=True,
    )


@pytest.mark.parametrize("bad", [1, 0, None, "true", []])
def test_policy_is_explicit_at_source_and_predicate(bad):
    with pytest.raises(ValueError, match="explicit boolean"):
        SourceVisibilityProducer(
            producer_method="test",
            producer_version="1",
            raster_paired_outer_faces_shadow=bad,
        )
    with pytest.raises(ValueError, match="explicit boolean"):
        _raster_wall_face_continues(
            source_mask(pair()), pair(), paired_original_faces_shadow=bad
        )


def test_source_policy_cannot_change_after_authority_creation():
    source = SourceVisibilityProducer(
        producer_method="test",
        producer_version="1",
        raster_paired_outer_faces_shadow=True,
    )
    authority = source.physical_opening_authority()
    assert authority is source.physical_opening_authority()
    assert authority._raster_paired_outer_faces_shadow is True
    source._raster_paired_outer_faces_shadow = False
    with pytest.raises(RuntimeError, match="policy changed"):
        source.physical_opening_authority()
    with pytest.raises(RuntimeError, match="policy changed"):
        authority.prove_existence(None)


def test_both_local_ends_narrowed_cannot_borrow_remote_envelope_faces():
    p = replace(pair(), thickness_a=14, thickness_b=14)
    mask = source_mask(p)
    assert _raster_wall_face_continues(mask, p, paired_original_faces_shadow=True)


def test_ordinary_source_still_has_original_policy_and_cached_identity():
    source = SourceVisibilityProducer(producer_method="test", producer_version="1")
    assert source._raster_paired_outer_faces_shadow is False
    authority = source.physical_opening_authority()
    assert authority._raster_paired_outer_faces_shadow is False
    assert source.physical_opening_authority() is authority


def _notched_source_pdf(turns=0, scale=1.0, outer_continuation=False):
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    gray[150, 400:404] = 255
    gray[164, 400:404] = 255
    for y in (151, 163):
        cv2.line(gray, (240, y), (400, y), 0, 1)
    if outer_continuation:
        for y in (150, 164):
            cv2.line(gray, (240, y), (400, y), 0, 1)
    gray = np.ascontiguousarray(np.rot90(gray, turns))
    ok, png = cv2.imencode(".png", gray)
    assert ok
    doc = fitz.open()
    page = doc.new_page(
        width=gray.shape[1] * scale / 2.0, height=gray.shape[0] * scale / 2.0
    )
    page.insert_image(page.rect, stream=bytes(png), keep_proportion=False)
    payload = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return payload


def _source_records(payload, enabled, *, double_face_negative=False):
    from tests.test_raster_framed_opening_g17_contract import _corroborated_records

    source = SourceVisibilityProducer(
        producer_method="paired-source-test",
        producer_version="1",
        raster_paired_outer_faces_shadow=enabled,
        raster_double_face_negative_shadow=double_face_negative,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id="paired-source-test",
        source_bytes=payload,
        source_locator="memory://paired-source-test.pdf",
        page_ids=("1",),
    )
    pub = source.augment_with_raster_opening_primitives(
        pub.revision.revision_id, page_ids=("1",)
    )
    before = deepcopy(source._producer._store.observations)
    records = _corroborated_records(source, pub)
    assert source._producer._store.observations == before
    return source, pub, records


@pytest.mark.parametrize(
    "turns,scale", [(0, 1.0), (1, 1.0), (2, 1.0), (3, 1.0), (0, 0.5)]
)
def test_paired_shadow_retains_double_painted_face_opposition_under_transforms(
    turns, scale
):
    payload = _notched_source_pdf(turns, scale)
    old, old_pub, old_records = _source_records(payload, False)
    source, pub, records = _source_records(payload, True, double_face_negative=True)
    assert old_pub == pub
    assert not old_records
    # The exact original fixture paints two uninterrupted tracks at the
    # upper/lower band quarters. The separate double-face opposing evidence
    # introduced on main must survive a paired-outer-face shadow nomination.
    assert not records
    comparisons = [
        r
        for rs in source.physical_opening_authority()._raster_outer_face_comparison_cache.values()
        for r in rs
    ]
    assert any(
        r["original_common_row_continuity"]
        and not r["paired_original_outer_face_continuity"]
        for r in comparisons
    )


def test_paired_face_policy_does_not_enable_the_separate_double_face_negative():
    payload = _notched_source_pdf()
    source, pub, records = _source_records(payload, True)
    negative, negative_pub, negative_records = _source_records(
        payload, True, double_face_negative=True)
    assert pub == negative_pub
    assert records and not negative_records
    assert source.physical_opening_authority()._raster_double_face_negative_shadow is False
    assert negative.physical_opening_authority()._raster_double_face_negative_shadow is True


def test_actual_outer_face_negative_survives_original_raster_source_replay():
    payload = _notched_source_pdf(outer_continuation=True)
    _source, _pub, records = _source_records(payload, True)
    assert not records


def test_scaling_outside_existing_band_thickness_domain_does_not_relax_detector_caps():
    from pb_raster_opening_source_primitives import BAND_MAX_THICKNESS_PT

    # The original fixture's15 source pixels at2x become15 PDF points.
    assert 15.0 > BAND_MAX_THICKNESS_PT
    payload = _notched_source_pdf(scale=2.0)
    _old, _old_pub, old_records = _source_records(payload, False)
    _source, _pub, records = _source_records(payload, True)
    assert not records and not old_records


def test_new_physical_policy_cannot_expand_original_source_capture_or_reissue_snapshot():
    payload = _notched_source_pdf()
    old, old_pub, old_records = _source_records(payload, False)
    source, pub, records = _source_records(payload, True, double_face_negative=True)
    assert not old_records and not records and old_pub == pub
    expected = old._proven_raster_opening_flank_boxes(old_pub, "1")
    actual = source._proven_raster_opening_flank_boxes(pub, "1")
    assert actual == expected == ()
    assert source.physical_opening_authority()._raster_paired_outer_faces_shadow is True
    assert (
        source._physical_source_capture_authority_cache._raster_paired_outer_faces_shadow
        is False
    )
    assert source.published_snapshot_for_revision(pub.revision.revision_id) == pub


def test_paired_outer_policy_is_separate_from_explicit_unmeasured_source_policy():
    from inspect import signature
    source=SourceVisibilityProducer(
        producer_method="paired-original-g17-shadow",
        producer_version="1.0.0",
        raster_paired_outer_faces_shadow=True,
    )
    physical=source.physical_opening_authority()
    assert physical._raster_paired_outer_faces_shadow is True
    # The default capture cannot expand the original physical set.
    from pb_source_visibility_authority import SourceVisibilityProducer as SourceType
    assert "include_unmeasured_ink_closed_flanks_shadow" not in str(
        signature(SourceType.augment_with_raster_visible_segments)
    )
    assert "include_unmeasured_ink_closed_flanks_shadow" in str(
        signature(SourceType._proven_raster_opening_flank_boxes)
    )


def test_original_producer_default_is_not_modified_by_shadow_ctor():
    s=SourceVisibilityProducer(
        producer_method="old-original-paired-face-baseline",
        producer_version="1.0.0",
    )
    assert s._raster_paired_outer_faces_shadow is False
    assert s.physical_opening_authority()._raster_paired_outer_faces_shadow is False
