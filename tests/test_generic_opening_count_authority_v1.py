"""Item 23 / F24 generic opening-count authority — fail-closed attack tests."""
from __future__ import annotations

import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessRecord,
    SourceEnumerationState,
    _AUTHORITY_SEAL as UNIV_SEAL,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
    PhysicalOpeningExistenceResult,
)
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingRecord,
    ScheduleOpeningInstanceBindingResult,
    _AUTHORITY_SEAL as BIND_SEAL,
)
from pb_schedule_row_quantity_authority import (
    ScheduleRowQuantityProducer,
    ScheduleRowQuantitySelector,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)

from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_CALLER_NON_PLAN_NOT_AUTHORITY,
    GENERIC_OPENING_COUNT_CALLER_SCHEDULE_COUNTS_NOT_AUTHORITY,
    GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED,
    GENERIC_OPENING_COUNT_NON_PLAN_VIEW,
    GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES,
    GENERIC_OPENING_COUNT_RESOLVED,
    GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
    GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL,
    GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE,
    GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE,
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
    OpeningCountDiagnosticRequest,
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)

DOC = "doc-1"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
PAGE = "1"
SCOPE = "scope-plan-1"
VP_PLAN = "vp-plan-1"
VP_ELEV = "vp-elev-named-elevation-section"


def _physical(
    opening_id: str,
    *,
    viewport_id: str = VP_PLAN,
    snap: str = SNAP,
) -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id=opening_id,
        source_observation_ids=(f"obs-{opening_id}",),
        source_lineage_root_ids=(f"root-{opening_id}",),
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=snap,
        page_id=PAGE,
        viewport_id=viewport_id,
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern="jamb_bounded",
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=(),
        producer_method="native_vector",
        producer_version="1.0.0",
        producer_generation=1,
    )


def _setup(
    *,
    openings: tuple[PhysicalOpeningExistenceRecord, ...],
    bindings: tuple[tuple[str, str, str], ...] = (),
    scope_complete: bool = True,
    view_kinds: dict[str, str] | None = None,
    schedule_qty: dict[tuple[str, ...], tuple[str, int]] | None = None,
    diagnostic: OpeningCountDiagnosticRequest | None = None,
    schedule_qty_complete: bool = True,
) -> tuple[GenericOpeningCountProducer, GenericOpeningCountSelector]:
    member_ids = tuple(op.record_id for op in openings)
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-1",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=(PAGE,),
        viewport_id=VP_PLAN,
        enumeration_state=(
            SourceEnumerationState.COMPLETE.value
            if scope_complete
            else SourceEnumerationState.INCOMPLETE.value
        ),
        source_decode_complete=scope_complete,
        semantic_enumeration_complete=scope_complete,
        decision_scope_complete=scope_complete,
        accounted_member_ids=member_ids,
        universe_fingerprint="fp-1",
        reason_codes=() if scope_complete else ("incomplete_scope",),
    )
    univ_key = (DOC, REV, SHA, SNAP, SCOPE)
    univ_auth = OpeningUniverseCompletenessAuthority(
        {univ_key: univ_rec}, _seal=UNIV_SEAL
    )
    # Test-only internal source-authenticated adapter marker. Public
    # completeness producers never receive this seal.
    object.__setattr__(
        univ_auth,
        "_source_authentication_seal",
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
    )

    src_auth = SourceObservationProducer(
        producer_method="test", producer_version="1.0"
    ).authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)
    by_id = {op.record_id: op for op in openings}

    def _prove(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        rec = by_id.get(selector.observation_id)
        if rec is None:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                physical_opening_existence="unresolved",
                reason_codes=("not_found",),
            )
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence="exists",
            reason_codes=(),
            existence_record=rec,
        )

    object.__setattr__(phys_auth, "prove_existence", _prove)

    view_prod = ViewportViewClassProducer.create()
    kinds = view_kinds or {VP_PLAN: VIEW_KIND_FLOOR_PLAN}
    for vp_id, kind in kinds.items():
        view_prod.publish(
            ViewportViewClassSelector(
                document_id=DOC,
                revision_id=REV,
                source_sha256=SHA,
                snapshot_id=SNAP,
                viewport_id=vp_id,
            ),
            view_kind=kind,
            evidence_observation_ids=(f"view-obs-{vp_id}",),
        )

    bind_results: dict = {}
    for op_id, mark, row_id in bindings:
        key = (DOC, REV, SHA, SNAP, SCOPE, op_id)
        bind_results[key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("binding_resolved",),
            record=ScheduleOpeningInstanceBindingRecord(
                record_id=f"bind-{op_id}",
                document_id=DOC,
                revision_id=REV,
                source_sha256=SHA,
                snapshot_id=SNAP,
                page_id=PAGE,
                decision_scope_id=SCOPE,
                opening_record_id=op_id,
                tag_observation_id=f"tag-{op_id}",
                tag_mark=mark,
                schedule_page_id=PAGE,
                schedule_row_observation_ids=(row_id,),
                schedule_row_type_mark=mark,
                schedule_row_width_mm=900,
                schedule_row_height_mm=2100,
            ),
        )
    bind_auth = (
        ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)
        if bindings
        else None
    )

    qty_auth = None
    if schedule_qty:
        qty_prod = ScheduleRowQuantityProducer.create()
        for row_ids, (mark, declared) in schedule_qty.items():
            qty_prod.publish(
                ScheduleRowQuantitySelector(
                    document_id=DOC,
                    revision_id=REV,
                    source_sha256=SHA,
                    snapshot_id=SNAP,
                    schedule_page_id=PAGE,
                    schedule_row_observation_ids=tuple(row_ids),
                ),
                declared_count=declared,
                type_mark=mark,
                universe_complete=schedule_qty_complete,
            )
        qty_auth = qty_prod.authority()

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=view_prod.authority(),
        schedule_binding_authority=bind_auth,
        schedule_row_quantity_authority=qty_auth,
        diagnostic_request=diagnostic,
    )
    selector = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
    )
    return producer, selector


