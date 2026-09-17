"""Final behavioral replay for Items 13 and 14.

TEST ONLY / DRAFT / NEVER MERGE.

This successor turns the formerly expected-red distinct-opening attack from #460 into
an ordinary assertion and exercises the exact source-backed applicability/deduction
chain without caller applicability truth or default measurement rules.
"""
from __future__ import annotations

import dataclasses
from types import SimpleNamespace

import fitz
import pytest

import tests.test_physical_opening_void_authority as void_tests
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT,
    OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,
    OpeningDeductionApplicabilityProducer,
    OpeningDeductionApplicabilitySelector,
    OpeningDeductionRuleProducer,
    OpeningDeductionTargetScopeProducer,
)
from pb_opening_deduction_authority import (
    OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED,
    OPENING_DEDUCTION_AUTHORIZED,
    OpeningDeductionProducer,
    OpeningDeductionSelector,
)
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


_BASE_PDF = void_tests._pdf
TARGET = "WALL-A-FINISH"
TRADE = "WALLING"
FINISH = "PAINT"
ASSEMBLY = "A1"


def _target_line(
    *,
    opening: str = "W1",
    trade: str = TRADE,
    finish: str = FINISH,
    assembly: str = ASSEMBLY,
) -> str:
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
        # Deliberately outside the opening schedule region.
        y = 330.0
        for text in lines:
            page.insert_text(fitz.Point(20.0, y), text, fontsize=5.0)
            y += 16.0
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _chain(
    monkeypatch: pytest.MonkeyPatch,
    lines: tuple[str, ...],
    *,
    partial_source: bool = False,
):
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

    # Corrupt only the source-universe completeness seen by the applicability
    # producers. The authenticated physical chain above remains healthy.
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

    rule_producer = OpeningDeductionRuleProducer.from_source_visibility_producer(
        source,
        target_scope_authority=target_producer.authority(),
    )
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
        void_producer=void_producer,
        void_result=void_result,
        host_producer=host_producer,
        target_producer=target_producer,
        rule_producer=rule_producer,
        applicability_producer=applicability_producer,
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
    assert result.applicability.record is None


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


@pytest.mark.parametrize(
    ("rule_line", "reason"),
    (
        (_rule_line(trade="PLASTERING"), OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH),
        (_rule_line(finish="TILE"), OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH),
        (_rule_line(assembly="A2"), OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH),
    ),
)
def test_wrong_trade_finish_and_assembly_fail_closed(monkeypatch, rule_line: str, reason: str) -> None:
    result = _chain(monkeypatch, (_target_line(), rule_line))
    assert result.rule.status is EvidenceResolutionStatus.CORROBORATED
    assert result.applicability.status is EvidenceResolutionStatus.CONFLICT
    assert reason in result.applicability.reason_codes
    assert result.applicability.record is None


def test_duplicate_identical_rule_observations_do_not_duplicate_authority(monkeypatch) -> None:
    rule = _rule_line()
    result = _chain(monkeypatch, (_target_line(), rule, rule))
    assert result.rule.status is EvidenceResolutionStatus.CORROBORATED
    assert result.applicability.status is EvidenceResolutionStatus.CORROBORATED
    assert result.applicability.record is not None


def test_same_target_rule_for_distinct_opening_is_not_a_competing_rule(monkeypatch) -> None:
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
    assert result.applicability.record is not None


@pytest.mark.parametrize(
    "field",
    ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id"),
)
def test_stale_lineage_addresses_never_resolve_applicability(monkeypatch, field: str) -> None:
    result = _chain(monkeypatch, (_target_line(), _rule_line()))
    stale = dataclasses.replace(result.selector, **{field: f"stale-{field}"})
    replay = result.applicability_producer.publish(stale)
    assert replay.status is not EvidenceResolutionStatus.CORROBORATED
    assert replay.record is None


def test_same_geometry_in_distinct_source_lineages_keeps_distinct_applicability_identity(monkeypatch) -> None:
    first = _chain(monkeypatch, (_target_line(), _rule_line(rule_id="R-A")))
    assert first.applicability.record is not None
    first_void = first.void_result.record
    assert first_void is not None

    monkeypatch.undo()
    second = _chain(monkeypatch, (_target_line(), _rule_line(rule_id="R-B")))
    assert second.applicability.record is not None
    second_void = second.void_result.record
    assert second_void is not None

    assert (first_void.u0, first_void.u1, first_void.z0, first_void.z1) == pytest.approx(
        (second_void.u0, second_void.u1, second_void.z0, second_void.z1)
    )
    assert first.selector.source_sha256 != second.selector.source_sha256
    assert first.selector.opening_identity_id != second.selector.opening_identity_id
    assert first.applicability.record.record_id != second.applicability.record.record_id


def test_item14_requires_positive_applicability_and_retains_its_provenance(monkeypatch) -> None:
    result = _chain(monkeypatch, (_target_line(), _rule_line()))
    assert result.applicability.record is not None
    producer = OpeningDeductionProducer.from_authorities(
        physical_void_authority=result.void_producer.authority(),
        host_binding_authority=result.host_producer.authority(),
        opening_universe_authority=result.void_producer._universe,
        target_applicability_authority=result.applicability_producer.authority(),
    )
    selector = OpeningDeductionSelector(**dataclasses.asdict(result.selector))
    deduction = producer.publish(selector)
    assert deduction.status is EvidenceResolutionStatus.CORROBORATED
    assert deduction.reason_codes == (OPENING_DEDUCTION_AUTHORIZED,)
    assert deduction.record is not None
    assert deduction.record.applicability_record_id == result.applicability.record.record_id
    assert deduction.record.physical_void_record_id == result.void_result.record.record_id


def test_item14_unknown_target_stays_unknown_not_zero_or_authorized(monkeypatch) -> None:
    result = _chain(monkeypatch, (_target_line(), _rule_line()))
    producer = OpeningDeductionProducer.from_authorities(
        physical_void_authority=result.void_producer.authority(),
        host_binding_authority=result.host_producer.authority(),
        opening_universe_authority=result.void_producer._universe,
        target_applicability_authority=result.applicability_producer.authority(),
    )
    selector = OpeningDeductionSelector(
        document_id=result.selector.document_id,
        revision_id=result.selector.revision_id,
        source_sha256=result.selector.source_sha256,
        snapshot_id=result.selector.snapshot_id,
        page_id=result.selector.page_id,
        decision_scope_id=result.selector.decision_scope_id,
        opening_identity_id=result.selector.opening_identity_id,
        target_scope_id="UNKNOWN-TARGET",
    )
    deduction = producer.publish(selector)
    assert deduction.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED in deduction.reason_codes
    assert deduction.record is None
