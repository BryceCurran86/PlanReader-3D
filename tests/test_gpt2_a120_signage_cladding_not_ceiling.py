"""Original A120 signage cladding must not acquire any ceiling area role."""
import hashlib
from dataclasses import replace
from pathlib import Path

import fitz
from pb_cross_view_ceiling_finish_authority import _definition_is_ceiling_finish
from pb_source_material_semantic_authority import SourceMaterialDefinitionRecord

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _definition(description,semantics):
    return SourceMaterialDefinitionRecord(
        record_id="separate-test-source-definition",
        document_id="original-source-test",revision_id="revision-sha",
        source_sha256=SHA,snapshot_id="original-snapshot",
        code="untrusted-original-code",description=description,
        substrate="",finish="",semantic_finish=semantics,
        source_definition_ids=("original-description-evidence",),
        source_page_ids=("9",),source_viewport_ids=("original-schedule",),
    )


def test_original_a120_cld3_schedule_signage_material_is_not_ceiling():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as d:
        groups={}
        for w in d[8].get_text("words"):
            groups.setdefault(int(w[5]),[]).append(str(w[4]))
        matches=[v for v in groups.values() if "CLD3" in v
                 and "SIGNAGE" in v and "CLADDING" in v]
        assert len(matches)==1
        description=" ".join(matches[0])
    assert "MARINE" in description and "BLUE" in description
    assert not _definition_is_ceiling_finish(_definition(description,"ceiling_grid"))
    assert not _definition_is_ceiling_finish(_definition(description,"plasterboard"))
    assert not _definition_is_ceiling_finish(_definition(description,"fibre_cement"))
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_existing_valid_ceiling_definitions_remain_eligible():
    assert _definition_is_ceiling_finish(
        _definition("Suspended CEILING GRID system", "ceiling_grid")
    )
    assert _definition_is_ceiling_finish(
        _definition("13mm flush-set plasterboard CEILING lining", "plasterboard")
    )
    assert not _definition_is_ceiling_finish(
        _definition("Vinyl faced plaster tile 600x1200", "")
    )
    assert not _definition_is_ceiling_finish(
        _definition("Blue signage cladding", "ceiling_grid")
    )


def test_material_code_or_room_label_cannot_override_signage_cladding():
    row=_definition("Signage contractor cladding to tenant specification","ceiling_grid")
    assert not _definition_is_ceiling_finish(replace(
        row,code="GRID",source_page_ids=("9",),source_viewport_ids=("rcp",)))
    assert not _definition_is_ceiling_finish(replace(row,code="CLD3"))
    assert _definition_is_ceiling_finish(replace(
        row,description="13mm plasterboard ceiling lining",
        semantic_finish="plasterboard"))
