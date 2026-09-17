"""Production regressions for source-space opening whole-wall host-frame authority."""
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
    OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN,
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


def _multi_opening_pdf(*, remote_unproven: bool = False) -> bytes:
    openings = ((100.0, 140.0), (220.0, 260.0))
    intervals = ((20.0, 100.0), (140.0, 220.0), (260.0, 340.0))
    doc = fitz.open()
    try:
        page = doc.new_page(width=620.0, height=360.0)
        shape = page.new_shape()
        for y in (80.0, 100.0):
            for start, end in intervals:
                shape.draw_line(fitz.Point(start, y), fitz.Point(end, y))
        for start, end in openings:
            shape.draw_line(fitz.Point(start, 80.0), fitz.Point(start, 100.0))
            shape.draw_line(fitz.Point(end, 80.0), fitz.Point(end, 100.0))
        if remote_unproven:
            for y in (80.0, 100.0):
                shape.draw_line(fitz.Point(420.0, y), fitz.Point(480.0, y))
        shape.finish(width=1.0)
        shape.commit()
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _fixture(payload: bytes | None = None):
    source = SourceVisibilityProducer(
        producer_method="opening-host-frame-production-test",
        producer_version="2.0",
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
    return (
        physical,
        wall_authority,
        opening_selector,
        opening_record,
        binding_producer,
        binding_selector,
        binding,
    )


def _frame(payload: bytes | None = None):
    (
        physical,
        wall_authority,
        opening_selector,
        opening,
        binding_producer,
        binding_selector,
        binding,
    ) = _fixture(payload)
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=binding_selector,
    )
    return producer, result, opening, binding, binding_selector


def _multi_fixture(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="opening-host-frame-multi-production-test",
        producer_version="2.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-host-frame-multi-production",
        source_bytes=payload,
        source_locator="memory://opening-host-frame-multi-production.pdf",
    )
    physical = PhysicalOpeningAuthority(source.authority())
    discovered: dict[str, tuple[ObservationSelector, object]] = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            discovered.setdefault(result.existence_record.record_id, (selector, result.existence_record))
    assert len(discovered) == 2

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    first = next(iter(discovered.values()))[1]
    universe_authority = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    universe_selector = OpeningHostWallUniverseSelector(
        document_id=first.document_id,
        revision_id=first.revision_id,
        source_sha256=first.source_sha256,
        snapshot_id=first.snapshot_id,
        page_id=first.page_id,
        decision_scope_id=f"wall-source:page-{first.page_id}",
    )
    binding_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=universe_authority,
    )
    bound = []
    for opening_selector, opening in discovered.values():
        binding = binding_producer.publish(
            opening_left_selector=opening_selector,
            opening_right_selector=opening_selector,
            host_universe_selector=universe_selector,
        )
        assert binding.status is EvidenceResolutionStatus.CORROBORATED
        assert binding.record is not None
        bound.append(
            (
                opening,
                opening_selector,
                OpeningHostBindingSelector(
                    document_id=binding.record.document_id,
                    revision_id=binding.record.revision_id,
                    source_sha256=binding.record.source_sha256,
                    snapshot_id=binding.record.snapshot_id,
                    page_id=binding.record.page_id,
                    decision_scope_id=binding.record.decision_scope_id,
                    opening_identity_id=binding.record.opening_identity_id,
                ),
            )
        )
    bound.sort(key=lambda item: min(float(value) for value in item[0].source_bbox[::2]))
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )
    return producer, tuple(bound)


def test_authority_and_producer_are_sealed_and_no_raw_geometry_surface() -> None:
    (
        physical,
        wall_authority,
        _opening_selector,
        _opening,
        binding_producer,
        _binding_selector,
        _binding,
    ) = _fixture()
    with pytest.raises(TypeError):
        OpeningHostFrameProducer(
            physical,
            binding_producer.authority(),
            wall_authority,
        )
    with pytest.raises(ValueError):
        OpeningHostFrameAuthority({}, _seal=object())
    forbidden = {
        "host_wall_id", "origin", "axis", "normal", "u0", "u1", "jambs",
        "thickness", "scale", "px_per_m", "confidence", "nearest", "radius",
        "member_wall_candidate_ids", "complete", "claimed_complete",
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
    (
        physical,
        wall_authority,
        opening_selector,
        _opening,
        binding_producer,
        binding_selector,
        _binding,
    ) = _fixture()
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
    )
    wrong = dataclasses.replace(binding_selector, opening_identity_id="wrong-opening")
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=wrong,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


def test_wrong_opening_observation_cannot_reuse_valid_host_binding() -> None:
    (
        physical,
        wall_authority,
        opening_selector,
        _opening,
        binding_producer,
        binding_selector,
        _binding,
    ) = _fixture()
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
        physical_wall_candidate_authority=wall_authority,
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


def test_two_openings_share_one_whole_wall_frame() -> None:
    producer, bound = _multi_fixture(_multi_opening_pdf())
    frames = []
    for _opening, opening_selector, binding_selector in bound:
        result = producer.publish(
            opening_selector=opening_selector,
            host_binding_selector=binding_selector,
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.evidence is not None
        frames.append(result.evidence)
    assert {frame.origin_pt for frame in frames} == {(20.0, 90.0)}
    assert len({frame.whole_wall_frame_id for frame in frames}) == 1
    assert tuple((frame.u0_pt, frame.u1_pt) for frame in frames) == (
        (80.0, 120.0),
        (200.0, 240.0),
    )


def test_unproven_aligned_remote_fragments_block_whole_wall_frame() -> None:
    producer, bound = _multi_fixture(_multi_opening_pdf(remote_unproven=True))
    _opening, opening_selector, binding_selector = bound[0]
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=binding_selector,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_HOST_FRAME_WHOLE_WALL_UNPROVEN in result.reason_codes
