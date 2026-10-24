"""External soffit material cannot be misclassified as an internal GRID ceiling."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from pb_cross_view_ceiling_finish_authority import _definition_is_ceiling_finish
from pb_source_material_semantic_authority import SourceMaterialDefinitionRecord

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _definition(description):
    return SourceMaterialDefinitionRecord(
        record_id="source-material-definition",
        document_id="doc", revision_id="rev", source_sha256="a" * 64,
        snapshot_id="snap", code="MAT",
        description=description, substrate="", finish="",
        semantic_finish="ceiling_grid",
        source_definition_ids=("authenticated-schedule-description",),
        source_page_ids=("2",), source_viewport_ids=("material-schedule",),
    )


@pytest.mark.parametrize("original_text", [
    "STRAMIT PREMIER 300 SOFFIT CLADDING COLOUR COLORBOND SURFMIST",
    "EXTERNAL SOFFIT-CLADDING",
    "CANOPY CLADDING",
    "EAVES CLADDING",
    "FASCIA CLADDING",
    "WALL CLADDING",
    "SIGNAGE CONTRACTOR CLADDING",
])
def test_explicit_original_non_ceiling_cladding_role_vetoes_stale_ceiling_grid(
    original_text,
):
    assert _definition_is_ceiling_finish(_definition(original_text)) is False


def test_true_grid_ceiling_source_definition_survives_external_role_veto():
    assert _definition_is_ceiling_finish(
        _definition("Vinyl faced plaster tile suspended grid 600x1200")
    ) is True


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="owner-private original unavailable")
def test_original_a253_stp_schedule_cannot_alias_a120_internal_grid_material():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    with fitz.open(stream=raw, filetype="pdf") as doc:
        words = doc[17].get_text("words", sort=False)
    row = [str(w[4]) for w in words if w[5] == 108]
    assert "STP" in row
    assert {"STRAMIT", "PREMIER", "300", "SOFFIT", "CLADDING"} <= {
        word.upper().strip(".,") for word in row
    }
    assert _definition_is_ceiling_finish(
        _definition(" ".join(row))
    ) is False
