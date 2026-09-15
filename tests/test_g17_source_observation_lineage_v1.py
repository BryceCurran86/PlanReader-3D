from __future__ import annotations

from dataclasses import replace
import inspect

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    OBSERVATION_UNAVAILABLE,
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PRODUCER_INTEGRITY_FAILURE,
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    SOURCE_OBSERVATION_EXISTS,
    STALE_REVISION,
    ObservationSelector,
    ProducerIntegrityError,
    SourceObservationInput,
    SourceObservationProducer,
)


SOURCE_A = b"%PDF-1.7\n% G17 phase-1 synthetic source A\n%%EOF\n"
SOURCE_B = b"%PDF-1.7\n% G17 phase-1 synthetic source B\n%%EOF\n"


def _producer() -> SourceObservationProducer:
    return SourceObservationProducer(
        producer_method="native-pdf-source-observation",
        producer_version="1.0.0",
    )


def _ingest(producer: SourceObservationProducer, source: bytes = SOURCE_A):
    return producer.ingest_source(
        document_id="doc-g17",
        source_bytes=source,
        source_locator="memory://g17-phase1.pdf",
        partition_ids=("page:1",),
    )


def _input(
    *,
    primitive_ref: str = "text:0",
    raw_text: str = "D01",
    origin_kind: str = "native",
    observation_kind: str = "native_text",
    viewport_id: str | None = "viewport:1",
    derivation_parent_ids: tuple[str, ...] = (),
) -> SourceObservationInput:
    return SourceObservationInput(
        source_partition_id="page:1",
        page_id="1",
        viewport_id=viewport_id,
        observation_kind=observation_kind,
        source_primitive_ref=primitive_ref,
        raw_text=raw_text,
        geometry=(10.0, 20.0, 30.0, 40.0),
        origin_kind=origin_kind,
        derivation_parent_ids=derivation_parent_ids,
    )


def _published(*, origin_kind: str = "native", observation_kind: str = "native_text"):
    producer = _producer()
    revision = _ingest(producer)
    snapshot = producer.publish_snapshot(
        revision_id=revision.revision_id,
        observations=(_input(origin_kind=origin_kind, observation_kind=observation_kind),),
    )
    selector = ObservationSelector(
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        observation_id=snapshot.observation_ids[0],
    )
    return producer, revision, snapshot, selector, producer.authority()


