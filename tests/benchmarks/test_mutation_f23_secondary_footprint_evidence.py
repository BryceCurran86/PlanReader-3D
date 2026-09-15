"""Legacy F.23 horizontal-chain suite replaced by orthogonal-depth attacks.

See ``test_mutation_f23_orthogonal_depth.py`` for the governing synthetic
matrix (all four edges, thickness traps, witness requirements, etc.).

This module keeps a narrow regression that F.15's horizontal-chain extractor
API is untouched by the F.23 depth work.
"""
from __future__ import annotations

import inspect

import pb_dimension_chain_evidence_extractor as f15


def test_f15_horizontal_chain_extractor_module_untouched_by_f23_depth_work():
    src = inspect.getsource(f15.extract_dimension_chains_from_page)
    # F.15 remains the horizontal consumer; F.23 must not invert this contract.
    assert "horizontal" in src.lower()
    assert f15.__doc__ is not None
    assert "F.15" in f15.__doc__
