"""Regression: applicability preserves exact opening identity, not geometry equality."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
)
from pb_physical_opening_void_authority import PhysicalOpeningVoidSelector
from tests.test_opening_deduction_applicability_production_v1 import (
    RULE_TOKEN,
    _setup,
)


def test_same_target_rule_for_distinct_opening_is_not_a_competing_rule(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    unrelated = (
        "ODRULE(target=wall-finish-1,opening=D2,trade=PAINT,finish=LOW-SHEEN,"
        "assembly=INT-WALL,id=other-opening-rule,version=1,decision=RETAIN)"
    )
    _, selector, target, rule, _, _, applicability = _setup(
        monkeypatch,
        rule_tokens=(RULE_TOKEN, unrelated),
    )
    assert target.status is EvidenceResolutionStatus.CORROBORATED
    assert rule.status is EvidenceResolutionStatus.CORROBORATED
    assert rule.record is not None
    assert rule.record.opening_mark == "W1"
    result = applicability.publish(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_DEDUCTION_APPLICABILITY_RESOLVED,)
    assert result.record is not None


def _void_result(void_producer, selector):
    return void_producer.authority().resolve(
        PhysicalOpeningVoidSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
        )
    )


def test_identical_void_geometry_in_distinct_authenticated_lineages_never_collapses_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_void_producer, first_selector, _, _, _, _, first_applicability = _setup(
        monkeypatch,
        rule_tokens=(RULE_TOKEN,),
    )
    first_app = first_applicability.publish(first_selector)
    first_void = _void_result(first_void_producer, first_selector)
    assert first_app.status is EvidenceResolutionStatus.CORROBORATED
    assert first_app.record is not None
    assert first_void.status is EvidenceResolutionStatus.CORROBORATED
    assert first_void.record is not None

    # Change only authenticated rule-source text. The drawn opening, scale, height,
    # host geometry and resulting wall-local physical void stay the same, while the
    # immutable source revision and opening lineage become distinct.
    monkeypatch.undo()
    second_rule = RULE_TOKEN.replace("id=project-mom", "id=project-mom-revision-b")
    second_void_producer, second_selector, _, _, _, _, second_applicability = _setup(
        monkeypatch,
        rule_tokens=(second_rule,),
    )
    second_app = second_applicability.publish(second_selector)
    second_void = _void_result(second_void_producer, second_selector)
    assert second_app.status is EvidenceResolutionStatus.CORROBORATED
    assert second_app.record is not None
    assert second_void.status is EvidenceResolutionStatus.CORROBORATED
    assert second_void.record is not None

    assert (
        first_void.record.u0,
        first_void.record.u1,
        first_void.record.z0,
        first_void.record.z1,
    ) == pytest.approx(
        (
            second_void.record.u0,
            second_void.record.u1,
            second_void.record.z0,
            second_void.record.z1,
        )
    )
    assert first_selector.source_sha256 != second_selector.source_sha256
    assert first_selector.opening_identity_id != second_selector.opening_identity_id
    assert first_app.record.physical_void_record_id != second_app.record.physical_void_record_id
    assert first_app.record.record_id != second_app.record.record_id
