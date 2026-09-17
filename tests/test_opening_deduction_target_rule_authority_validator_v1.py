"""Independent expected-RED validator for the Opening Deduction target/rule authority.

TEST ONLY / EXPECTED-RED / DRAFT / NEVER MERGE.

Each test below either:
  A. constructs the genuine source-backed forbidden / attack condition and proves
     the production code fails closed; or
  B. proves structurally that the public API exposes no route for the attack.

No shotgun reason-code testing: every test exercises the actual condition.
"""
from __future__ import annotations

import dataclasses
import re
from dataclasses import fields, is_dataclass
import inspect
import io

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingProducer,
    OpeningHostBindingSelector,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_opening_universe_completeness_authority import OpeningUniverseCompletenessProducer
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_opening_void_authority import (
    PHYSICAL_OPENING_VOID_RESOLVED,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidProducer,
    PhysicalOpeningVoidSelector,
)
from pb_physical_scale_authority import PhysicalScaleProducer, PhysicalScaleSelector
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_opening_height_authority import OpeningHeightProducer, OpeningHeightSelector
from pb_opening_vertical_placement_authority import (
    OpeningVerticalPlacementProducer,
    OpeningVerticalPlacementSelector,
    ScheduleRowVerticalPlacementProducer,
    ScheduleRowVerticalPlacementSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_RESOLVED,
    ScheduleOpeningInstanceBindingProducer,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_schedule_row_height_authority import ScheduleRowHeightProducer, ScheduleRowHeightSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

from tests.test_physical_opening_void_authority import _pdf as _void_test_pdf
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT,
    OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH,
    OpeningDeductionApplicabilityAuthority,
    OpeningDeductionApplicabilityProducer,
    OpeningDeductionApplicabilityRecord,
    OpeningDeductionApplicabilityResult,
    OpeningDeductionApplicabilitySelector,
    OpeningDeductionRuleAuthority,
    OpeningDeductionRuleProducer,
    OpeningDeductionRuleRecord,
    OpeningDeductionRuleResult,
    OpeningDeductionTargetScopeAuthority,
    OpeningDeductionTargetScopeProducer,
    OpeningDeductionTargetScopeRecord,
    OpeningDeductionTargetScopeResult,
)

# -------------------------------------------------------------------------
# Constants
# -------------------------------------------------------------------------
SCOPE = "wall-source:page-1"
TARGET = "T1"
TRADE = "PLASTER"
FINISH = "F1"
ASSEMBLY = "A1"
RULE_ID = "R1"
RULE_VER = "1.0"


# -------------------------------------------------------------------------
# PDF builders — geometry matches test_physical_opening_void_authority._pdf()
# -------------------------------------------------------------------------

def _build_pdf(
    *,
    odtarget_token: str | None = None,
    odrule_token: str | None = None,
    additional_tokens: tuple[str, ...] = (),
    width_text: str = "900",
    height_text: str = "2100",
) -> bytes:
    """Build a minimal PDF containing an opening and optional ODTARGET/ODRULE tokens.

    Uses the authoritative void-chain test fixture geometry.
    """
    doc = fitz.open("pdf", _void_test_pdf(width_text=width_text, height_text=height_text))
    page = doc[0]
    y = 10.0
    if odtarget_token:
        page.insert_text(fitz.Point(10.0, y), odtarget_token, fontsize=8)
        y += 10.0
    if odrule_token:
        page.insert_text(fitz.Point(10.0, y), odrule_token, fontsize=8)
        y += 10.0
    for tok in additional_tokens:
        page.insert_text(fitz.Point(10.0, y), tok, fontsize=8)
        y += 10.0
    return bytes(doc.tobytes(garbage=4, deflate=True))


def _default_pdf(**kwargs) -> bytes:
    return _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,"
            f"trade={TRADE},finish={FINISH},assembly={ASSEMBLY})"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,"
            f"trade={TRADE},finish={FINISH},assembly={ASSEMBLY},"
            f"id={RULE_ID},version={RULE_VER},decision=DEDUCT)"
        ),
        **kwargs,
    )


