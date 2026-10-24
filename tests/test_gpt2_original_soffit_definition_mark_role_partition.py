"""Material legend words may not double-own original plan-finish occurrence."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from tests.test_gpt2_exterior_overhead_soffit_source_census_shadow import _synthetic
from tools.diag_gpt2_exterior_overhead_soffit_source_census_shadow import (
    audit_exterior_overhead_source_census_shadow as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _assert_partition_is_exact(result):
    all_codes = result["all_original_code_word_candidates"]
    defs = result["original_material_definition_code_addresses"]
    other = result["unclassified_nondefinition_source_code_word_candidates"]
    all_addresses = [tuple(row["source_word_address"]) for row in all_codes]
    nondefinition_addresses = [tuple(row["source_word_address"]) for row in other]
    assert set(defs).isdisjoint(nondefinition_addresses)
    assert sorted(all_addresses) == sorted([*defs, *nondefinition_addresses])
    assert result["nondefinition_code_physical_finish_owner_proven"] is False
    assert result["new_firm_quantities"] == 0
    assert result["exterior_soffit_area_m2"] is None


def test_generic_stp_definition_source_word_is_not_second_physical_mark():
    raw = _synthetic()
    result = audit(raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
                   page_number=1, material_code="STP")
    assert len(result["all_original_code_word_candidates"]) == 2
    assert len(result["original_material_definition_code_addresses"]) == 1
    assert len(result["unclassified_nondefinition_source_code_word_candidates"]) == 1
    _assert_partition_is_exact(result)


def test_absent_definition_preserves_all_unclassified_source_words_without_firm():
    raw = _synthetic()
    result = audit(raw, expected_sha256=hashlib.sha256(raw).hexdigest(),
                   page_number=1, material_code="IPF1")
    assert result["original_material_definition_code_addresses"] == ()
    assert result["unclassified_nondefinition_source_code_word_candidates"] == ()
    _assert_partition_is_exact(result)


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="original owner PDF unavailable")
def test_original_a253_exact_five_stp_words_are_not_five_physical_finish_marks():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = audit(raw, expected_sha256=SHA, page_number=18, material_code="STP")
    assert len(result["all_original_code_word_candidates"]) == 5
    assert result["original_material_definition_code_addresses"] == (
        (18, 108, 0, 0),
    )
    assert len(result["unclassified_nondefinition_source_code_word_candidates"]) == 4
    _assert_partition_is_exact(result)
