"""Public source-neutral Lot16 revision authority checks."""
import pytest
from tools.diag_gptmax_lot16_revision_870_source import _hash_file


def test_nonoriginal_source_bytes_are_rejected(tmp_path):
    sample = tmp_path / 'substitute.pdf'
    sample.write_bytes(b'not original')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        _hash_file(sample, '0' * 64)
