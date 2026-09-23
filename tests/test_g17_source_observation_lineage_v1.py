from __future__ import annotations

from dataclasses import replace
import hashlib
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import (
    LINEAGE_UNAVAILABLE,
    OBSERVATION_UNAVAILABLE,
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PRODUCER_INTEGRITY_FAILURE,
    SNAPSHOT_MISMATCH,
    SOURCE_HASH_MISMATCH,
    SOURCE_OBSERVATION_EXISTS,
    SOURCE_UNAVAILABLE,
    STALE_REVISION,
    ObservationSelector,
    ProducerIntegrityError,
    SourceObservationProducer,
)


def _pdf_bytes(*, text: str = "D01", draw_line: bool = True) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    if text:
        page.insert_text((40, 40), text)
    if draw_line:
        page.draw_line((30, 90), (220, 90))
    payload = doc.tobytes()
    doc.close()
    return payload


def _producer() -> SourceObservationProducer:
    return SourceObservationProducer(
        producer_method="native-pdf-source-observation",
        producer_version="1.0.0",
    )


def _published(document_id: str = "doc-g17", *, text: str = "D01"):
    producer = _producer()
    source = _pdf_bytes(text=text)
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=source,
        source_locator=f"memory://{document_id}.pdf",
    )
    authority = producer.authority()
    assert published.snapshot.observation_ids
    selector = ObservationSelector(
        document_id=document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=published.snapshot.observation_ids[0],
    )
    return producer, authority, published, selector, source


def _find_observation(authority, published, *, kind: str):
    for observation_id in published.snapshot.observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = authority.resolve(selector)
        if result.observation is not None and result.observation.observation_kind == kind:
            return selector, result
    raise AssertionError(f"missing observation kind {kind}")


def test_native_pdf_bytes_are_really_decoded_into_producer_observations() -> None:
    _producer_obj, authority, published, _selector, _source = _published()
    selector, result = _find_observation(authority, published, kind="native_pdf_word")

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.observation is not None
    assert result.observation.raw_text == "D01"
    assert result.observation.source_partition_id == "page:1"
    assert result.observation.page_id == "1"
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert result.semantic_enumeration_complete is None
    assert result.decision_scope_complete is None
    assert selector.observation_id in published.snapshot.observation_ids


def test_hash_and_decoder_use_same_immutable_source_bytes() -> None:
    _producer_obj, authority, published, _selector, source = _published(text="EXACT-BUFFER")
    assert published.revision.source_sha256 == hashlib.sha256(source).hexdigest()
    _selector2, result = _find_observation(authority, published, kind="native_pdf_word")
    assert result.observation is not None
    assert result.observation.raw_text == "EXACT-BUFFER"
    assert result.observation.source_sha256 == published.revision.source_sha256


def test_page_partition_inventory_is_producer_derived_not_consumer_supplied() -> None:
    assert "partition_ids" not in inspect.signature(
        SourceObservationProducer.ingest_native_pdf_bytes
    ).parameters
    _producer_obj, _authority, published, _selector, _source = _published()
    assert published.revision.partition_ids == ("page:1",)
    assert published.coverage.decoded_pages == (1,)
    assert published.coverage.failed_pages == ()
    assert published.coverage.state == "complete"


def test_identical_looking_caller_record_cannot_be_submitted_as_authority() -> None:
    _producer_obj, authority, _published_obj, selector, _source = _published()
    resolved = authority.resolve(selector)
    assert resolved.observation is not None
    caller_copy = replace(resolved.observation)
    assert caller_copy == resolved.observation
    assert "observation" not in inspect.signature(authority.resolve).parameters
    with pytest.raises(TypeError):
        authority.resolve(selector, observation=caller_copy)  # type: ignore[call-arg]


def test_invented_source_hash_abstains() -> None:
    _producer_obj, authority, _published_obj, selector, _source = _published()
    result = authority.resolve(replace(selector, source_sha256="0" * 64))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_HASH_MISMATCH in result.reason_codes


def test_changed_target_id_is_unavailable() -> None:
    _producer_obj, authority, _published_obj, selector, _source = _published()
    result = authority.resolve(replace(selector, observation_id="source_observation_missing"))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OBSERVATION_UNAVAILABLE in result.reason_codes


