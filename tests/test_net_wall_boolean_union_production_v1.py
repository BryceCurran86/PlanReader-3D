"""Comprehensive production test suite for Net-wall Boolean Union Authority.

Covers all 21 production scenarios plus geometry layer regressions:
1. one gross wall, no openings
2. one applicable opening
3. two distinct openings
4. overlapping openings (overlap deducted once)
5. duplicate observations of same physical opening
6. distinct equal-size openings
7. wrong-wall opening (ignored)
8. non-applicable opening (not deducted)
9. unresolved applicability (fail closed)
10. mixed coordinate frames (fail closed)
11. mismatched physical wall IDs (fail closed)
12. incomplete opening universe (fail closed)
13. incomplete wall evidence (fail closed)
14. missing vertical evidence (fail closed)
15. mismatched source/revision/viewport (fail closed)
16. caller-forged authenticity (fail closed)
17. stale snapshot/fingerprint (fail closed)
18. opening partially outside wall (fail closed)
19. opening completely outside wall (fail closed)
20. empty union (gross wall preserved)
21. deterministic replay (stable IDs)
"""
from __future__ import annotations

import inspect
import pytest
from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_gross_wall_geometry_authority import (
    GROSS_WALL_GEOMETRY_RESOLVED,
    GrossWallGeometryAuthority,
    GrossWallGeometryProducer,
    GrossWallGeometryRecord,
    GrossWallGeometryResult,
    GrossWallGeometrySelector,
    _AUTHORITY_SEAL as GROSS_SEAL,
)
from pb_physical_opening_void_authority import (
    PHYSICAL_OPENING_VOID_RESOLVED,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidRecord,
    PhysicalOpeningVoidResult,
    PhysicalOpeningVoidSelector,
    _AUTHORITY_SEAL as VOID_SEAL,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessRecord,
    OpeningUniverseCompletenessResult,
    OpeningUniverseSelector,
    _AUTHORITY_SEAL as UNIV_SEAL,
)
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,
)
from pb_opening_deduction_authority import (
    OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED,
    OPENING_DEDUCTION_AUTHORIZED,
    OpeningDeductionAuthority,
    OpeningDeductionRecord,
    OpeningDeductionResult,
    OpeningDeductionSelector,
    _AUTHORITY_SEAL as DED_SEAL,
)
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE,
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NET_WALL_BOOLEAN_UNION_UPSTREAM_UNAVAILABLE,
    NET_WALL_DEDUCTION_UNRESOLVED,
    NET_WALL_FRAME_MISMATCH,
    NET_WALL_GROSS_UNRESOLVED,
    NET_WALL_LINEAGE_MISMATCH,
    NET_WALL_OPENING_UNIVERSE_INCOMPLETE,
    NET_WALL_VOID_UNRESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionProducer,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionResult,
    NetWallBooleanUnionSelector,
    _AUTHORITY_SEAL as NET_WALL_SEAL,
    deterministic_net_wall_record_id,
    subtract_void_union_from_wall_polygon,
    union_wall_local_void_polygons,
)


DOC = "doc-1"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
PAGE = "page-1"
SCOPE = "scope-1"
WALL = "wall-1"
TRADE = "plaster-paint"
FRAME = "whole-wall-frame-1"


def _selector(**overrides) -> NetWallBooleanUnionSelector:
    kwargs = dict(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=WALL,
        trade_scope_id=TRADE,
    )
    kwargs.update(overrides)
    return NetWallBooleanUnionSelector(**kwargs)


def _gross_record(*, wall_id: str = WALL, length: float = 10.0, height: float = 3.0, frame_id: str = FRAME, **overrides) -> GrossWallGeometryRecord:
    doc = overrides.get("document_id", DOC)
    rev = overrides.get("revision_id", REV)
    sha = overrides.get("source_sha256", SHA)
    snap = overrides.get("snapshot_id", SNAP)
    page = overrides.get("page_id", PAGE)
    scope = overrides.get("decision_scope_id", SCOPE)
    poly = box(0.0, 0.0, length, height)
    payload = {
        "document_id": doc,
        "revision_id": rev,
        "source_sha256": sha,
        "snapshot_id": snap,
        "page_id": page,
        "decision_scope_id": scope,
        "physical_wall_id": wall_id,
        "wall_local_frame_id": frame_id,
        "length_m": length,
        "height_m": height,
        "gross_area_m2": round(length * height, 12),
        "polygon_wkb_hex": poly.wkb_hex,
    }
    rec_id = stable_contract_id("gross_wall_geom", payload)
    return GrossWallGeometryRecord(record_id=rec_id, **payload)


