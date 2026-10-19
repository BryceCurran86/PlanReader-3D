"""Original figured-total source rivals remain complete under value indexing."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.test_gpt2_exterior_overhead_soffit_source_census_shadow import (
    _synthetic,
)
from tools.diag_gpt2_exterior_overhead_soffit_source_census_shadow import (
    audit_exterior_overhead_source_census_shadow as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _naive_original_rivals(result):
    """Independent quadratic reference for exactly the returned source words."""
    words = result["original_figured_number_candidates"]
    for chain in result["all_competing_figured_arithmetic_chains"]:
        block = chain["component_source_word_addresses"][0][1]
        total = chain["arithmetic_total_untrusted"]
        expected = tuple(
            row["source_word_address"] for row in words
            if row["printed_value_untrusted"] == total
            and row["source_word_address"][1] != block
        )
        assert chain["rival_total_source_word_addresses"] == expected


def test_exact_index_is_equivalent_to_all_page_scanned_source_numbers():
    raw = _synthetic()
    result = audit(
        raw,
        expected_sha256=hashlib.sha256(raw).hexdigest(),
        page_number=1, material_code="STP",
    )
    assert len(result["all_competing_figured_arithmetic_chains"]) == 1
    _naive_original_rivals(result)
    assert result["exterior_soffit_area_m2"] is None
    assert result["new_firm_quantities"] == 0


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="private original unavailable")
def test_unchanged_real_a253_all_number_rivals_vs_naive_original_scan():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = audit(raw, expected_sha256=SHA, page_number=18, material_code="STP")
    assert result["all_competing_figured_arithmetic_chains"]
    _naive_original_rivals(result)
    assert result["new_firm_quantities"] == 0


def test_wrong_source_sha_fails_closed_before_indexing():
    raw = _synthetic()
    with pytest.raises(ValueError, match="immutable_original_pdf_source_sha"):
        audit(raw, expected_sha256="0" * 64,
              page_number=1, material_code="STP")
