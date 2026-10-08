"""Actual raster PDFs exercise source-only dimension and schedule handoffs."""
from __future__ import annotations

from dataclasses import replace
import hashlib

import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_dimension_authority import OPENING_DIMENSION_EXISTENCE_REQUIRED
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_schedule_opening_instance_binding_authority import (
    BINDING_AMBIGUOUS_ROWS,
    BINDING_AMBIGUOUS_TAGS,
    BINDING_NO_CONTAINED_TAG,
    BINDING_OPENING_UNRESOLVED,
    BINDING_PARTIAL_SOURCE_COVERAGE,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_door_swing_g17_contract import _pdf, _sheet
from test_raster_framed_opening_g17_contract import _pdf as _framed_pdf


def _prepare(payload: bytes, *, pages=None):
    source = SourceVisibilityProducer(
        producer_method="raster-measurement-source-handoff",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="raster-measurement-source-handoff",
        source_bytes=payload,
        source_locator="memory://raster-measurement-source-handoff.pdf",
        page_ids=pages,
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",),
    )
    physical = source.physical_opening_authority()
    proven = {}
    for oid in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        result = physical.prove_existence(selector)
        if result.status is Status.CORROBORATED and result.proposition == PHYSICAL_OPENING_EXISTS:
            assert result.existence_record is not None
            proven.setdefault(result.existence_record.record_id, (selector, result.existence_record))
    assert len(proven) == 1
    selector, opening = next(iter(proven.values()))
    return source, published, selector, opening


def _swing_pdf(*, rotated=False):
    gray = _sheet(leaf=True, arc=True, leaf_bundle=True)
    if rotated:
        gray = np.ascontiguousarray(np.rot90(gray))
    return _pdf(gray)


@pytest.mark.parametrize("family", ("swing", "frame"))
@pytest.mark.parametrize("rotated", (False, True))
def test_all_exact_isolated_supports_authenticate_without_inventing_width(family, rotated):
    if family == "swing":
        payload = _swing_pdf(rotated=rotated)
    else:
        from test_raster_framed_opening_g17_contract import _sheet as _frame_sheet
        gray = _frame_sheet(frame_lines=2)
        payload = _pdf(np.ascontiguousarray(np.rot90(gray))) if rotated else _framed_pdf(frame_lines=2)
    source, published, selector, opening = _prepare(payload)
    authority = source.opening_dimension_authority()
    before = replace(opening)
    for _ in range(2):
        support = authority._visible_records(opening)
        assert {row.observation_id for row in support} == set(opening.source_observation_ids)
        assert all(row.source_sha256 == hashlib.sha256(payload).hexdigest() for row in support)
        width = authority.resolve_width(selector)
        assert width.status is Status.ABSTAINED
        assert width.value_mm is None
        assert OPENING_DIMENSION_EXISTENCE_REQUIRED not in width.reason_codes
        assert any("jamb" in reason or "witness" in reason for reason in width.reason_codes)
        assert source.physical_opening_authority().prove_existence(selector).existence_record == opening
    assert authority._visible_records(replace(
        opening, source_observation_ids=tuple(reversed(opening.source_observation_ids)),
    )) == tuple(reversed(authority._visible_records(opening)))
    assert opening == before
    assert published.revision.source_sha256 == hashlib.sha256(payload).hexdigest()


def test_partial_foreign_and_stale_support_cannot_be_used_for_measurement():
    source, _, _, opening = _prepare(_swing_pdf())
    authority = source.opening_dimension_authority()
    assert authority._visible_records(replace(
        opening, source_observation_ids=(*opening.source_observation_ids[:-1], "unowned"),
    )) == ()
    assert authority._visible_records(replace(opening, source_sha256="0" * 64)) == ()
    assert authority._visible_records(replace(opening, snapshot_id="foreign-snapshot")) == ()


def test_missing_receipt_after_warm_support_read_cannot_publish_width():
    source, _, selector, opening = _prepare(_swing_pdf())
    authority = source.opening_dimension_authority()
    assert authority._visible_records(opening)
    key = (opening.snapshot_id, opening.source_observation_ids[-1])
    receipt = source._raster_opening_primitive_receipts.pop(key)
    try:
        assert authority._visible_records(opening) == ()
        width = authority.resolve_width(selector)
        assert width.status is not Status.CORROBORATED
        assert width.value_mm is None
    finally:
        source._raster_opening_primitive_receipts[key] = receipt


def test_ordinary_conflict_is_never_retried_as_isolated_support(monkeypatch):
    source, _, _, opening = _prepare(_swing_pdf())
    authority = source.opening_dimension_authority()
    conflict = authority._visibility._conflict("test_ordinary_source_conflict")
    monkeypatch.setattr(authority._visibility, "resolve_visible", lambda selector: conflict)

    def forbidden(selector):
        raise AssertionError("a conflicting source claim must not fall back")
    monkeypatch.setattr(authority._visibility, "resolve_raster_opening_primitive", forbidden)
    assert authority._visible_records(opening) == ()


def _tagged_swing_pdf(*, tag_mode="inside", duplicate_row=False, rotated=False):
    payload = _swing_pdf(rotated=rotated)
    _, _, _, opening = _prepare(payload)
    assert opening.aperture_bbox_pt is not None
    x0, y0, x1, y1 = opening.aperture_bbox_pt
    font = min(2.0, (y1 - y0) / 5.0, (x1 - x0) / 12.0)
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        page = doc[0]
        if tag_mode == "inside":
            page.insert_text(fitz.Point((x0 + x1) / 2.0, (y0 + y1) / 2.0 + font / 2.0), "D1", fontsize=font)
        elif tag_mode == "ambiguous":
            if x1 - x0 > y1 - y0:
                positions = ((x0 + (x1 - x0) / 3.0, (y0 + y1) / 2.0),
                             (x0 + 2.0 * (x1 - x0) / 3.0, (y0 + y1) / 2.0))
            else:
                positions = (((x0 + x1) / 2.0, y0 + (y1 - y0) / 3.0),
                             ((x0 + x1) / 2.0, y0 + 2.0 * (y1 - y0) / 3.0))
            for mark, (x, y) in zip(("D1", "D2"), positions):
                page.insert_text(fitz.Point(x, y + font / 2.0), mark, fontsize=font)
        elif tag_mode == "outside":
            # Inside the swing sector in the unrotated drawing, but outside
            # the jamb-bounded aperture. This must not govern the opening.
            page.insert_text(fitz.Point(155.0, 120.0), "D1", fontsize=2.0)
        else:
            raise ValueError(tag_mode)
        schedule = doc.new_page(width=760.0, height=220.0)
        for text, x in zip(("MARK", "ROWDTH-MM", "ROHT-MM"), (50.0, 200.0, 350.0)):
            schedule.insert_text(fitz.Point(x, 50.0), text)
        for text, x in zip(("D1", "931", "2047"), (50.0, 200.0, 350.0)):
            schedule.insert_text(fitz.Point(x, 80.0), text)
        if duplicate_row:
            for text, x in zip(("D1", "931", "2047"), (50.0, 200.0, 350.0)):
                schedule.insert_text(fitz.Point(x, 110.0), text)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _binding(source, selector):
    return ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source).publish_scope(
        opening_selector=selector, decision_scope_id="raster-source-handoff",
    )


