"""A missing original PDF wall primitive must not disappear before registration."""
from __future__ import annotations

import pytest

from tools.diag_gpt2_ft3_cross_sheet_native_wall_pairs import (
    require_complete_original_native_source_primitive_ids as require_all,
)


def _native():
    return {
        "original-d0i0": {"id": "original-d0i0"},
        "original-d1i0": {"id": "original-d1i0"},
    }


@pytest.mark.parametrize("source_ids", [
    ("original-d0i0", "missing-original-d2i0"),
    ("missing-original-d2i0", "original-d0i0"),
])
def test_missing_indexed_original_w4_wall_cannot_be_dropped_from_registration(source_ids):
    with pytest.raises(ValueError, match="original_source_native_primitive_universe_incomplete"):
        require_all(source_ids, _native(), page_id=11)


@pytest.mark.parametrize("ids", [
    (),
    ("original-d0i0", "original-d0i0"),
    ("original-d0i0", None),
    ("original-d0i0", []),
    ("original-d0i0", " original-d1i0 "),
    "original-d0i0",
])
def test_source_primitive_universe_must_be_typed_exact_and_unique(ids):
    with pytest.raises(ValueError, match="original_source_native_primitive_universe_invalid"):
        require_all(ids, _native(), page_id=7)


def test_source_original_walls_keep_identity_and_input_order_without_election():
    ids = ("original-d1i0", "original-d0i0")
    assert require_all(ids, _native(), page_id=7) == ids


def test_zero_and_noninteger_source_page_never_authenticates_native_wall():
    for page in (0, None, "11", -1, True):
        with pytest.raises(ValueError, match="original_source_native_primitive_universe_invalid"):
            require_all(("original-d0i0",), _native(), page_id=page)
