"""Opening vertical-placement authority validator V1.

TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / DO NOT MERGE / NOT FROZEN.

The validator deliberately separates semantic schedule-row vertical placement from
physical-opening applicability. It must never turn height, type, or a door label into
an assumed sill/head.
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
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_schedule_opening_instance_binding_authority_v1 import (
    _draw_opening,
    _ingest,
    _opening_selector,
)

MODULE_NAME = "pb_opening_vertical_placement_authority"
HAS_VERTICAL_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_VERTICAL_AUTHORITY,
    strict=True,
    reason="opening vertical-placement production authority is intentionally absent",
)
SCOPE = "opening-vertical-placement:page-1"

_FORBIDDEN_PUBLIC = {
    "z0", "z1", "z0_mm", "z1_mm", "sill", "head", "sill_height",
    "head_height", "center_z", "centre_z", "height", "height_mm", "width",
    "width_mm", "raw_text", "text", "ocr_text", "header_text", "units",
    "unit_factor", "dimension_basis", "basis", "default_sill", "default_head",
    "default_height", "typical_height", "confidence", "nearest", "first",
    "radius", "complete", "authenticated", "is_valid",
}


def _module():
    assert HAS_VERTICAL_AUTHORITY, (
        "pb_opening_vertical_placement_authority is the missing production module; "
        "do not satisfy this validator with a test shim"
    )
    return importlib.import_module(MODULE_NAME)


def _placement_pdf(
    *,
    sill_heading: str = "ROUGH-OPENING-SILL-MM",
    head_heading: str = "ROUGH-OPENING-HEAD-MM",
    sill_value: str = "900",
    head_value: str = "3000",
    tag_text: str = "W1",
) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=760, height=650)
    _draw_opening(
        page,
        x0=20.0,
        gap0=100.0,
        gap1=140.0,
        x1=220.0,
        y0=100.0,
        y1=110.0,
    )
    page.insert_text(fitz.Point(112.0, 106.0), tag_text)
    xs = (50.0, 150.0, 250.0, 350.0, 520.0)
    header = ("MARK", "WIDTH", "HEIGHT", sill_heading, head_heading)
    row = (tag_text, "900", "2100", sill_value, head_value)
    for text, x in zip(header, xs):
        page.insert_text(fitz.Point(x, 500.0), text)
    for text, x in zip(row, xs):
        page.insert_text(fitz.Point(x, 530.0), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def _binding_fixture(payload: bytes | None = None):
    src = SourceVisibilityProducer(
        producer_method="opening-vertical-placement-validator",
        producer_version="1.0",
    )
    published = _ingest(src, payload or _placement_pdf(), "vertical-placement-doc")
    opening_selector = _opening_selector(published, src.authority())
    binder = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    binding = binder.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=SCOPE,
    )
    assert binding.status is EvidenceResolutionStatus.CORROBORATED
    assert binding.record is not None
    return src, binder, binding


def _row_texts(src: SourceVisibilityProducer, binding) -> tuple[str, ...]:
    record = binding.record
    assert record is not None
    text_integrity = src.text_integrity_authority()
    texts: list[str] = []
    for observation_id in record.schedule_row_observation_ids:
        resolved = text_integrity.resolve_text(
            ObservationSelector(
                document_id=record.document_id,
                revision_id=record.revision_id,
                source_sha256=record.source_sha256,
                snapshot_id=record.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert resolved.status is EvidenceResolutionStatus.CORROBORATED
        assert resolved.trusted_text is not None
        texts.append(str(resolved.trusted_text))
    return tuple(texts)


def test_merged_schedule_binding_preserves_full_governing_row_observations() -> None:
    src, _binder, binding = _binding_fixture()
    texts = set(_row_texts(src, binding))
    assert {"W1", "900", "2100", "3000"} <= texts


def test_existing_binding_public_surface_cannot_accept_vertical_truth() -> None:
    params = set(inspect.signature(ScheduleOpeningInstanceBindingProducer.publish_scope).parameters)
    assert not (params & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_public_types_are_sealed_selector_only_authorities() -> None:
    mod = _module()
    required = {
        "ScheduleRowVerticalPlacementProducer",
        "ScheduleRowVerticalPlacementAuthority",
        "ScheduleRowVerticalPlacementSelector",
        "OpeningVerticalPlacementProducer",
        "OpeningVerticalPlacementAuthority",
        "OpeningVerticalPlacementSelector",
    }
    assert required <= set(dir(mod))
    row_selector = mod.ScheduleRowVerticalPlacementSelector
    opening_selector = mod.OpeningVerticalPlacementSelector
    assert is_dataclass(row_selector)
    assert is_dataclass(opening_selector)
    assert not ({item.name for item in fields(row_selector)} & _FORBIDDEN_PUBLIC)
    assert not ({item.name for item in fields(opening_selector)} & _FORBIDDEN_PUBLIC)
    for callable_obj in (
        mod.ScheduleRowVerticalPlacementProducer.publish_scope,
        mod.OpeningVerticalPlacementProducer.publish_scope,
        mod.ScheduleRowVerticalPlacementAuthority.resolve,
        mod.OpeningVerticalPlacementAuthority.resolve,
    ):
        assert not (set(inspect.signature(callable_obj).parameters) & _FORBIDDEN_PUBLIC)


def _publish_row(mod, payload: bytes):
    src, binder, binding = _binding_fixture(payload)
    record = binding.record
    assert record is not None
    row_producer = mod.ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(src)
    row_selector = mod.ScheduleRowVerticalPlacementSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        schedule_page_id=record.schedule_page_id,
        schedule_row_observation_ids=record.schedule_row_observation_ids,
    )
    row_result = row_producer.publish_scope(row_selector)
    return src, binder, binding, row_producer, row_selector, row_result


def _publish_opening(mod, src, binder, binding, row_producer):
    record = binding.record
    assert record is not None
    opening_producer = mod.OpeningVerticalPlacementProducer.from_authorities(
        binding_authority=binder.authority(),
        row_vertical_placement_authority=row_producer.authority(),
    )
    selector = mod.OpeningVerticalPlacementSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        decision_scope_id=record.decision_scope_id,
        opening_record_id=record.opening_record_id,
    )
    return opening_producer, selector, opening_producer.publish_scope(selector)


@EXPECTED_RED
def test_explicit_rough_opening_sill_and_head_mm_produce_exact_instance_placement() -> None:
    mod = _module()
    src, binder, binding, row_producer, _row_selector, row_result = _publish_row(
        mod, _placement_pdf()
    )
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.z0_mm == 900.0
    assert row_result.evidence.z1_mm == 3000.0
    opening_producer, selector, result = _publish_opening(
        mod, src, binder, binding, row_producer
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.opening_record_id == selector.opening_record_id
    assert result.evidence.z0_mm == 900.0
    assert result.evidence.z1_mm == 3000.0
    assert opening_producer.authority().resolve(selector) == result


@pytest.mark.parametrize(
    "sill_heading,head_heading",
    [
        ("SILL-MM", "HEAD-MM"),
        ("FRAME-SILL-MM", "FRAME-HEAD-MM"),
        ("LEAF-SILL-MM", "LEAF-HEAD-MM"),
        ("CLEAR-OPENING-SILL-MM", "CLEAR-OPENING-HEAD-MM"),
    ],
)
@EXPECTED_RED
def test_non_structural_vertical_semantics_cannot_become_wall_void_placement(
    sill_heading: str,
    head_heading: str,
) -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(sill_heading=sill_heading, head_heading=head_heading),
    )
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert row_result.evidence is None


@EXPECTED_RED
def test_rough_opening_headings_without_units_do_not_assume_mm() -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(
            sill_heading="ROUGH-OPENING-SILL",
            head_heading="ROUGH-OPENING-HEAD",
        ),
    )
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert row_result.evidence is None


@EXPECTED_RED
def test_height_only_does_not_imply_sill_zero_or_head_height() -> None:
    mod = _module()
    payload = _placement_pdf(
        sill_heading="NOTE",
        head_heading="NOTE2",
        sill_value="",
        head_value="",
    )
    *_prefix, row_result = _publish_row(mod, payload)
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert row_result.evidence is None


@EXPECTED_RED
def test_top_not_above_bottom_fails_closed() -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(sill_value="3000", head_value="900"),
    )
    assert row_result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert row_result.evidence is None


@EXPECTED_RED
def test_wrong_opening_lineage_cannot_reuse_valid_placement() -> None:
    mod = _module()
    src, binder, binding, row_producer, _row_selector, row_result = _publish_row(
        mod, _placement_pdf()
    )
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    opening_producer, selector, valid = _publish_opening(
        mod, src, binder, binding, row_producer
    )
    assert valid.status is EvidenceResolutionStatus.CORROBORATED
    tampered = dataclasses.replace(selector, opening_record_id="not-the-bound-opening")
    blocked = opening_producer.publish_scope(tampered)
    assert blocked.status is EvidenceResolutionStatus.ABSTAINED
    assert blocked.evidence is None


@EXPECTED_RED
def test_caller_cannot_invent_row_observation_identity() -> None:
    mod = _module()
    src, _binder, binding = _binding_fixture()
    record = binding.record
    assert record is not None
    producer = mod.ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(src)
    selector = mod.ScheduleRowVerticalPlacementSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        schedule_page_id=record.schedule_page_id,
        schedule_row_observation_ids=("caller-invented-row-id",),
    )
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


@EXPECTED_RED
def test_door_type_does_not_imply_sill_zero() -> None:
    """Door label must not stand in for missing sill evidence -- the same
    'height only' abstention required for windows must hold for a door
    mark too, not just for the window fixture used throughout the rest of
    this file."""
    mod = _module()
    payload = _placement_pdf(
        tag_text="D1",
        sill_heading="NOTE",
        head_heading="NOTE2",
        sill_value="",
        head_value="",
    )
    *_prefix, row_result = _publish_row(mod, payload)
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert row_result.evidence is None


@EXPECTED_RED
def test_stale_source_lineage_cannot_reuse_valid_row_placement() -> None:
    """A row selector's own document/revision/sha/snapshot lineage must be
    re-verified, not merely its schedule_row_observation_ids -- pointing
    the same real row ids at a foreign/fabricated source identity must
    abstain rather than resolve against whichever real evidence happens
    to share that snapshot_id."""
    mod = _module()
    src, _binder, binding = _binding_fixture()
    record = binding.record
    assert record is not None
    producer = mod.ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(src)
    valid_selector = mod.ScheduleRowVerticalPlacementSelector(
        document_id=record.document_id,
        revision_id=record.revision_id,
        source_sha256=record.source_sha256,
        snapshot_id=record.snapshot_id,
        schedule_page_id=record.schedule_page_id,
        schedule_row_observation_ids=record.schedule_row_observation_ids,
    )
    valid = producer.publish_scope(valid_selector)
    assert valid.status is EvidenceResolutionStatus.CORROBORATED

    for field_name, tampered_value in (
        ("document_id", "not-the-real-document"),
        ("revision_id", "not-the-real-revision"),
        ("source_sha256", "0" * 64),
        ("snapshot_id", "not-the-real-snapshot"),
    ):
        tampered = dataclasses.replace(valid_selector, **{field_name: tampered_value})
        blocked = producer.publish_scope(tampered)
        assert blocked.status is EvidenceResolutionStatus.ABSTAINED, field_name
        assert blocked.evidence is None, field_name
