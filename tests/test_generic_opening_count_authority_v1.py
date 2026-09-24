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
    ScheduleOpeningInstanceBindingSelector,
    _AUTHORITY_SEAL as BIND_SEAL,
)
from pb_schedule_row_quantity_authority import (
    ScheduleRowQuantityProducer,
    ScheduleRowQuantitySelector,
)
from pb_schedule_row_quantity_binding_adapter import (
    publish_schedule_row_quantity_from_binding,
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
    GENERIC_OPENING_COUNT_IDENTITY_CONTRADICTION,
    GENERIC_OPENING_COUNT_IDENTITY_PAIRWISE_UNRESOLVED,
    GENERIC_OPENING_COUNT_LINEAGE_MISMATCH,
    GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED,
    GENERIC_OPENING_COUNT_NON_PLAN_VIEW,
    GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES,
    GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED,
    GENERIC_OPENING_COUNT_RESOLVED,
    GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
    GENERIC_OPENING_COUNT_SCHEDULE_ONLY_NOT_PHYSICAL,
    GENERIC_OPENING_COUNT_SCHEDULE_ROW_DUPLICATE,
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
        schedule_spec = (
            schedule_qty.get((row_id,))
            if schedule_qty is not None
            else None
        )
        explicit_count = int(schedule_spec[1]) if schedule_spec is not None else None
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
                schedule_row_count=explicit_count,
                schedule_row_count_explicit=schedule_spec is not None,
            ),
        )
    bind_auth = (
        ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)
        if bindings
        else None
    )

    qty_auth = None
    if schedule_qty and bind_auth is not None and schedule_qty_complete:
        qty_prod = ScheduleRowQuantityProducer.create()
        published_rows: set[tuple[str, ...]] = set()
        for op_id, _mark, row_id in bindings:
            row_ids = (row_id,)
            if row_ids not in schedule_qty or row_ids in published_rows:
                continue
            publish_schedule_row_quantity_from_binding(
                schedule_row_quantity_producer=qty_prod,
                schedule_binding_authority=bind_auth,
                binding_selector=ScheduleOpeningInstanceBindingSelector(
                    document_id=DOC,
                    revision_id=REV,
                    source_sha256=SHA,
                    snapshot_id=SNAP,
                    decision_scope_id=SCOPE,
                    opening_record_id=op_id,
                ),
            )
            published_rows.add(row_ids)
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
    # Lineage now cites the corroborating schedule row alongside the
    # physical geometry evidence, not physical geometry alone.
    assert "row-d1" in res.record.quantity_evidence.evidence_ids
    for i in range(4):
        assert f"obs-op-{i}" in res.record.quantity_evidence.evidence_ids


def test_uncorroborated_quantity_evidence_excludes_schedule_row_lineage() -> None:
    """When the schedule does not corroborate (mismatch case is blocked
    before a record publishes), an ABSTAINED/no-schedule count's evidence
    lineage must not cite schedule rows it never actually relied on."""
    openings = tuple(_physical(f"op-{i}") for i in range(2))
    bindings = tuple((f"op-{i}", "D1", "row-d1") for i in range(2))
    # No schedule_qty published at all -> schedule_corroborated stays False.
    producer, _ = _setup(openings=openings, bindings=bindings)
    sel = GenericOpeningCountSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="D1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.schedule_corroborated is False
    assert res.record.quantity_evidence is not None
    assert "row-d1" not in res.record.quantity_evidence.evidence_ids


def test_two_marks_on_same_page_do_not_cross_contaminate_counts() -> None:
    w1_openings = tuple(_physical(f"w1-{i}") for i in range(2))
    d1_openings = tuple(_physical(f"d1-{i}") for i in range(3))
    bindings = tuple((op.record_id, "W1", "row-w1") for op in w1_openings) + tuple(
        (op.record_id, "D1", "row-d1") for op in d1_openings
    )
    producer, _ = _setup(
        openings=w1_openings + d1_openings,
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 2), ("row-d1",): ("D1", 3)},
    )
    w1_res = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="W1",
        )
    )
    d1_res = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="D1",
        )
    )
    assert w1_res.status is EvidenceResolutionStatus.CORROBORATED
    assert w1_res.record is not None
    assert w1_res.record.count == 2
    assert set(w1_res.record.physical_instance_record_ids) == {"w1-0", "w1-1"}

    assert d1_res.status is EvidenceResolutionStatus.CORROBORATED
    assert d1_res.record is not None
    assert d1_res.record.count == 3
    assert set(d1_res.record.physical_instance_record_ids) == {"d1-0", "d1-1", "d1-2"}


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


