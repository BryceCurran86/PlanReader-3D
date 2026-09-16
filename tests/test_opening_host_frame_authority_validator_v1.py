"""Opening host-frame authority V1 validator.

TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / NOT FROZEN / DO NOT MERGE.

The future authority may expose authenticated *source-space* wall-local geometry
only after both G17 physical-opening existence and merged #381 host binding are
re-proved.  It does not establish physical units.
"""
from __future__ import annotations

import dataclasses
from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

MODULE_NAME = "pb_opening_host_frame_authority"
HAS_FRAME_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_FRAME_AUTHORITY,
    strict=True,
    reason="opening host-frame production authority is intentionally absent",
)

_FORBIDDEN_PUBLIC = {
    "host_wall_id", "wall_candidate_id", "wall_candidates", "origin", "origin_x",
    "origin_y", "axis", "normal", "u0", "u1", "u0_pt", "u1_pt", "jambs",
    "opening_span", "thickness", "scale", "px_per_m", "points_per_mm",
    "confidence", "nearest", "first", "radius", "complete", "claimed_complete",
}


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
        producer_method="opening-host-frame-validator",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-host-frame-doc",
        source_bytes=payload or _pdf(),
        source_locator="memory://opening-host-frame.pdf",
    )
    visibility = source.authority()
    physical = PhysicalOpeningAuthority(visibility)
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
    assert opening_selector is not None
    assert opening_record is not None

    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source).authority()
    universe_authority = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    decision_scope = f"wall-source:page-{opening_record.page_id}"
    universe_selector = OpeningHostWallUniverseSelector(
        document_id=opening_record.document_id,
        revision_id=opening_record.revision_id,
        source_sha256=opening_record.source_sha256,
        snapshot_id=opening_record.snapshot_id,
        page_id=opening_record.page_id,
        decision_scope_id=decision_scope,
    )
    universe = universe_authority.resolve_scope(universe_selector)
    assert universe.status is EvidenceResolutionStatus.CORROBORATED
    assert universe.scope_complete is True

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
    assert binding_producer.authority().resolve(binding_selector) == binding
    return physical, opening_selector, opening_record, binding_producer, binding_selector, binding


def test_merged_host_binding_real_source_fixture_is_positive() -> None:
    physical, _selector, opening, _producer, _binding_selector, binding = _fixture()
    geometry = host._opening_geometry(physical, opening)
    assert geometry is not None
    assert abs(geometry.length - 40.0) <= 1e-6
    assert abs(geometry.thickness - 20.0) <= 1e-6
    assert binding.record is not None
    assert binding.record.opening_identity_id == opening.record_id


def test_existing_host_selector_and_publish_surface_accept_no_raw_frame_truth() -> None:
    selector_fields = {field.name for field in fields(OpeningHostBindingSelector)}
    assert not (selector_fields & _FORBIDDEN_PUBLIC)
    params = set(inspect.signature(OpeningHostBindingProducer.publish).parameters)
    assert not (params & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_future_host_frame_api_is_sealed_selector_only() -> None:
    mod = importlib.import_module(MODULE_NAME)
    required = {
        "OpeningHostFrameSelector", "OpeningHostFrameEvidence", "OpeningHostFrameResult",
        "OpeningHostFrameProducer", "OpeningHostFrameAuthority",
    }
    assert required <= set(dir(mod))
    assert is_dataclass(mod.OpeningHostFrameSelector)
    assert not ({field.name for field in fields(mod.OpeningHostFrameSelector)} & _FORBIDDEN_PUBLIC)
    for callable_obj in (
        mod.OpeningHostFrameProducer.publish,
        mod.OpeningHostFrameAuthority.resolve,
    ):
        assert not (set(inspect.signature(callable_obj).parameters) & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_real_source_opening_and_host_publish_source_space_frame() -> None:
    mod = importlib.import_module(MODULE_NAME)
    physical, opening_selector, opening, binding_producer, binding_selector, binding = _fixture()
    producer = mod.OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
    )
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=binding_selector,
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    evidence = result.evidence
    assert evidence.opening_identity_id == opening.record_id
    assert evidence.host_binding_record_id == binding.record.record_id
    assert evidence.host_wall_id == binding.record.host_wall_id
    assert evidence.coordinate_unit == "pdf_point"
    assert abs(evidence.u0_pt - 0.0) <= 1e-9
    assert abs(evidence.u1_pt - 40.0) <= 1e-6
    assert abs(evidence.wall_thickness_pt - 20.0) <= 1e-6
    assert producer.authority().resolve(evidence.selector) == result


@EXPECTED_RED
def test_translation_changes_origin_only_not_local_span() -> None:
    mod = importlib.import_module(MODULE_NAME)
    results = []
    for payload in (_pdf(), _pdf(dx=50.0, dy=40.0)):
        physical, opening_selector, _opening, binding_producer, binding_selector, _binding = _fixture(payload)
        producer = mod.OpeningHostFrameProducer.from_authorities(
            physical_opening_authority=physical,
            host_binding_authority=binding_producer.authority(),
        )
        result = producer.publish(
            opening_selector=opening_selector,
            host_binding_selector=binding_selector,
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        results.append(result.evidence)
    first, translated = results
    assert first is not None and translated is not None
    assert first.u0_pt == translated.u0_pt == 0.0
    assert abs(first.u1_pt - translated.u1_pt) <= 1e-6
    assert abs(first.wall_thickness_pt - translated.wall_thickness_pt) <= 1e-6
    assert first.origin_pt != translated.origin_pt


@EXPECTED_RED
def test_reversing_all_source_segment_directions_does_not_reverse_local_frame() -> None:
    mod = importlib.import_module(MODULE_NAME)
    frames = []
    for payload in (_pdf(), _pdf(reverse=True)):
        physical, opening_selector, _opening, binding_producer, binding_selector, _binding = _fixture(payload)
        producer = mod.OpeningHostFrameProducer.from_authorities(
            physical_opening_authority=physical,
            host_binding_authority=binding_producer.authority(),
        )
        result = producer.publish(
            opening_selector=opening_selector,
            host_binding_selector=binding_selector,
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        frames.append(result.evidence)
    first, reversed_frame = frames
    assert first is not None and reversed_frame is not None
    assert first.axis_unit == reversed_frame.axis_unit
    assert first.origin_pt == reversed_frame.origin_pt
    assert abs(first.u1_pt - reversed_frame.u1_pt) <= 1e-6


@EXPECTED_RED
def test_cross_wired_host_binding_selector_fails_closed() -> None:
    mod = importlib.import_module(MODULE_NAME)
    physical, opening_selector, _opening, binding_producer, binding_selector, _binding = _fixture()
    producer = mod.OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=physical,
        host_binding_authority=binding_producer.authority(),
    )
    wrong = dataclasses.replace(binding_selector, opening_identity_id="different-opening")
    result = producer.publish(
        opening_selector=opening_selector,
        host_binding_selector=wrong,
    )
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.evidence is None
