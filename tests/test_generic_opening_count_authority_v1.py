"""Tests for generic opening count recovery authority (Item 23 / F24)."""
import inspect
import pytest

from pb_geometry_takeoff_model import AuthorityStatus
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessRecord,
    SourceEnumerationState,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
    PhysicalOpeningExistenceResult,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_RESOLVED,
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingRecord,
    ScheduleOpeningInstanceBindingResult,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationAuthorityResult,
    SourceObservationRecord,
)

from pb_generic_opening_count_authority import (
    GENERIC_OPENING_COUNT_AMBIGUOUS,
    GENERIC_OPENING_COUNT_LINEAGE_MISMATCH,
    GENERIC_OPENING_COUNT_NON_PLAN_VIEW,
    GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES,
    GENERIC_OPENING_COUNT_RESOLVED,
    GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH,
    GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE,
    GENERIC_OPENING_COUNT_UNAVAILABLE,
    GenericOpeningCountAuthority,
    GenericOpeningCountProducer,
    GenericOpeningCountRecord,
    GenericOpeningCountResult,
    GenericOpeningCountSelector,
)

DOC = "doc-1"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
PAGE = "1"
SCOPE = "scope-plan-1"

UNIV_SEAL = object()
PHYS_SEAL = object()
BIND_SEAL = object()


def _make_physical_record(
    opening_id: str,
    *,
    page: str = PAGE,
    viewport_id: str = "view-plan",
    doc: str = DOC,
    rev: str = REV,
    sha: str = SHA,
    snap: str = SNAP,
) -> PhysicalOpeningExistenceRecord:
    return PhysicalOpeningExistenceRecord(
        record_id=opening_id,
        source_observation_ids=(f"obs-{opening_id}",),
        source_lineage_root_ids=(f"root-{opening_id}",),
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id=page,
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


def _setup_count_authorities(
    *,
    openings: tuple[PhysicalOpeningExistenceRecord, ...],
    bindings: tuple[tuple[str, str, str], ...] = (),  # (opening_id, mark, row_id)
    scope_complete: bool = True,
    schedule_counts: dict[str, int] | None = None,
    non_plan_viewports: tuple[str, ...] = (),
    doc: str = DOC,
    rev: str = REV,
    sha: str = SHA,
    snap: str = SNAP,
    scope: str = SCOPE,
    page: str = PAGE,
    univ_overrides: dict | None = None,
    ambiguous_opening_id: str | None = None,
) -> tuple[GenericOpeningCountProducer, GenericOpeningCountSelector]:
    # 1. Universe Authority
    member_ids = tuple(op.record_id for op in openings)
    univ_payload = {
        "decision_scope_id": scope,
        "decision_scope_kind": "viewport",
        "document_id": doc,
        "revision_id": rev,
        "source_sha256": sha,
        "snapshot_id": snap,
        "page_ids": (page,),
        "viewport_id": "view-plan",
        "enumeration_state": SourceEnumerationState.COMPLETE if scope_complete else SourceEnumerationState.INCOMPLETE,
        "source_decode_complete": scope_complete,
        "semantic_enumeration_complete": scope_complete,
        "decision_scope_complete": scope_complete,
        "accounted_member_ids": member_ids,
        "universe_fingerprint": "fp-1",
        "reason_codes": () if scope_complete else ("incomplete_scope",),
    }
    if univ_overrides:
        univ_payload.update(univ_overrides)
    univ_rec = OpeningUniverseCompletenessRecord(
        record_id="univ-rec-1",
        **univ_payload,
    )
    univ_key = (
        univ_rec.document_id,
        univ_rec.revision_id,
        univ_rec.source_sha256,
        univ_rec.snapshot_id,
        univ_rec.decision_scope_id,
    )

    import pb_opening_universe_completeness_authority as pb_u
    univ_auth = pb_u.OpeningUniverseCompletenessAuthority(
        {univ_key: univ_rec},
        _seal=pb_u._AUTHORITY_SEAL,
    )

    # 2. Physical Opening Authority
    from pb_source_observation_authority import SourceObservationProducer
    src_producer = SourceObservationProducer(producer_method="test", producer_version="1.0")
    src_auth = src_producer.authority()
    phys_auth = PhysicalOpeningAuthority(src_auth)

    physical_by_id = {op.record_id: op for op in openings}

    def _custom_prove_existence(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        rec = physical_by_id.get(selector.observation_id)
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

    object.__setattr__(phys_auth, "prove_existence", _custom_prove_existence)

    # 3. Schedule Binding Authority
    import pb_schedule_opening_instance_binding_authority as pb_b
    binding_map: dict[str, tuple[str, str]] = {op_id: (mark, row_id) for op_id, mark, row_id in bindings}

    bind_results = {}
    if ambiguous_opening_id is not None:
        b_key = (doc, rev, sha, snap, scope, ambiguous_opening_id)
        bind_results[b_key] = pb_b.ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=("ambiguous_schedule_rows",),
            record=None,
        )
    for op_id, (mark, row_id) in binding_map.items():
        if ambiguous_opening_id is not None and op_id == ambiguous_opening_id:
            continue
        rec = pb_b.ScheduleOpeningInstanceBindingRecord(
            record_id=f"bind-{op_id}",
            document_id=doc,
            revision_id=rev,
            source_sha256=sha,
            snapshot_id=snap,
            page_id=page,
            decision_scope_id=scope,
            opening_record_id=op_id,
            tag_observation_id="tag-1",
            tag_mark=mark,
            schedule_page_id=page,
            schedule_row_observation_ids=(row_id,),
            schedule_row_type_mark=mark,
            schedule_row_width_mm=900,
            schedule_row_height_mm=2100,
        )
        res = pb_b.ScheduleOpeningInstanceBindingResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(pb_b.BINDING_RESOLVED,),
            record=rec,
        )
        b_key = (doc, rev, sha, snap, scope, op_id)
        bind_results[b_key] = res

    bind_auth = pb_b.ScheduleOpeningInstanceBindingAuthority(
        bind_results,
        _seal=pb_b._AUTHORITY_SEAL,
    )

    producer = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=univ_auth,
        physical_opening_authority=phys_auth,
        schedule_binding_authority=bind_auth,
        schedule_declared_counts=schedule_counts,
        non_plan_viewport_ids=non_plan_viewports,
    )
    sel = GenericOpeningCountSelector(
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        decision_scope_id=scope,
    )
    return producer, sel


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_physical_opening_instance_identity_preserved() -> None:
    """Distinct physical openings are preserved and counted by instance identity."""
    op1 = _make_physical_record("op-1")
    op2 = _make_physical_record("op-2")
    op3 = _make_physical_record("op-3")
    producer, sel = _setup_count_authorities(openings=(op1, op2, op3))

    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 3
    assert res.record.physical_instance_record_ids == ("op-1", "op-2", "op-3")