def test_pairwise_identity_contradiction_conflicts() -> None:
    """record_id dedup says op-x and op-y are distinct; an independently
    re-proven compare_identity() that disagrees must fail closed, never be
    silently trusted away."""
    openings = (_physical("op-x"), _physical("op-y"))
    producer, selector = _setup(openings=openings)

    from pb_physical_opening_authority import (
        PHYSICAL_OPENING_IDENTITY_RESOLVED,
        PhysicalOpeningIdentityResult,
    )

    def _forced_same(left_selector, right_selector):
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            physical_opening_identity="op-x",
            proven_same=True,
            reason_codes=(PHYSICAL_OPENING_IDENTITY_RESOLVED,),
        )

    object.__setattr__(producer._physical, "compare_identity", _forced_same)
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert res.record is None
    assert GENERIC_OPENING_COUNT_IDENTITY_CONTRADICTION in res.reason_codes


def test_pairwise_identity_unresolved_abstains() -> None:
    """An independently re-proven pairwise identity comparison that cannot
    resolve must abstain the whole count, not silently keep the cheap
    record_id-based dedup's answer."""
    openings = (_physical("op-x"), _physical("op-y"))
    producer, selector = _setup(openings=openings)

    from pb_physical_opening_authority import (
        PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
        PhysicalOpeningIdentityResult,
    )

    def _unresolved(left_selector, right_selector):
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
            proven_same=False,
            reason_codes=(PHYSICAL_OPENING_IDENTITY_UNRESOLVED,),
        )

    object.__setattr__(producer._physical, "compare_identity", _unresolved)
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert GENERIC_OPENING_COUNT_IDENTITY_PAIRWISE_UNRESOLVED in res.reason_codes


def test_duplicate_schedule_rows_same_value_different_rows_conflicts() -> None:
    """Two DISTINCT schedule rows that happen to declare the same count for
    one mark must never collapse into one agreeing value — that would hide
    a real duplicate/conflicting schedule entry."""
    openings = (_physical("op-1"), _physical("op-2"))
    bindings = (
        ("op-1", "W1", "row-a"),
        ("op-2", "W1", "row-b"),
    )
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-a",): ("W1", 2), ("row-b",): ("W1", 2)},
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
    assert res.record is None
    assert GENERIC_OPENING_COUNT_SCHEDULE_ROW_DUPLICATE in res.reason_codes


def test_one_unresolvable_member_blocks_entire_count_even_if_others_match_schedule() -> None:
    """Universe of 4 accounted members (A,B,C,D). A/B/C exist and bind to
    W1; D's existence cannot be proven. Schedule declares W1=3 — the exact
    count A/B/C alone would produce. The count must still NEVER corroborate:
    an unresolvable member of a claimed-complete universe blocks the whole
    scope rather than silently counting only the resolvable subset."""
    a, b, c = _physical("A"), _physical("B"), _physical("C")
    member_ids = ("A", "B", "C", "D")
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-abcd",
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
        universe_fingerprint="fp-abcd",
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
    by_id = {op.record_id: op for op in (a, b, c)}

    def _prove(sel: ObservationSelector) -> PhysicalOpeningExistenceResult:
        rec = by_id.get(sel.observation_id)
        if rec is None:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                physical_opening_existence="unresolved",
                reason_codes=("d_unresolvable",),
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
    view_prod.publish(
        ViewportViewClassSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, viewport_id=VP_PLAN,
        ),
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("v1",),
    )

    bind_results = {}
    for op_id in ("A", "B", "C"):
        key = (DOC, REV, SHA, SNAP, SCOPE, op_id)
        bind_results[key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("binding_resolved",),
            record=ScheduleOpeningInstanceBindingRecord(
                record_id=f"bind-{op_id}",
                document_id=DOC, revision_id=REV, source_sha256=SHA,
                snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
                opening_record_id=op_id, tag_observation_id=f"tag-{op_id}",
                tag_mark="W1", schedule_page_id=PAGE,
                schedule_row_observation_ids=("row-w1",),
                schedule_row_type_mark="W1",
                schedule_row_width_mm=900, schedule_row_height_mm=2100,
                schedule_row_count=3,
                schedule_row_count_explicit=True,
            ),
        )
    bind_auth = ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)

    qty_prod = ScheduleRowQuantityProducer.create()
    publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=qty_prod,
        schedule_binding_authority=bind_auth,
        binding_selector=ScheduleOpeningInstanceBindingSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
            opening_record_id="A",
        ),
    )

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=view_prod.authority(),
        schedule_binding_authority=bind_auth,
        schedule_row_quantity_authority=qty_prod.authority(),
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="W1",
    )
    res = producer.publish(sel)
    assert res.status is not EvidenceResolutionStatus.CORROBORATED
    assert res.record is None
    assert GENERIC_OPENING_COUNT_PHYSICAL_INSTANCE_UNRESOLVED in res.reason_codes


