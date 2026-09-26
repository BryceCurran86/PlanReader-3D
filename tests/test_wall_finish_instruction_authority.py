from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_wall_finish_callout_wall_authority as callout
from pb_wall_finish_instruction_authority import (
    WallFinishInstructionProducer,
    WallFinishInstructionSelector,
)


def _binding(binding_id: str, text: str):
    return callout.WallFinishCalloutWallBindingRecord(
        binding_id=binding_id,
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        viewport_id="view-1",
        decision_scope_id="finish-callout-wall:view-1",
        physical_wall_decision_scope_id="wall-source:viewport:1:view-1:abc",
        physical_wall_id="wall-a",
        raw_owner_wall_ids=("wall-a", "wall-b"),
        equivalence_group_wall_ids=("wall-a", "wall-b"),
        equivalence_pair_classifications=(
            ("wall-a", "wall-b", "same_physical_wall"),
        ),
        source_wall_primitive_ids=("raw-a", "raw-b"),
        trusted_annotation_text=text,
        annotation_observation_ids=("text-1",),
        leader_path_ids=("leader-1",),
        terminator_primitive_ids=("term-1",),
        source_evidence_ids=("text-1", "leader-1", "term-1", "raw-a", "raw-b"),
        source_evidence_kind="native_direct_finish_callout",
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("wall_finish_callout_wall_binding_resolved",),
        _seal=callout._RECORD_SEAL,
    )


def _producer(*bindings):
    scope = callout.WallFinishCalloutWallScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("wall_finish_callout_wall_binding_resolved",),
        bindings=tuple(bindings),
    )
    return callout.WallFinishCalloutWallProducer(
        {(
            "doc",
            "rev",
            "a" * 64,
            "snap",
            "1",
            "view-1",
            "finish-callout-wall:view-1",
        ): scope},
        _seal=callout._PRODUCER_SEAL,
    )


def test_explicit_internal_finish_instruction_publishes_plaster_and_paint() -> None:
    source = _producer(
        _binding(
            "binding-internal",
            "150mm thick walling blocks plaster and paint to finish internally.",
        )
    )
    producer = WallFinishInstructionProducer.from_callout_wall_producer(source)
    records = [
        result.record
        for result in producer.published_results()
        if result.record is not None
    ]

    assert {(r.trade_scope_id, r.finish_material, r.semantic_direction) for r in records} == {
        ("internal_plaster", "plaster", "internally"),
        ("internal_paint", "paint", "internally"),
    }
    assert all(r.physical_wall_id == "wall-a" for r in records)
    assert all(r.equivalence_group_wall_ids == ("wall-a", "wall-b") for r in records)
    assert all(r.source_wall_primitive_ids == ("raw-a", "raw-b") for r in records)


def test_explicit_external_finish_instruction_publishes_key_pointing() -> None:
    source = _producer(
        _binding(
            "binding-external",
            "150mm thick walling blocks key to finish externally.",
        )
    )
    producer = WallFinishInstructionProducer.from_callout_wall_producer(source)
    records = [
        result.record
        for result in producer.published_results()
        if result.record is not None
    ]
    assert len(records) == 1
    record = records[0]
    assert record.trade_scope_id == "external_key_pointing"
    assert record.finish_material == "key_pointing"
    assert record.semantic_direction == "externally"


@pytest.mark.parametrize(
    "text",
    [
        "150mm thick walling blocks key to finish",
        "150mm thick walling blocks plaster and paint to finish",
        "finish internally.",
        "walling internally.",
        "walling blocks paint internally.",
    ],
)
def test_missing_required_semantics_do_not_publish_instruction(text: str) -> None:
    source = _producer(_binding("binding-partial", text))
    producer = WallFinishInstructionProducer.from_callout_wall_producer(source)
    assert producer.published_results() == ()


def test_unknown_selector_abstains() -> None:
    source = _producer(
        _binding(
            "binding-internal",
            "walling blocks plaster and paint to finish internally.",
        )
    )
    authority = WallFinishInstructionProducer.from_callout_wall_producer(
        source
    ).authority()
    result = authority.resolve(
        WallFinishInstructionSelector(
            binding_id="does-not-exist",
            trade_scope_id="internal_plaster",
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None


def test_fake_callout_producer_is_rejected() -> None:
    with pytest.raises(TypeError):
        WallFinishInstructionProducer.from_callout_wall_producer(object())
