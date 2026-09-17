"""Behavioral production tests for Item 14 target applicability and deduction."""
from __future__ import annotations

import dataclasses

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
    OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT,
    OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,
    OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH,
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
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer as RealSourceVisibilityProducer
import tests.test_physical_opening_void_authority as void_tests


TARGET_ID = "wall-finish-1"
TARGET_TOKEN = "ODTARGET(target=wall-finish-1,opening=W1,trade=PAINT,finish=LOW-SHEEN,assembly=INT-WALL)"
RULE_TOKEN = "ODRULE(target=wall-finish-1,opening=W1,trade=PAINT,finish=LOW-SHEEN,assembly=INT-WALL,id=project-mom,version=1,decision=DEDUCT)"


def _setup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    target_token: str = TARGET_TOKEN,
    rule_tokens: tuple[str, ...] = (RULE_TOKEN,),
):
    created: list[RealSourceVisibilityProducer] = []
    original_pdf = void_tests._pdf

    def capture_source(*, producer_method: str, producer_version: str):
        source = RealSourceVisibilityProducer(
            producer_method=producer_method,
            producer_version=producer_version,
        )
        created.append(source)
        return source

    def patched_pdf(*, width_text: str = "900", height_text: str = "2100") -> bytes:
        raw = original_pdf(width_text=width_text, height_text=height_text)
        doc = fitz.open(stream=raw, filetype="pdf")
        try:
            page = doc.load_page(0)
            y = 570.0
            if target_token:
                page.insert_text(fitz.Point(10.0, y), target_token, fontsize=4.5)
                y += 18.0
            for token in rule_tokens:
                page.insert_text(fitz.Point(10.0, y), token, fontsize=4.5)
                y += 18.0
            return bytes(doc.tobytes(garbage=4, deflate=True))
        finally:
            doc.close()

    monkeypatch.setattr(void_tests, "SourceVisibilityProducer", capture_source)
    monkeypatch.setattr(void_tests, "_pdf", patched_pdf)
    void_producer, opening_selector, void_selector = void_tests._fixture()
    assert len(created) == 1
    source = created[0]
    void_result = void_producer.publish(
        opening_selector=opening_selector,
        selector=void_selector,
    )
    assert void_result.status is EvidenceResolutionStatus.CORROBORATED
    assert void_result.record is not None

    schedule = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    schedule_result = schedule.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=void_selector.decision_scope_id,
    )
    assert schedule_result.status is EvidenceResolutionStatus.CORROBORATED
    assert schedule_result.record is not None

    selector = OpeningDeductionApplicabilitySelector(
        document_id=void_selector.document_id,
        revision_id=void_selector.revision_id,
        source_sha256=void_selector.source_sha256,
        snapshot_id=void_selector.snapshot_id,
        page_id=void_selector.page_id,
        decision_scope_id=void_selector.decision_scope_id,
        opening_identity_id=void_selector.opening_identity_id,
        target_scope_id=TARGET_ID,
    )
    target = OpeningDeductionTargetScopeProducer.from_authorities(
        source_visibility_producer=source,
        schedule_binding_authority=schedule.authority(),
        host_binding_authority=void_producer._host,
    )
    target_result = target.publish(selector)
    target_authority = target.authority()
    rule = OpeningDeductionRuleProducer.from_source_visibility_producer(
        source,
        target_scope_authority=target_authority,
    )
    rule_result = rule.publish(selector)
    rule_authority = rule.authority()
    applicability = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=void_producer.authority(),
        host_binding_authority=void_producer._host,
        target_scope_authority=target_authority,
        rule_authority=rule_authority,
    )
    return (
        void_producer,
        selector,
        target_result,
        rule_result,
        target_authority,
        rule_authority,
        applicability,
    )


def test_real_source_target_and_rule_publish_positive_applicability(monkeypatch: pytest.MonkeyPatch) -> None:
    _, selector, target, rule, _, _, applicability = _setup(monkeypatch)
    assert target.status is EvidenceResolutionStatus.CORROBORATED
    assert rule.status is EvidenceResolutionStatus.CORROBORATED
    result = applicability.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_DEDUCTION_APPLICABILITY_RESOLVED,)
    assert result.record is not None
    assert result.record.opening_identity_id == selector.opening_identity_id
    assert result.record.target_scope_id == TARGET_ID


