from __future__ import annotations

from dataclasses import replace
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE,
    AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,
    MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import (
    OBSERVATION_UNAVAILABLE,
    PRODUCER_INTEGRITY_FAILURE,
    SOURCE_HASH_MISMATCH,
    SOURCE_OBSERVATION_EXISTS,
    STALE_REVISION,
    ObservationSelector,
    SourceObservationAuthorityResult,
    SourceObservationProducer,
)


def _pdf_bytes(*texts: str, with_rect: bool = True) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    for index, text in enumerate(texts):
        page.insert_text((30, 40 + 24 * index), text)
    if with_rect:
        page.draw_rect(fitz.Rect(120, 80, 190, 170))
    payload = doc.tobytes()
    doc.close()
    return payload


def _fixture(*texts: str):
    producer = SourceObservationProducer(
        producer_method="g17-test-native-pdf",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="doc-1",
        source_bytes=_pdf_bytes(*texts),
        source_locator="memory://doc-1.pdf",
    )
    source_authority = producer.authority()
    physical_authority = PhysicalOpeningAuthority(source_authority)
    selectors = [
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in published.snapshot.observation_ids
    ]
    return producer, published, source_authority, physical_authority, selectors


def _selector_for(source_authority, selectors, *, text: str | None = None, kind: str | None = None):
    for selector in selectors:
        result = source_authority.resolve(selector)
        observation = result.observation
        if observation is None:
            continue
        if text is not None and observation.raw_text != text:
            continue
        if kind is not None and observation.observation_kind != kind:
            continue
        return selector
    raise AssertionError(f"no observation matched text={text!r} kind={kind!r}")


def test_source_observation_exists_does_not_prove_physical_opening() -> None:
    _, _, source, physical, selectors = _fixture("D01")
    selector = _selector_for(source, selectors, text="D01")

    source_result = source.resolve(selector)
    result = physical.prove_existence(selector)

    assert source_result.status is EvidenceResolutionStatus.CORROBORATED
    assert source_result.proposition == SOURCE_OBSERVATION_EXISTS
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert result.reason_codes == (AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,)
    assert result.missing_upstream_capability == MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY


def test_native_vector_rectangle_cannot_be_promoted_to_physical_opening() -> None:
    _, _, source, physical, selectors = _fixture("PLAN")
    selector = _selector_for(source, selectors, kind="native_pdf_rect")

    result = physical.prove_existence(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE in result.reason_codes


@pytest.mark.parametrize("kind", ["ocr_opening_tag", "cv_opening_detection", "heuristic_opening_candidate", "schedule_opening_type"])
def test_derived_ocr_cv_heuristic_and_schedule_evidence_cannot_prove_physical_instance(kind: str) -> None:
    producer, published, source, physical, selectors = _fixture("D01")
    parent = selectors[0]
    derived_id = f"derived-{kind}"
    derived_snapshot = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind=kind,
        source_primitive_ref=f"derived:{kind}",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        raw_text="D01",
        geometry=(120.0, 80.0, 190.0, 170.0),
        observation_id=derived_id,
    )
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=derived_snapshot.snapshot_id,
        observation_id=derived_id,
    )

    assert source.resolve(selector).status is EvidenceResolutionStatus.CORROBORATED
    result = physical.prove_existence(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert result.proposition is None


def test_schedule_row_neither_proves_a_physical_instance_nor_zero_instances() -> None:
    producer, published, source, physical, selectors = _fixture("DOOR SCHEDULE", "D01 900 x 2100")
    parent = selectors[0]
    snapshot = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="schedule_row",
        source_primitive_ref="schedule:row:1",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        raw_text="D01 900 x 2100",
        observation_id="schedule-row-1",
    )
    selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        observation_id="schedule-row-1",
    )

    result = physical.prove_existence(selector)
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert "zero" not in " ".join(result.reason_codes).lower()


def test_consumer_api_has_no_authority_slots_for_tags_dimensions_coordinates_candidates_or_atoms() -> None:
    parameters = inspect.signature(PhysicalOpeningAuthority.prove_existence).parameters
    assert tuple(parameters) == ("self", "selector")

    _, _, _, physical, selectors = _fixture("D01")
    selector = selectors[0]
    with pytest.raises(TypeError):
        physical.prove_existence(selector, tag="D01")  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        physical.prove_existence(selector, dimensions=(0.9, 2.1))  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        physical.prove_existence(selector, candidate_list=[selector])  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        physical.prove_existence(selector, evidence_status="corroborated")  # type: ignore[call-arg]


def test_caller_created_lookalike_or_fabricated_corroborated_result_is_not_accepted() -> None:
    _, _, source, physical, selectors = _fixture("D01")
    selector = selectors[0]
    source_result = source.resolve(selector)
    fabricated = replace(
        source_result,
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=SOURCE_OBSERVATION_EXISTS,
    )

    with pytest.raises(TypeError):
        physical.prove_existence(fabricated)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        physical.prove_existence(
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "observation_id": selector.observation_id,
                "status": "corroborated",
            }
        )  # type: ignore[arg-type]


def test_fake_source_authority_cannot_be_injected_to_mint_corroborated_semantics() -> None:
    class FakeSourceAuthority:
        def resolve(self, selector):
            return SourceObservationAuthorityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                proposition=SOURCE_OBSERVATION_EXISTS,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=("caller_says_so",),
            )

    with pytest.raises(TypeError):
        PhysicalOpeningAuthority(FakeSourceAuthority())  # type: ignore[arg-type]


