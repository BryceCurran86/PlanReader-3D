"""Real-drawing shadow gate for wall-boundary role. Skips without PDFs."""
from __future__ import annotations

import pytest

from scripts.wall_boundary_role_real_drawing_shadow import available_drawings, run_shadow


def test_real_drawing_wall_role_shadow_does_not_require_firm_roles() -> None:
    drawings = available_drawings()
    if not drawings:
        pytest.skip("real-drawing PDFs are not present under benchmarks/sources")
    reports = run_shadow()
    assert reports
    for report in reports:
        assert report["canonical_walls"] >= 0
        print(
            f"{report['label']}: walls={report['canonical_walls']} "
            f"existence={report['existence_corroborated']} "
            f"two_faces={report['two_authoritative_incident_faces']} "
            f"EXT={report['external']} INT={report['internal_partition']} "
            f"UNK={report['unknown']} CONF={report['conflict']}"
        )
