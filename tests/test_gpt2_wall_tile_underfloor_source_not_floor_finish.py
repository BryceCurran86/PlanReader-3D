"""A source wall-tile or underfloor descriptor cannot be counted as floor tiling."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from pb_cross_view_floor_finish_authority import _definition_is_floor_finish
from pb_source_material_semantic_authority import SourceMaterialDefinitionRecord

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _definition(text, semantic="tile"):
    return SourceMaterialDefinitionRecord(
        record_id="definition-source",
        document_id="doc", revision_id="rev",
        source_sha256="a"*64, snapshot_id="snap",
        code="FT", description=text, substrate="", finish="",
        semantic_finish=semantic,
        source_definition_ids=("native-schedule",),
        source_page_ids=("11",), source_viewport_ids=("schedule",),
    )


@pytest.mark.parametrize("source_text", [
    "WALL TILES FROM FLOOR TO CEILING",
    "WALL TILE 200X200 ABOVE FLOOR",
    "UNDERFLOOR INSULATION",
    "UNDER-FLOOR WATERPROOFING",
    "SUBFLOOR INSTALLATION",
    "SUB-FLOOR MEMBRANE",
    "FLOOR DRAIN GRATE",
    "FLOOR INSULATION LINING",
])
def test_explicit_original_non_floor_finish_vetoes_stale_tile_semantic(source_text):
    assert _definition_is_floor_finish(_definition(source_text)) is False


@pytest.mark.parametrize("source_text", [
    "FLOOR TILE 800x400 STOCKTON WHITE",
    "FLOOR TILE 600x600 DURA GREY",
    "VINYL FLOORING",
    "EPOXY FLOOR COATING",
])
def test_authentic_floor_finish_role_remains_eligible(source_text):
    assert _definition_is_floor_finish(_definition(source_text)) is True


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="owner-private Maryborough PDF unavailable")
def test_original_ft2_ft3_schedule_floor_tile_meaning_not_regressed():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    with fitz.open(stream=raw, filetype="pdf") as doc:
        words = doc[10].get_text("words", sort=False)
    for block in (243, 244):
        text = " ".join(str(w[4]) for w in words if int(w[5]) == block)
        assert "FLOOR TILE" in text.upper()
        assert _definition_is_floor_finish(_definition(text)) is True
