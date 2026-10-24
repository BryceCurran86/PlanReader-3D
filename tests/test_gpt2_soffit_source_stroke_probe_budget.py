"""All source stroke visits, not just successful combinations, are bounded."""
from __future__ import annotations

import pytest

import tools.diag_gpt2_exterior_overhead_soffit_source_census_shadow as census
from tests.test_gpt2_exterior_soffit_bounded_rivals import _run


def test_source_stroke_probe_budget_preserves_complete_original_ink_candidates(monkeypatch):
    result = _run(monkeypatch)
    assert result["all_source_ink_correspondence_rivals_complete"] is True
    row = result["all_competing_figured_arithmetic_chains"][0]
    assert row["source_ink_stroke_probes"] > 0
    assert row["source_ink_combination_trials"] == 1
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("max_probes", [0, 1, 4, 8])
def test_small_source_stroke_probe_budget_abstains_with_explicit_incomplete_scope(
    monkeypatch, max_probes,
):
    monkeypatch.setattr(census, "_MAX_INK_SOURCE_STROKE_PROBES", max_probes)
    result = _run(monkeypatch)
    assert result["all_source_ink_correspondence_rivals_complete"] is False
    assert result["first_unclosed_gate"] == (
        "bounded_original_ink_correspondence_universe_incomplete"
    )
    row = result["all_competing_figured_arithmetic_chains"][0]
    assert row["source_ink_stroke_probes"] <= max_probes
    assert row["source_ink_line_correspondence_complete"] is False
    assert result["new_firm_quantities"] == 0
    assert result["exterior_soffit_area_m2"] is None