def _universe_record(*, member_ids: tuple[str, ...] = (), complete: bool = True, **overrides) -> OpeningUniverseCompletenessRecord:
    doc = overrides.get("document_id", DOC)
    rev = overrides.get("revision_id", REV)
    sha = overrides.get("source_sha256", SHA)
    snap = overrides.get("snapshot_id", SNAP)
    page = overrides.get("page_id", PAGE)
    scope = overrides.get("decision_scope_id", SCOPE)
    payload = {
        "decision_scope_id": scope,
        "decision_scope_kind": "full_page",
        "document_id": doc,
        "revision_id": rev,
        "source_sha256": sha,
        "snapshot_id": snap,
        "page_ids": (page,),
        "viewport_id": None,
        "enumeration_state": "complete" if complete else "incomplete",
        "source_decode_complete": complete,
        "semantic_enumeration_complete": complete,
        "decision_scope_complete": complete,
        "accounted_member_ids": member_ids,
        "universe_fingerprint": "fp-1",
        "reason_codes": () if complete else ("incomplete_scope",),
    }
    rec_id = stable_contract_id("univ_record", payload)
    return OpeningUniverseCompletenessRecord(record_id=rec_id, **payload)


def _void_record(
    opening_id: str,
    *,
    wall_id: str = WALL,
    frame_id: str = FRAME,
    u0: float = 1.0,
    u1: float = 2.0,
    z0: float = 0.0,
    z1: float = 2.0,
    **overrides,
) -> PhysicalOpeningVoidRecord:
    doc = overrides.get("document_id", DOC)
    rev = overrides.get("revision_id", REV)
    sha = overrides.get("source_sha256", SHA)
    snap = overrides.get("snapshot_id", SNAP)
    page = overrides.get("page_id", PAGE)
    scope = overrides.get("decision_scope_id", SCOPE)
    payload = {
        "document_id": doc,
        "revision_id": rev,
        "source_sha256": sha,
        "snapshot_id": snap,
        "page_id": page,
        "viewport_id": None,
        "decision_scope_id": scope,
        "opening_identity_id": opening_id,
        "host_binding_record_id": f"host-{opening_id}",
        "host_wall_id": wall_id,
        "opening_universe_record_id": "univ-1",
        "width_record_id": f"width-{opening_id}",
        "height_record_id": f"height-{opening_id}",
        "wall_local_frame_id": frame_id,
        "unit_mapping_record_id": "scale-1",
        "vertical_placement_record_id": f"vert-{opening_id}",
        "profile_kind": "rectangular_rough_opening",
        "coordinate_unit": "metre",
        "u0": u0,
        "u1": u1,
        "z0": z0,
        "z1": z1,
    }
    rec_id = stable_contract_id("void_record", payload)
    return PhysicalOpeningVoidRecord(record_id=rec_id, **payload)


def _deduction_record(
    opening_id: str,
    *,
    trade_id: str = TRADE,
    **overrides,
) -> OpeningDeductionRecord:
    doc = overrides.get("document_id", DOC)
    rev = overrides.get("revision_id", REV)
    sha = overrides.get("source_sha256", SHA)
    snap = overrides.get("snapshot_id", SNAP)
    page = overrides.get("page_id", PAGE)
    scope = overrides.get("decision_scope_id", SCOPE)
    payload = {
        "document_id": doc,
        "revision_id": rev,
        "source_sha256": sha,
        "snapshot_id": snap,
        "page_id": page,
        "decision_scope_id": scope,
        "opening_identity_id": opening_id,
        "host_binding_record_id": f"host-{opening_id}",
        "physical_void_record_id": f"void-{opening_id}",
        "opening_universe_record_id": "univ-1",
        "target_scope_id": trade_id,
        "applicability_record_id": f"app-{opening_id}",
    }
    rec_id = stable_contract_id("ded_record", payload)
    return OpeningDeductionRecord(record_id=rec_id, **payload)


