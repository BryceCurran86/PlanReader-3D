"""Original RCP page authority must not coerce a caller's page into a real one.

Legacy trusted room-area metadata stores canonical decimal strings, so that
strict original page scope must preserve those already-source-issued receipts.
"""
from dataclasses import replace

import pytest

from pb_ceiling_lining_quantity import (
    _base_context_blockers,
    _original_page_no_or_none,
    _source_area_page_no_or_none,
)
from tests.test_c15_ceiling_lining_quantity import (
    _context,
    _document,
    _viewport,
    _area_quantity,
    _build,
)


def test_real_original_native_integer_scope_and_legacy_receipt_both_continue():
    area = _area_quantity()
    assert _build(area=area).value == area.value
    legacy = replace(area, metadata={**dict(area.metadata), "page_no": "1"})
    assert _build(area=legacy).value == area.value
    assert _source_area_page_no_or_none("1") == 1


@pytest.mark.parametrize("invalid", [True, 1.0, 1.5, "1", "01", None, 0, -1])
def test_caller_page_must_be_positive_exact_original_integer(invalid):
    assert _original_page_no_or_none(invalid) is None
    blockers = _base_context_blockers(
        context=_context(), document=_document(), viewport=_viewport(),
        page_no=invalid,
    )
    assert "page_not_owned" in blockers


@pytest.mark.parametrize("invalid", [
    True, 1.0, 1.5, None, 0, -1, "", "0", "01",
    " 1", "1 ", "1.0", "1e0", "+1", "١", "1a",
])
def test_corrupted_source_area_page_metadata_cannot_borrow_authenticated_scope(invalid):
    assert _source_area_page_no_or_none(invalid) is None
    source = _area_quantity()
    forged = replace(source, metadata={**dict(source.metadata), "page_no": invalid})
    result = _build(area=forged)
    assert result.abstained and result.value is None
    assert "upstream_area_page_unbound" in result.blocking_reasons


def test_distinct_authenticated_page_is_a_mismatch_not_coercion():
    source = _area_quantity()
    altered = replace(source, metadata={**dict(source.metadata), "page_no": "2"})
    result = _build(area=altered)
    assert result.abstained and result.value is None
    assert "upstream_area_page_mismatch" in result.blocking_reasons


def test_bad_caller_page_returns_shadow_abstention_without_throwing():
    from tests.test_c15_ceiling_lining_quantity import _finish_atom, SCOPE_ID
    from pb_ceiling_lining_quantity import build_ceiling_lining_quantity
    for page in (True, 1.5, "1", None):
        row = build_ceiling_lining_quantity(
            scope_entity_id=SCOPE_ID,
            area_quantity=_area_quantity(),
            finish_evidence_atoms=(_finish_atom(),),
            context=_context(), document=_document(), viewport=_viewport(),
            page_no=page,
        )
        assert row.abstained and row.value is None
        assert row.metadata["page_no"] is None
