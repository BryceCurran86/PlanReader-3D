"""Production + adversarial tests for pb_cross_sheet_registration_authority (Item 32).

Tests cover:
  - Happy-path plan <-> elevation and plan <-> section registration
  - Rejection of caller_asserted registration (ABSTAINED)
  - Rejection of page_label_only registration (ABSTAINED)
  - Rejection of same_mark_only registration (ABSTAINED)
  - Stale lineage (SHA/revision/snapshot mismatch) fails closed (CONFLICT)
  - Ambiguous many-to-many registrations fail closed (CONFLICT)
  - Sealed authority constructor
  - Selector validation
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_cross_sheet_registration_authority import (
    CROSS_SHEET_AMBIGUOUS_MANY_TO_MANY,
    CROSS_SHEET_CALLER_ASSERTION_REJECTED,
    CROSS_SHEET_LABEL_ONLY_REJECTED,
    CROSS_SHEET_LINEAGE_MISMATCH,
    CROSS_SHEET_MARK_ONLY_REJECTED,
    CROSS_SHEET_RECORD_UNAVAILABLE,
    CROSS_SHEET_RESOLVED,
    CROSS_SHEET_UNRESOLVED,
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationProducer,
    CrossSheetRegistrationProof,
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


def _proof(
    elem_id: str = ELEM,
    src_page: str = SRC_PAGE,
    tgt_page: str = TGT_PAGE,
    kind: str = "geometric_projection_alignment",
    src_view: str = "plan",
    tgt_view: str = "elevation",
    sha: str = SHA,
    rev: str = REV,
    snap: str = SNAP,
    pid: str | None = None,
) -> CrossSheetRegistrationProof:
    if pid is None:
        pid = stable_contract_id("proof", {"elem": elem_id, "kind": kind})
    return CrossSheetRegistrationProof(
        proof_id=pid,
        source_sha256=sha,
        revision_id=rev,
        snapshot_id=snap,
        source_page_id=src_page,
        source_viewport_id="vp-plan",
        source_view_type=src_view,
        target_page_id=tgt_page,
        target_viewport_id="vp-elev",
        target_view_type=tgt_view,
        physical_element_id=elem_id,
        proof_kind=kind,
        correspondence_evidence_ids=("ev-align-1",),
        confidence=0.9,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        CrossSheetRegistrationAuthority({})


def test_producer_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="create()"):
        CrossSheetRegistrationProducer()  # type: ignore[call-arg]


# ── Happy Path ────────────────────────────────────────────────────────────────

def test_plan_to_elevation_registration_resolved() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prf = [_proof(kind="geometric_projection_alignment")]
    res = prod.publish(sel, prf)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.source_view_type == "plan"
    assert res.record.target_view_type == "elevation"
    assert CROSS_SHEET_RESOLVED in res.reason_codes


def test_plan_to_section_registration_resolved() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prf = [_proof(kind="authenticated_callout_cut", tgt_view="section")]
    res = prod.publish(sel, prf)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.target_view_type == "section"


# ── Adversarial: Rejected Heuristics ─────────────────────────────────────────

def test_caller_asserted_proof_rejected() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prf = [_proof(kind="caller_asserted")]
    res = prod.publish(sel, prf)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CALLER_ASSERTION_REJECTED in res.reason_codes
    assert res.record is None


def test_page_label_only_proof_rejected() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prf = [_proof(kind="page_label_only")]
    res = prod.publish(sel, prf)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_LABEL_ONLY_REJECTED in res.reason_codes


def test_same_mark_only_proof_rejected() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prf = [_proof(kind="same_mark_only")]
    res = prod.publish(sel, prf)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_MARK_ONLY_REJECTED in res.reason_codes


# ── Adversarial: Stale & Ambiguous ────────────────────────────────────────────

def test_stale_lineage_fails_closed() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prf = [_proof(sha="d" * 64)]
    res = prod.publish(sel, prf)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert CROSS_SHEET_LINEAGE_MISMATCH in res.reason_codes


def test_ambiguous_many_to_many_views_conflicts() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prfs = [
        _proof(tgt_view="elevation", pid="p-elev"),
        _proof(tgt_view="section", pid="p-sec"),
    ]
    res = prod.publish(sel, prfs)
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert CROSS_SHEET_AMBIGUOUS_MANY_TO_MANY in res.reason_codes


def test_empty_proofs_abstains() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    res = prod.publish(sel, [])
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_UNRESOLVED in res.reason_codes


# ── Authority Lookup ──────────────────────────────────────────────────────────

def test_authority_lookup_published_record() -> None:
    prod = CrossSheetRegistrationProducer.create()
    sel = _selector()
    prod.publish(sel, [_proof()])
    auth = prod.authority()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record.physical_element_id == ELEM


def test_authority_lookup_missing_abstains() -> None:
    prod = CrossSheetRegistrationProducer.create()
    auth = prod.authority()
    sel = _selector()
    res = auth.resolve(sel)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    prod = CrossSheetRegistrationProducer.create()
    auth = prod.authority()
    with pytest.raises(TypeError, match="CrossSheetRegistrationSelector"):
        auth.resolve("not-a-selector")  # type: ignore[arg-type]


# ── Validation ────────────────────────────────────────────────────────────────

def test_proof_empty_evidence_ids_raises() -> None:
    with pytest.raises(ValueError, match="correspondence_evidence_ids"):
        CrossSheetRegistrationProof(
            proof_id="p-bad", source_sha256=SHA, revision_id=REV, snapshot_id=SNAP,
            source_page_id=SRC_PAGE, source_viewport_id="vp1", source_view_type="plan",
            target_page_id=TGT_PAGE, target_viewport_id="vp2", target_view_type="elevation",
            physical_element_id=ELEM, proof_kind="geometric_projection_alignment",
            correspondence_evidence_ids=(), confidence=0.9,
        )


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        CrossSheetRegistrationSelector(
            document_id="", revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, source_page_id=SRC_PAGE, target_page_id=TGT_PAGE,
            physical_element_id=ELEM,
        )
