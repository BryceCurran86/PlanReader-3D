"""Negative-only strict persisted customer notes provenance checks."""
from __future__ import annotations

import json
import pytest

from pb_customer_output_verification import (
    CustomerOutputVerificationError,
    _strict_customer_notes,
)


@pytest.mark.parametrize("bad", [
    '{"adapter":"commercial_takeoff","extra":NaN}',
    '{"adapter":"commercial_takeoff","extra":Infinity}',
    '{"adapter":"commercial_takeoff","extra":-Infinity}',
    '{"adapter":"commercial_takeoff","extra":1e10000}',
    '{"adapter":"commercial_takeoff","extra":' + '9' * 400 + '}',
    '{"adapter":"commercial_takeoff","source":{"sha":"a","sha":"b"}}',
    '{"adapter":"commercial_takeoff","quantity":{"quantity_id":"a","quantity_id":"b"}}',
    '{"adapter":"commercial_takeoff","extra":' + '[' * 513 + '0' + ']' * 513 + '}',
])
def test_rejects_invalid_embedded_machine_provenance(bad: str) -> None:
    with pytest.raises(CustomerOutputVerificationError):
        _strict_customer_notes(bad)


def test_duplicate_provenance_reason_is_backward_compatible() -> None:
    with pytest.raises(CustomerOutputVerificationError, match="duplicate provenance key: quantity_id"):
        _strict_customer_notes('{"adapter":"commercial_takeoff","quantity_id":"a","quantity_id":"b"}')


def test_valid_notes_preserve_values_and_escaped_brackets() -> None:
    expected = {
        "adapter": "commercial_takeoff",
        "quantity": {"quantity_id": "q", "numeric_metadata": 12345678901234567890},
        "literal": 'an escaped "quote" and [not nesting]',
        "enabled": True,
        "absent": None,
    }
    notes = json.dumps(expected, ensure_ascii=False)
    assert _strict_customer_notes(notes) == expected
    assert notes == json.dumps(expected, ensure_ascii=False)


def test_top_level_non_object_fails_closed() -> None:
    with pytest.raises(CustomerOutputVerificationError, match="not an object"):
        _strict_customer_notes('["commercial_takeoff"]')