def test_source_observation_exists_binds_immutable_producer_lineage() -> None:
    producer, revision, snapshot, selector, authority = _published()

    result = authority.resolve(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert result.source_revision == revision
    assert result.snapshot == snapshot
    assert result.observation is not None
    assert result.observation.document_id == revision.document_id
    assert result.observation.revision_id == revision.revision_id
    assert result.observation.source_sha256 == revision.source_sha256
    assert result.observation.source_partition_id == "page:1"
    assert result.observation.page_id == "1"
    assert result.observation.viewport_id == "viewport:1"
    assert result.observation.source_primitive_ref == "text:0"
    assert result.observation.raw_text == "D01"
    assert result.observation.geometry == (10.0, 20.0, 30.0, 40.0)
    assert result.observation.producer_method == "native-pdf-source-observation"
    assert result.observation.producer_version == "1.0.0"
    assert result.observation.producer_generation == snapshot.producer_generation
    assert result.observation.snapshot_id == snapshot.snapshot_id
    assert result.observation.invalidation_conditions
    assert producer.current_revision_id(revision.document_id) == revision.revision_id


def test_identical_looking_caller_record_cannot_be_submitted_as_authority() -> None:
    _, _, _, selector, authority = _published()
    resolved = authority.resolve(selector)
    caller_copy = replace(resolved.observation)

    assert caller_copy == resolved.observation
    assert "observation" not in inspect.signature(authority.resolve).parameters
    with pytest.raises(TypeError):
        authority.resolve(selector, observation=caller_copy)  # type: ignore[call-arg]

    assert authority.resolve(selector).proposition == SOURCE_OBSERVATION_EXISTS


def test_invented_source_hash_abstains() -> None:
    _, _, _, selector, authority = _published()

    result = authority.resolve(replace(selector, source_sha256="0" * 64))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None
    assert SOURCE_HASH_MISMATCH in result.reason_codes


def test_changed_observation_target_id_is_unavailable() -> None:
    _, _, _, selector, authority = _published()

    result = authority.resolve(replace(selector, observation_id="source_observation_missing"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OBSERVATION_UNAVAILABLE in result.reason_codes


def test_stale_revision_fails_closed_after_source_changes() -> None:
    producer, first_revision, _, selector, authority = _published()
    second_revision = _ingest(producer, SOURCE_B)

    assert second_revision.revision_id != first_revision.revision_id
    assert second_revision.source_sha256 != first_revision.source_sha256
    result = authority.resolve(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert STALE_REVISION in result.reason_codes


def test_snapshot_mismatch_cannot_rebind_an_observation() -> None:
    producer, revision, first_snapshot, selector, authority = _published()
    second_snapshot = producer.publish_snapshot(
        revision_id=revision.revision_id,
        observations=(_input(primitive_ref="text:1", raw_text="D02"),),
    )

    assert second_snapshot.snapshot_id != first_snapshot.snapshot_id
    result = authority.resolve(replace(selector, snapshot_id=second_snapshot.snapshot_id))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SNAPSHOT_MISMATCH in result.reason_codes


def test_duplicate_observation_id_with_different_content_is_integrity_failure() -> None:
    producer, revision, _, _, _ = _published()

    with pytest.raises(ProducerIntegrityError, match=PRODUCER_INTEGRITY_FAILURE):
        producer.publish_snapshot(
            revision_id=revision.revision_id,
            observations=(_input(raw_text="DIFFERENT CONTENT"),),
        )


def test_returned_record_mutation_cannot_change_store_state() -> None:
    _, _, _, selector, authority = _published()
    first = authority.resolve(selector)
    assert first.observation is not None

    object.__setattr__(first.observation, "raw_text", "caller mutation")
    second = authority.resolve(selector)

    assert first.observation.raw_text == "caller mutation"
    assert second.observation is not None
    assert second.observation.raw_text == "D01"
    assert second.proposition == SOURCE_OBSERVATION_EXISTS


def test_deterministic_replay_reuses_revision_snapshot_and_observation_ids() -> None:
    producer = _producer()
    first_revision = _ingest(producer)
    first_snapshot = producer.publish_snapshot(
        revision_id=first_revision.revision_id,
        observations=(_input(),),
    )

    replay_revision = _ingest(producer)
    replay_snapshot = producer.publish_snapshot(
        revision_id=replay_revision.revision_id,
        observations=(_input(),),
    )

    assert replay_revision == first_revision
    assert replay_snapshot == first_snapshot
    assert replay_snapshot.observation_ids == first_snapshot.observation_ids


def test_changed_source_revision_invalidates_old_snapshot_without_mutating_history() -> None:
    producer, first_revision, first_snapshot, selector, authority = _published()
    old_snapshot_id = first_snapshot.snapshot_id

    second_revision = _ingest(producer, SOURCE_B)

    assert first_revision.revision_id != second_revision.revision_id
    assert first_snapshot.snapshot_id == old_snapshot_id
    result = authority.resolve(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert STALE_REVISION in result.reason_codes


@pytest.mark.parametrize("origin_kind", ["ocr", "cv", "heuristic"])
def test_heuristic_observation_never_becomes_physical_opening_truth(origin_kind: str) -> None:
    _, _, _, selector, authority = _published(
        origin_kind=origin_kind,
        observation_kind="opening_detection",
    )

    result = authority.resolve(selector)

    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_schedule_row_does_not_prove_physical_instance() -> None:
    _, _, _, selector, authority = _published(
        origin_kind="schedule",
        observation_kind="schedule_row",
    )

    result = authority.resolve(selector)

    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_full_decode_with_zero_detections_does_not_claim_semantic_completeness() -> None:
    producer = _producer()
    revision = _ingest(producer)
    empty_snapshot = producer.publish_snapshot(revision_id=revision.revision_id, observations=())
    authority = producer.authority()

    assert empty_snapshot.observation_ids == ()
    assert not hasattr(empty_snapshot, "semantic_enumeration_complete")
    assert not hasattr(authority, "resolve_opening_universe")


def test_local_crop_is_only_observation_context_not_decision_scope() -> None:
    producer = _producer()
    revision = _ingest(producer)
    snapshot = producer.publish_snapshot(
        revision_id=revision.revision_id,
        observations=(_input(viewport_id="local-crop:10,10,20,20"),),
    )
    selector = ObservationSelector(
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        observation_id=snapshot.observation_ids[0],
    )

    result = producer.authority().resolve(selector)

    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.observation is not None
    assert result.observation.viewport_id == "local-crop:10,10,20,20"
    assert not hasattr(result, "decision_scope_complete")
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_derived_observation_retains_lineage_and_cannot_gain_physical_authority() -> None:
    producer = _producer()
    revision = _ingest(producer)
    parent_snapshot = producer.publish_snapshot(
        revision_id=revision.revision_id,
        observations=(_input(primitive_ref="segment:0", raw_text="", observation_kind="native_segment"),),
    )
    parent_id = parent_snapshot.observation_ids[0]
    derived_snapshot = producer.publish_snapshot(
        revision_id=revision.revision_id,
        observations=(
            _input(
                primitive_ref="derived:opening:0",
                raw_text="opening candidate",
                origin_kind="derived",
                observation_kind="opening_reconstruction",
                derivation_parent_ids=(parent_id,),
            ),
        ),
    )
    selector = ObservationSelector(
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=derived_snapshot.snapshot_id,
        observation_id=derived_snapshot.observation_ids[0],
    )

    result = producer.authority().resolve(selector)

    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.observation is not None
    assert result.observation.derivation_parent_ids == (parent_id,)
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_derived_observation_without_existing_support_is_rejected() -> None:
    producer = _producer()
    revision = _ingest(producer)

    with pytest.raises(ValueError, match="lineage parent"):
        producer.publish_snapshot(
            revision_id=revision.revision_id,
            observations=(
                _input(
                    primitive_ref="derived:opening:0",
                    origin_kind="derived",
                    observation_kind="opening_reconstruction",
                    derivation_parent_ids=("source_observation_missing",),
                ),
            ),
        )


def test_adding_contradictory_observation_cannot_strengthen_opening_existence() -> None:
    producer = _producer()
    revision = _ingest(producer)
    snapshot = producer.publish_snapshot(
        revision_id=revision.revision_id,
        observations=(
            _input(
                primitive_ref="ocr:0",
                raw_text="DOOR D01",
                origin_kind="ocr",
                observation_kind="opening_label_candidate",
            ),
            _input(
                primitive_ref="ocr:1",
                raw_text="NOT A DOOR / LEGEND SAMPLE",
                origin_kind="ocr",
                observation_kind="contradictory_label_context",
            ),
        ),
    )
    authority = producer.authority()

    for observation_id in snapshot.observation_ids:
        result = authority.resolve(
            ObservationSelector(
                document_id=revision.document_id,
                revision_id=revision.revision_id,
                source_sha256=revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.proposition == SOURCE_OBSERVATION_EXISTS
        assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
