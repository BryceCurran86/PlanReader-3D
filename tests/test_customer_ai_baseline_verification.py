"""Regression: customer AI baseline must retain the sealed quantity."""
from __future__ import annotations

import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent))
from test_customer_output_verification import sealed_and_rows
from pb_customer_output_verification import (
    CustomerOutputVerificationError, verify_sealed_customer_output,
)


@pytest.mark.parametrize("replacement", (None, True, "invalid", 1000.0))
def test_forged_baseline_rejected(replacement):
    sealed, rows = sealed_and_rows()
    altered = dict(rows[0], ai_baseline_quantity=replacement)
    with pytest.raises(CustomerOutputVerificationError, match="baseline"):
        verify_sealed_customer_output(sealed, [altered, rows[1]])


def test_persisted_baseline_numeric_string_accepted():
    sealed, rows = sealed_and_rows()
    persisted = dict(rows[0], ai_baseline_quantity="12.5")
    assert verify_sealed_customer_output(sealed, [persisted, rows[1]]).valid_quantity_count == 2
