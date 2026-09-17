"""Production + adversarial tests for pb_secondary_footprint_authority (Item 29).

Tests cover:
  - Happy-path verandah and primary enclosed footprint resolution from upstream candidate
  - Unresolved candidate category or geometry fails closed (ABSTAINED)
  - Missing candidate abstains (WALL_UNRESOLVED)
  - Sealed authority constructor
  - Sealed producer constructor
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleEvidence,
    PhysicalScaleResult,
    PhysicalScaleSelector,
    _AUTHORITY_SEAL as SCALE_SEAL,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    PhysicalWallCandidateSelector,
    _AUTHORITY_SEAL as CANDIDATE_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_wall_room_topology_contracts import InteriorExterior, JunctionType, MeasurementAuthorityType, WallCandidate
from pb_secondary_footprint_authority import (
    FootprintCategory,
    SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE,
    SECONDARY_FOOTPRINT_RESOLVED,
    SECONDARY_FOOTPRINT_UNRESOLVED,
    SECONDARY_FOOTPRINT_WALL_UNRESOLVED,
    SecondaryFootprintAuthority,
    SecondaryFootprintProducer,
    SecondaryFootprintRecord,
    SecondaryFootprintResult,
    SecondaryFootprintSelector,
)

DOC = "doc-fp-test"
REV = "R1"
SHA = "d" * 64
SNAP = "snap-fp-1"
PAGE = "page-FP01"
SCOPE = f"wall-source:page-{PAGE}"
VP = "vp-FP01"
FOOTPRINT_A = "fp-verandah-1"
FOOTPRINT_B = "fp-main-1"

PTS = ((0.0, 0.0), (100.0, 0.0), (100.0, 50.0), (0.0, 50.0), (0.0, 0.0))


def _selector(fp_id: str = FOOTPRINT_A) -> SecondaryFootprintSelector:
    return SecondaryFootprintSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        footprint_id=fp_id,
    )


def _make_candidate(
    candidate_id: str,
    interior_exterior: str = "exterior",
    pts: tuple[tuple[float, float], ...] = PTS,
) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=VP,
        representation="double_line",
        centerline_pts=pts,
        face_a_segment_ids=("seg-a",),
        face_b_segment_ids=("seg-b",),
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.23,
        thickness_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION,
        length_m=10.0,
        end_node_ids=("n1", "n2"),
        junction_types=("free_end", "free_end"),
        interior_exterior=interior_exterior,
        level_id="L1",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _setup_authorities(*fp_specs: tuple[str, str]):
    if not fp_specs:
        fp_specs = ((FOOTPRINT_A, "exterior"),)
    records = []
    for wid, ie in fp_specs:
        ident = PhysicalWallIdentity(
            wall_candidate_id=wid, viewport_id=VP, candidate_identity_id=None,
            path_fingerprint=None, source_primitive_ids=(), edge_ids=(),
            status=EvidenceResolutionStatus.CORROBORATED,
        )
        wc = _make_candidate(wid, interior_exterior=ie)
        rec = PhysicalWallCandidateRecord(
            wall_candidate_id=wid, wall_candidate=wc, physical_identity=ident,
        )
        records.append(rec)

    cand_key = _ScopeKey(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
    )
    cand_auth = PhysicalWallCandidateAuthority(
        {cand_key: PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
            records=tuple(records), source_observation_ids=(), document_id=DOC,
            revision_id=REV, source_sha256=SHA, snapshot_id=SNAP, page_id=PAGE,
            decision_scope_id=SCOPE, reason_codes=(),
        )}, _seal=CANDIDATE_SEAL,
    )

    scale_sel = PhysicalScaleSelector(
        document_id=DOC, revision_id=REV, source_sha256=SHA,
        snapshot_id=SNAP, page_id=PAGE,
    )
    scale_ev = PhysicalScaleEvidence(
        selector=scale_sel, record_id="rec-scale", source_kind="graphic_scale",
        source_span_pt=100.0, physical_span_mm=10000.0, points_per_mm=0.01,
        mm_per_point=100.0, source_segment_observation_ids=(),
        source_text_observation_ids=(), viewport_id=None,
    )
    scale_auth = PhysicalScaleAuthority(
        {scale_sel.key: PhysicalScaleResult(
            status=EvidenceResolutionStatus.CORROBORATED, reason_codes=(), evidence=scale_ev,
        )}, _seal=SCALE_SEAL,
    )

    return cand_auth, scale_auth


def _producer(*fp_specs: tuple[str, str]) -> SecondaryFootprintProducer:
    cand_auth, scale_auth = _setup_authorities(*fp_specs)
    return SecondaryFootprintProducer.from_authorities(
        physical_wall_candidate_authority=cand_auth,
        physical_scale_authority=scale_auth,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SecondaryFootprintAuthority({})


def test_producer_constructor_sealed() -> None:
    cand_auth, scale_auth = _setup_authorities((FOOTPRINT_A, "exterior"))
    with pytest.raises(TypeError, match="from_authorities"):
        SecondaryFootprintProducer(cand_auth, scale_auth)  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_verandah_footprint_resolved_from_candidate() -> None:
    prod = _producer((FOOTPRINT_A, "exterior"))
    sel = _selector(FOOTPRINT_A)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.category is FootprintCategory.VERANDAH
    assert res.record.is_enclosed is False
    assert SECONDARY_FOOTPRINT_RESOLVED in res.reason_codes


def test_primary_enclosed_footprint_resolved_from_candidate() -> None:
    prod = _producer((FOOTPRINT_B, "interior"))
    sel = _selector(FOOTPRINT_B)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.category is FootprintCategory.PRIMARY_ENCLOSED
    assert res.record.is_enclosed is True


# ── Adversarial: Missing / Unknown ─────────────────────────────────────────────

def test_unknown_footprint_candidate_abstains() -> None:
    prod = _producer((FOOTPRINT_A, "exterior"))
    sel = _selector("fp-UNKNOWN")
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_WALL_UNRESOLVED in res.reason_codes


def test_unresolved_footprint_category_abstains() -> None:
    prod = _producer((FOOTPRINT_A, "unresolved"))
    sel = _selector(FOOTPRINT_A)
    res = prod.publish(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = _producer((FOOTPRINT_A, "exterior"))
    sel = _selector(FOOTPRINT_A)
    prod.publish(sel)
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.footprint_id == FOOTPRINT_A


def test_authority_lookup_missing_abstains() -> None:
    prod = _producer((FOOTPRINT_A, "exterior"))
    auth = prod.authority()
    sel = _selector(FOOTPRINT_A)
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = _producer((FOOTPRINT_A, "exterior"))
    auth = prod.authority()
    with pytest.raises(TypeError, match="SecondaryFootprintSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        SecondaryFootprintSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, page_id=PAGE, decision_scope_id=SCOPE,
            footprint_id=FOOTPRINT_A,
        )
