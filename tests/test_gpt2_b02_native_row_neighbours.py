"""Native FT2/FT3 row candidates cannot grant material meaning."""
from tools.diag_gpt2_maryborough_b02_material_source import (
    _native_lateral_row_neighbours,
)


def _block(bbox, text):
    return {
        "type":0,
        "bbox":bbox,
        "lines":[{"spans":[{"text":text}]}],
    }


def test_source_row_probe_preserves_native_block_id_and_is_untrusted():
    blocks = (
        _block((10,10,25,25),"FT3"),
        _block((35,11,230,25),"SOURCE DEFINED FLOOR FINISH"),
        _block((35,60,230,75),"UNRELATED CEILING"),
        _block((600,10,750,25),"FAR AWAY"),
    )
    rows=_native_lateral_row_neighbours(blocks,blocks[0]["bbox"],0)
    assert len(rows)==1
    assert rows[0]["native_block_no"]==1
    assert rows[0]["text"]=="SOURCE DEFINED FLOOR FINISH"
    assert rows[0]["candidate_only"] is True


def test_code_cell_alone_cannot_invent_adjacent_description():
    blocks=(_block((10,10,25,25),"FT2"),)
    assert _native_lateral_row_neighbours(blocks,blocks[0]["bbox"],0)==[]