# -------------------------------------------------------------------------
# Infrastructure: ingest + build void chain
# -------------------------------------------------------------------------

def _ingest(src: SourceVisibilityProducer, pdf: bytes, doc_id: str = "test-doc"):
    return src.ingest_native_pdf_bytes(
        document_id=doc_id,
        source_bytes=pdf,
        source_locator=f"memory://{doc_id}.pdf",
    )


def _opening_selector(published, phys: PhysicalOpeningAuthority):
    """Return ObservationSelector for the single physical opening in the PDF."""
    resolved: dict[str, ObservationSelector] = {}
    rev, snap = published.revision, published.snapshot
    for obs_id in published.visible_observation_ids:
        sel = ObservationSelector(
            document_id=rev.document_id,
            revision_id=rev.revision_id,
            source_sha256=rev.source_sha256,
            snapshot_id=snap.snapshot_id,
            observation_id=obs_id,
        )
        result = phys.prove_existence(sel)
        if (
            result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            resolved.setdefault(result.existence_record.record_id, sel)
    assert len(resolved) >= 1, "No physical opening found in fixture PDF"
    return next(iter(resolved.values()))


def _complete_opening_universe(src, published):
    from types import SimpleNamespace
    from pb_opening_universe_completeness_authority import OpeningUniverseCompletenessProducer
    rev, snap = published.revision, published.snapshot
    visible = src.authority()
    primitives = []
    for obs_id in published.visible_observation_ids:
        sel = ObservationSelector(
            document_id=rev.document_id,
            revision_id=rev.revision_id,
            source_sha256=rev.source_sha256,
            snapshot_id=snap.snapshot_id,
            observation_id=obs_id,
        )
        obs = visible.resolve_visible(sel).observation
        if obs is None or obs.observation_kind != "native_pdf_visible_segment":
            continue
        primitives.append(
            SimpleNamespace(
                primitive_id=obs.observation_id,
                page_id=obs.page_id,
                geometry=obs.geometry,
                layer="native-pdf-visible",
                clip_known=True,
                clip_present=False,
                clip=None,
            )
        )
    producer = OpeningUniverseCompletenessProducer(
        producer_method="test", producer_version="1.0"
    )
    record = producer.publish_enumeration(
        decision_scope_id=SCOPE,
        decision_scope_kind="full-source-page",
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        page_ids=("1",),
        viewport_id=None,
        coverage=published.coverage,
        source_primitives=tuple(primitives),
        enumerated_primitives=tuple(primitives),
        optional_content_state="known_visible",
        xobject_traversal_truncated=False,
    )
    assert record.decision_scope_complete
    return producer.authority()







def _build_void_chain(pdf: bytes, doc_id: str = "test-doc"):
    """Build and return (src, published, void_producer, opening_selector, void_selector)."""
    src = SourceVisibilityProducer(producer_method="test", producer_version="1.0")
    published = _ingest(src, pdf, doc_id)
    rev = published.revision
    snap = published.snapshot
    phys = PhysicalOpeningAuthority(src.authority())
    opening_sel = _opening_selector(published, phys)
    opening_rec = phys.prove_existence(opening_sel).existence_record
    assert opening_rec is not None

    wall_auth = PhysicalWallCandidateProducer.from_source_visibility_producer(src).authority()
    wall_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_auth
    ).authority()
    host_universe_sel = OpeningHostWallUniverseSelector(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        page_id="1",
        decision_scope_id=SCOPE,
    )
    host_prod = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=phys,
        host_wall_universe_authority=wall_universe,
    )
    host = host_prod.publish(
        opening_left_selector=opening_sel,
        opening_right_selector=opening_sel,
        host_universe_selector=host_universe_sel,
    )
    assert host.status is EvidenceResolutionStatus.CORROBORATED
    assert host.record is not None

    host_sel = OpeningHostBindingSelector(
        document_id=host.record.document_id,
        revision_id=host.record.revision_id,
        source_sha256=host.record.source_sha256,
        snapshot_id=host.record.snapshot_id,
        page_id=host.record.page_id,
        decision_scope_id=host.record.decision_scope_id,
        opening_identity_id=host.record.opening_identity_id,
    )
    frame_prod = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=phys,
        host_binding_authority=host_prod.authority(),
        physical_wall_candidate_authority=wall_auth,
    )
    frame = frame_prod.publish(opening_selector=opening_sel, host_binding_selector=host_sel)
    assert frame.status is EvidenceResolutionStatus.CORROBORATED

    sched_prod = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(src)
    sched = sched_prod.publish_scope(
        opening_selector=opening_sel, decision_scope_id=SCOPE
    )
    assert sched.status is EvidenceResolutionStatus.CORROBORATED
    assert sched.record is not None

    row_height_prod = ScheduleRowHeightProducer.from_source_visibility_producer(src)
    row_height_sel = ScheduleRowHeightSelector(
        document_id=sched.record.document_id,
        revision_id=sched.record.revision_id,
        source_sha256=sched.record.source_sha256,
        snapshot_id=sched.record.snapshot_id,
        schedule_page_id=sched.record.schedule_page_id,
        schedule_row_observation_ids=sched.record.schedule_row_observation_ids,
    )
    row_height_prod.publish_scope(row_height_sel)

    height_prod = OpeningHeightProducer.from_authorities(
        src, sched_prod.authority(), row_height_prod.authority()
    )
    height_sel = OpeningHeightSelector(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        decision_scope_id=SCOPE,
        opening_record_id=opening_rec.record_id,
    )
    height_prod.publish_scope(height_sel)

    row_vert_prod = ScheduleRowVerticalPlacementProducer.from_source_visibility_producer(src)
    row_vert_sel = ScheduleRowVerticalPlacementSelector(
        document_id=sched.record.document_id,
        revision_id=sched.record.revision_id,
        source_sha256=sched.record.source_sha256,
        snapshot_id=sched.record.snapshot_id,
        schedule_page_id=sched.record.schedule_page_id,
        schedule_row_observation_ids=sched.record.schedule_row_observation_ids,
    )
    row_vert_prod.publish_scope(row_vert_sel)

    vert_prod = OpeningVerticalPlacementProducer.from_authorities(
        binding_authority=sched_prod.authority(),
        row_vertical_placement_authority=row_vert_prod.authority(),
    )
    vert_sel = OpeningVerticalPlacementSelector(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        decision_scope_id=SCOPE,
        opening_record_id=opening_rec.record_id,
    )
    vert_prod.publish_scope(vert_sel)

    scale_prod = PhysicalScaleProducer.from_source_visibility_producer(src)
    scale_sel = PhysicalScaleSelector(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        page_id="1",
        viewport_id=None,
    )
    scale = scale_prod.publish_scope(scale_sel)
    assert scale.status is EvidenceResolutionStatus.CORROBORATED

    void_sel = PhysicalOpeningVoidSelector(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        page_id="1",
        decision_scope_id=SCOPE,
        opening_identity_id=opening_rec.record_id,
    )
    void_prod = PhysicalOpeningVoidProducer.from_authorities(
        physical_opening_authority=phys,
        opening_universe_authority=_complete_opening_universe(src, published),
        host_binding_authority=host_prod.authority(),
        host_frame_authority=frame_prod.authority(),
        opening_dimension_authority=src.opening_dimension_authority(),
        opening_height_authority=height_prod.authority(),
        vertical_placement_authority=vert_prod.authority(),
        physical_scale_authority=scale_prod.authority(),
    )
    void = void_prod.publish(opening_selector=opening_sel, selector=void_sel)
    assert void.status is EvidenceResolutionStatus.CORROBORATED, void.reason_codes

    return (
        src,
        published,
        void_prod,
        host_prod,
        sched_prod,
        opening_sel,
        void_sel,
        opening_rec,
    )