def _setup_pipeline(
    *,
    gross: GrossWallGeometryRecord | None = None,
    universe: OpeningUniverseCompletenessRecord | None = None,
    voids: tuple[PhysicalOpeningVoidRecord, ...] = (),
    deductions: tuple[tuple[str, OpeningDeductionResult], ...] = (),
) -> tuple[NetWallBooleanUnionProducer, NetWallBooleanUnionSelector]:
    sel = _selector()
    if gross is None:
        gross = _gross_record()
    if universe is None:
        member_ids = tuple(v.opening_identity_id for v in voids)
        universe = _universe_record(member_ids=member_ids)

    gross_results = {
        GrossWallGeometrySelector(
            document_id=sel.document_id,
            revision_id=sel.revision_id,
            source_sha256=sel.source_sha256,
            snapshot_id=sel.snapshot_id,
            page_id=sel.page_id,
            decision_scope_id=sel.decision_scope_id,
            physical_wall_id=sel.physical_wall_id,
        ).key: GrossWallGeometryResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(GROSS_WALL_GEOMETRY_RESOLVED,),
            record=gross,
        )
    }
    gross_auth = GrossWallGeometryAuthority(gross_results, _seal=GROSS_SEAL)

    univ_key = (
        universe.document_id,
        universe.revision_id,
        universe.source_sha256,
        universe.snapshot_id,
        universe.decision_scope_id,
    )
    univ_records = {univ_key: universe}
    univ_auth = OpeningUniverseCompletenessAuthority(univ_records, _seal=UNIV_SEAL)

    void_results = {}
    for v in voids:
        v_sel = PhysicalOpeningVoidSelector(
            document_id=v.document_id,
            revision_id=v.revision_id,
            source_sha256=v.source_sha256,
            snapshot_id=v.snapshot_id,
            page_id=v.page_id,
            decision_scope_id=v.decision_scope_id,
            opening_identity_id=v.opening_identity_id,
        )
        void_results[v_sel.key] = PhysicalOpeningVoidResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=frozenset([PHYSICAL_OPENING_VOID_RESOLVED]),
            record=v,
        )
    void_auth = PhysicalOpeningVoidAuthority(void_results, _seal=VOID_SEAL)

    ded_results = {}
    for op_id, res in deductions:
        d_sel = OpeningDeductionSelector(
            document_id=sel.document_id,
            revision_id=sel.revision_id,
            source_sha256=sel.source_sha256,
            snapshot_id=sel.snapshot_id,
            page_id=sel.page_id,
            decision_scope_id=sel.decision_scope_id,
            opening_identity_id=op_id,
            target_scope_id=sel.trade_scope_id,
        )
        ded_results[d_sel.key] = res
    ded_auth = OpeningDeductionAuthority(ded_results, _seal=DED_SEAL)

    producer = NetWallBooleanUnionProducer.from_authorities(
        physical_void_authority=void_auth,
        opening_deduction_authority=ded_auth,
        opening_universe_authority=univ_auth,
        gross_wall_authority=gross_auth,
    )
    return producer, sel


# ---------------------------------------------------------------------------
# SCENARIOS 1-21
# ---------------------------------------------------------------------------

def test_scenario_01_one_gross_wall_no_openings() -> None:
    producer, sel = _setup_pipeline(gross=_gross_record(length=10.0, height=3.0))
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.gross_area_m2 == pytest.approx(30.0)
    assert res.record.void_union_area_m2 == pytest.approx(0.0)
    assert res.record.net_area_m2 == pytest.approx(30.0)
    assert NET_WALL_BOOLEAN_UNION_RESOLVED in res.reason_codes