def test_mark_filtered_count_abstains_when_any_physical_member_mark_is_unresolved() -> None:
    """Known W1 members are not the same proposition as all W1 members.

    A second independently proven physical opening with no authenticated
    tag/schedule binding could still be W1, so the filtered count must abstain
    rather than silently dropping that universe member.
    """
    openings = (_physical("w1-known"), _physical("mark-unknown"))
    producer, _ = _setup(
        openings=openings,
        bindings=(("w1-known", "W1", "row-w1"),),
    )
    result = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
            opening_mark="W1",
        )
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert (
        GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED
        in result.reason_codes
    )
    assert any(
        "mark-unknown" in reason
        for reason in result.reason_codes
    )


def test_family_filtered_count_abstains_when_any_physical_member_family_is_unresolved() -> None:
    """A proven but unclassified opening may still belong to the requested family."""
    openings = (_physical("door-known"), _physical("family-unknown"))
    producer, _ = _setup(
        openings=openings,
        bindings=(("door-known", "D1", "row-d1"),),
    )
    result = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
            opening_family="door",
        )
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert (
        GENERIC_OPENING_COUNT_MEMBER_CLASSIFICATION_UNRESOLVED
        in result.reason_codes
    )
    assert any(
        "family-unknown" in reason
        for reason in result.reason_codes
    )


def test_known_other_mark_can_be_ruled_out_without_blocking_w1_count() -> None:
    """Complete classification may exclude a known W2 while publishing W1."""
    openings = (_physical("w1-known"), _physical("w2-known"))
    producer, _ = _setup(
        openings=openings,
        bindings=(
            ("w1-known", "W1", "row-w1"),
            ("w2-known", "W2", "row-w2"),
        ),
    )
    result = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            decision_scope_id=SCOPE,
            opening_mark="W1",
        )
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.count == 1
    assert result.record.physical_instance_record_ids == ("w1-known",)


def test_physical_exceeds_schedule_conflicts() -> None:
    """physical > schedule must CONFLICT, never silently take the smaller
    (schedule) number."""
    openings = tuple(_physical(f"op-{i}") for i in range(6))
    bindings = tuple((f"op-{i}", "W1", "row-w1") for i in range(6))
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 4)},
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="W1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert res.record is None
    assert GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH in res.reason_codes


def test_producer_signature_cannot_accept_caller_instance_bundles() -> None:
    """Architectural guarantee, not just empirical behavior: the producer's
    public construction surface has no parameter through which a caller
    could hand it a hand-picked subset of instance/evidence bundles. The
    only inputs are producer-owned Authorities; the universe's own
    accounted_member_ids is what determines which members require
    reconciliation, and omitting one is not expressible through this
    signature."""
    import inspect

    params = set(inspect.signature(GenericOpeningCountProducer.from_authorities).parameters)
    forbidden = {
        "instance_evidence", "opening_instance_evidence", "instances",
        "physical_instance_ids", "member_ids", "bundles", "candidates",
    }
    assert not (params & forbidden), (
        f"from_authorities must not accept caller-selected instance params: {params & forbidden}"
    )
    assert params == {
        "opening_universe_authority",
        "physical_opening_authority",
        "viewport_view_class_authority",
        "schedule_binding_authority",
        "schedule_row_quantity_authority",
        "diagnostic_request",
        "schedule_declared_counts",
        "non_plan_viewport_ids",
    }