def _app_selector(
    rev,
    snap,
    opening_rec,
    target: str = TARGET,
) -> OpeningDeductionApplicabilitySelector:
    return OpeningDeductionApplicabilitySelector(
        document_id=rev.document_id,
        revision_id=rev.revision_id,
        source_sha256=rev.source_sha256,
        snapshot_id=snap.snapshot_id,
        page_id="1",
        decision_scope_id=SCOPE,
        opening_identity_id=opening_rec.record_id,
        target_scope_id=target,
    )


# =========================================================================
# 1. Positive test — real source PDF with valid ODTARGET + ODRULE tokens
# =========================================================================

def test_positive_valid_source_token_produces_corroborated_applicability() -> None:
    pdf = _default_pdf()
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf)
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)

    target_prod.publish(sel)
    rule_prod.publish(sel)

    app_prod = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_prod.authority(),
        host_binding_authority=host_prod.authority(),
        target_scope_authority=target_prod.authority(),
        rule_authority=rule_prod.authority(),
    )
    result = app_prod.publish(sel)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert OPENING_DEDUCTION_APPLICABILITY_RESOLVED in result.reason_codes
    assert result.record is not None
    rec = result.record
    assert rec.opening_identity_id == opening_rec.record_id
    assert rec.target_scope_id == TARGET
    assert rec.rule_version == RULE_VER
    assert rec.physical_void_record_id
    assert rec.host_binding_record_id
    assert rec.target_scope_record_id
    assert rec.rule_record_id


