"""Production regressions for source-space opening host-frame authority."""
from __future__ import annotations

import dataclasses
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_host_frame_authority import (
    OpeningHostFrameAuthority,
    OpeningHostFrameProducer,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf(*, dx: float = 0.0, dy: float = 0.0, reverse: bool = False) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=420.0, height=320.0)
        shape = page.new_shape()
        segments = [
            ((20.0 + dx, 80.0 + dy), (120.0 + dx, 80.0 + dy)),
            ((160.0 + dx, 80.0 + dy), (280.0 + dx, 80.0 + dy)),
            ((20.0 + dx, 100.0 + dy), (120.0 + dx, 100.0 + dy)),
            ((160.0 + dx, 100.0 + dy), (280.0 + dx, 100.0 + dy)),
            ((120.0 + dx, 80.0 + dy), (120.0 + dx, 100.0 + dy)),
            ((160.0 + dx, 80.0 + dy), (160.0 + dx, 100.0 + dy)),
        ]
        for start, end in segments:
            if reverse:
                start, end = end, start
            shape.draw_line(fitz.Point(*start), fitz.Point(*end))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _fixture(payload: bytes | None = None):
    source = SourceVisibilityProducer(
        producer_method="opening-host-frame-production-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-host-frame-production",
        source_bytes=payload or _pdf(),
        source_locator="memory://opening-host-frame-production.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    opening_selector = None
    opening_record = None
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS and result.existence_record is not None:
            opening_selector = selector
            opening_record = result.existence_record
            break
    assert opening_selector is not None and opening_record is not None

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    universe_authority = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    universe_selector = OpeningHostWallUniverseSelector(
        document_id=opening_record.document_id,
        revision_id=opening_record.revision_id,
        source_sha256=opening_record.source_sha256,
        snapshot_id=opening_record.snapshot_id,
        page_id=opening_record.page_id,
        decision_scope_id=f"wall-source:page-{opening_record.page_id}",
    )
    binding_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=universe_authority,
    )
    binding = binding_producer.publish(
        opening_left_selector=opening_selector,
        opening_right_selector=opening_selector,
        host_universe_selector=universe_selector,
    )
    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.record is not None
    binding_selector = OpeningHostBindingSelector(
        document_id=binding.record.document_id,
        revision_id=binding.record.revision_id,
        source_sha256=binding.record.source_sha256,
        snapshot_id=binding.record.snapshot_id,
        page_id=binding.record.page_id,
        decision_scope_id=binding.record.decision_scope_id,
        opening_identity_id=binding.record.opening_identity_id,
    )
    return physical, opening_selector, opening_record, binding_producer, binding_selector, binding


def _frame(payload: bytes | None = None):
    physical, opening_selector, opening, binding_producer, binding_selector, binding = _fixture(payload)
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
    )
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=binding_selector,
    )
    return producer, result, opening, binding, binding_selector


def test_authority_and_producer_are_sealed_and_no_raw_geometry_surface() -> None:
    physical, _opening_selector, _opening, binding_producer, _binding_selector, _binding = _fixture()
    with pytest.raises(TypeError):
        OpeningHostFrameProducer(
            physical,
            binding_producer.authority(),
        )
    with pytest.raises(ValueError):
        OpeningHostFrameAuthority({}, _seal=object())
    forbidden = {
        "host_wall_id", "origin", "axis", "normal", "u0", "u1", "jambs",
        "thickness", "scale", "px_per_m", "confidence", "nearest", "radius",
    }
    params = set(inspect.signature(OpeningHostFrameProducer.publish).parameters)
    assert not (params & forbidden)


def test_real_source_host_frame_resolves_and_replays() -> None:
    producer, result, opening, binding, _binding_selector = _frame()
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    evidence = result.evidence
    assert evidence.opening_identity_id == opening.record_id
    assert evidence.host_binding_record_id == binding.record.record_id
    assert evidence.host_wall_id == binding.record.host_wall_id
    assert evidence.coordinate_unit == "pdf_point"
    # The frame is host-wall-local, not opening-local.  The authenticated host
    # band runs x=20..280 around a 40-point aperture at x=120..160, so the
    # opening occupies u=100..140 in the common wall frame.
    assert evidence.origin_pt == (20.0, 90.0)
    assert evidence.axis_unit == (1.0, 0.0)
    assert evidence.u0_pt == 100.0
    assert abs(evidence.u1_pt - 140.0) <= 1e-6
    assert abs(evidence.wall_thickness_pt - 20.0) <= 1e-6
    assert producer.authority().resolve(evidence.selector) == result


def test_translation_changes_host_origin_only_not_wall_local_geometry() -> None:
    first = _frame(_pdf())[1].evidence
    translated = _frame(_pdf(dx=50.0, dy=40.0))[1].evidence
    assert first is not None and translated is not None
    assert first.origin_pt == (20.0, 90.0)
    assert translated.origin_pt == (70.0, 130.0)
    assert first.axis_unit == translated.axis_unit
    assert first.u0_pt == translated.u0_pt == 100.0
    assert abs(first.u1_pt - translated.u1_pt) <= 1e-6
    assert abs(first.wall_thickness_pt - translated.wall_thickness_pt) <= 1e-6


def test_reversing_source_primitive_directions_keeps_canonical_frame() -> None:
    first = _frame(_pdf())[1].evidence
    reversed_frame = _frame(_pdf(reverse=True))[1].evidence
    assert first is not None and reversed_frame is not None
    assert first.origin_pt == reversed_frame.origin_pt
    assert first.axis_unit == reversed_frame.axis_unit
    assert first.normal_unit == reversed_frame.normal_unit
    assert first.u0_pt == reversed_frame.u0_pt
    assert abs(first.u1_pt - reversed_frame.u1_pt) <= 1e-6


def test_cross_wired_host_binding_selector_fails_closed() -> None:
    physical, opening_selector, _opening, binding_producer, binding_selector, _binding = _fixture()
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
    )
    wrong = dataclasses.replace(binding_selector, opening_identity_id="wrong-opening")
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=wrong,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


def test_wrong_opening_observation_cannot_reuse_valid_host_binding() -> None:
    physical, opening_selector, _opening, binding_producer, binding_selector, _binding = _fixture()
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
    )
    wrong = dataclasses.replace(opening_selector, observation_id="not-a-real-observation")
    result = producer.publish(
        opening_selector=wrong,
        host_binding_selector=binding_selector,
    )
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.evidence is None