def test_stale_revision_lineage_fails() -> None:
    """Distinct from the existing stale-snapshot test: a physical existence
    record published under a different revision_id than the selector must
    also fail closed via the same lineage cross-check."""
    openings = (_physical("op-1"),)
    member_ids = ("op-1",)
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-stale-rev",
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
        universe_fingerprint="fp-stale-rev",
        reason_codes=(),
    )
    univ_auth = OpeningUniverseCompletenessAuthority(
        {(DOC, REV, SHA, SNAP, SCOPE): univ_rec}, _seal=UNIV_SEAL
    )
    object.__setattr__(
        univ_auth, "_source_authentication_seal", _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
    )
    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)
    # Existence record was published under a DIFFERENT revision_id than the
    # selector queries -- must fail the lineage cross-check.
    stale_rev_record = PhysicalOpeningExistenceRecord(
        record_id="op-1",
        source_observation_ids=("obs-op-1",),
        source_lineage_root_ids=("root-op-1",),
        document_id=DOC,
        revision_id="rev-stale",
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        viewport_id=VP_PLAN,
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

    def _prove(sel: ObservationSelector) -> PhysicalOpeningExistenceResult:
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence="exists",
            reason_codes=(),
            existence_record=stale_rev_record,
        )

    object.__setattr__(phys_auth, "prove_existence", _prove)
    view_prod = ViewportViewClassProducer.create()
    view_prod.publish(
        ViewportViewClassSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, viewport_id=VP_PLAN,
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
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, decision_scope_id=SCOPE,
        )
    )
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert res.record is None
    assert GENERIC_OPENING_COUNT_LINEAGE_MISMATCH in res.reason_codes


def test_same_same_distinct_three_node_contradiction_conflicts() -> None:
    """Literal 3-node inconsistency: A~B proven SAME, B~C proven SAME, but
    A~C proven DISTINCT. Real G17 record-id equality is always transitively
    consistent by construction (plain string equality), so this exact
    contradiction cannot arise from the real dependency -- this test proves
    the reconciliation code's own all-pairs check does not assume that
    regardless, using a forced mock exactly like the deleted standalone
    module's graph-consistency test did."""
    openings = (_physical("op-a"), _physical("op-b"), _physical("op-c"))
    producer, selector = _setup(openings=openings)

    from pb_physical_opening_authority import (
        PHYSICAL_OPENING_IDENTITY_RESOLVED,
        PhysicalOpeningIdentityResult,
    )

    def _inconsistent_graph(left_selector, right_selector):
        left_id = left_selector.observation_id
        right_id = right_selector.observation_id
        pair = {left_id, right_id}
        if pair == {"op-a", "op-b"} or pair == {"op-b", "op-c"}:
            proven_same = True
        else:  # {"op-a", "op-c"}
            proven_same = False
        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            physical_opening_identity="op-a" if proven_same else "distinct",
            proven_same=proven_same,
            reason_codes=(PHYSICAL_OPENING_IDENTITY_RESOLVED,),
        )

    object.__setattr__(producer._physical, "compare_identity", _inconsistent_graph)
    res = producer.publish(selector)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert res.record is None
    assert GENERIC_OPENING_COUNT_IDENTITY_CONTRADICTION in res.reason_codes


def test_incomplete_universe_abstains_despite_apparent_schedule_equality() -> None:
    """Physical count and schedule count would agree (2 == 2) if only
    completeness held -- but the universe is INCOMPLETE, so apparent
    numeric agreement must never substitute for a proven-complete universe."""
    openings = tuple(_physical(f"op-{i}") for i in range(2))
    bindings = tuple((f"op-{i}", "W1", "row-w1") for i in range(2))
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 2)},
        scope_complete=False,
    )
    sel = GenericOpeningCountSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="W1",
    )
    res = producer.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE in res.reason_codes