def test_scenario_02_one_applicable_opening() -> None:
    v = _void_record("op-1", u0=1.0, u1=2.0, z0=0.0, z1=2.0)  # 1m x 2m = 2 m2
    ded_rec = _deduction_record("op-1")
    ded_res = OpeningDeductionResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(OPENING_DEDUCTION_AUTHORIZED,),
        record=ded_rec,
    )
    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v,),
        deductions=(("op-1", ded_res),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.gross_area_m2 == pytest.approx(30.0)
    assert res.record.void_union_area_m2 == pytest.approx(2.0)
    assert res.record.net_area_m2 == pytest.approx(28.0)


def test_scenario_03_two_distinct_openings() -> None:
    v1 = _void_record("op-1", u0=1.0, u1=2.0, z0=0.0, z1=2.0)  # 2 m2
    v2 = _void_record("op-2", u0=5.0, u1=7.0, z0=0.0, z1=2.0)  # 4 m2
    d1 = _deduction_record("op-1")
    d2 = _deduction_record("op-2")
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), d1)
    res2 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), d2)

    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1, v2),
        deductions=(("op-1", res1), ("op-2", res2)),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.void_union_area_m2 == pytest.approx(6.0)
    assert res.record.net_area_m2 == pytest.approx(24.0)


def test_scenario_04_overlapping_openings_overlap_deducted_once() -> None:
    # v1: [1, 4] x [0, 2] -> area 6 m2
    # v2: [3, 6] x [0, 2] -> area 6 m2
    # Overlap is [3, 4] x [0, 2] -> area 2 m2
    # Union area is 10 m2 (never scalar sum of 12 m2!)
    v1 = _void_record("op-1", u0=1.0, u1=4.0, z0=0.0, z1=2.0)
    v2 = _void_record("op-2", u0=3.0, u1=6.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))
    res2 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-2"))

    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1, v2),
        deductions=(("op-1", res1), ("op-2", res2)),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.void_union_area_m2 == pytest.approx(10.0)
    assert res.record.net_area_m2 == pytest.approx(20.0)


def test_scenario_05_duplicate_observations_of_same_physical_opening() -> None:
    # Same opening_identity_id "op-1" reported twice
    v1 = _void_record("op-1", u0=1.0, u1=3.0, z0=0.0, z1=2.0)
    v2 = _void_record("op-1", u0=1.0, u1=3.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))

    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1, v2),
        deductions=(("op-1", res1),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.void_union_area_m2 == pytest.approx(4.0)
    assert res.record.net_area_m2 == pytest.approx(26.0)
    assert len(res.record.physical_void_record_ids) == 1


def test_scenario_06_distinct_equal_size_openings() -> None:
    # Two distinct openings with same size: both must be retained
    v1 = _void_record("op-1", u0=1.0, u1=2.0, z0=0.0, z1=2.0)
    v2 = _void_record("op-2", u0=4.0, u1=5.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))
    res2 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-2"))

    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1, v2),
        deductions=(("op-1", res1), ("op-2", res2)),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.void_union_area_m2 == pytest.approx(4.0)
    assert res.record.net_area_m2 == pytest.approx(26.0)
    assert len(res.record.physical_void_record_ids) == 2


def test_scenario_07_wrong_wall_opening_ignored() -> None:
    # Opening v2 belongs to WALL-2; target wall is WALL-1
    v1 = _void_record("op-1", wall_id=WALL, u0=1.0, u1=2.0, z0=0.0, z1=2.0)
    v2 = _void_record("op-2", wall_id="wall-2", u0=4.0, u1=5.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))
    res2 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-2"))

    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1, v2),
        deductions=(("op-1", res1), ("op-2", res2)),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.void_union_area_m2 == pytest.approx(2.0)
    assert res.record.net_area_m2 == pytest.approx(28.0)


