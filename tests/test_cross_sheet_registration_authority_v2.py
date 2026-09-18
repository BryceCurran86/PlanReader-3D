"""Production + adversarial tests for pb_cross_sheet_registration_authority (Item 32 V2).

The frozen #493 validator (tests/test_cross_sheet_registration_redteam_v2.py)
already covers: same id/mark on unrelated pages, conflicting physical
identity, empty correspondence-evidence universe, and ambiguous duplicate
target candidates -- all must remain NOT registered. This file adds the
positive path (a real, source-backed callout cross-reference) plus the
remaining required attacks: wrong revision, wrong source SHA, wrong
snapshot, and wrong/ambiguous target sheet identity.
"""
from __future__ import annotations

import fitz
import pytest

from pb_cross_sheet_registration_authority import (
    CROSS_SHEET_AMBIGUOUS_ELEMENT_MATCH,
    CROSS_SHEET_CORRESPONDENCE_EVIDENCE_UNAVAILABLE,
    CROSS_SHEET_CORRESPONDENCE_UNRESOLVED,
    CROSS_SHEET_RECORD_UNAVAILABLE,
    CROSS_SHEET_RESOLVED,
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationProducer,
    CrossSheetRegistrationSelector,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
    _AUTHORITY_SEAL as CANDIDATE_AUTHORITY_SEAL,
    _ScopeKey,
)
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_contracts import MeasurementAuthorityType, WallCandidate

DOC = "doc-item32-v2-test"
REV = "R1"
SNAP = "snap-1"
SRC_PAGE = "1"
TGT_PAGE = "2"
ELEMENT = "wall-1"


def _candidate(candidate_id: str, *, viewport_id: str, pts) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id=viewport_id,
        representation="double_line",
        centerline_pts=pts,
        face_a_segment_ids=(f"{viewport_id}-face-a",),
        face_b_segment_ids=(f"{viewport_id}-face-b",),
        is_curved=False,
        curve_control_pts=None,
        thickness_m=0.11,
        thickness_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION,
        length_m=10.0,
        end_node_ids=(f"{viewport_id}-n1", f"{viewport_id}-n2"),
        junction_types=("free_end", "free_end"),
        interior_exterior="unresolved",
        level_id="L1",
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=1.0,
    )


def _record(candidate_id: str, *, viewport_id: str, pts, suffix: str) -> PhysicalWallCandidateRecord:
    return PhysicalWallCandidateRecord(
        wall_candidate_id=candidate_id,
        wall_candidate=_candidate(candidate_id, viewport_id=viewport_id, pts=pts),
        physical_identity=PhysicalWallIdentity(
            wall_candidate_id=candidate_id,
            viewport_id=viewport_id,
            candidate_identity_id=f"identity-{suffix}",
            path_fingerprint=f"path-{suffix}",
            source_primitive_ids=(f"primitive-{suffix}",),
            edge_ids=(f"edge-{suffix}",),
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )


def _candidate_authority(
    *,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    source_records,
    target_records,
) -> PhysicalWallCandidateAuthority:
    def _scope(page_id: str, records):
        key = _ScopeKey(
            document_id=DOC, revision_id=revision_id, source_sha256=source_sha256,
            snapshot_id=snapshot_id, page_id=page_id, decision_scope_id=f"wall-source:page-{page_id}",
        )
        result = PhysicalWallCandidateScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True,
            records=records, source_observation_ids=(), document_id=DOC,
            revision_id=revision_id, source_sha256=source_sha256, snapshot_id=snapshot_id,
            page_id=page_id, decision_scope_id=f"wall-source:page-{page_id}", reason_codes=(),
        )
        return key, result

    src_key, src_res = _scope(SRC_PAGE, source_records)
    tgt_key, tgt_res = _scope(TGT_PAGE, target_records)
    return PhysicalWallCandidateAuthority({src_key: src_res, tgt_key: tgt_res}, _seal=CANDIDATE_AUTHORITY_SEAL)


def _registration_pdf(
    *,
    callout_text: str | None = "1/A20",
    callout_near_wall: bool = True,
    target_sheet_text: str | None = "A20",
    duplicate_target_sheet: bool = False,
) -> bytes:
    doc = fitz.open()
    src = doc.new_page(width=400, height=400)
    src.draw_line((50, 50), (150, 50))  # the wall itself: y=50, x in [50,150]
    if callout_text is not None:
        x = 90 if callout_near_wall else 350
        src.insert_text((x, 55 if callout_near_wall else 380), callout_text, fontsize=10)

    tgt = doc.new_page(width=400, height=400)
    if target_sheet_text is not None:
        tgt.insert_text((350, 380), target_sheet_text, fontsize=10)
    if duplicate_target_sheet:
        tgt.insert_text((20, 20), "B77", fontsize=10)  # a second, distinct sheet-code-shaped token

    data = doc.tobytes()
    doc.close()
    return data


def _ingest(pdf_bytes: bytes):
    source = SourceVisibilityProducer(producer_method="item32_v2_test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id=DOC, source_bytes=pdf_bytes, source_locator="memory:item32-v2-test.pdf",
    )
    return source, published


def _selector(published) -> CrossSheetRegistrationSelector:
    return CrossSheetRegistrationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_page_id=SRC_PAGE,
        target_page_id=TGT_PAGE,
        physical_element_id=ELEMENT,
    )


def _producer_for(pdf_bytes: bytes, source, published) -> CrossSheetRegistrationProducer:
    candidate_authority = _candidate_authority(
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_records=(_record(ELEMENT, viewport_id="src-vp", pts=((50.0, 50.0), (150.0, 50.0)), suffix="src"),),
        target_records=(_record(ELEMENT, viewport_id="tgt-vp", pts=((0.0, 0.0), (10.0, 0.0)), suffix="tgt"),),
    )
    return CrossSheetRegistrationProducer.from_authorities(
        physical_wall_candidate_authority=candidate_authority,
        source_visibility_producer=source,
    )