def test_caller_declared_counts_cannot_mint_count_ten() -> None:
    producer, selector = _setup(
        openings=(),
        diagnostic=OpeningCountDiagnosticRequest(
            schedule_declared_counts={"W1": 10},
        ),
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="W1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES in res.reason_codes
    assert GENERIC_OPENING_COUNT_CALLER_SCHEDULE_COUNTS_NOT_AUTHORITY in res.reason_codes
    assert GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL in res.reason_codes


def test_legacy_caller_kwargs_rejected() -> None:
    producer, _ = _setup(openings=(_physical("op-1"),))
    univ = producer._universe
    phys = producer._physical
    view = producer._view_class
    with pytest.raises(TypeError, match="not authority"):
        GenericOpeningCountProducer.from_authorities(
            opening_universe_authority=univ,
            physical_opening_authority=phys,
            viewport_view_class_authority=view,
            schedule_declared_counts={"W1": 10},
        )
    with pytest.raises(TypeError, match="not authority"):
        GenericOpeningCountProducer.from_authorities(
            opening_universe_authority=univ,
            physical_opening_authority=phys,
            viewport_view_class_authority=view,
            non_plan_viewport_ids=("elevation-1",),
        )


def test_caller_non_plan_viewport_ids_cannot_suppress_or_alter_count() -> None:
    openings = tuple(_physical(f"op-{i}") for i in range(3))
    producer, selector = _setup(
        openings=openings,
        diagnostic=OpeningCountDiagnosticRequest(
            non_plan_viewport_ids=(VP_PLAN, "view-plan"),
        ),
    )
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 3
    assert GENERIC_OPENING_COUNT_CALLER_NON_PLAN_NOT_AUTHORITY in res.reason_codes


def test_guessed_elevation_viewport_name_cannot_establish_authority() -> None:
    """Viewport id containing 'elevation' is irrelevant without view-class authority."""
    op = _physical("op-elev-name", viewport_id=VP_ELEV)
    # No view-class published for VP_ELEV → unavailable, not keyword sniff.
    producer, _ = _setup(
        openings=(op,),
        view_kinds={VP_PLAN: VIEW_KIND_FLOOR_PLAN},  # not VP_ELEV
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_VIEWPORT_CLASS_UNAVAILABLE in res.reason_codes


def test_authenticated_elevation_view_class_blocks_plan_count() -> None:
    op = _physical("op-e", viewport_id=VP_ELEV)
    producer, selector = _setup(
        openings=(op,),
        view_kinds={VP_ELEV: VIEW_KIND_ELEVATION},
    )
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_NON_PLAN_VIEW in res.reason_codes


def test_schedule_eight_vs_six_physical_conflicts() -> None:
    openings = tuple(_physical(f"op-{i}") for i in range(6))
    bindings = tuple((f"op-{i}", "W1", "row-w1") for i in range(6))
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 8)},
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="W1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH in res.reason_codes
    assert res.record is None