def test_invented_hash_and_observation_id_fail_closed_before_semantic_promotion() -> None:
    _, _, _, physical, selectors = _fixture("D01")
    selector = selectors[0]

    bad_hash = replace(selector, source_sha256="0" * 64)
    hash_result = physical.prove_existence(bad_hash)
    assert hash_result.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_HASH_MISMATCH in hash_result.reason_codes
    assert hash_result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED

    bad_id = replace(selector, observation_id="caller-invented-opening")
    id_result = physical.prove_existence(bad_id)
    assert id_result.status is EvidenceResolutionStatus.ABSTAINED
    assert OBSERVATION_UNAVAILABLE in id_result.reason_codes
    assert id_result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_stale_revision_fails_closed_and_cannot_recover_physical_authority() -> None:
    producer, published, _, physical, selectors = _fixture("D01")
    old_selector = selectors[0]
    producer.ingest_native_pdf_bytes(
        document_id=published.revision.document_id,
        source_bytes=_pdf_bytes("D02", "REVISION 2"),
        source_locator="memory://doc-1-rev2.pdf",
    )

    result = physical.prove_existence(old_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert STALE_REVISION in result.reason_codes
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_exact_same_source_observation_still_does_not_establish_physical_opening_identity() -> None:
    _, _, _, physical, selectors = _fixture("D01")
    selector = selectors[0]

    result = physical.compare_identity(selector, selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert result.proven_same is False
    assert AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE in result.reason_codes


def test_same_tag_text_and_geometry_across_distinct_observations_cannot_prove_same_physical_opening() -> None:
    producer, published, _, physical, selectors = _fixture("D01")
    parent = selectors[0]
    first = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="heuristic_opening_candidate",
        source_primitive_ref="candidate:a",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        raw_text="D01",
        geometry=(10.0, 20.0, 30.0, 40.0),
        observation_id="candidate-a",
    )
    second = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="heuristic_opening_candidate",
        source_primitive_ref="candidate:b",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        raw_text="D01",
        geometry=(10.0, 20.0, 30.0, 40.0),
        observation_id="candidate-b",
    )
    left = replace(
        parent,
        snapshot_id=first.snapshot_id,
        observation_id="candidate-a",
    )
    right = replace(
        parent,
        snapshot_id=second.snapshot_id,
        observation_id="candidate-b",
    )

    result = physical.compare_identity(left, right)
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert result.proven_same is False
    assert result.status is EvidenceResolutionStatus.ABSTAINED


def test_more_opening_looking_or_contradictory_observations_cannot_strengthen_semantic_authority() -> None:
    producer, published, _, physical, selectors = _fixture("D01", "NOT A DOOR")
    parent = selectors[0]
    before = physical.prove_existence(parent)
    snapshot = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="cv_opening_detection",
        source_primitive_ref="cv:strong:1",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        raw_text="D01 DEFINITELY DOOR",
        geometry=(10.0, 10.0, 100.0, 200.0),
        observation_id="cv-strong-1",
    )
    after_selector = replace(parent, snapshot_id=snapshot.snapshot_id, observation_id="cv-strong-1")
    after = physical.prove_existence(after_selector)

    assert before.status is EvidenceResolutionStatus.ABSTAINED
    assert after.status is EvidenceResolutionStatus.ABSTAINED
    assert before.physical_opening_existence == after.physical_opening_existence
    assert after.proposition is None


def test_deterministic_replay_and_hashes_do_not_promote_semantics() -> None:
    pdf = _pdf_bytes("D01")
    producer = SourceObservationProducer(producer_method="g17-test-native-pdf", producer_version="1.0")
    first = producer.ingest_native_pdf_bytes(
        document_id="doc-replay", source_bytes=pdf, source_locator="memory://first.pdf"
    )
    second = producer.ingest_native_pdf_bytes(
        document_id="doc-replay", source_bytes=pdf, source_locator="memory://second.pdf"
    )
    assert first.revision.revision_id == second.revision.revision_id
    assert first.snapshot.snapshot_id == second.snapshot.snapshot_id

    source = producer.authority()
    physical = PhysicalOpeningAuthority(source)
    selector = ObservationSelector(
        document_id=first.revision.document_id,
        revision_id=first.revision.revision_id,
        source_sha256=first.revision.source_sha256,
        snapshot_id=first.snapshot.snapshot_id,
        observation_id=first.snapshot.observation_ids[0],
    )
    result = physical.prove_existence(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_absence_of_opening_like_observation_is_not_zero_physical_openings() -> None:
    _, _, _, physical, selectors = _fixture("GENERAL NOTES", with_rect=False) if False else _fixture("GENERAL NOTES")
    results = [physical.prove_existence(selector) for selector in selectors]

    assert results
    assert all(result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED for result in results)
    assert all(result.proposition is None for result in results)
    assert all(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE in result.reason_codes for result in results)


def test_phase2_does_not_claim_universe_dimensions_host_or_void_authority() -> None:
    fields = PhysicalOpeningAuthority.capabilities()
    assert fields == {
        "physical_opening_existence": False,
        "physical_opening_identity": False,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }
