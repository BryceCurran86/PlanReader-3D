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
    universe_record_id: str = "univ-1",
    binding_record_prefix: str = "bind",
) -> tuple[GenericOpeningCountProducer, GenericOpeningCountSelector]:
    member_ids = tuple(op.record_id for op in openings)
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id=universe_record_id,
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
                record_id=f"{binding_record_prefix}-{op_id}",
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


def test_commercial_quantity_carries_complete_authority_lineage() -> None:
    openings = tuple(_physical(f"lineage-{i}") for i in range(2))
    bindings = tuple((f"lineage-{i}", "W1", "row-w1") for i in range(2))
    producer, _ = _setup(
        openings=openings,
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 2)},
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
    record = result.record
    assert record.completeness_record_id == "univ-1"
    assert set(record.schedule_binding_record_ids) == {
        "bind-lineage-0",
        "bind-lineage-1",
    }
    assert len(record.schedule_quantity_record_ids) == 1
    assert record.schedule_row_ids == ("row-w1",)

    quantity = record.quantity_evidence
    assert quantity is not None
    assert "univ-1" in quantity.evidence_ids
    assert "bind-lineage-0" in quantity.evidence_ids
    assert "bind-lineage-1" in quantity.evidence_ids
    assert "tag-lineage-0" in quantity.evidence_ids
    assert "tag-lineage-1" in quantity.evidence_ids
    assert "row-w1" in quantity.evidence_ids
    assert set(record.schedule_quantity_record_ids).issubset(
        set(quantity.evidence_ids)
    )
    assert quantity.metadata["completeness_record_id"] == "univ-1"
    assert tuple(quantity.metadata["schedule_binding_record_ids"]) == (
        record.schedule_binding_record_ids
    )
    assert tuple(quantity.metadata["schedule_quantity_record_ids"]) == (
        record.schedule_quantity_record_ids
    )


def test_completeness_record_identity_changes_commercial_record_and_quantity_ids() -> None:
    opening = _physical("lineage-completeness")
    bindings = (("lineage-completeness", "W1", "row-w1"),)

    producer_a, _ = _setup(
        openings=(opening,),
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 1)},
        universe_record_id="univ-a",
    )
    producer_b, _ = _setup(
        openings=(opening,),
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 1)},
        universe_record_id="univ-b",
    )
    selector = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="W1",
    )
    result_a = producer_a.publish(selector)
    result_b = producer_b.publish(selector)

    assert result_a.record is not None
    assert result_b.record is not None
    assert result_a.record.record_id != result_b.record.record_id
    assert result_a.record.quantity_evidence is not None
    assert result_b.record.quantity_evidence is not None
    assert (
        result_a.record.quantity_evidence.quantity_id
        != result_b.record.quantity_evidence.quantity_id
    )


def test_binding_record_identity_changes_commercial_record_and_quantity_ids() -> None:
    opening = _physical("lineage-binding")
    bindings = (("lineage-binding", "W1", "row-w1"),)

    producer_a, _ = _setup(
        openings=(opening,),
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 1)},
        binding_record_prefix="binding-a",
    )
    producer_b, _ = _setup(
        openings=(opening,),
        bindings=bindings,
        schedule_qty={("row-w1",): ("W1", 1)},
        binding_record_prefix="binding-b",
    )
    selector = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="W1",
    )
    result_a = producer_a.publish(selector)
    result_b = producer_b.publish(selector)

    assert result_a.record is not None
    assert result_b.record is not None
    assert result_a.record.schedule_binding_record_ids != (
        result_b.record.schedule_binding_record_ids
    )
    assert result_a.record.record_id != result_b.record.record_id
    assert result_a.record.quantity_evidence is not None
    assert result_b.record.quantity_evidence is not None
    assert (
        result_a.record.quantity_evidence.quantity_id
        != result_b.record.quantity_evidence.quantity_id
    )


def test_filtered_count_lineage_keeps_exclusion_bindings_but_not_other_mark_quantity() -> None:
    w1 = _physical("lineage-w1")
    d1 = _physical("lineage-d1")
    producer, _ = _setup(
        openings=(w1, d1),
        bindings=(
            ("lineage-w1", "W1", "row-w1"),
            ("lineage-d1", "D1", "row-d1"),
        ),
        schedule_qty={
            ("row-w1",): ("W1", 1),
            ("row-d1",): ("D1", 1),
        },
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
    record = result.record

    # D1's binding is material: it is the affirmative evidence that lets the
    # complete universe rule that physical opening OUT of the W1 subset.
    assert set(record.schedule_binding_record_ids) == {
        "bind-lineage-w1",
        "bind-lineage-d1",
    }
    assert set(record.schedule_row_ids) == {"row-w1", "row-d1"}

    # Only W1's schedule quantity corroborates the W1 commercial count.
    assert len(record.schedule_quantity_record_ids) == 1
    quantity = record.quantity_evidence
    assert quantity is not None
    assert quantity.metadata["schedule_corroborated"] is True
    assert "row-d1" in quantity.evidence_ids
    # The D1 row is classification evidence, not a second quantity authority:
    # only one schedule quantity record participates in this W1 result.
    assert len(quantity.metadata["schedule_quantity_record_ids"]) == 1


def test_unfiltered_physical_count_excludes_unused_schedule_binding_lineage() -> None:
    openings = (_physical("raw-a"), _physical("raw-b"))
    producer, selector = _setup(
        openings=openings,
        bindings=(
            ("raw-a", "W1", "row-w1"),
            ("raw-b", "D1", "row-d1"),
        ),
    )
    result = producer.publish(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.count == 2
    assert result.record.schedule_binding_record_ids == ()
    assert result.record.schedule_quantity_record_ids == ()
    assert result.record.schedule_row_ids == ()
    assert result.record.quantity_evidence is not None
    assert result.record.quantity_evidence.metadata["schedule_binding_record_ids"] == ()
