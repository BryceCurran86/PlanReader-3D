"""3Laurel original-source ASW windows, exact SHA and negative scope gates."""
from pathlib import Path
import pytest
from tools.diag_gpt1_original_3laurel_asw_candidates import (
    ORIGINAL_SHA256, _dimension, _original_token_chain,
    read_original_3laurel_asw_candidates,
)


def _word(token, block, line, num, x0, y0=100):
    return (x0, y0, x0 + 9, y0 + 7, token, block, line, num)


def test_figured_dimension_values_cannot_be_inferred_from_invalid_tokens():
    assert _dimension("1,200") == 1200
    assert _dimension("910") == 910
    assert _dimension("0") is None
    assert _dimension("1.200") is None
    assert _dimension("1,2") is None
    assert _dimension("N/A") is None


def test_same_native_line_and_unique_adjacent_stacked_lines_only():
    same = [_word("1,800", 0, 0, 0, 100), _word("-", 0, 0, 1, 110),
            _word("610", 0, 0, 2, 120), _word("asw", 0, 0, 3, 130)]
    assert _original_token_chain(same) == "same_native_line"
    stacked = same[:3] + [_word("asw", 1, 0, 0, 107, 108)]
    assert _original_token_chain(stacked) == "stacked_native_lines"
    assert _original_token_chain(same[:3] + [_word("asw", 1, 0, 0, 180, 108)]) is None
    assert _original_token_chain(same[:3] + [_word("asw", 1, 0, 0, 107, 130)]) is None
    assert _original_token_chain(same[:3] + [_word("asw", 1, 0, 0, 107, 95)]) is None
    assert _original_token_chain(same[:3] + [_word("asw", 0, 0, 9, 130)]) is None
    backtrack = [_word("600", 0, 0, 0, 100), _word("-", 0, 1, 0, 110, 108),
                 _word("1210", 0, 0, 1, 120), _word("asw", 0, 1, 1, 115, 108)]
    assert _original_token_chain(backtrack) is None


def test_foreign_source_bytes_never_gain_original_identity():
    with pytest.raises(ValueError, match="SHA-verified"):
        read_original_3laurel_asw_candidates(b"%PDF-1.4\nsynthetic")
    with pytest.raises(ValueError, match="SHA-verified"):
        read_original_3laurel_asw_candidates("not bytes")


def test_exact_original_3laurel_source_positive_labels_are_only_candidates():
    original = Path("documents/sources/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf")
    if not original.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: not an original-source pass")
    from hashlib import sha256
    contents = original.read_bytes()
    assert sha256(contents).hexdigest() == ORIGINAL_SHA256
    report = read_original_3laurel_asw_candidates(contents)
    candidates = report["two_axis_candidates"]
    assert len(candidates) == 14
    assert sum(r["source"]["line_layout"] == "stacked_native_lines" for r in candidates) == 4
    assert len(report["non_metric_asw_observations"]) == 0
    assert len({tuple(r["source"][k] for k in ("native_block", "native_line", "first_word"))
                for r in candidates}) == 14
    assert all(r["metric_authority"] == "candidate_only"
               and not r["structural_host_proven"]
               and not r["physical_opening_identity_proven"]
               and not r["signed_quantity_allowed"] for r in candidates)
    assert report["customer_quantity_count"] == 0
    assert report["official_benchmark_match_count"] is None
    expected = ([[1200, 1810]] * 4 + [[1800, 610], [1800, 910]] +
                [[600, 1510]] * 2 + [[1800, 2410]] * 4 +
                [[600, 1210]] * 2)
    assert sorted(r["figured_axes_mm"] for r in candidates) == sorted(expected)
    with pytest.raises(ValueError, match="SHA-verified"):
        read_original_3laurel_asw_candidates(contents + b"altered")
