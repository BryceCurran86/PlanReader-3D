"""Compact immutable source records preserve exactly the historical public contract."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, asdict, fields, replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    SourceObservationAuthorityResult,
    SourceObservationRecord,
)


def _record() -> SourceObservationRecord:
    return SourceObservationRecord(
        observation_id="source-obs-1",
        document_id="original-document",
        revision_id="original-revision",
        source_sha256="a" * 64,
        source_partition_id="page:1",
        page_id="1",
        viewport_id=None,
        observation_kind="native_pdf_segment",
        source_primitive_ref="segment:1",
        raw_text="",
        geometry=(1.0, 2.0, 3.0, 4.0),
        origin_kind="native_pdf",
        derivation_parent_ids=(),
        producer_method="original-source-producer",
        producer_version="1",
        producer_generation=1,
        snapshot_id="snapshot-1",
        observation_payload_sha256="b" * 64,
    )


def test_source_observation_compact_record_preserves_fields_and_frozen_copy():
    record = _record()
    assert not hasattr(record, "__dict__")
    assert {f.name for f in fields(record)} >= {
        "source_sha256", "snapshot_id", "observation_payload_sha256",
        "derivation_parent_ids", "geometry", "producer_generation",
    }
    clone = replace(record, snapshot_id="snapshot-2", producer_generation=2)
    assert clone.snapshot_id == "snapshot-2"
    assert clone.producer_generation == 2
    assert record.snapshot_id == "snapshot-1"
    assert asdict(clone)["geometry"] == (1.0, 2.0, 3.0, 4.0)
    with pytest.raises(FrozenInstanceError):
        record.snapshot_id = "foreign"


def test_verified_resolution_compact_result_keeps_defensive_record_contract():
    record = _record()
    result = SourceObservationAuthorityResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition="source_observation_exists",
        physical_opening_existence="physical_opening_existence_unresolved",
        reason_codes=("producer_owned_source_observation_resolved",),
        observation=record,
    )
    assert not hasattr(result, "__dict__")
    assert result.observation == record
    cloned = replace(result, observation=replace(record, snapshot_id="new-snapshot"))
    assert cloned.observation.snapshot_id == "new-snapshot"
    assert result.observation.snapshot_id == "snapshot-1"
    with pytest.raises(FrozenInstanceError):
        result.observation = cloned.observation
