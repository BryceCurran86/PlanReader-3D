from __future__ import annotations

import cv2
import fitz
import numpy as np
import pytest
from dataclasses import replace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _sheet(
    *,
    frame_lines: int,
    continue_faces: bool = False,
) -> np.ndarray:
    """One generic raster wall-band interruption; no text or dimensions."""

    gray = np.full((360, 640), 255, np.uint8)
    # 7 pt source wall thickness when the 640 px image fills a 320 pt page.
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)

    for y in (154, 160)[:frame_lines]:
        cv2.line(gray, (240, y), (400, y), 0, 1)

    if continue_faces:
        # A recess / glazing-style outline keeps the actual wall faces running
        # through the gap. Positive frame lines inside the band cannot override it.
        cv2.line(gray, (240, 150), (400, 150), 0, 1)
        cv2.line(gray, (240, 164), (400, 164), 0, 1)
    return gray


def _pdf(
    *,
    frame_lines: int,
    continue_faces: bool = False,
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320.0, height=180.0)
    page.insert_image(
        page.rect,
        stream=_png(
            _sheet(
                frame_lines=frame_lines,
                continue_faces=continue_faces,
            )
        ),
        keep_proportion=False,
    )
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _prepare(
    *,
    frame_lines: int,
    continue_faces: bool = False,
):
    producer = SourceVisibilityProducer(
        producer_method="raster-framed-g17-contract",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="raster-framed-g17-contract",
        source_bytes=_pdf(
            frame_lines=frame_lines,
            continue_faces=continue_faces,
        ),
        source_locator="memory://raster-framed-g17-contract.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    assert published.raster_opening_primitive_observation_ids
    return producer, published


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _corroborated_records(producer, published):
    authority = producer.physical_opening_authority()
    records = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(
            _selector(published, observation_id)
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            records[result.existence_record.record_id] = result.existence_record
    return tuple(records[key] for key in sorted(records))


def test_g17_promotes_one_framed_raster_wall_band_interruption() -> None:
    """EXPECTED RED until G17 explicitly consumes isolated raster primitives."""

    producer, published = _prepare(frame_lines=2)
    records = _corroborated_records(producer, published)

    assert len(records) == 1
    record = records[0]
    assert record.proposition == PHYSICAL_OPENING_EXISTS
    assert record.structural_pattern == "raster_framed_wall_band_interruption"
    assert len(record.source_observation_ids) >= 8


def test_bare_raster_wall_break_does_not_prove_an_opening() -> None:
    producer, published = _prepare(frame_lines=0)
    assert _corroborated_records(producer, published) == ()


def test_one_frame_line_is_not_enough_to_prove_an_opening() -> None:
    producer, published = _prepare(frame_lines=1)
    assert _corroborated_records(producer, published) == ()


def test_face_continuation_blocks_frame_lookalike() -> None:
    producer, published = _prepare(
        frame_lines=2,
        continue_faces=True,
    )
    assert _corroborated_records(producer, published) == ()


def _closure_source(gray, *, native_line=False, scale=1, floor_plan_title=False):
    doc = fitz.open()
    page = doc.new_page(width=scale * gray.shape[1] / 2, height=scale * gray.shape[0] / 2)
    page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
    if native_line:
        page.draw_line((10, 20), (40, 20), color=(0, 0, 0), width=1)
    if floor_plan_title:
        page.insert_text((10, 15), "FLOOR PLAN", fontsize=8)
    payload = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    source = SourceVisibilityProducer(producer_method="raster-candidate-audit", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="raster-candidate-audit", source_bytes=payload,
        source_locator="memory://candidate-audit.pdf", page_ids=("1",))
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",))
    return source, published


@pytest.mark.parametrize("turns", range(4))
def test_complete_raster_gap_support_is_reproved_under_quarter_turns(turns):
    gray = np.ascontiguousarray(np.rot90(_sheet(frame_lines=2), turns))
    before = gray.copy()
    source, published = _closure_source(gray)
    authority = source.physical_opening_authority()
    selector = _selector(published, published.raster_opening_primitive_observation_ids[0])
    closure = authority.assess_raster_candidate_closure(selector)
    assert closure.candidate_universe_complete
    assert closure.raw_candidate_count == closure.resolved_candidate_count == 1
    assert closure.unresolved_observation_ids == ()
    assert closure == authority.assess_raster_candidate_closure(selector)
    assert np.array_equal(gray, before)
    assert len(_corroborated_records(source, published)) == 1


@pytest.mark.parametrize("frame_lines", [0, 1])
def test_weak_gap_is_retained_and_cannot_close_the_raster_universe(frame_lines):
    source, published = _prepare(frame_lines=frame_lines)
    closure = source.physical_opening_authority().assess_raster_candidate_closure(
        _selector(published, published.raster_opening_primitive_observation_ids[0]))
    assert not closure.candidate_universe_complete
    assert closure.raw_candidate_count == 1
    assert closure.resolved_candidate_count == 0
    assert len(closure.unresolved_candidate_ids) == 1
    assert len(closure.unresolved_observation_ids) == 6


def test_a_valid_opening_cannot_hide_a_second_bare_wall_gap():
    gray = _sheet(frame_lines=2)
    cv2.rectangle(gray, (30, 260), (240, 274), 0, -1)
    cv2.rectangle(gray, (400, 260), (610, 274), 0, -1)
    source, published = _closure_source(gray, native_line=True)
    closure = source.physical_opening_authority().assess_raster_candidate_closure(
        _selector(published, published.raster_opening_primitive_observation_ids[0]))
    assert not closure.candidate_universe_complete
    assert closure.raw_candidate_count == 2
    assert closure.resolved_candidate_count == 1
    assert len(closure.unresolved_observation_ids) == 6
    from pb_semantic_opening_enumeration_authority import SemanticOpeningEnumerationProducer
    result = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source).publish_page_scope(
        revision_id=published.revision.revision_id, decision_scope_id="weak-gap", page_ids=("1",))
    assert len(result.record.physical_opening_record_ids) == 1
    assert not result.record.physical_opening_universe_complete
    assert set(closure.unresolved_observation_ids) <= set(result.record.residual_visible_observation_ids)


def test_zero_detected_candidates_does_not_authenticate_completeness():
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (610, 164), 0, -1)
    source, published = _closure_source(gray)
    assert published.raster_opening_primitive_observation_ids
    closure = source.physical_opening_authority().assess_raster_candidate_closure(
        _selector(published, published.raster_opening_primitive_observation_ids[0]))
    assert closure.raw_candidate_count == 0
    assert not closure.candidate_universe_complete


