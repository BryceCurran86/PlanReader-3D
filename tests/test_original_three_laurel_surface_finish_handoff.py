"""Original 3Laurel SHA-locked surface-finish handoff helpers.

Public CI without the private PDF must skip via require_original_3laurel.
This file is intentionally NOT part of exact-source-safety's public pytest set.
"""
from __future__ import annotations

from tools.run_source_closed_project_handoff import (
    _THREE_LAUREL_SOURCE_SHA256,
    _original_three_laurel_ceiling_handoff,
    _original_three_laurel_floor_finish_handoff,
    _original_three_laurel_wall_finish_handoff,
)
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def test_original_three_laurel_surface_finish_handoffs_return_twenty_two_firm_items():
    assert ORIGINAL_SHA256 == _THREE_LAUREL_SOURCE_SHA256
    pdf = require_original_3laurel()

    floor = _original_three_laurel_floor_finish_handoff(
        pdf, workspace_id=1, source_sha256=ORIGINAL_SHA256,
    )
    wall = _original_three_laurel_wall_finish_handoff(
        pdf, workspace_id=1, source_sha256=ORIGINAL_SHA256,
    )
    ceiling = _original_three_laurel_ceiling_handoff(
        pdf, workspace_id=1, source_sha256=ORIGINAL_SHA256,
    )
    assert floor is not None and wall is not None and ceiling is not None
    floor_q, floor_sealed, floor_rows = floor
    wall_q, wall_sealed, wall_rows = wall
    ceiling_q, ceiling_sealed, ceiling_rows = ceiling
    assert len(floor_q) == 7 and len(floor_sealed.quantities) == 7 and len(floor_rows) == 7
    assert len(wall_q) == 8 and len(wall_sealed.quantities) == 8 and len(wall_rows) == 8
    assert (
        len(ceiling_q) == 7
        and len(ceiling_sealed.quantities) == 7
        and len(ceiling_rows) == 7
    )
    assert all(q.status == "firm" and not q.abstained for q in floor_q)
    assert all(q.family == "floor_finish_area" for q in floor_q)
    assert all(q.family == "wall_finish_area" for q in wall_q)
    assert all(q.family == "ceiling_lining" for q in ceiling_q)
    assert all(row["quantity_status"] == "To review" for row in floor_rows)
    assert all(row["quantity_status"] == "To review" for row in wall_rows)
    assert all(row["quantity_status"] == "To review" for row in ceiling_rows)
    assert (
        _original_three_laurel_floor_finish_handoff(
            pdf, workspace_id=1, source_sha256="0" * 64,
        )
        is None
    )