def test_scenario_08_non_applicable_opening_not_deducted() -> None:
    # Opening op-1 is on this wall, but applicability authority reports trade scope mismatch
    v1 = _void_record("op-1", u0=1.0, u1=2.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(
        EvidenceResolutionStatus.ABSTAINED,
        (OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,),
        None,
    )
    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.void_union_area_m2 == pytest.approx(0.0)
    assert res.record.net_area_m2 == pytest.approx(30.0)


def test_scenario_09_unresolved_applicability_fails_closed() -> None:
    # Opening op-1 is on this wall, but applicability is completely unresolved
    v1 = _void_record("op-1", u0=1.0, u1=2.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(
        EvidenceResolutionStatus.ABSTAINED,
        (OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED,),
        None,
    )
    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert NET_WALL_DEDUCTION_UNRESOLVED in res.reason_codes
    assert res.record is not None
    assert res.record.net_area_m2 is None  # Net area blocked!
    assert res.record.gross_area_m2 == pytest.approx(30.0)  # Gross area preserved!


def test_scenario_10_mixed_coordinate_frames_fails_closed() -> None:
    # Opening void has different wall_local_frame_id than gross wall
    v1 = _void_record("op-1", frame_id="wrong-frame", u0=1.0, u1=2.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))

    producer, sel = _setup_pipeline(
        gross=_gross_record(frame_id=FRAME),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert NET_WALL_FRAME_MISMATCH in res.reason_codes
    assert res.record is not None
    assert res.record.net_area_m2 is None


def test_scenario_11_mismatched_physical_wall_ids_fails_closed() -> None:
    # Gross wall is recorded for wall-2, but selector queries wall-1
    producer, sel = _setup_pipeline(gross=_gross_record(wall_id="wall-2"))
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert NET_WALL_GROSS_UNRESOLVED in res.reason_codes


def test_scenario_12_incomplete_opening_universe_fails_closed() -> None:
    universe = _universe_record(complete=False)
    producer, sel = _setup_pipeline(universe=universe)
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert NET_WALL_OPENING_UNIVERSE_INCOMPLETE in res.reason_codes
    assert res.record is not None
    assert res.record.net_area_m2 is None
    assert res.record.gross_area_m2 == pytest.approx(30.0)


def test_scenario_13_incomplete_wall_evidence_fails_closed() -> None:
    gross_results = {}  # Empty gross wall authority
    gross_auth = GrossWallGeometryAuthority(gross_results, _seal=GROSS_SEAL)
    _, sel = _setup_pipeline()
    producer = NetWallBooleanUnionProducer.from_authorities(
        physical_void_authority=PhysicalOpeningVoidAuthority({}, _seal=VOID_SEAL),
        opening_deduction_authority=OpeningDeductionAuthority({}, _seal=DED_SEAL),
        opening_universe_authority=OpeningUniverseCompletenessAuthority({}, _seal=UNIV_SEAL),
        gross_wall_authority=gross_auth,
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert NET_WALL_GROSS_UNRESOLVED in res.reason_codes


def test_scenario_14_missing_vertical_evidence_fails_closed() -> None:
    # Gross wall geometry producer rejects invalid/non-positive height
    producer_geom = GrossWallGeometryProducer.create()
    g_sel = GrossWallGeometrySelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        physical_wall_id=WALL,
    )
    res = producer_geom.register_geometry(
        selector=g_sel,
        wall_local_frame_id=FRAME,
        length_m=10.0,
        height_m=-1.0,  # Invalid vertical extent
    )
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert res.record is None


def test_scenario_15_mismatched_source_revision_fails_closed() -> None:
    # Gross record has revision rev-999 while selector has rev-1
    gross = _gross_record(revision_id="rev-999")
    producer, sel = _setup_pipeline(gross=gross)
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert NET_WALL_LINEAGE_MISMATCH in res.reason_codes


def test_scenario_16_caller_forged_authenticity_fails_closed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        NetWallBooleanUnionAuthority({})
    with pytest.raises(TypeError, match="must be obtained from from_authorities"):
        NetWallBooleanUnionProducer(None, None, None, None)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="instance required"):
        NetWallBooleanUnionProducer.from_authorities(object(), object(), object(), object())

    producer, _ = _setup_pipeline()
    with pytest.raises(TypeError, match="selector must be NetWallBooleanUnionSelector"):
        producer.publish(object())  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="selector must be NetWallBooleanUnionSelector"):
        producer.authority().resolve(object())  # type: ignore[arg-type]


def test_scenario_17_stale_snapshot_fingerprint_fails_closed() -> None:
    gross = _gross_record(snapshot_id="stale-snap")
    producer, sel = _setup_pipeline(gross=gross)
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert NET_WALL_LINEAGE_MISMATCH in res.reason_codes


def test_scenario_18_opening_partially_outside_wall_fails_closed() -> None:
    # Gross wall length is 10m; opening u1 is 11m (extends beyond wall end)
    v1 = _void_record("op-1", u0=9.0, u1=11.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))
    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert NET_WALL_VOID_UNRESOLVED in res.reason_codes


