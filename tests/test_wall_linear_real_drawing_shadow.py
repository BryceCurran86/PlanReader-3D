"""Real-drawing shadow gate for the wall-linear authority bridge.

Skips when source PDFs are absent. Never invents scale or treats a region clip
as a whole-building perimeter.
"""
from __future__ import annotations

from scripts.wall_linear_authority_real_drawing_shadow import available_drawings, run_shadow

import pytest


def test_real_drawing_wall_linear_shadow_does_not_invent_scale_or_perimeter() -> None:
    drawings = available_drawings()
    if not drawings:
        pytest.skip("real-drawing PDFs are not present under benchmarks/sources")
    reports = run_shadow()
    assert reports, "available drawings produced no shadow reports"
    for report in reports:
        assert report["firm_scale_available"] is False
        assert report["firm_wall_length_quantities"] == 0
        assert report["canonical_walls_considered"] >= 0
        print(
            f"{report['label']}: walls={report['canonical_walls_considered']} "
            f"existence_corroborated={report['physical_existence_corroborated']} "
            f"entity_corroborated={report['entity_evidence_corroborated']} "
            f"firm_lengths={report['firm_wall_length_quantities']} "
            f"abstentions={report['abstentions_by_reason']}"
        )
