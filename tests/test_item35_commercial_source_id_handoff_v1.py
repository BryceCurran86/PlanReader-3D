from __future__ import annotations

from pb_generic_opening_count_authority import (
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
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
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)

DOC = "doc"
REV = "rev"
SHA = "a" * 64
SNAP = "snap"
SCOPE = "scope"
OBS = "source-observation-1"
OPENING = "opening-1"
VP = "viewport-1"


def test_sealed_completeness_uses_source_observation_ids_not_hashed_member_ids() -> None:
    record = OpeningUniverseCompletenessRecord(
        record_id="universe",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=("1",),
        viewport_id=VP,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=("hashed-member-id",),
        universe_fingerprint="fingerprint",
        reason_codes=(),
        accounted_source_observation_ids=(OBS,),
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
            producer_method="test",
            producer_version="1",
        ).authority()
    )
    opening = PhysicalOpeningExistenceRecord(
        record_id=OPENING,
        source_observation_ids=(OBS,),
        source_lineage_root_ids=("root-1",),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id="1",
        viewport_id=VP,
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

    def _prove(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        assert selector.observation_id == OBS
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence=PHYSICAL_OPENING_EXISTS,
            reason_codes=(),
            existence_record=opening,
        )

    object.__setattr__(physical, "prove_existence", _prove)

    view = ViewportViewClassProducer.create()
    view.publish(
        ViewportViewClassSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            viewport_id=VP,
        ),
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("view-evidence",),
    )

    result = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=universe,
        physical_opening_authority=physical,
        viewport_view_class_authority=view.authority(),
    ).publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
        )
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.count == 1