def test_duplicate_observations_of_same_opening_count_once() -> None:
    """Duplicate observations of the same opening instance are deduplicated to count once."""
    op1 = _make_physical_record("op-1")
    # Same physical opening record passed twice in universe
    producer, sel = _setup_count_authorities(openings=(op1, op1))

    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 1
    assert res.record.physical_instance_record_ids == ("op-1",)


def test_distinct_equal_size_openings_count_separately() -> None:
    """Two openings with identical dimensions but distinct IDs count separately."""
    op1 = _make_physical_record("door-north")
    op2 = _make_physical_record("door-south")
    producer, sel = _setup_count_authorities(
        openings=(op1, op2),
        bindings=(("door-north", "D1", "row-D1"), ("door-south", "D1", "row-D1")),
    )

    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 2
    assert set(res.record.physical_instance_record_ids) == {"door-north", "door-south"}


def test_schedule_row_cannot_manufacture_physical_instance() -> None:
    """Schedule marks or rows alone cannot fabricate physical instances."""
    # Case 1: Schedule claims Qty 5, but plan has 0 instances -> CONFLICT mismatch
    producer, sel = _setup_count_authorities(
        openings=(),
        schedule_counts={"D1": 5},
    )
    d1_sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="D1",
    )
    res = producer.publish(d1_sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH in res.reason_codes
    assert res.record is None

    # Case 2: Schedule has no count, but 0 plan instances exist for mark -> ABSTAINED
    producer2, sel2 = _setup_count_authorities(
        openings=(),
        schedule_counts=None,
    )
    res2 = producer2.publish(d1_sel)
    assert res2.status == EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_NO_PHYSICAL_INSTANCES in res2.reason_codes
    assert res2.record is None


def test_plan_and_schedule_corroborate_matching_count() -> None:
    """Plan instances and schedule declared counts corroborate when they match."""
    op1 = _make_physical_record("op-1")
    op2 = _make_physical_record("op-2")
    producer, _ = _setup_count_authorities(
        openings=(op1, op2),
        bindings=(("op-1", "D1", "row-1"), ("op-2", "D1", "row-1")),
        schedule_counts={"D1": 2},
    )
    d1_sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="D1",
    )
    res = producer.publish(d1_sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.count == 2
    assert res.record.schedule_corroborated is True


def test_plan_and_schedule_count_mismatch_fails_closed() -> None:
    """Count mismatch between schedule Qty and plan instances fails closed with CONFLICT."""
    op1 = _make_physical_record("op-1")
    op2 = _make_physical_record("op-2")
    op3 = _make_physical_record("op-3")
    producer, _ = _setup_count_authorities(
        openings=(op1, op2, op3),
        bindings=(
            ("op-1", "D1", "row-1"),
            ("op-2", "D1", "row-1"),
            ("op-3", "D1", "row-1"),
        ),
        schedule_counts={"D1": 2},  # Schedule says 2, but plan has 3!
    )
    d1_sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_mark="D1",
    )
    res = producer.publish(d1_sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_SCHEDULE_MISMATCH in res.reason_codes
    assert res.record is None


def test_non_plan_view_elevation_or_detail_fails_closed() -> None:
    """Openings situated in non-plan viewports (elevations, details) are excluded."""
    op_elev = _make_physical_record("op-elev", viewport_id="view-elevation")
    producer, sel = _setup_count_authorities(
        openings=(op_elev,),
        non_plan_viewports=("view-elevation",),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_NON_PLAN_VIEW in res.reason_codes
    assert res.record is None


def test_ambiguous_mark_or_binding_fails_closed() -> None:
    """Ambiguous schedule row or tag binding fails closed with CONFLICT."""
    op1 = _make_physical_record("op-1")
    producer, sel = _setup_count_authorities(
        openings=(op1,),
        ambiguous_opening_id="op-1",
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_AMBIGUOUS in res.reason_codes
    assert res.record is None


def test_stale_revision_fails_closed() -> None:
    """Stale revision across participating records returns CONFLICT."""
    op_old = _make_physical_record("op-1", rev="rev-old")
    producer, sel = _setup_count_authorities(openings=(op_old,), rev="rev-current")
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_LINEAGE_MISMATCH in res.reason_codes
    assert res.record is None


def test_stale_source_sha_fails_closed() -> None:
    """Stale source SHA returns CONFLICT."""
    op_old = _make_physical_record("op-1", sha="b" * 64)
    producer, sel = _setup_count_authorities(openings=(op_old,), sha="a" * 64)
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert GENERIC_OPENING_COUNT_LINEAGE_MISMATCH in res.reason_codes
    assert res.record is None


def test_incomplete_opening_universe_fails_closed() -> None:
    """Incomplete opening universe fails closed with ABSTAINED."""
    op1 = _make_physical_record("op-1")
    producer, sel = _setup_count_authorities(openings=(op1,), scope_complete=False)
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert GENERIC_OPENING_COUNT_SCOPE_INCOMPLETE in res.reason_codes
    assert res.record is None


def test_family_filtering_doors_vs_windows() -> None:
    """Family filtering partitions doors from windows accurately."""
    door1 = _make_physical_record("d-1")
    door2 = _make_physical_record("d-2")
    win1 = _make_physical_record("w-1")
    producer, _ = _setup_count_authorities(
        openings=(door1, door2, win1),
        bindings=(
            ("d-1", "D1", "row-d1"),
            ("d-2", "D2", "row-d2"),
            ("w-1", "W1", "row-w1"),
        ),
    )
    door_sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_family="door",
    )
    door_res = producer.publish(door_sel)
    assert door_res.status == EvidenceResolutionStatus.CORROBORATED
    assert door_res.record is not None
    assert door_res.record.count == 2
    assert door_res.record.physical_instance_record_ids == ("d-1", "d-2")

    win_sel = GenericOpeningCountSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_family="window",
    )
    win_res = producer.publish(win_sel)
    assert win_res.status == EvidenceResolutionStatus.CORROBORATED
    assert win_res.record is not None
    assert win_res.record.count == 1
    assert win_res.record.physical_instance_record_ids == ("w-1",)


def test_quantity_evidence_emission_ea() -> None:
    """Verified count emits QuantityEvidence with unit 'ea' and FIRM status."""
    op1 = _make_physical_record("op-1")
    producer, sel = _setup_count_authorities(openings=(op1,))
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    qty = res.record.quantity_evidence
    assert qty is not None
    assert qty.unit == "ea"
    assert qty.value == 1.0
    assert qty.family == "opening_count"
    assert qty.status == AuthorityStatus.FIRM.value
    assert qty.abstained is False


def test_selector_is_address_only_no_caller_counts() -> None:
    """Selector accepts only addressing keys, never caller counts or candidates."""
    params = inspect.signature(GenericOpeningCountSelector).parameters
    assert "document_id" in params
    assert "decision_scope_id" in params
    for forbidden in ("count", "candidates", "instances", "openings", "confidence", "total"):
        assert forbidden not in params


def test_producer_sealed_cannot_instantiate_raw() -> None:
    """GenericOpeningCountProducer cannot be constructed without internal seal."""
    with pytest.raises(TypeError, match="must be obtained from from_authorities"):
        GenericOpeningCountProducer(None, None)  # type: ignore[arg-type]


def test_authority_resolver_is_selector_only() -> None:
    """GenericOpeningCountAuthority.resolve only accepts GenericOpeningCountSelector."""
    with pytest.raises(TypeError, match="producer-owned"):
        GenericOpeningCountAuthority({}, _seal=object())  # Raw seal rejected
    # Test valid construction via producer
    producer, sel = _setup_count_authorities(openings=())
    pub_auth = producer.authority()
    with pytest.raises(TypeError, match="selector must be GenericOpeningCountSelector"):
        pub_auth.resolve(object())  # type: ignore[arg-type]