def test_scenario_19_opening_completely_outside_wall_fails_closed() -> None:
    # Gross wall length is 10m; opening is at u in [15, 17]
    v1 = _void_record("op-1", u0=15.0, u1=17.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))
    producer, sel = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CONFLICT
    assert NET_WALL_VOID_UNRESOLVED in res.reason_codes


def test_scenario_20_empty_union_gross_wall_preserved() -> None:
    # Empty universe / no applicable voids: gross wall geometry is fully preserved
    producer, sel = _setup_pipeline(gross=_gross_record(length=12.0, height=2.5))
    res = producer.publish(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.gross_area_m2 == pytest.approx(30.0)
    assert res.record.void_union_area_m2 == pytest.approx(0.0)
    assert res.record.net_area_m2 == pytest.approx(30.0)


def test_scenario_21_deterministic_replay_stable_ids() -> None:
    v1 = _void_record("op-1", u0=1.0, u1=3.0, z0=0.0, z1=2.0)
    res1 = OpeningDeductionResult(EvidenceResolutionStatus.CORROBORATED, (OPENING_DEDUCTION_AUTHORIZED,), _deduction_record("op-1"))
    producer1, sel1 = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    producer2, sel2 = _setup_pipeline(
        gross=_gross_record(length=10.0, height=3.0),
        voids=(v1,),
        deductions=(("op-1", res1),),
    )
    r1 = producer1.publish(sel1)
    r2 = producer2.publish(sel2)
    assert r1.status == r2.status
    assert r1.record is not None and r2.record is not None
    assert r1.record.record_id == r2.record.record_id
    assert r1.record.union_geometry_id == r2.record.union_geometry_id
    assert r1.record.net_area_m2 == r2.record.net_area_m2


# ---------------------------------------------------------------------------
# PR 433 GEOMETRY LAYER & SEALED REGRESSIONS
# ---------------------------------------------------------------------------

def test_geometry_union_deduplicates_overlap_geometrically() -> None:
    left = box(0, 0, 2, 2)
    right = box(1, 0, 3, 2)
    merged = union_wall_local_void_polygons((left, right))
    assert merged.area == pytest.approx(6.0)


def test_subtraction_uses_union_not_scalar_sum() -> None:
    gross = box(0, 0, 10, 3)
    first = box(2, 0, 4, 2)
    second = box(3, 1, 5, 3)
    assert subtract_void_union_from_wall_polygon(gross, (first, second)).area == pytest.approx(23.0)


def test_geometry_rejects_invalid_input() -> None:
    with pytest.raises(ValueError):
        subtract_void_union_from_wall_polygon(None, ())  # type: ignore[arg-type]


def test_public_resolver_is_selector_only() -> None:
    assert tuple(inspect.signature(NetWallBooleanUnionAuthority.resolve).parameters) == ("self", "selector")
    selector_fields = tuple(inspect.signature(NetWallBooleanUnionSelector).parameters)
    assert "physical_wall_id" in selector_fields
    for forbidden in ("polygon", "voids", "void_areas", "complete", "nearest", "radius", "confidence", "net_area"):
        assert not any(forbidden in field for field in selector_fields)


def test_from_authorities_has_no_raw_geometry_or_self_certification_inputs() -> None:
    params = tuple(inspect.signature(NetWallBooleanUnionProducer.from_authorities).parameters)
    for forbidden in (
        "gross_polygon",
        "void_polygons",
        "void_areas",
        "opening_ids",
        "deductible",
        "claimed_complete",
        "candidate_wall_ids",
        "nearest_wall_id",
    ):
        assert forbidden not in params


def test_missing_selector_record_abstains_not_zero() -> None:
    auth = NetWallBooleanUnionAuthority({}, _seal=NET_WALL_SEAL)  # Using valid seal
    res = auth.resolve(_selector())
    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE in res.reason_codes


def test_record_id_is_deterministic_addressing_only() -> None:
    selector = _selector()
    first = deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-1",
        opening_deduction_record_ids=("d2", "d1"),
        physical_void_record_ids=("v2", "v1"),
    )
    second = deterministic_net_wall_record_id(
        selector,
        gross_wall_record_id="gross-1",
        opening_deduction_record_ids=("d1", "d2"),
        physical_void_record_ids=("v1", "v2"),
    )
    assert first == second