def test_differing_dimensions_do_not_affect_count_reconciliation() -> None:
    """Two instances of the same mark whose binding records carry different
    (independently, perhaps imprecisely parsed) width/height values must
    still reconcile purely on mark + schedule-row-observation-id identity --
    dimension fields are diagnostic on the binding record, never part of
    the count reconciliation logic."""
    op_a, op_b = _physical("op-dim-a"), _physical("op-dim-b")
    member_ids = ("op-dim-a", "op-dim-b")
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-dims",
        decision_scope_id=SCOPE,
        decision_scope_kind="viewport",
        document_id=DOC, revision_id=REV, source_sha256=SHA, snapshot_id=SNAP,
        page_ids=(PAGE,), viewport_id=VP_PLAN,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True, semantic_enumeration_complete=True,
        decision_scope_complete=True, accounted_member_ids=member_ids,
        universe_fingerprint="fp-dims", reason_codes=(),
    )
    univ_auth = OpeningUniverseCompletenessAuthority(
        {(DOC, REV, SHA, SNAP, SCOPE): univ_rec}, _seal=UNIV_SEAL
    )
    object.__setattr__(
        univ_auth, "_source_authentication_seal", _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
    )
    src_auth = SourceObservationProducer(producer_method="test", producer_version="1.0").authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)
    by_id = {op_a.record_id: op_a, op_b.record_id: op_b}

    def _prove(sel: ObservationSelector) -> PhysicalOpeningExistenceResult:
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence="exists",
            reason_codes=(),
            existence_record=by_id[sel.observation_id],
        )

    object.__setattr__(phys_auth, "prove_existence", _prove)
    view_prod = ViewportViewClassProducer.create()
    view_prod.publish(
        ViewportViewClassSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, viewport_id=VP_PLAN,
        ),
        view_kind=VIEW_KIND_FLOOR_PLAN, evidence_observation_ids=("v1",),
    )
    # Same mark, same schedule row -- but deliberately mismatched dimension
    # fields on each binding record (e.g. one leaf parsed as rough opening,
    # the other as frame size -- a real-world source of noisy dimension
    # text unrelated to count truth).
    bind_results = {}
    for op_id, w, h in (("op-dim-a", 900, 2100), ("op-dim-b", 850, 2050)):
        key = (DOC, REV, SHA, SNAP, SCOPE, op_id)
        bind_results[key] = ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("binding_resolved",),
            record=ScheduleOpeningInstanceBindingRecord(
                record_id=f"bind-{op_id}",
                document_id=DOC, revision_id=REV, source_sha256=SHA,
                snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
                opening_record_id=op_id, tag_observation_id=f"tag-{op_id}",
                tag_mark="W1", schedule_page_id=PAGE,
                schedule_row_observation_ids=("row-w1",),
                schedule_row_type_mark="W1",
                schedule_row_width_mm=w, schedule_row_height_mm=h,
                schedule_row_count=2, schedule_row_count_explicit=True,
            ),
        )
    bind_auth = ScheduleOpeningInstanceBindingAuthority(bind_results, _seal=BIND_SEAL)

    qty_prod = ScheduleRowQuantityProducer.create()
    # Both openings bind to the same row-w1 -- publish once through the
    # authority-resolved adapter (direct declared_count publication is no
    # longer accepted, see ScheduleRowQuantityProducer.publish()'s own
    # rejection of raw quantity publication).
    publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=qty_prod,
        schedule_binding_authority=bind_auth,
        binding_selector=ScheduleOpeningInstanceBindingSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, decision_scope_id=SCOPE,
            opening_record_id="op-dim-a",
        ),
    )

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        viewport_view_class_authority=view_prod.authority(),
        schedule_binding_authority=bind_auth,
        schedule_row_quantity_authority=qty_prod.authority(),
    )
    res = producer.publish(
        GenericOpeningCountSelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, decision_scope_id=SCOPE, opening_mark="W1",
        )
    )
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 2
    assert res.record.schedule_corroborated is True
