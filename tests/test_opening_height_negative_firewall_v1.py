"""Opening-height authority negative firewall v1.

TEST-ONLY / SELF-AUTHORED / INDEPENDENT REVIEW REQUIRED.

Current production correctly has no positive opening-height route. This suite
locks that fail-closed behavior while the upstream prerequisite is designed.

A future positive may be added only after one of these independently reviewed
instance-binding authorities exists:

Route A: authenticated physical opening instance <-> registered elevation or
section instance, with source/revision/page/view registration and vertical
figured-dimension evidence.

Route B: authenticated schedule-row <-> exact physical opening instance binding,
with repeated type marks/counts resolved without nearest/first/tag-only choice.

Route C: an equivalent source-native producer-owned instance-height authority.

Until then, 2100/2040 defaults, typical notes, nearest elevation text, repeated
schedule tags, OCR/CV labels, caller-provided dimensions and source-space gap
heuristics must remain incapable of resolving height.
"""
from __future__ import annotations

import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_dimension_authority import (
    OPENING_DIMENSION_EXISTENCE_REQUIRED,
    OPENING_HEIGHT_EVIDENCE_UNAVAILABLE,
    OpeningDimensionAuthority,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


BASE_SHA = "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"


def _opening_pdf(*, extra_text: str = "") -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=500, height=300)
        # Two wall faces with one explicit gap and two jambs. This is the same
        # source-native opening geometry family used by the reviewed opening
        # dimension/existence validators.
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((140.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        if extra_text:
            page.insert_text(fitz.Point(105.0, 80.0), extra_text)
        payload = doc.tobytes(garbage=4, deflate=True)
        return bytes(payload)
    finally:
        doc.close()


def _ingest(*, extra_text: str = ""):
    producer = SourceVisibilityProducer(
        producer_method="opening-height-negative-firewall-v1",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="opening-height-negative-v1",
        source_bytes=_opening_pdf(extra_text=extra_text),
        source_locator="memory://opening-height-negative-v1.pdf",
    )
    return producer, published, producer.authority()


def _selector(published, observation_id: str, **changes: str) -> ObservationSelector:
    values = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "observation_id": observation_id,
    }
    values.update(changes)
    return ObservationSelector(**values)


def _positive_selector(published, visibility) -> ObservationSelector:
    physical = PhysicalOpeningAuthority(visibility)
    positives = []
    record_ids = []
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        result = physical.prove_existence(selector)
        if result.proposition == PHYSICAL_OPENING_EXISTS:
            positives.append(selector)
            assert result.existence_record is not None
            record_ids.append(result.existence_record.record_id)
    assert positives, "fixture must prove one real physical opening"
    assert len(set(record_ids)) == 1
    return positives[0]


def _assert_height_unresolved(result) -> None:
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.value_mm is None
    assert result.proposition is None
    assert result.axis == "height"


def test_exact_base_is_current_main() -> None:
    assert BASE_SHA == "76c7882b1c4b28764d1e6a6f467d72bb276c2e01"


def test_resolve_height_public_api_is_selector_only() -> None:
    signature = inspect.signature(OpeningDimensionAuthority.resolve_height)
    assert set(signature.parameters) == {"self", "selector"}


def test_real_physical_opening_without_height_instance_binding_abstains() -> None:
    producer, published, visibility = _ingest()
    selector = _positive_selector(published, visibility)
    result = producer.opening_dimension_authority().resolve_height(selector)
    _assert_height_unresolved(result)
    assert OPENING_HEIGHT_EVIDENCE_UNAVAILABLE in result.reason_codes


@pytest.mark.parametrize(
    "extra_text",
    [
        "2100",
        "2040",
        "TYPICAL DOOR HEIGHT 2100",
        "D-01 900 x 2100",
        "DOOR SCHEDULE D-01 900 x 2100 4 No.",
    ],
)
def test_nearby_default_typical_or_schedule_text_cannot_resolve_height(extra_text: str) -> None:
    producer, published, visibility = _ingest(extra_text=extra_text)
    selector = _positive_selector(published, visibility)
    result = producer.opening_dimension_authority().resolve_height(selector)
    _assert_height_unresolved(result)
    assert OPENING_HEIGHT_EVIDENCE_UNAVAILABLE in result.reason_codes


def test_wrong_snapshot_cannot_launder_height_authority() -> None:
    producer, published, visibility = _ingest(extra_text="2100")
    selector = _positive_selector(published, visibility)
    wrong = ObservationSelector(
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id="wrong-snapshot",
        observation_id=selector.observation_id,
    )
    result = producer.opening_dimension_authority().resolve_height(wrong)
    _assert_height_unresolved(result)
    assert OPENING_DIMENSION_EXISTENCE_REQUIRED in result.reason_codes


def test_height_api_has_no_default_ocr_schedule_or_nearest_inputs() -> None:
    names = {
        name.lower()
        for name in inspect.signature(OpeningDimensionAuthority.resolve_height).parameters
    }
    forbidden = {
        "height_mm",
        "default_height",
        "typical_height",
        "ocr_height",
        "schedule_height",
        "schedule_row",
        "opening_tag",
        "nearest_text",
        "confidence",
        "radius",
        "bound_wall_id",
    }
    assert not (names & forbidden)
