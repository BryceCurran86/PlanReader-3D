"""Native Colorbond sheet cladding is not self-authenticating GRID ceiling."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from pb_cross_view_ceiling_finish_authority import _definition_is_ceiling_finish
from tests.test_gpt2_external_soffit_cladding_not_internal_ceiling import (
    _definition,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.mark.parametrize("description", [
    "STRAMIT PREMIER 300 COLORBOND CLADDING SURFMIST",
    "Colorbond cladding to match adjoining roof sheeting",
    "COLORBOND CLADDING external wall",
])
def test_colorbond_cladding_without_explicit_ceiling_role_cannot_be_internal_grid(description):
    assert _definition_is_ceiling_finish(_definition(description)) is False


@pytest.mark.parametrize("description", [
    "Colorbond CEILING cladding suspended over meeting room",
    "Vinyl faced plaster tile suspended GRID 600x1200",
    "FLUSHSET PLASTERBOARD CEILING FINISH",
])
def test_explicit_ceiling_material_description_is_not_vetoed(description):
    assert _definition_is_ceiling_finish(_definition(description)) is True


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="private Maryborough original unavailable")
def test_original_rcp_material_key_contains_colorbond_cladding_not_an_internal_grid_spec():
    data = ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    with fitz.open(stream=data, filetype="pdf") as doc:
        original_words = doc[8].get_text("words", sort=False)
    legend = tuple(str(w[4]) for w in original_words if int(w[5]) == 5)
    assert {"STP", "STRAMIT", "PREMIER", "300", "COLORBOND", "CLADDING"} <= set(legend)
    assert _definition_is_ceiling_finish(
        _definition("STRAMIT PREMIER 300 COLORBOND CLADDING SURFMIST")
    ) is False