@pytest.mark.parametrize("scale,pad", [(0.5, 0), (1, 40)])
def test_raster_candidate_audit_preserves_positive_coverage_under_scale_and_translation(scale, pad):
    gray = np.pad(_sheet(frame_lines=2), ((pad, pad), (pad, pad)), constant_values=255)
    source, published = _closure_source(gray, scale=scale)
    result = source.physical_opening_authority().assess_raster_candidate_closure(
        _selector(published, published.raster_opening_primitive_observation_ids[0]))
    assert result.candidate_universe_complete
    assert result.raw_candidate_count == result.resolved_candidate_count == 1


def test_transform_outside_existing_detector_proof_cannot_gain_completeness():
    source, published = _closure_source(_sheet(frame_lines=2), scale=2)
    result = source.physical_opening_authority().assess_raster_candidate_closure(
        _selector(published, published.raster_opening_primitive_observation_ids[0]))
    # The existing raster morphology does not prove this enlarged stroke family.
    # An empty candidate path must remain incomplete rather than certify zero.
    assert not result.candidate_universe_complete
    assert result.raw_candidate_count == 0


@pytest.mark.parametrize("warm", [False, True])
@pytest.mark.parametrize("defect", ["missing_receipt", "geometry", "source_bytes", "snapshot"])
def test_raster_candidate_closure_reauthenticates_the_whole_source_before_cache(warm, defect):
    source, published = _prepare(frame_lines=2)
    authority = source.physical_opening_authority()
    selector = _selector(published, published.raster_opening_primitive_observation_ids[0])
    if warm:
        assert authority.assess_raster_candidate_closure(selector).candidate_universe_complete
    # Damage a non-seed support; a cached candidate must not hide it.
    other_id = published.raster_opening_primitive_observation_ids[-1]
    key = (published.snapshot.snapshot_id, other_id)
    if defect == "missing_receipt":
        del source._raster_opening_primitive_receipts[key]
    elif defect == "geometry":
        receipt = source._raster_opening_primitive_receipts[key]
        source._raster_opening_primitive_receipts[key] = replace(
            receipt, geometry=tuple(value + 1 for value in receipt.geometry))
    elif defect == "source_bytes":
        source._producer._store.source_bytes_by_revision[published.revision.revision_id] = b"changed"
    else:
        selector = replace(selector, snapshot_id="unowned-snapshot")
    result = authority.assess_raster_candidate_closure(selector)
    assert not result.candidate_universe_complete
    assert result.status in {EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT}


def test_positive_candidate_closure_does_not_default_an_opening_count_to_one():
    from pb_generic_opening_count_authority import GenericOpeningCountProducer, GenericOpeningCountSelector
    from pb_opening_universe_completeness_source_adapter import build_semantic_opening_inventory_completeness
    from pb_page_view_class_source_adapter import build_source_page_view_class_authority
    source, published = _closure_source(_sheet(frame_lines=2), native_line=True, floor_plan_title=True)
    completeness = build_semantic_opening_inventory_completeness(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        decision_scope_id="audit-count", page_ids=("1",))
    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=completeness,
        physical_opening_authority=source.physical_opening_authority(),
        viewport_view_class_authority=build_source_page_view_class_authority(
            source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=("1",)))
    result = producer.publish(GenericOpeningCountSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        decision_scope_id="audit-count"))
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is None
