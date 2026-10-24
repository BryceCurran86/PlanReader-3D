"""Bounded original-ink dimension rivals must report incomplete evidence, not FIRM."""
from __future__ import annotations

import hashlib

import fitz
import pytest

import tools.diag_gpt2_exterior_overhead_soffit_source_census_shadow as census


class _SourcePage:
    def get_text(self, kind, sort=False):
        assert kind == "words" and sort is False
        return (
            (10., 10., 30., 20., "STP", 0, 0, 0),
            (35., 10., 68., 20., "SOFFIT", 0, 0, 1),
            (69., 10., 102., 20., "CLADDING", 0, 0, 2),
            (10., 40., 30., 50., "1000", 1, 0, 0),
            (10., 60., 30., 70., "2000", 1, 1, 0),
            (10., 80., 30., 90., "3000", 1, 2, 0),
            (50., 40., 70., 90., "6000", 2, 0, 0),
        )

    def get_drawings(self):
        # Each line is >=30pt (the real detector's minimum), so this
        # synthetic positive exercises its actual source-stroke path.
        # The three independent component spans jointly cover the
        # independent full-length overall line, without aliasing IDs.
        strokes = ((31., 30., 60.), (31., 50., 80.),
                   (31., 70., 100.), (71., 30., 100.))
        return tuple({
            "type": "s", "color": (0., 0., 0.),
            "stroke_opacity": 1, "width": 0.48,
            "items": (("l", fitz.Point(x, y0), fitz.Point(x, y1)),),
        } for x, y0, y1 in strokes)


class _SourceDocument:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def __len__(self):
        return 1

    def __getitem__(self, index):
        assert index == 0
        return _SourcePage()


def _run(monkeypatch):
    monkeypatch.setattr(census.fitz, "open", lambda **kwargs: _SourceDocument())
    return census.audit_exterior_overhead_source_census_shadow(
        b"original-source-stub",
        expected_sha256=hashlib.sha256(b"original-source-stub").hexdigest(),
        page_number=1,
        material_code="STP",
    )


def test_complete_source_ink_correspondence_is_reported_without_quantity(monkeypatch):
    result = _run(monkeypatch)
    assert result["all_source_ink_correspondence_rivals_complete"] is True
    assert result["new_firm_quantities"] == 0
    assert result["exterior_soffit_area_m2"] is None
    assert len(result["all_competing_figured_arithmetic_chains"]) == 1
    row = result["all_competing_figured_arithmetic_chains"][0]
    assert row["source_ink_line_correspondence_complete"] is True
    assert row["source_ink_combination_trials"] == 1
    assert len(row["source_ink_line_correspondence_candidates"]) == 1
    assert row["source_ink_line_correspondence_candidates"][0][
        "firm_metric_authority"] is False


@pytest.mark.parametrize("bound_name", [
    "_MAX_INK_COMBINATION_TRIALS", "_MAX_INK_MATCHES",
])
def test_truncation_is_exposed_and_never_claims_firm(monkeypatch, bound_name):
    monkeypatch.setattr(census, bound_name, 0 if bound_name.endswith("TRIALS") else 1)
    result = _run(monkeypatch)
    assert result["all_source_ink_correspondence_rivals_complete"] is False
    row = result["all_competing_figured_arithmetic_chains"][0]
    assert row["source_ink_line_correspondence_complete"] is False
    assert result["first_unclosed_gate"] == (
        "bounded_original_ink_correspondence_universe_incomplete")
    assert result["exterior_soffit_area_m2"] is None
    assert result["new_firm_quantities"] == 0


def test_malformed_sha_still_fails_before_fake_source_open(monkeypatch):
    monkeypatch.setattr(census.fitz, "open",
                        lambda **kwargs: pytest.fail("must not read a foreign source"))
    with pytest.raises(ValueError, match="immutable_original_pdf_source_sha_required"):
        census.audit_exterior_overhead_source_census_shadow(
            b"original-source-stub", expected_sha256="0" * 64,
            page_number=1, material_code="STP",
        )
