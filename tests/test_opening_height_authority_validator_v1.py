from __future__ import annotations

import inspect

import pytest

from pb_opening_height_authority import (
    OpeningHeightProducer,
    OpeningHeightSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _mock_src() -> SourceVisibilityProducer:
    return SourceVisibilityProducer(producer_method="height-validator", producer_version="1.0")

def _valid_selector() -> OpeningHeightSelector:
    return OpeningHeightSelector(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="sha-1",
        snapshot_id="snap-1",
        decision_scope_id="scope-1",
        opening_record_id="opening-1",
    )

def test_positive_height_evidence_requires_legitimate_instance_binding() -> None:
    src = _mock_src()
    # Assume src has the required binding record internally
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_default_heights_never_synthesized() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_width_used_as_height() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_caller_supplied_height_is_rejected() -> None:
    params = set(inspect.signature(OpeningHeightProducer.publish_scope).parameters)
    assert "height" not in params
    assert "height_mm" not in params
    assert "evidence" not in params

def test_attack_raw_schedule_text_without_binding() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_nearest_dimension_or_unrelated_elevation_text() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_wrong_lineage_fails_closed() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_conflicting_matching_rows_abstains() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_cross_sheet_use_without_registration() -> None:
    src = _mock_src()
    producer = OpeningHeightProducer.from_source_visibility_producer(src)
    with pytest.raises(NotImplementedError):
        producer.publish_scope(_valid_selector(), "scope-1")

def test_attack_caller_authenticated_flags() -> None:
    params = set(inspect.signature(OpeningHeightSelector).parameters)
    assert "authenticated" not in params
    assert "is_valid" not in params
