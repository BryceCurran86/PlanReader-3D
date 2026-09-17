"""Regression: rules for another physical opening cannot create a false conflict."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
)
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