# =========================================================================
# 2. Physical void alone is not deduction permission
# =========================================================================

def test_physical_void_alone_without_source_tokens_cannot_establish_applicability() -> None:
    """No ODTARGET or ODRULE → structural impossibility of positive applicability."""
    pdf = _build_pdf()  # no tokens
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf)
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)

    t_result = target_prod.publish(sel)
    r_result = rule_prod.publish(sel)
    assert t_result.status is not EvidenceResolutionStatus.CORROBORATED
    assert r_result.status is not EvidenceResolutionStatus.CORROBORATED


# =========================================================================
# 3. Caller-supplied deductible bool is not accepted (structural)
# =========================================================================

def test_caller_applicability_boolean_has_no_path_into_producer() -> None:
    forbidden = {
        "deductible",
        "deduction_allowed",
        "is_applicable",
        "applicable",
        "trade_applicable",
        "finish_applicable",
        "assembly_applicable",
        "commercial_applicability",
        "host_wall_id",
        "wall_id",
        "trade",
        "trade_id",
        "finish",
        "finish_id",
        "assembly",
        "assembly_id",
        "rule",
        "rule_id",
        "rule_version",
    }
    for method in (
        OpeningDeductionApplicabilityProducer.from_authorities,
        OpeningDeductionApplicabilityProducer.publish,
        OpeningDeductionTargetScopeProducer.from_authorities,
        OpeningDeductionTargetScopeProducer.publish,
        OpeningDeductionRuleProducer.from_source_visibility_producer,
        OpeningDeductionRuleProducer.publish,
    ):
        params = set(inspect.signature(method).parameters)
        leaked = params & forbidden
        assert not leaked, f"{method.__qualname__} leaks caller truth: {leaked}"


# =========================================================================
# 4. Workspace default standard is insufficient
# =========================================================================

def test_workspace_default_standard_cannot_establish_authority() -> None:
    """Source text must not mention AS4041 or hardcoded rule names."""
    import importlib.util
    from pathlib import Path
    spec = importlib.util.find_spec("pb_opening_deduction_applicability_authority")
    assert spec is not None
    source = Path(spec.origin).read_text(encoding="utf-8").lower()
    assert "as4041" not in source
    assert "pb_australian_takeoff_standards" not in source
    assert "calculate_wall_takeoff" not in source
    assert "deductible=true" not in source


# =========================================================================
# 5. Wrong target_scope_id → abstain
# =========================================================================

def test_wrong_target_scope_id_abstains() -> None:
    pdf = _default_pdf()
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf)
    )
    rev, snap = published.revision, published.snapshot
    # Ask for a target that doesn't match what's in the PDF
    sel = _app_selector(rev, snap, opening_rec, target="WRONG_TARGET")

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    result = target_prod.publish(sel)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.record is None


# =========================================================================
# 6. Stale revision/SHA/snapshot → fails closed
# =========================================================================

def test_stale_revision_fails_closed() -> None:
    pdf = _default_pdf()
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf)
    )
    rev, snap = published.revision, published.snapshot

    # No valid selector can be built for a different SHA because our module re-derives
    # the text universe using the exact lineage from the selector.  Provide a real selector
    # but with a stale source_sha256.
    try:
        sel = OpeningDeductionApplicabilitySelector(
            document_id=rev.document_id,
            revision_id=rev.revision_id,
            source_sha256="a" * 64,   # wrong SHA
            snapshot_id=snap.snapshot_id,
            page_id="1",
            decision_scope_id=SCOPE,
            opening_identity_id=opening_rec.record_id,
            target_scope_id=TARGET,
        )
    except ValueError:
        # If the selector validates SHA format and rejects it, that's also fine
        return

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    result = target_prod.publish(sel)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED


# =========================================================================
# 7. Conflicting source rules → CONFLICT
# =========================================================================

def test_two_conflicting_odrule_tokens_produce_conflict() -> None:
    """Two different ODRULE tokens for the same target → CONFLICT, not arbitrary pick."""
    pdf = _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly={ASSEMBLY})"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly={ASSEMBLY},"
            f"id=R1,version=1.0,decision=DEDUCT)"
        ),
        additional_tokens=(
            f"ODRULE(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly={ASSEMBLY},"
            f"id=R2,version=2.0,decision=DEDUCT)",
        ),
    )
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "conflict-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)
    result = rule_prod.publish(sel)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None


# =========================================================================
# 8. Wrong trade → TRADE_SCOPE_MISMATCH
# =========================================================================

def test_wrong_trade_in_rule_produces_trade_mismatch() -> None:
    """ODTARGET has trade=PLASTER but ODRULE has trade=TILES → mismatch."""
    pdf = _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,trade=PLASTER,finish={FINISH},assembly={ASSEMBLY})"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,trade=TILES,finish={FINISH},assembly={ASSEMBLY},"
            f"id={RULE_ID},version={RULE_VER},decision=DEDUCT)"
        ),
    )
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "trade-mismatch-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)
    target_prod.publish(sel)
    rule_prod.publish(sel)

    app_prod = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_prod.authority(),
        host_binding_authority=host_prod.authority(),
        target_scope_authority=target_prod.authority(),
        rule_authority=rule_prod.authority(),
    )
    result = app_prod.publish(sel)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH in result.reason_codes


# =========================================================================
# 9. Wrong finish → FINISH_SCOPE_MISMATCH
# =========================================================================

def test_wrong_finish_in_rule_produces_finish_mismatch() -> None:
    pdf = _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,trade={TRADE},finish=F1,assembly={ASSEMBLY})"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,trade={TRADE},finish=F2,assembly={ASSEMBLY},"
            f"id={RULE_ID},version={RULE_VER},decision=DEDUCT)"
        ),
    )
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "finish-mismatch-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)
    target_prod.publish(sel)
    rule_prod.publish(sel)

    app_prod = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_prod.authority(),
        host_binding_authority=host_prod.authority(),
        target_scope_authority=target_prod.authority(),
        rule_authority=rule_prod.authority(),
    )
    result = app_prod.publish(sel)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH in result.reason_codes


# =========================================================================
# 10. Wrong assembly → ASSEMBLY_SCOPE_MISMATCH
# =========================================================================

def test_wrong_assembly_in_rule_produces_assembly_mismatch() -> None:
    pdf = _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly=A1)"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly=A2,"
            f"id={RULE_ID},version={RULE_VER},decision=DEDUCT)"
        ),
    )

    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "assembly-mismatch-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)
    target_prod.publish(sel)
    rule_prod.publish(sel)

    app_prod = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_prod.authority(),
        host_binding_authority=host_prod.authority(),
        target_scope_authority=target_prod.authority(),
        rule_authority=rule_prod.authority(),
    )
    result = app_prod.publish(sel)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH in result.reason_codes


# =========================================================================
# 11. RETAIN decision → not CORROBORATED
# =========================================================================

def test_odrule_retain_decision_cannot_produce_positive_applicability() -> None:
    pdf = _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,"
            f"trade={TRADE},finish={FINISH},assembly={ASSEMBLY})"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,"
            f"trade={TRADE},finish={FINISH},assembly={ASSEMBLY},"
            f"id={RULE_ID},version={RULE_VER},decision=RETAIN)"
        ),
    )
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "retain-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    rule_prod = OpeningDeductionRuleProducer.from_source_visibility_producer(src)
    target_prod.publish(sel)
    rule_prod.publish(sel)

    app_prod = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_prod.authority(),
        host_binding_authority=host_prod.authority(),
        target_scope_authority=target_prod.authority(),
        rule_authority=rule_prod.authority(),
    )
    result = app_prod.publish(sel)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED


# =========================================================================
# 12. Conflicting ODTARGET tokens → CONFLICT
# =========================================================================

def test_two_conflicting_odtarget_tokens_produce_conflict() -> None:
    pdf = _build_pdf(
        odtarget_token=(
            f"ODTARGET(target={TARGET},opening=W1,trade=PLASTER,finish={FINISH},assembly={ASSEMBLY})"
        ),
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly={ASSEMBLY},"
            f"id={RULE_ID},version={RULE_VER},decision=DEDUCT)"
        ),
        additional_tokens=(
            f"ODTARGET(target={TARGET},opening=W1,trade=TILES,finish={FINISH},assembly={ASSEMBLY})",
        ),
    )
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "target-conflict-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    result = target_prod.publish(sel)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.record is None


# =========================================================================
# 13. Positive applicability record fields contain required provenance
# =========================================================================

def test_positive_record_has_required_provenance_fields() -> None:
    req = {
        "record_id",
        "document_id",
        "revision_id",
        "source_sha256",
        "snapshot_id",
        "page_id",
        "decision_scope_id",
        "opening_identity_id",
        "host_binding_record_id",
        "physical_void_record_id",
        "target_scope_id",
        "target_scope_record_id",
        "rule_record_id",
        "rule_version",
    }
    assert is_dataclass(OpeningDeductionApplicabilityRecord)
    names = {f.name for f in fields(OpeningDeductionApplicabilityRecord)}
    missing = req - names
    assert not missing, f"Missing provenance fields: {sorted(missing)}"


# =========================================================================
# 14. Applicability record must not mint downstream outputs
# =========================================================================

def test_positive_record_does_not_mint_net_wall_firm_or_jobhub() -> None:
    forbidden_tokens = ("net_wall", "firm", "commercial_quantity", "jobhub")
    names = {f.name.lower() for f in fields(OpeningDeductionApplicabilityRecord)}
    assert not any(any(t in n for t in forbidden_tokens) for n in names)


# =========================================================================
# 15. Selector fields are address-only — no caller truth
# =========================================================================

def test_selector_is_address_only_not_applicability_truth() -> None:
    forbidden = {
        "deductible",
        "deduction_allowed",
        "applicable",
        "is_applicable",
        "trade",
        "trade_id",
        "finish",
        "finish_id",
        "assembly",
        "assembly_id",
        "rule",
        "rule_id",
        "rule_version",
        "area",
        "width",
        "height",
    }
    assert is_dataclass(OpeningDeductionApplicabilitySelector)
    names = {f.name for f in fields(OpeningDeductionApplicabilitySelector)}
    assert not (names & forbidden)


# =========================================================================
# 16. Duplicate identical token → deterministic (not conflict)
# =========================================================================

def test_duplicate_identical_token_is_deterministic_not_conflict() -> None:
    """Exact-duplicate token bytes with identical payload_key must not produce conflict."""
    token = f"ODTARGET(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly={ASSEMBLY})"
    pdf = _build_pdf(
        odtarget_token=token,
        odrule_token=(
            f"ODRULE(target={TARGET},opening=W1,trade={TRADE},finish={FINISH},assembly={ASSEMBLY},"
            f"id={RULE_ID},version={RULE_VER},decision=DEDUCT)"
        ),
        additional_tokens=(token,),  # exact duplicate
    )
    src, published, void_prod, host_prod, sched_prod, opening_sel, void_sel, opening_rec = (
        _build_void_chain(pdf, "dedup-doc")
    )
    rev, snap = published.revision, published.snapshot
    sel = _app_selector(rev, snap, opening_rec)

    target_prod = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=src,
        schedule_binding_authority=sched_prod.authority(),
        host_binding_authority=host_prod.authority(),
    )
    result = target_prod.publish(sel)
    # Exact duplicates must resolve deterministically (CORROBORATED, not CONFLICT)
    assert result.status is EvidenceResolutionStatus.CORROBORATED


# =========================================================================
# 17. Authority resolve is selector-only
# =========================================================================

def test_authority_resolve_and_publish_are_selector_only() -> None:
    resolve_params = set(
        inspect.signature(OpeningDeductionApplicabilityAuthority.resolve).parameters
    )
    publish_params = set(
        inspect.signature(OpeningDeductionApplicabilityProducer.publish).parameters
    )
    assert resolve_params == {"self", "selector"}
    assert publish_params == {"self", "selector"}


# =========================================================================
# 18. Factory consumes only sealed upstream authorities
# =========================================================================

def test_factory_consumes_sealed_upstream_authorities_not_caller_truth() -> None:
    factory_params = set(
        inspect.signature(
            OpeningDeductionApplicabilityProducer.from_authorities
        ).parameters
    )
    assert {
        "physical_void_authority",
        "host_binding_authority",
        "target_scope_authority",
        "rule_authority",
    } <= factory_params
    forbidden = {
        "deductible",
        "trade",
        "finish",
        "assembly",
        "rule_version",
        "applicable",
        "commercial_applicability",
    }
    assert not (factory_params & forbidden)


# =========================================================================
# 19. Source does not import legacy standards or geometry shortcuts
# =========================================================================

def test_source_requires_exact_joins_and_no_heuristic_shortcuts() -> None:
    import importlib.util
    from pathlib import Path
    spec = importlib.util.find_spec("pb_opening_deduction_applicability_authority")
    assert spec is not None
    source = Path(spec.origin).read_text(encoding="utf-8")
    lower = source.lower()
    required = (
        "pb_physical_opening_void_authority",
        "pb_opening_host_binding_authority",
        "physical_void_record_id",
        "host_binding_record_id",
        "target_scope_record_id",
        "rule_record_id",
        "rule_version",
    )
    missing = [f for f in required if f not in source]
    assert not missing, f"Missing required source fragments: {missing}"
    forbidden = (
        "as4041",
        "nearest_target",
        "first_target",
        "default_target",
        "max(confidence",
        "sorted(rules)[0]",
        "rules[0]",
    )
    present = [f for f in forbidden if f in lower]
    assert not present, f"Forbidden shortcut present: {present}"
