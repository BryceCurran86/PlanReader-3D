"""Independent red-team coverage for opening-height unit application.

TEST ONLY / REPLAY against production head 5217504851ef... / DO NOT MERGE.
Assertions and adversarial fixtures are unchanged from the prior replay.

The production proposition requires explicit source units to govern the
published physical-opening height. A metre-labelled source must never allow a
mm-like legacy parser value to be re-labelled as metres without applying the
source unit to the governing source cell.
"""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_pb_opening_height_authority import _fixture, _publish_row


def test_metres_header_cannot_relabel_unitless_mm_like_height() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (("MARK", "ROWDTH-M", "ROHT-M"), ("W1", "900", "2100"))
    )
    assert binding_result.status is EvidenceResolutionStatus.CORROBORATED
    assert binding_result.record is not None
    assert binding_result.record.schedule_row_height_mm == 2100

    _row_selector, result = _publish_row(binding_result, row_height)

    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is None


def test_metres_dims_cell_cannot_preserve_mm_like_legacy_pair() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (("MARK", "RO SIZE-M"), ("W1", "900x2100m"))
    )
    assert binding_result.status is EvidenceResolutionStatus.CORROBORATED
    assert binding_result.record is not None
    assert binding_result.record.schedule_row_height_mm == 2100

    _row_selector, result = _publish_row(binding_result, row_height)

    # Legacy parse_dimension sees 900x2100 before the trailing metre token.
    # Semantic authority must apply metres to 2100, making it implausible, and
    # therefore fail closed instead of publishing 2100 mm as metre-sourced.
    assert result.status is not EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is None


def test_explicit_metres_dims_pair_still_normalizes_to_mm() -> None:
    _src, _binding, binding_result, row_height, _selector = _fixture(
        (("MARK", "RO SIZE-M"), ("W1", "0.9m x 2.1m"))
    )
    assert binding_result.status is EvidenceResolutionStatus.CORROBORATED
    assert binding_result.record is not None
    # Exact row binding does not depend on legacy dimension convenience fields.
    # The semantic-height layer must parse the producer-owned trusted cell itself.
    assert binding_result.record.schedule_row_height_mm is None

    _row_selector, result = _publish_row(binding_result, row_height)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.height_mm == 2100.0
    assert result.evidence.source_units == "m"
