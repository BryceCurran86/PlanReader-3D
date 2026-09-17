"""Production + adversarial tests for pb_cross_sheet_registration_authority (Item 32).

Tests cover:
  - Happy-path plan <-> elevation and plan <-> section registration from candidate scope authorities
  - Element missing on source page fails closed (ABSTAINED with CROSS_SHEET_SOURCE_PAGE_UNRESOLVED)
  - Element missing on target page fails closed (ABSTAINED with CROSS_SHEET_TARGET_PAGE_UNRESOLVED)
  - Sealed authority constructor
  - Sealed producer constructor
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import MeasurementAuthorityType, WallCandidate
from pb_cross_sheet_registration_authority import (
    CROSS_SHEET_RECORD_UNAVAILABLE,
    CROSS_SHEET_RESOLVED,
    CROSS_SHEET_SOURCE_PAGE_UNRESOLVED,
    CROSS_SHEET_TARGET_PAGE_UNRESOLVED,
    CROSS_SHEET_UNRESOLVED,
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationProducer,
    CrossSheetRegistrationRecord,
    CrossSheetRegistrationResult,
    CrossSheetRegistrationSelector,
)

DOC = "doc-cross-test"
REV = "R1"
SHA = "c" * 64
SNAP = "snap-cross-1"
SRC_PAGE = "page-A101"
TGT_PAGE = "page-A201"
ELEM = "wall-PHYS-32"


def _selector(
    elem_id: str = ELEM,
    src_page: str = SRC_PAGE,
    tgt_page: str = TGT_PAGE,
) -> CrossSheetRegistrationSelector:
    return CrossSheetRegistrationSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        source_page_id=src_page,
        target_page_id=tgt_page,
        physical_element_id=elem_id,
    )


def _make_candidate(
    candidate_id: str,
    viewport_id: str = "vp-1",
) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="double_line",
        centerline_pts=((0.0, 0.0), (100.0, 0.0)),
        face_a_segment_ids=("seg-a",),
        face_b_segment_ids=("seg-b",),
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.11,
        thickness_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=("free_end", "free_end"),
        interior_exterior="exterior",
        level_id="L1",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _setup_candidate_authority(
    src_elements: tuple[str, ...] = (ELEM,),
    tgt_elements: tuple[str, ...] = (ELEM,),
):
    scopes = {}

    # Source page scope
    src_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=SRC_PAGE, decision_scope_id=f"wall-source:page-{SRC_PAGE}",
    )
    src_recs = [
        PhysicalWallCandidateRecord(
            wall_candidate_id=eid,
            wall_candidate=_make_candidate(eid, viewport_id="vp-src"),
            physical_identity=PhysicalWallIdentity(
                wall_candidate_id=eid, viewport_id="vp-src", candidate_identity_id=None,
                path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        )
        for eid in src_elements
    ]
    scopes[src_key] = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
        records=tuple(src_recs), source_observation_ids=(), document_id=DOC,
        revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=SRC_PAGE,
        decision_scope_id=f"wall-source:page-{SRC_PAGE}", reason_codes=(),
    )

    # Target page scope
    tgt_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=TGT_PAGE, decision_scope_id=f"wall-source:page-{TGT_PAGE}",
    )
    tgt_recs = [
        PhysicalWallCandidateRecord(
            wall_candidate_id=eid,
            wall_candidate=_make_candidate(eid, viewport_id="vp-tgt"),
            physical_identity=PhysicalWallIdentity(
                wall_candidate_id=eid, viewport_id="vp-tgt", candidate_identity_id=None,
                path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
                status=EvidenceResolutionStatus.CORROBORATED,
            ),
        )
        for eid in tgt_elements
    ]
    scopes[tgt_key] = PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
        records=tuple(tgt_recs), source_observation_ids=(), document_id=DOC,
        revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=TGT_PAGE,
        decision_scope_id=f"wall-source:page-{TGT_PAGE}", reason_codes=(),
    )

    return PhysicalWallCandidateAuthority(scopes, _seal=CANDIDATE_SEAL)


def _producer(
    src_elements: tuple[str, ...] = (ELEM,),
    tgt_elements: tuple[str, ...] = (ELEM,),
) -> CrossSheetRegistrationProducer:
    cand_auth = _setup_candidate_authority(src_elements, tgt_elements)
    return CrossSheetRegistrationProducer.from_authorities(physical_wall_candidate_authority=cand_auth)


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        CrossSheetRegistrationAuthority({})


def test_producer_constructor_sealed() -> None:
    cand_auth = _setup_candidate_authority()
    with pytest.raises(TypeError, match="from_authorities"):
        CrossSheetRegistrationProducer(cand_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_cross_sheet_registration_resolved() -> None:
    prod = _producer(src_elements=(ELEM,), tgt_elements=(ELEM,))
    sel = _selector(ELEM)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.physical_element_id == ELEM
    assert CROSS_SHEET_RESOLVED in res.reason_codes


# ── Fail Closed: Missing Element on Source or Target ──────────────────────────

def test_element_missing_on_source_page_abstains() -> None:
    prod = _producer(src_elements=(), tgt_elements=(ELEM,))
    sel = _selector(ELEM)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_SOURCE_PAGE_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_element_missing_on_target_page_abstains() -> None:
    prod = _producer(src_elements=(ELEM,), tgt_elements=())
    sel = _selector(ELEM)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_TARGET_PAGE_UNRESOLVED in res.reason_codes
    assert res.record is None


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer(src_elements=(ELEM,), tgt_elements=(ELEM,))
    sel = _selector(ELEM)
    prod.publish(sel)
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.physical_element_id == ELEM


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer(src_elements=(ELEM,), tgt_elements=(ELEM,))
    auth = prod.authority()
    sel = _selector(ELEM)
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer(src_elements=(ELEM,), tgt_elements=(ELEM,))
    auth = prod.authority()
    with pytest.raises(TypeError, match="CrossSheetRegistrationSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        CrossSheetRegistrationSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, source_page_id=SRC_PAGE, target_page_id=TGT_PAGE,
            physical_element_id=ELEM,
        )