# ── Constructor Seals ─────────────────────────────────────────────────────────

def test_authority_constructor_sealed() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        CrossSheetRegistrationAuthority({})


def test_producer_constructor_sealed() -> None:
    pdf = _registration_pdf()
    _source, published = _ingest(pdf)
    candidate_authority = _candidate_authority(
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_records=(), target_records=(),
    )
    with pytest.raises(TypeError, match="from_authorities"):
        CrossSheetRegistrationProducer(candidate_authority, None)  # type: ignore[call-arg]


# ── Happy path: real source-backed callout correspondence ─────────────────────

def test_real_callout_reference_resolves_registration() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.referenced_sheet_code == "A20"
    assert res.record.callout_mark == "1"
    assert CROSS_SHEET_RESOLVED in res.reason_codes


def test_authority_lookup_published_record() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    sel = _selector(published)
    producer.publish(sel)
    res = producer.authority().resolve(sel)
    assert res.status is EvidenceResolutionStatus.CORROBORATED


# ── Adversarial: no correspondence evidence source ─────────────────────────────

def test_no_source_visibility_producer_always_abstains() -> None:
    pdf = _registration_pdf()
    _source, published = _ingest(pdf)
    candidate_authority = _candidate_authority(
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_records=(_record(ELEMENT, viewport_id="src-vp", pts=((0.0, 0.0), (1.0, 0.0)), suffix="src"),),
        target_records=(_record(ELEMENT, viewport_id="tgt-vp", pts=((0.0, 0.0), (1.0, 0.0)), suffix="tgt"),),
    )
    producer = CrossSheetRegistrationProducer.from_authorities(
        physical_wall_candidate_authority=candidate_authority,
    )
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CORRESPONDENCE_EVIDENCE_UNAVAILABLE in res.reason_codes


def test_callout_referencing_wrong_sheet_does_not_register() -> None:
    pdf = _registration_pdf(callout_text="1/Z99")
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CORRESPONDENCE_UNRESOLVED in res.reason_codes


def test_callout_far_from_element_geometry_does_not_register() -> None:
    pdf = _registration_pdf(callout_near_wall=False)
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CORRESPONDENCE_UNRESOLVED in res.reason_codes


def test_no_callout_at_all_does_not_register() -> None:
    pdf = _registration_pdf(callout_text=None)
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CORRESPONDENCE_UNRESOLVED in res.reason_codes


def test_ambiguous_target_sheet_identity_does_not_register() -> None:
    pdf = _registration_pdf(duplicate_target_sheet=True)
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CORRESPONDENCE_UNRESOLVED in res.reason_codes


def test_missing_target_sheet_identity_does_not_register() -> None:
    pdf = _registration_pdf(target_sheet_text=None)
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_CORRESPONDENCE_UNRESOLVED in res.reason_codes


def test_ambiguous_source_page_element_match_fails_closed() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    candidate_authority = _candidate_authority(
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        source_records=(
            _record(ELEMENT, viewport_id="src-vp-1", pts=((0.0, 0.0), (1.0, 0.0)), suffix="dup-a"),
            _record(ELEMENT, viewport_id="src-vp-2", pts=((5.0, 5.0), (6.0, 5.0)), suffix="dup-b"),
        ),
        target_records=(_record(ELEMENT, viewport_id="tgt-vp", pts=((0.0, 0.0), (1.0, 0.0)), suffix="tgt"),),
    )
    producer = CrossSheetRegistrationProducer.from_authorities(
        physical_wall_candidate_authority=candidate_authority, source_visibility_producer=source,
    )
    res = producer.publish(_selector(published))
    assert res.status is EvidenceResolutionStatus.CONFLICT
    assert CROSS_SHEET_AMBIGUOUS_ELEMENT_MATCH in res.reason_codes


# ── Adversarial: stale lineage cannot replay a record ──────────────────────────

def test_stale_revision_source_or_snapshot_cannot_replay_record() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    good = _selector(published)
    producer.publish(good)
    authority = producer.authority()

    bad = CrossSheetRegistrationSelector(
        document_id=good.document_id,
        revision_id=good.revision_id + "-stale",
        source_sha256="e" * 64,
        snapshot_id=good.snapshot_id + "-stale",
        source_page_id=good.source_page_id,
        target_page_id=good.target_page_id,
        physical_element_id=good.physical_element_id,
    )
    res = authority.resolve(bad)
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


def test_authority_lookup_missing_abstains() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    res = producer.authority().resolve(_selector(published))
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert CROSS_SHEET_RECORD_UNAVAILABLE in res.reason_codes


def test_authority_lookup_wrong_selector_type_raises() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    with pytest.raises(TypeError, match="CrossSheetRegistrationSelector"):
        producer.authority().resolve("not-a-selector")  # type: ignore[arg-type]


def test_publish_wrong_selector_type_raises() -> None:
    pdf = _registration_pdf()
    source, published = _ingest(pdf)
    producer = _producer_for(pdf, source, published)
    with pytest.raises(TypeError, match="CrossSheetRegistrationSelector"):
        producer.publish("not-a-selector")  # type: ignore[arg-type]


def test_selector_empty_field_raises() -> None:
    with pytest.raises(ValueError):
        CrossSheetRegistrationSelector(
            document_id="", revision_id=REV, source_sha256="a" * 64,
            snapshot_id=SNAP, source_page_id=SRC_PAGE, target_page_id=TGT_PAGE,
            physical_element_id=ELEMENT,
        )
