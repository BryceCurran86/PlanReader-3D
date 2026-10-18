"""Canonical ceiling FIRM code, original material and source object are one semantic."""
import pytest
from pb_live_ceiling_lining_source_closed_export import _require_exact_ceiling_finish_semantic
from pb_source_closed_run_export import SourceClosedRunConflictError


def _seal(key="ceiling_lining:ceiling-1:GRID:ceiling_grid",code="GRID",finish="ceiling_grid"):
    return _require_exact_ceiling_finish_semantic(
        semantic_key=key,canonical_ceiling_id="ceiling-1",
        finish_code=code,semantic_finish=finish,
    )


def test_original_producer_issued_grid_ceiling_semantic_passes():
    assert _seal() is None
    assert _seal(
        "ceiling_lining:ceiling-1:IPF1:plasterboard",
        "IPF1","plasterboard",
    ) is None


@pytest.mark.parametrize("key,code,finish",[
    ("ceiling_lining:ceiling-2:GRID:ceiling_grid","GRID","ceiling_grid"),
    ("ceiling_lining:ceiling-1:IPF1:ceiling_grid","GRID","ceiling_grid"),
    ("ceiling_lining:ceiling-1:GRID:plasterboard","GRID","ceiling_grid"),
    ("ceiling_lining:ceiling-1","GRID","ceiling_grid"),
    ("ceiling_lining:ceiling-1:GRID:ceiling_grid",None,"ceiling_grid"),
    ("ceiling_lining:ceiling-1:GRID:ceiling_grid"," GRID","ceiling_grid"),
    ("ceiling_lining:ceiling-1:GRID:ceiling_grid","GRID","ceiling_grid "),
])
def test_source_rekeying_material_code_or_physical_ceiling_never_seals(key,code,finish):
    with pytest.raises(SourceClosedRunConflictError,match="semantic"):
        _seal(key,code,finish)
