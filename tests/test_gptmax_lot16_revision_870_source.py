"""Original Lot16 source census regression, only when source PDFs exist."""
import os
from pathlib import Path
import pytest
from tools.diag_gptmax_lot16_revision_870_source import source_census

A = Path(os.getenv('LOT16_ARCH_ORIGINAL', '/missing/architectural.pdf'))
S = Path(os.getenv('LOT16_STRUCT_ORIGINAL', '/missing/structural.pdf'))

@pytest.mark.skipif(not (A.is_file() and S.is_file()), reason='original PDFs unavailable')
def test_original_census_keeps_unproven_host_abstained():
    result = source_census(A, S)
    assert result['canonical_w4_host'] == 'ABSTAIN'
    assert result['new_firm_quantity'] is False
