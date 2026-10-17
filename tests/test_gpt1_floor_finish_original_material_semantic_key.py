"""A printed floor material mark cannot be rekeyed to a different floor or finish."""
import pytest
from pb_live_floor_finish_area_source_closed_export import _require_exact_floor_finish_semantic
from pb_source_closed_run_export import SourceClosedRunConflictError


def _seal(semantic="floor_finish_area:floor-1:FT2:tile",code="FT2",finish="tile"):
    _require_exact_floor_finish_semantic(
        semantic,canonical_floor_id="floor-1",
        finish_code=code,semantic_finish=finish,
    )


def test_independent_original_source_mark_grammars_remain_eligible():
    assert _seal() is None
    assert _seal("floor_finish_area:floor-1:FT3:epoxy_tile","FT3","epoxy_tile") is None


@pytest.mark.parametrize("key,code,finish",[
    ("floor_finish_area:floor-2:FT2:tile","FT2","tile"),
    ("room_area:floor-1:FT2:tile","FT2","tile"),
    ("floor_finish_area:floor-1:FT3:tile","FT2","tile"),
    ("floor_finish_area:floor-1:FT2:epoxy_tile","FT2","tile"),
    ("floor_finish_area:floor-1:FT2:tile",None,"tile"),
    ("floor_finish_area:floor-1:FT2:tile"," FT2","tile"),
])
def test_rekeyed_source_material_or_floor_must_not_seal(key,code,finish):
    with pytest.raises(SourceClosedRunConflictError,match="semantic identity"):
        _seal(key,code,finish)
