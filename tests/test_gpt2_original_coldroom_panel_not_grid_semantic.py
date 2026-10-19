"""Insulated cold-room panel is a distinct source material from GRID tile."""
from dataclasses import replace
import hashlib
from pathlib import Path

import fitz
import pytest

from pb_cross_view_ceiling_finish_authority import _definition_is_ceiling_finish
from tests.test_gpt2_external_soffit_cladding_not_internal_ceiling import _definition

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.mark.parametrize("description", [
    "INSULATED COLDROOM PANEL 100mm THICK",
    "COLD ROOM SANDWICH PANELS",
    "insulated cold-room ceiling panel to refrigeration specification",
])
def test_original_coldroom_panel_source_cannot_be_stale_suspended_grid(description):
    assert _definition_is_ceiling_finish(_definition(description)) is False


def test_source_owned_insulated_panel_semantic_not_blanket_rejected():
    definition = replace(
        _definition("INSULATED COLDROOM PANEL 100mm THICK"),
        semantic_finish="insulated_panel",
    )
    assert _definition_is_ceiling_finish(definition) is True


def test_real_grid_plaster_tile_source_definition_still_eligible():
    assert _definition_is_ceiling_finish(
        _definition("GRID VINYL FACED PLASTER TILE 600x1200")
    ) is True


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="owner-private PDF unavailable")
def test_original_a120_source_has_independent_coldroom_and_grid_material_words():
    data = ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    with fitz.open(stream=data, filetype="pdf") as pdf:
        words = pdf[8].get_text("words", sort=False)
    legend = tuple(str(w[4]) for w in words if int(w[5]) == 5)
    assert {"IP", "INSULATED", "COLDROOM", "PANEL", "GRID", "VINYL", "TILE"} <= set(legend)
    assert _definition_is_ceiling_finish(
        _definition("INSULATED COLDROOM PANEL 100mm THICK")
    ) is False