@pytest.mark.parametrize(
    ("rule_token", "reason"),
    (
        (
            "ODRULE(target=wall-finish-1,opening=W1,trade=PLASTER,finish=LOW-SHEEN,assembly=INT-WALL,id=project-mom,version=1,decision=DEDUCT)",
            OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,
        ),
        (
            "ODRULE(target=wall-finish-1,opening=W1,trade=PAINT,finish=HIGH-GLOSS,assembly=INT-WALL,id=project-mom,version=1,decision=DEDUCT)",
            OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH,
        ),
        (
            "ODRULE(target=wall-finish-1,opening=W1,trade=PAINT,finish=LOW-SHEEN,assembly=EXT-WALL,id=project-mom,version=1,decision=DEDUCT)",
            OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH,
        ),
    ),
)
def test_wrong_trade_finish_or_assembly_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    rule_token: str,
    reason: str,
) -> None:
    _, selector, _, _, _, _, applicability = _setup(monkeypatch, rule_tokens=(rule_token,))
    result = applicability.publish(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert reason in result.reason_codes
    assert result.record is None


def test_conflicting_rule_versions_fail_closed_without_latest_winner(monkeypatch: pytest.MonkeyPatch) -> None:
    second = RULE_TOKEN.replace("version=1", "version=2")
    _, selector, _, rule, _, _, applicability = _setup(
        monkeypatch,
        rule_tokens=(RULE_TOKEN, second),
    )
    assert rule.status is EvidenceResolutionStatus.CONFLICT
    result = applicability.publish(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT in result.reason_codes
    assert result.record is None


def test_duplicate_identical_rule_observation_does_not_create_a_second_rule(monkeypatch: pytest.MonkeyPatch) -> None:
    _, selector, _, rule, _, _, applicability = _setup(
        monkeypatch,
        rule_tokens=(RULE_TOKEN, RULE_TOKEN),
    )
    assert rule.status is EvidenceResolutionStatus.CORROBORATED
    result = applicability.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None


def test_wrong_host_authority_cannot_authorize_target(monkeypatch: pytest.MonkeyPatch) -> None:
    first_void, selector, target, rule, target_authority, rule_authority, _ = _setup(monkeypatch)
    assert target.status is EvidenceResolutionStatus.CORROBORATED
    assert rule.status is EvidenceResolutionStatus.CORROBORATED

    monkeypatch.undo()
    second_rule = RULE_TOKEN.replace("version=1", "version=9")
    second_void, _, _, _, _, _, _ = _setup(monkeypatch, rule_tokens=(second_rule,))
    applicability = OpeningDeductionApplicabilityProducer.from_authorities(
        physical_void_authority=first_void.authority(),
        host_binding_authority=second_void._host,
        target_scope_authority=target_authority,
        rule_authority=rule_authority,
    )
    result = applicability.publish(selector)
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH in result.reason_codes
    assert result.record is None


def test_item14_requires_and_retains_positive_applicability(monkeypatch: pytest.MonkeyPatch) -> None:
    void_producer, app_selector, _, _, _, _, applicability = _setup(monkeypatch)
    app_result = applicability.publish(app_selector)
    assert app_result.status is EvidenceResolutionStatus.CORROBORATED
    assert app_result.record is not None

    deduction_selector = OpeningDeductionSelector(**dataclasses.asdict(app_selector))
    producer = OpeningDeductionProducer.from_authorities(
        physical_void_authority=void_producer.authority(),
        host_binding_authority=void_producer._host,
        opening_universe_authority=void_producer._universe,
        target_applicability_authority=applicability.authority(),
    )
    result = producer.publish(deduction_selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_DEDUCTION_AUTHORIZED,)
    assert result.record is not None
    assert result.record.applicability_record_id == app_result.record.record_id
    assert result.record.physical_void_record_id == app_result.record.physical_void_record_id


def test_item14_unknown_target_never_becomes_zero_or_authorized(monkeypatch: pytest.MonkeyPatch) -> None:
    void_producer, app_selector, _, _, _, _, applicability = _setup(monkeypatch)
    applicability.publish(app_selector)
    producer = OpeningDeductionProducer.from_authorities(
        physical_void_authority=void_producer.authority(),
        host_binding_authority=void_producer._host,
        opening_universe_authority=void_producer._universe,
        target_applicability_authority=applicability.authority(),
    )
    selector = OpeningDeductionSelector(
        document_id=app_selector.document_id,
        revision_id=app_selector.revision_id,
        source_sha256=app_selector.source_sha256,
        snapshot_id=app_selector.snapshot_id,
        page_id=app_selector.page_id,
        decision_scope_id=app_selector.decision_scope_id,
        opening_identity_id=app_selector.opening_identity_id,
        target_scope_id="different-target",
    )
    result = producer.publish(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED in result.reason_codes
    assert result.record is None