@pytest.mark.parametrize("rotated", (False, True))
def test_proven_swing_aperture_owns_one_explicit_schedule_row_without_a_count(rotated):
    payload = _tagged_swing_pdf(rotated=rotated)
    source, published, selector, opening = _prepare(payload)
    result = _binding(source, selector)
    assert result.status is Status.CORROBORATED
    assert result.record is not None
    record = result.record
    assert record.opening_record_id == opening.record_id
    assert record.source_sha256 == hashlib.sha256(payload).hexdigest()
    assert record.tag_mark == "D1"
    assert record.schedule_page_id == "2"
    assert record.schedule_row_width_mm == 931
    assert record.schedule_row_height_mm == 2047
    assert record.schedule_row_dimension_basis == "rough_opening"
    assert record.schedule_row_count is None
    assert record.schedule_row_count_explicit is False
    assert record.tag_observation_id in published.text_observation_ids
    assert set(record.schedule_row_observation_ids) <= set(published.text_observation_ids)
    assert _binding(source, selector) == result
    assert source.physical_opening_authority().prove_existence(selector).existence_record == opening
    width = source.opening_dimension_authority().resolve_width(selector)
    assert width.status is Status.ABSTAINED
    assert width.value_mm is None


@pytest.mark.parametrize(("mode", "status", "reason"), (
    ("outside", Status.ABSTAINED, BINDING_NO_CONTAINED_TAG),
    ("ambiguous", Status.CONFLICT, BINDING_AMBIGUOUS_TAGS),
))
def test_swing_sector_and_ambiguous_marks_cannot_own_the_aperture(mode, status, reason):
    source, _, selector, _ = _prepare(_tagged_swing_pdf(tag_mode=mode))
    result = _binding(source, selector)
    assert result.status is status
    assert reason in result.reason_codes
    assert result.record is None


def test_equal_dimensions_in_duplicate_source_rows_still_conflict():
    source, _, selector, _ = _prepare(_tagged_swing_pdf(duplicate_row=True))
    result = _binding(source, selector)
    assert result.status is Status.CONFLICT
    assert BINDING_AMBIGUOUS_ROWS in result.reason_codes
    assert result.record is None


def test_partial_source_and_stale_selector_cannot_bind_schedule():
    payload = _tagged_swing_pdf()
    source, _, selector, _ = _prepare(payload, pages=("1",))
    result = _binding(source, selector)
    assert result.status is Status.ABSTAINED
    assert BINDING_PARTIAL_SOURCE_COVERAGE in result.reason_codes
    assert result.record is None
    result = _binding(source, replace(selector, source_sha256="0" * 64))
    assert result.status is Status.ABSTAINED
    assert BINDING_OPENING_UNRESOLVED in result.reason_codes
    assert result.record is None
