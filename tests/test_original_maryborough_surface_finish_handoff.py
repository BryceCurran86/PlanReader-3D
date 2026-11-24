"""Original Maryborough SHA-locked surface-finish handoff helpers.

Verifies:
1. _original_maryborough_floor_finish_handoff returns exactly 2 FIRM quantities
   (Office FT3 9.05352 m2, Food Prep FT3 13.270425 m2), verified sealed run,
   and 2 customer rows.
2. _original_maryborough_ceiling_handoff returns exactly 2 FIRM quantities
   (Office GRID 9.05352 m2, Food Prep FPB 13.270425 m2), verified sealed run,
   and 2 customer rows.
3. Fail-closed: invalid SHA-256 returns None.
"""
from __future__ import annotations

import os
from pathlib import Path
import pytest

from tools.run_source_closed_project_handoff import (
    _MARYBOROUGH_PROJECT_ID,
    _MARYBOROUGH_SOURCE_SHA256,
    _original_maryborough_floor_finish_handoff,
    _original_maryborough_ceiling_handoff,
)


@pytest.fixture
def maryborough_pdf_path() -> Path:
    path = Path(
        os.environ.get(
            "PLANREADER_ORIGINAL_MARYBOROUGH",
            "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
        )
    )
    if not path.is_file():
        pytest.skip("private original Maryborough PDF unavailable in test environment")
    return path


def test_original_maryborough_surface_finish_handoffs(maryborough_pdf_path):
    floor = _original_maryborough_floor_finish_handoff(
        maryborough_pdf_path,
        workspace_id=1,
        source_sha256=_MARYBOROUGH_SOURCE_SHA256,
    )
    assert floor is not None
    floor_q, floor_sealed, floor_rows = floor
    assert len(floor_q) == 2
    assert len(floor_sealed.quantities) == 2
    assert len(floor_rows) == 2
    assert all(q.status == "firm" and not q.abstained for q in floor_q)
    assert all(q.family == "floor_finish_area" for q in floor_q)
    assert {q.value for q in floor_q} == {9.05352, 13.270425}
    assert all(row["quantity_status"] == "To review" for row in floor_rows)

    ceiling = _original_maryborough_ceiling_handoff(
        maryborough_pdf_path,
        workspace_id=1,
        source_sha256=_MARYBOROUGH_SOURCE_SHA256,
    )
    assert ceiling is not None
    ceiling_q, ceiling_sealed, ceiling_rows = ceiling
    assert len(ceiling_q) == 2
    assert len(ceiling_sealed.quantities) == 2
    assert len(ceiling_rows) == 2
    assert all(q.status == "firm" and not q.abstained for q in ceiling_q)
    assert all(q.family == "ceiling_lining" for q in ceiling_q)
    assert {q.value for q in ceiling_q} == {9.05352, 13.270425}
    assert all(row["quantity_status"] == "To review" for row in ceiling_rows)

    # Fail closed on wrong SHA
    assert (
        _original_maryborough_floor_finish_handoff(
            maryborough_pdf_path, workspace_id=1, source_sha256="0" * 64,
        )
        is None
    )
    assert (
        _original_maryborough_ceiling_handoff(
            maryborough_pdf_path, workspace_id=1, source_sha256="0" * 64,
        )
        is None
    )