def test_schedule_only_eight_does_not_manufacture_physical() -> None:
    producer, _ = _setup(
        openings=(),
        schedule_qty={("row-w1",): ("W1", 8)},
        diagnostic=OpeningCountDiagnosticRequest(schedule_declared_counts={"W1": 8}),
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="W1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES in res.reason_codes


def test_duplicate_observations_of_same_physical_count_once() -> None:
    # Universe lists same member twice; existence record_id dedupes.
    op = _physical("op-same")
    member_ids = ("op-same", "op-same")
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-dup",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=(PAGE,),
        viewport_id=VP_PLAN,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=member_ids,
        universe_fingerprint="fp-dup",
        reason_codes=(),
    )
    univ_auth = OpeningUniverseCompletenessAuthority(
        {(DOC, REV, SHA, SNAP, SCOPE): univ_rec}, _seal=UNIV_SEAL
    )
    object.__setattr__(
        univ_auth,
        "_source_authentication_seal",
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
    )
    src_auth = SourceObservationProducer(
        producer_method="test", producer_version="1.0"
    ).authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)

    def _prove(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence="exists",
            reason_codes=(),
            existence_record=op,
        )

    object.__setattr__(phys_auth, "prove_existence", _prove)
    view_prod = ViewportViewClassProducer.create()
    view_prod.publish(
        ViewportViewClassSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            viewport_id=VP_PLAN,
        ),
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("v1",),
    )
    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=view_prod.authority(),
    )
    res = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
        )
    )
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 1


def test_equal_size_distinct_physical_openings_count_independently() -> None:
    openings = (_physical("op-a"), _physical("op-b"), _physical("op-c"))
    producer, selector = _setup(openings=openings)
    res = producer.publish(selector)
    assert res.record is not None
    assert res.record.count == 3
    assert set(res.record.physical_instance_record_ids) == {"op-a", "op-b", "op-c"}


def test_stale_schedule_lineage_fails() -> None:
    openings = (_physical("op-1"),)
    # Binding/qty published under stale snapshot via physical snap mismatch.
    stale = _physical("op-1", snap="snap-stale")
    producer, selector = _setup(openings=(stale,))
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.CONFLICT


def test_incomplete_schedule_universe_abstains_qty() -> None:
    openings = tuple(_physical(f"op-{i}") for i in range(2))
    bindings = tuple((f"op-{i}", "D1", "row-d1") for i in range(2))
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-d1",): ("D1", 2)},
        schedule_qty_complete=False,
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="D1",
    )
    res = producer.publish(sel)
    # Physical count still publishes; incomplete schedule qty cannot corroborate.
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 2
    assert res.record.schedule_corroborated is False


def test_incomplete_opening_universe_abstains() -> None:
    producer, selector = _setup(
        openings=(_physical("op-1"),),
        scope_complete=False,
    )
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE in res.reason_codes


def test_physical_plus_matching_schedule_corroborates() -> None:
    openings = tuple(_physical(f"op-{i}") for i in range(4))
    bindings = tuple((f"op-{i}", "D1", "row-d1") for i in range(4))
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-d1",): ("D1", 4)},
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="D1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert GENERIC_OPENING_COUNT_RESOLVED in res.reason_codes
    assert res.record is not None
    assert res.record.count == 4
    assert res.record.schedule_corroborated is True
    assert res.record.quantity_evidence is not None
    assert res.record.quantity_evidence.status == AuthorityStatus.FIRM.value


def test_public_unsealed_completeness_cannot_unlock_firm_count() -> None:
    op = _physical("op-public")
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-public",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_ids=(PAGE,),
        viewport_id=VP_PLAN,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=(op.record_id,),
        universe_fingerprint="caller-fp",
        reason_codes=(),
    )
    univ_auth = OpeningUniverseCompletenessAuthority(
        {(DOC, REV, SHA, SNAP, SCOPE): univ_rec}, _seal=UNIV_SEAL
    )
    src_auth = SourceObservationProducer(
        producer_method="test", producer_version="1.0"
    ).authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)
    view_prod = ViewportViewClassProducer.create()
    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=view_prod.authority(),
    )
    res = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
        )
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert GENERIC_OPENING_COUNT_COMPLETENESS_NOT_SOURCE_AUTHENTICATED in res.reason_codes