def test_stale_revision_after_source_bytes_change() -> None:
    producer, authority, first, selector, _source = _published("doc-revision")
    second = producer.ingest_native_pdf_bytes(
        document_id="doc-revision",
        source_bytes=_pdf_bytes(text="D02"),
        source_locator="memory://doc-revision-v2.pdf",
    )
    assert first.revision.revision_id != second.revision.revision_id
    result = authority.resolve(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert STALE_REVISION in result.reason_codes


def test_snapshot_mismatch_cannot_rebind_observation() -> None:
    producer, authority, _published_obj, selector, _source = _published("doc-snapshot")
    other = producer.ingest_native_pdf_bytes(
        document_id="doc-other",
        source_bytes=_pdf_bytes(text="OTHER"),
        source_locator="memory://doc-other.pdf",
    )
    result = authority.resolve(replace(selector, snapshot_id=other.snapshot.snapshot_id))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert SNAPSHOT_MISMATCH in result.reason_codes


def test_duplicate_id_with_different_content_is_integrity_failure() -> None:
    producer, _authority, published, _selector, _source = _published("doc-collision")
    colliding = published.snapshot.observation_ids[0]
    with pytest.raises(ProducerIntegrityError, match=PRODUCER_INTEGRITY_FAILURE):
        producer.publish_derived_observation(
            document_id="doc-collision",
            revision_id=published.revision.revision_id,
            base_snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            source_partition_id="page:1",
            observation_kind="cv_candidate",
            source_primitive_ref="cv:collision",
            origin_kind="cv",
            parent_observation_ids=(colliding,),
            raw_text="opening",
            observation_id=colliding,
        )


def test_returned_record_mutation_cannot_change_store_state() -> None:
    _producer_obj, authority, _published_obj, selector, _source = _published()
    first = authority.resolve(selector)
    assert first.observation is not None
    original = first.observation.raw_text
    object.__setattr__(first.observation, "raw_text", "caller mutation")
    second = authority.resolve(selector)
    assert second.observation is not None
    assert second.observation.raw_text == original
    assert second.proposition == SOURCE_OBSERVATION_EXISTS


def test_deterministic_replay_is_idempotent_but_id_is_not_authority() -> None:
    source = _pdf_bytes(text="REPLAY")
    producer = _producer()
    first = producer.ingest_native_pdf_bytes(
        document_id="doc-replay", source_bytes=source, source_locator="memory://replay.pdf"
    )
    second = producer.ingest_native_pdf_bytes(
        document_id="doc-replay", source_bytes=source, source_locator="memory://replay.pdf"
    )
    assert first == second

    empty_authority = _producer().authority()
    result = empty_authority.resolve(
        ObservationSelector(
            document_id="doc-replay",
            revision_id=first.revision.revision_id,
            source_sha256=first.revision.source_sha256,
            snapshot_id=first.snapshot.snapshot_id,
            observation_id=first.snapshot.observation_ids[0],
        )
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED


@pytest.mark.parametrize("origin_kind", ["ocr", "cv", "heuristic"])
def test_heuristic_observation_never_becomes_physical_opening_truth(origin_kind: str) -> None:
    producer, authority, published, _selector, _source = _published(f"doc-{origin_kind}")
    parent = published.snapshot.observation_ids[0]
    derived = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="opening_detection",
        source_primitive_ref=f"{origin_kind}:1",
        origin_kind=origin_kind,
        parent_observation_ids=(parent,),
        raw_text="D01",
    )
    new_id = next(x for x in derived.observation_ids if x not in published.snapshot.observation_ids)
    result = authority.resolve(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=derived.snapshot_id,
            observation_id=new_id,
        )
    )
    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_schedule_row_does_not_prove_physical_instance() -> None:
    producer, authority, published, _selector, _source = _published("doc-schedule")
    parent = published.snapshot.observation_ids[0]
    derived = producer.publish_derived_observation(
        document_id="doc-schedule",
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="schedule_row",
        source_primitive_ref="schedule:row:1",
        origin_kind="schedule",
        parent_observation_ids=(parent,),
        raw_text="D01 900x2100",
    )
    new_id = next(x for x in derived.observation_ids if x not in published.snapshot.observation_ids)
    result = authority.resolve(
        ObservationSelector(
            document_id="doc-schedule",
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=derived.snapshot_id,
            observation_id=new_id,
        )
    )
    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_complete_decode_with_no_semantic_detector_cannot_claim_complete_empty_universe() -> None:
    producer = _producer()
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-zero",
        source_bytes=_pdf_bytes(text="", draw_line=False),
        source_locator="memory://zero.pdf",
    )
    authority = producer.authority()
    assert published.coverage.state == "complete"
    selector = ObservationSelector(
        document_id="doc-zero",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=published.snapshot.observation_ids[0],
    )
    result = authority.resolve(selector)
    assert result.semantic_enumeration_complete is None
    assert not hasattr(authority, "resolve_opening_universe")


