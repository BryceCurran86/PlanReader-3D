"""Adversarial semantic-cell regressions for vertical placement."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_vertical_placement_authority import ROW_VERTICAL_FIELD_UNAVAILABLE
from tests.test_opening_vertical_placement_authority import _fixture, _pdf


@pytest.mark.parametrize(
    "sill_value,head_value",
    [
        ("TYPICAL 900", "3000"),
        ("900 MIN", "3000"),
        ("900", "SEE NOTE 3000"),
        ("NOM 900 mm", "3000"),
    ],
)
def test_decorated_numeric_cells_cannot_mint_exact_vertical_placement(
    sill_value: str,
    head_value: str,
) -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector = _fixture(
        _pdf(sill_value=sill_value, head_value=head_value)
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert ROW_VERTICAL_FIELD_UNAVAILABLE in result.reason_codes
    assert result.evidence is None


def test_exact_numeric_cells_with_matching_units_remain_valid() -> None:
    _src, _binder, _binding, row_producer, row_selector, _opening_selector = _fixture(
        _pdf(sill_value="900 mm", head_value="3000 mm")
    )
    result = row_producer.publish_scope(row_selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.z0_mm == 900.0
    assert result.evidence.z1_mm == 3000.0
