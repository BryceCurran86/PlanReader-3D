"""Only exact positive SQLite primary keys can retain reviewed commercial rows.

Source-neutral source-blocked claim controls, not original-PDF FIRM authority.
"""
from __future__ import annotations

import json
import pytest

from pb_takeoff_output_supersedence import (
    blocked_commercial_claim_key,
    select_prior_reviewed_row_ids_to_retain,
)
from test_takeoff_output_supersedence import (
    SHA_A, SHA_B, blocked_quantity, prior_row, reviewed_prior_row,
)


def _key(sha=SHA_A):
    key = blocked_commercial_claim_key(blocked_quantity(), source_sha256=sha)
    assert key is not None
    return key


@pytest.mark.parametrize("forged", [
    None, False, True, "17", "017", " 17 ", "", "-17", 0, -1,
    17.0, 17.9, 1e308, float("nan"), float("inf"),
    b"17", [17], {"id": 17},
])
def test_aliased_reviewed_row_id_cannot_preserve_wrong_sqlite_row(forged):
    row = reviewed_prior_row(row_id=17)
    row["id"] = forged
    with pytest.raises(ValueError, match="exact positive integer"):
        select_prior_reviewed_row_ids_to_retain(
            [row], blocked_claim_keys=(_key(),),
        )


def test_two_independent_reviewed_physical_ids_replay_exactly():
    key_a = _key()
    key_b = blocked_commercial_claim_key(
        blocked_quantity(
            quantity_id="blocked-2", semantic_key="room_area:room-2",
            input_entity_ids=("room-2",),
        ), source_sha256=SHA_A,
    )
    assert key_b is not None
    first = reviewed_prior_row(row_id=17)
    second = reviewed_prior_row(row_id=18)
    p = json.loads(second["notes"])
    p["quantity"]["semantic_key"] = "room_area:room-2"
    p["quantity"]["input_entity_ids"] = ["room-2"]
    p["source_trace"]["canonical_entity_ids"] = ["room-2"]
    second["notes"] = json.dumps(p, sort_keys=True)
    assert select_prior_reviewed_row_ids_to_retain(
        [first, second], blocked_claim_keys=(key_b, key_a),
    ) == (17, 18)


def test_mismatched_source_refuses_retention_before_row_identity():
    row = reviewed_prior_row(row_id="017", sha=SHA_A)
    assert select_prior_reviewed_row_ids_to_retain(
        [row], blocked_claim_keys=(_key(SHA_B),),
    ) == ()
    with pytest.raises(ValueError, match="exact positive integer"):
        select_prior_reviewed_row_ids_to_retain(
            [row], blocked_claim_keys=(_key(SHA_A),),
        )


def test_replacement_wins_without_minting_an_alias_id():
    row = reviewed_prior_row(row_id="017")
    assert select_prior_reviewed_row_ids_to_retain(
        [row], blocked_claim_keys=(_key(),),
        replacement_rows=(prior_row(),),
    ) == ()


def test_positive_integer_retention_and_empty_input_remain_stable():
    assert select_prior_reviewed_row_ids_to_retain(
        [reviewed_prior_row(row_id=17)], blocked_claim_keys=(_key(),),
    ) == (17,)
    assert select_prior_reviewed_row_ids_to_retain(
        [], blocked_claim_keys=(_key(),),
    ) == ()
