from __future__ import annotations

from types import SimpleNamespace

from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessProducer,
    OpeningUniverseCompletenessRecord,
    SourceEnumerationState,
    _AUTHORITY_SEAL as UNIVERSE_AUTHORITY_SEAL,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
    PhysicalOpeningExistenceResult,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceDecodeCoverageRecord,
    SourceObservationProducer,
)
from pb_viewport_view_class_authority import ViewportViewClassProducer


DOC = "doc"
REV = "rev"
SHA = "a" * 64
SNAP = "snap"
SCOPE = "scope"


def test_completeness_record_retains_exact_source_primitive_ids() -> None:
    primitive = SimpleNamespace(
        primitive_id="obs-real",
        page_id="1",
        geometry=(10.0, 10.0, 20.0, 10.0),
        layer="semantic-opening",
        clip_known=True,
        clip_present=False,
        clip=None,
    )
    producer = OpeningUniverseCompletenessProducer(
        producer_method="source-id-test",
        producer_version="1",
    )
    record = producer.publish_enumeration(
        decision_scope_id=SCOPE,
        decision_scope_kind="pages",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=("1",),
        viewport_id=None,
        coverage=SourceDecodeCoverageRecord(
            document_id=DOC,
            revision_id=REV,
            total_pages=1,
            decoded_pages=(1,),
            failed_pages=(),
            state="complete",
        ),
        source_primitives=(primitive,),
        enumerated_primitives=(primitive,),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
        semantic_enumeration_proven=True,
    )

    assert record.decision_scope_complete is True
    assert record.accounted_source_observation_ids == ("obs-real",)
    assert record.accounted_member_ids
    assert record.accounted_member_ids != record.accounted_source_observation_ids


def test_generic_count_reproves_source_ids_before_hashed_member_ids() -> None:
    record = OpeningUniverseCompletenessRecord(
        record_id="univ",
        decision_scope_id=SCOPE,
        decision_scope_kind="pages",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=("1",),
        viewport_id=None,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=("semantic-member-hash",),
        universe_fingerprint="fp",
        reason_codes=(),
        accounted_source_observation_ids=("obs-real",),
    )
    universe = OpeningUniverseCompletenessAuthority(
        {(DOC, REV, SHA, SNAP, SCOPE): record},
        _seal=UNIVERSE_AUTHORITY_SEAL,
    )
    object.__setattr__(
        universe,
        "_source_authentication_seal",
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
    )

    physical = PhysicalOpeningAuthority(
        SourceObservationProducer(
            producer_method="source-id-test",
            producer_version="1",
        ).authority()
    )
    seen: list[str] = []

    def _prove(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        seen.append(selector.observation_id)
        existence = PhysicalOpeningExistenceRecord(
            record_id="opening-1",
            source_observation_ids=("obs-real",),
            source_lineage_root_ids=("root-1",),
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id="1",
            viewport_id=None,
            semantic_class="opening",
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            structural_pattern="test",
            diagnostic_confidence=1.0,
            blocking_reasons=(),
            structural_reason_codes=(),
            producer_method="test",
            producer_version="1",
            producer_generation=1,
        )
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence=PHYSICAL_OPENING_EXISTS,
            reason_codes=(),
            existence_record=existence,
        )

    object.__setattr__(physical, "prove_existence", _prove)

    generic = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=universe,
        physical_opening_authority=physical,
        viewport_view_class_authority=ViewportViewClassProducer.create().authority(),
    )
    result = generic.publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
        )
    )

    assert seen == ["obs-real"]
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE in result.reason_codes