def test_local_crop_cannot_define_decision_complete_scope() -> None:
    producer, authority, published, _selector, _source = _published("doc-crop")
    parent = published.snapshot.observation_ids[0]
    derived = producer.publish_derived_observation(
        document_id="doc-crop",
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="local_crop_observation",
        source_primitive_ref="crop:1",
        origin_kind="derived",
        parent_observation_ids=(parent,),
        viewport_id="crop:10,10,20,20",
    )
    new_id = next(x for x in derived.observation_ids if x not in published.snapshot.observation_ids)
    result = authority.resolve(
        ObservationSelector(
            document_id="doc-crop",
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=derived.snapshot_id,
            observation_id=new_id,
        )
    )
    assert result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.decision_scope_complete is None


def test_derived_observation_requires_parent_in_same_snapshot() -> None:
    producer, _authority, published, _selector, _source = _published("doc-parent")
    with pytest.raises(ValueError, match=LINEAGE_UNAVAILABLE):
        producer.publish_derived_observation(
            document_id="doc-parent",
            revision_id=published.revision.revision_id,
            base_snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            source_partition_id="page:1",
            observation_kind="derived_opening",
            source_primitive_ref="derived:1",
            origin_kind="derived",
            parent_observation_ids=("source_observation_missing",),
        )


def test_adding_contradiction_cannot_strengthen_semantics() -> None:
    producer, authority, published, _selector, _source = _published("doc-conflict")
    parent = published.snapshot.observation_ids[0]
    first = producer.publish_derived_observation(
        document_id="doc-conflict",
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="heuristic_classification",
        source_primitive_ref="heuristic:opening",
        origin_kind="heuristic",
        parent_observation_ids=(parent,),
        raw_text="opening",
    )
    first_new = next(x for x in first.observation_ids if x not in published.snapshot.observation_ids)
    second = producer.publish_derived_observation(
        document_id="doc-conflict",
        revision_id=published.revision.revision_id,
        base_snapshot_id=first.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="heuristic_classification",
        source_primitive_ref="heuristic:not-opening",
        origin_kind="heuristic",
        parent_observation_ids=(parent,),
        raw_text="not opening",
    )
    second_new = next(x for x in second.observation_ids if x not in first.observation_ids)
    for observation_id in (first_new, second_new):
        result = authority.resolve(
            ObservationSelector(
                document_id="doc-conflict",
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=second.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.proposition == SOURCE_OBSERVATION_EXISTS
        assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_consumer_authority_has_no_writer_capability() -> None:
    producer, authority, _published_obj, _selector, _source = _published()
    assert hasattr(producer, "ingest_native_pdf_bytes")
    assert hasattr(producer, "publish_derived_observation")
    assert not hasattr(authority, "ingest_native_pdf_bytes")
    assert not hasattr(authority, "publish_derived_observation")


def _multi_page_pdf_bytes() -> bytes:
    doc = fitz.open()
    for index in range(3):
        page = doc.new_page(width=300, height=200)
        page.insert_text((40, 40), f"PAGE-{index + 1}")
        page.draw_line((30, 90), (220, 90))
    payload = doc.tobytes()
    doc.close()
    return payload


def test_scoped_native_ingestion_preserves_full_source_identity_but_decodes_only_scope() -> None:
    source = _multi_page_pdf_bytes()
    producer = _producer()
    scoped = producer.ingest_native_pdf_bytes(
        document_id="doc-scoped",
        source_bytes=source,
        source_locator="memory://doc-scoped.pdf",
        page_ids=("2",),
    )

    assert scoped.revision.source_sha256 == hashlib.sha256(source).hexdigest()
    assert scoped.revision.partition_ids == ("page:1", "page:2", "page:3")
    assert scoped.coverage.total_pages == 3
    assert scoped.coverage.decoded_pages == (2,)
    assert scoped.coverage.failed_pages == ()
    assert scoped.coverage.state == "partial"

    authority = producer.authority()
    resolved_pages = set()
    for observation_id in scoped.snapshot.observation_ids:
        result = authority.resolve(
            ObservationSelector(
                document_id=scoped.revision.document_id,
                revision_id=scoped.revision.revision_id,
                source_sha256=scoped.revision.source_sha256,
                snapshot_id=scoped.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        assert result.status is EvidenceResolutionStatus.CORROBORATED
        assert result.observation is not None
        resolved_pages.add(result.observation.page_id)
    assert resolved_pages == {"2"}

    png, page_parent = producer.render_native_page_png(
        document_id=scoped.revision.document_id,
        revision_id=scoped.revision.revision_id,
        source_sha256=scoped.revision.source_sha256,
        snapshot_id=scoped.snapshot.snapshot_id,
        page_id="2",
        dpi=72,
    )
    assert png
    assert page_parent.page_id == "2"

    with pytest.raises(ValueError, match=SOURCE_UNAVAILABLE):
        producer.render_native_page_png(
            document_id=scoped.revision.document_id,
            revision_id=scoped.revision.revision_id,
            source_sha256=scoped.revision.source_sha256,
            snapshot_id=scoped.snapshot.snapshot_id,
            page_id="1",
            dpi=72,
        )


def test_scoped_snapshot_keeps_its_coverage_after_full_replay_of_same_revision() -> None:
    source = _multi_page_pdf_bytes()
    producer = _producer()
    scoped = producer.ingest_native_pdf_bytes(
        document_id="doc-scope-then-full",
        source_bytes=source,
        source_locator="memory://doc-scope-then-full.pdf",
        page_ids=(2,),
    )
    full = producer.ingest_native_pdf_bytes(
        document_id="doc-scope-then-full",
        source_bytes=source,
        source_locator="memory://doc-scope-then-full.pdf",
    )

    assert full.revision.revision_id == scoped.revision.revision_id
    assert full.snapshot.snapshot_id != scoped.snapshot.snapshot_id
    assert full.coverage.decoded_pages == (1, 2, 3)
    assert full.coverage.state == "complete"
    assert producer._store.coverage_by_snapshot[
        scoped.snapshot.snapshot_id
    ].decoded_pages == (2,)

    with pytest.raises(ValueError, match=SOURCE_UNAVAILABLE):
        producer.native_page_image_regions(
            document_id=scoped.revision.document_id,
            revision_id=scoped.revision.revision_id,
            source_sha256=scoped.revision.source_sha256,
            snapshot_id=scoped.snapshot.snapshot_id,
            page_id="1",
        )

    regions = producer.native_page_image_regions(
        document_id=full.revision.document_id,
        revision_id=full.revision.revision_id,
        source_sha256=full.revision.source_sha256,
        snapshot_id=full.snapshot.snapshot_id,
        page_id="1",
    )
    assert regions == ()


def test_full_revision_coverage_is_not_downgraded_by_later_scoped_snapshot() -> None:
    source = _multi_page_pdf_bytes()
    producer = _producer()
    full = producer.ingest_native_pdf_bytes(
        document_id="doc-full-then-scope",
        source_bytes=source,
        source_locator="memory://doc-full-then-scope.pdf",
    )
    scoped = producer.ingest_native_pdf_bytes(
        document_id="doc-full-then-scope",
        source_bytes=source,
        source_locator="memory://doc-full-then-scope.pdf",
        page_ids=(2,),
    )

    assert full.coverage.state == "complete"
    assert scoped.coverage.decoded_pages == (2,)
    legacy = producer.authority().coverage(
        document_id=full.revision.document_id,
        revision_id=full.revision.revision_id,
    )
    assert legacy is not None
    assert legacy.state == "complete"
    assert legacy.decoded_pages == (1, 2, 3)
    assert producer._store.coverage_by_snapshot[
        scoped.snapshot.snapshot_id
    ].decoded_pages == (2,)
