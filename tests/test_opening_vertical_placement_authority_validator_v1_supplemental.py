"""Supplemental independent attacks for vertical-placement validator v1.

TEST ONLY / EXPECTED RED ON BASELINE / DO NOT MERGE.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_opening_vertical_placement_authority_validator_v1 import (
    EXPECTED_RED,
    _module,
    _placement_pdf,
    _publish_row,
)


@EXPECTED_RED
def test_spaced_rough_opening_headings_resolve_from_authenticated_words() -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(
            sill_heading="ROUGH OPENING SILL-MM",
            head_heading="ROUGH OPENING HEAD-MM",
        ),
    )
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.z0_mm == 900.0
    assert row_result.evidence.z1_mm == 3000.0


@EXPECTED_RED
def test_spaced_clear_opening_headings_remain_non_structural() -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(
            sill_heading="CLEAR OPENING SILL-MM",
            head_heading="CLEAR OPENING HEAD-MM",
        ),
    )
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert row_result.evidence is None


@pytest.mark.parametrize(
    "sill_value,head_value",
    [
        ("TYPICAL 900", "3000"),
        ("900 MIN", "3000"),
        ("900", "SEE NOTE 3000"),
        ("NOM 900 mm", "3000"),
    ],
)
@EXPECTED_RED
def test_decorated_numeric_cells_cannot_mint_exact_vertical_placement(
    sill_value: str,
    head_value: str,
) -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(sill_value=sill_value, head_value=head_value),
    )
    assert row_result.status is EvidenceResolutionStatus.ABSTAINED
    assert row_result.evidence is None


@EXPECTED_RED
def test_exact_numeric_cells_with_explicit_matching_units_still_resolve() -> None:
    mod = _module()
    *_prefix, row_result = _publish_row(
        mod,
        _placement_pdf(sill_value="900 mm", head_value="3000 mm"),
    )
    assert row_result.status is EvidenceResolutionStatus.CORROBORATED
    assert row_result.evidence is not None
    assert row_result.evidence.z0_mm == 900.0
    assert row_result.evidence.z1_mm == 3000.0
