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
    SOURCE_HASH_MISMATCH,
    SOURCE_OBSERVATION_EXISTS,
    STALE_REVISION,
    ObservationSelector,
    SourceObservationAuthorityResult,
    SourceObservationProducer,
)


def _pdf_bytes(*texts: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=320, height=240)
    for index, text in enumerate(texts):
        page.insert_text((30, 40 + 24 * index), text)
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
    source = producer.authority()
    physical = PhysicalOpeningAuthority(source)
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
    return producer, published, source, physical, selectors


def _selector_for(source, selectors, *, text: str | None = None, kind: str | None = None):
    for selector in selectors:
        result = source.resolve(selector)
        observation = result.observation
        if observation is None:
            continue
        if text is not None and observation.raw_text != text:
            continue
        if kind is not None and observation.observation_kind != kind:
            continue
        return selector
    raise AssertionError("matching source observation not found")


def test_source_observation_alone_does_not_prove_physical_opening() -> None:
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


def test_native_rectangle_alone_does_not_prove_opening() -> None:
    _, _, source, physical, selectors = _fixture("PLAN")
    selector = _selector_for(source, selectors, kind="native_pdf_rect")
    assert physical.prove_existence(selector).status is EvidenceResolutionStatus.ABSTAINED


@pytest.mark.parametrize(
    "kind",
    ["ocr_opening_tag", "cv_opening_detection", "heuristic_opening_candidate", "schedule_opening_type"],
)
def test_derived_labels_and_detector_outputs_do_not_prove_opening(kind: str) -> None:
    producer, published, source, physical, selectors = _fixture("D01")
    parent = selectors[0]
    snapshot = producer.publish_derived_observation(
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
        observation_id=f"derived-{kind}",
    )
    selector = replace(parent, snapshot_id=snapshot.snapshot_id, observation_id=f"derived-{kind}")
    assert source.resolve(selector).status is EvidenceResolutionStatus.CORROBORATED
    assert physical.prove_existence(selector).status is EvidenceResolutionStatus.ABSTAINED


def test_consumer_cannot_supply_authority_claims() -> None:
    assert tuple(inspect.signature(PhysicalOpeningAuthority.prove_existence).parameters) == (
        "self",
        "selector",
    )
    _, _, _, physical, selectors = _fixture("D01")
    selector = selectors[0]
    for kwargs in (
        {"tag": "D01"},
        {"dimensions": (0.9, 2.1)},
        {"candidate_list": [selector]},
        {"confidence": 1.0},
        {"evidence_status": "corroborated"},
    ):
        with pytest.raises(TypeError):
            physical.prove_existence(selector, **kwargs)  # type: ignore[call-arg]


def test_fake_source_authority_cannot_be_injected() -> None:
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


def test_bad_hash_bad_id_and_stale_revision_fail_closed() -> None:
    producer, published, _, physical, selectors = _fixture("D01")
    selector = selectors[0]
    bad_hash = physical.prove_existence(replace(selector, source_sha256="0" * 64))
    assert bad_hash.status is EvidenceResolutionStatus.ABSTAINED
    assert SOURCE_HASH_MISMATCH in bad_hash.reason_codes
    bad_id = physical.prove_existence(replace(selector, observation_id="invented-opening"))
    assert bad_id.status is EvidenceResolutionStatus.ABSTAINED
    assert OBSERVATION_UNAVAILABLE in bad_id.reason_codes
    producer.ingest_native_pdf_bytes(
        document_id=published.revision.document_id,
        source_bytes=_pdf_bytes("REVISION 2"),
        source_locator="memory://doc-1-rev2.pdf",
    )
    stale = physical.prove_existence(selector)
    assert stale.status is EvidenceResolutionStatus.ABSTAINED
    assert STALE_REVISION in stale.reason_codes


def test_identity_remains_unresolved_even_for_same_observation() -> None:
    _, _, _, physical, selectors = _fixture("D01")
    result = physical.compare_identity(selectors[0], selectors[0])
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.physical_opening_identity == PHYSICAL_OPENING_IDENTITY_UNRESOLVED
    assert result.proven_same is False
    assert AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE in result.reason_codes


def test_phase2_capability_is_existence_only() -> None:
    assert PhysicalOpeningAuthority.capabilities() == {
        "physical_opening_existence": True,
        "physical_opening_identity": False,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }
