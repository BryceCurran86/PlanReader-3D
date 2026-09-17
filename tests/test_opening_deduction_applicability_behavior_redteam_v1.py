"""Real-source behavioral red team for Opening Deduction applicability.

TEST ONLY / DRAFT / DO NOT MERGE.

Runs through native PDF ingestion and the merged physical opening -> host -> void
chain. Target/rule truth must come from the producer-owned complete trusted-text
universe. The tests intentionally never pass caller applicability booleans or
trade/finish/assembly truth into the public applicability selector.
"""
from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

import tests.test_physical_opening_void_authority as void_tests
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import (
    OpeningHostBindingProducer,
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT,
    OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
    OpeningDeductionApplicabilityProducer,
    OpeningDeductionApplicabilitySelector,
    OpeningDeductionRuleProducer,
    OpeningDeductionTargetScopeProducer,
)


_BASE_PDF = void_tests._pdf
TARGET = "WALL-A-FINISH"
TRADE = "WALLING"
FINISH = "PAINT"
ASSEMBLY = "A1"


def _target_line(*, opening: str = "W1", trade: str = TRADE, finish: str = FINISH, assembly: str = ASSEMBLY) -> str:
    return (
        f"ODTARGET(target={TARGET},opening={opening},trade={trade},"
        f"finish={finish},assembly={assembly})"
    )


def _rule_line(
    *,
    opening: str = "W1",
    trade: str = TRADE,
    finish: str = FINISH,
    assembly: str = ASSEMBLY,
    rule_id: str = "R1",
    version: str = "V1",
    decision: str = "DEDUCT",
) -> str:
    return (
        f"ODRULE(target={TARGET},opening={opening},trade={trade},finish={finish},"
        f"assembly={assembly},id={rule_id},version={version},decision={decision})"
    )


def _pdf_with_applicability_lines(
    lines: tuple[str, ...],
    *,
    width_text: str = "900",
    height_text: str = "2100",
) -> bytes:
    payload = _BASE_PDF(width_text=width_text, height_text=height_text)
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        page = doc.load_page(0)
        y = 330.0
        for text in lines:
            page.insert_text(fitz.Point(20.0, y), text, fontsize=5.0)
            y += 16.0
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _chain(monkeypatch: pytest.MonkeyPatch, lines: tuple[str, ...], *, partial_source: bool = False):
    captured: dict[str, SourceVisibilityProducer] = {}

    def _source_factory(*, producer_method: str, producer_version: str) -> SourceVisibilityProducer:
        source = SourceVisibilityProducer(
            producer_method=producer_method,
            producer_version=producer_version,
        )
        captured["source"] = source
        return source

    monkeypatch.setattr(void_tests, "SourceVisibilityProducer", _source_factory)
    monkeypatch.setattr(
        void_tests,
        "_pdf",
        lambda *, width_text="900", height_text="2100": _pdf_with_applicability_lines(
            lines,
            width_text=width_text,
            height_text=height_text,
        ),
    )

    void_producer, opening_selector, void_selector = void_tests._fixture()
    void_result = void_producer.publish(
        opening_selector=opening_selector,
        selector=void_selector,
    )
    assert void_result.status is EvidenceResolutionStatus.CORROBORATED
    assert void_result.record is not None

    source = captured["source"]
    published = source.published_snapshot_for_revision(void_selector.revision_id)
    assert published is not None

    physical = PhysicalOpeningAuthority(source.authority())
    wall_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source
    ).authority()
    wall_universe = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(
        wall_authority
    ).authority()
    host_universe_selector = OpeningHostWallUniverseSelector(
        document_id=void_selector.document_id,
        revision_id=void_selector.revision_id,
        source_sha256=void_selector.source_sha256,
        snapshot_id=void_selector.snapshot_id,
        page_id=void_selector.page_id,
        decision_scope_id=void_selector.decision_scope_id,
    )
    host_producer = OpeningHostBindingProducer.from_authorities(
        physical_opening_authority=physical,
        host_wall_universe_authority=wall_universe,
    )
    host = host_producer.publish(
        opening_left_selector=opening_selector,
        opening_right_selector=opening_selector,
        host_universe_selector=host_universe_selector,
    )
    assert host.status is EvidenceResolutionStatus.CORROBORATED
    assert host.record is not None
    assert host.record.record_id == void_result.record.host_binding_record_id

    schedule_producer = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(
        source
    )
    schedule = schedule_producer.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=void_selector.decision_scope_id,
    )
    assert schedule.status is EvidenceResolutionStatus.CORROBORATED
    assert schedule.record is not None
    assert schedule.record.tag_mark == "W1"

    # Corrupt only the source-universe completeness seen by the target/rule
    # producers. The authenticated opening/host/void/schedule chain above must stay
    # healthy so this test isolates the applicability source-completeness boundary.
    if partial_source:
        object.__setattr__(published.coverage, "state", "partial")
        object.__setattr__(published.coverage, "failed_pages", (1,))

    selector = OpeningDeductionApplicabilitySelector(
        document_id=void_selector.document_id,
        revision_id=void_selector.revision_id,
        source_sha256=void_selector.source_sha256,
        snapshot_id=void_selector.snapshot_id,
        page_id=void_selector.page_id,
        decision_scope_id=void_selector.decision_scope_id,
        opening_identity_id=void_selector.opening_identity_id,
        target_scope_id=TARGET,
    )

    target_producer = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=source,
        schedule_binding_authority=schedule_producer.authority(),
        host_binding_authority=host_producer.authority(),
    )
    target = target_producer.publish(selector)

    rule_producer = OpeningDeductionRuleProducer.from_source_visibility_producer(source)
    rule = rule_producer.publish(selector)

    applicability_producer = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_producer.authority(),
        host_binding_authority=host_producer.authority(),
        target_scope_authority=target_producer.authority(),
        rule_authority=rule_producer.authority(),
    )
    applicability = applicability_producer.publish(selector)
    return SimpleNamespace(
        target=target,
        rule=rule,
        applicability=applicability,
        selector=selector,
        source=source,
    )


def test_exact_source_target_and_deduct_rule_publish_positive_applicability(monkeypatch) -> None:
    result = _chain(monkeypatch, (_target_line(), _rule_line()))
    assert result.target.status is EvidenceResolutionStatus.CORROBORATED
    assert result.rule.status is EvidenceResolutionStatus.CORROBORATED
    assert result.applicability.status is EvidenceResolutionStatus.CORROBORATED
    assert result.applicability.reason_codes == (OPENING_DEDUCTION_APPLICABILITY_RESOLVED,)
    assert result.applicability.record is not None
    assert result.applicability.record.target_scope_record_id == result.target.record.record_id
    assert result.applicability.record.rule_record_id == result.rule.record.record_id


def test_physical_void_plus_target_without_rule_abstains(monkeypatch) -> None:
    result = _chain(monkeypatch, (_target_line(),))
    assert result.target.status is EvidenceResolutionStatus.CORROBORATED
    assert result.rule.status is EvidenceResolutionStatus.ABSTAINED
    assert result.applicability.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED in result.applicability.reason_codes
    assert result.applicability.record is None


def test_explicit_retain_rule_does_not_become_deduction_permission(monkeypatch) -> None:
    result = _chain(monkeypatch, (_target_line(), _rule_line(decision="RETAIN")))
    assert result.rule.status is EvidenceResolutionStatus.CORROBORATED
    assert result.applicability.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED in result.applicability.reason_codes
    assert result.applicability.record is None


def test_conflicting_deduct_and_retain_rules_fail_closed(monkeypatch) -> None:
    result = _chain(
        monkeypatch,
        (
            _target_line(),
            _rule_line(rule_id="R-DEDUCT", decision="DEDUCT"),
            _rule_line(rule_id="R-RETAIN", decision="RETAIN"),
        ),
    )
    assert result.rule.status is EvidenceResolutionStatus.CONFLICT
    assert result.applicability.status is EvidenceResolutionStatus.CONFLICT
    assert OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT in result.applicability.reason_codes
    assert result.applicability.record is None


def test_incomplete_source_universe_cannot_mint_target_or_rule(monkeypatch) -> None:
    result = _chain(
        monkeypatch,
        (_target_line(), _rule_line()),
        partial_source=True,
    )
    assert result.target.status is EvidenceResolutionStatus.ABSTAINED
    assert result.rule.status is EvidenceResolutionStatus.ABSTAINED
    assert result.applicability.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED in result.applicability.reason_codes


def test_conflicting_target_semantics_fail_closed(monkeypatch) -> None:
    result = _chain(
        monkeypatch,
        (
            _target_line(),
            _target_line(trade="PLASTERING"),
            _rule_line(),
        ),
    )
    assert result.target.status is EvidenceResolutionStatus.CONFLICT
    assert result.applicability.status is EvidenceResolutionStatus.CONFLICT
    assert result.applicability.record is None


@pytest.mark.xfail(
    strict=True,
    reason=(
        "rule producer currently resolves conflicts by target only; it must isolate "
        "rules for the exact authenticated opening before treating another opening's "
        "rule as a competitor"
    ),
)
def test_same_target_rules_for_distinct_openings_do_not_false_conflict(monkeypatch) -> None:
    result = _chain(
        monkeypatch,
        (
            _target_line(opening="W1"),
            _rule_line(opening="W1", rule_id="RW1", decision="DEDUCT"),
            _rule_line(opening="D2", rule_id="RD2", decision="RETAIN"),
        ),
    )
    assert result.target.status is EvidenceResolutionStatus.CORROBORATED
    assert result.rule.status is EvidenceResolutionStatus.CORROBORATED
    assert result.rule.record is not None
    assert result.rule.record.opening_mark == "W1"
    assert result.applicability.status is EvidenceResolutionStatus.CORROBORATED
