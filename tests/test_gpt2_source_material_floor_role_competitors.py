"""Source-owned material-role competition; never invent W4 or a finish quantity."""
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
import pb_source_material_semantic_authority as semantic
from tools.diag_gpt2_source_finish_floor_handoff_shadow import (
    audit_gpt2_source_material_floor_handoff,
)


def _fixture(*, rival_description, rival_semantic, rival_status=Status.CORROBORATED,
             rival_source_record_id="wall-definition", include_rival_definition=True,
             rival_code="WA04", reverse=False, extra_floor_rival=False):
    lineage = dict(
        document_id="document", revision_id="revision",
        source_sha256="a" * 64, snapshot_id="snapshot",
    )
    ft_selector = semantic.SourceMaterialDefinitionSelector(**lineage, code="FT3")
    occurrence_selector = semantic.SourceMaterialOccurrenceSelector(
        **lineage, page_id="11", viewport_id="finish-plan",
    )
    def definition(code, rid, description, finish):
        return semantic.SourceMaterialDefinitionRecord(
            record_id=rid, **lineage, code=code, description=description,
            substrate="", finish="", semantic_finish=finish,
            source_definition_ids=("source-original-definition-" + code,),
            source_page_ids=("11",),
            source_viewport_ids=("source-material-schedule",),
        )
    ft = definition("FT3", "ft3-definition", "FLOOR TILE", "tile")
    other = definition(rival_code, rival_source_record_id,
                       rival_description, rival_semantic)
    ft_occ = semantic.SourceMaterialOccurrenceRecord(
        record_id="original-ft3-mark", **lineage, page_id="11",
        viewport_id="finish-plan", code="FT3", semantic_finish="tile",
        definition_record_id=ft.record_id, bbox_pdf_pts=(10., 10., 20., 20.),
        raw_text="FT3", source_evidence_id="ft3-ink",
        source_text_observation_ids=("ft3-original-word",),
    )
    other_occ = semantic.SourceMaterialOccurrenceRecord(
        record_id="original-other-mark", **lineage, page_id="11",
        viewport_id="finish-plan", code=rival_code,
        semantic_finish=rival_semantic,
        definition_record_id="wall-definition",
        bbox_pdf_pts=(30., 30., 40., 40.),
        raw_text=rival_code, source_evidence_id="other-ink",
        source_text_observation_ids=("other-original-word",),
    )
    rows = (other_occ, ft_occ) if reverse else (ft_occ, other_occ)
    definitions = {
        ft_selector.key: semantic.SourceMaterialDefinitionResult(
            status=Status.CORROBORATED, reason_codes=(), record=ft),
    }
    if include_rival_definition:
        rival_selector = semantic.SourceMaterialDefinitionSelector(
            **lineage, code=rival_code,
        )
        definitions[rival_selector.key] = semantic.SourceMaterialDefinitionResult(
            status=rival_status,
            reason_codes=() if rival_status is Status.CORROBORATED else ("incomplete",),
            record=other if rival_status is Status.CORROBORATED else None,
        )
    if extra_floor_rival:
        rival = definition("FT2", "ft2-definition", "FLOOR TILE", "tile")
        definitions[
            semantic.SourceMaterialDefinitionSelector(**lineage, code="FT2").key
        ] = semantic.SourceMaterialDefinitionResult(
            status=Status.CORROBORATED, reason_codes=(), record=rival,
        )
        rows += (semantic.SourceMaterialOccurrenceRecord(
            record_id="competing-ft2", **lineage, page_id="11",
            viewport_id="finish-plan", code="FT2", semantic_finish="tile",
            definition_record_id=rival.record_id,
            bbox_pdf_pts=(50., 50., 60., 60.), raw_text="FT2",
            source_evidence_id="ft2-ink",
            source_text_observation_ids=("ft2-original-word",),
        ),)
    authority = semantic.SourceMaterialSemanticAuthority(
        definitions,
        {occurrence_selector.key: semantic.SourceMaterialOccurrenceScopeResult(
            status=Status.CORROBORATED, reason_codes=(), scope_complete=True,
            records=rows, source_viewport_ownership_id="source-plan-ownership",
        )},
        _seal=semantic._AUTHORITY_SEAL,
    )
    registration = {
        "status": "original_source_ink_ring_translation_candidate",
        "original_source_sha256": lineage["source_sha256"],
        "original_floor_page": 7, "original_finish_page": 11,
        "source_floor_perimeter_polygon_pdf_pts": (
            (0., 0.), (100., 0.), (100., 100.), (0., 100.),
        ),
        "source_finishes_perimeter_polygon_pdf_pts": (
            (0., 0.), (100., 0.), (100., 100.), (0., 100.),
        ),
    }
    return audit_gpt2_source_material_floor_handoff(
        registration,
        material_authority=authority,
        definition_selector=ft_selector,
        occurrence_selector=occurrence_selector,
        original_finish_code="FT3",
    )


@pytest.mark.parametrize("reverse", (True, False))
@pytest.mark.parametrize("text,semantic", (
    ("METAL STUD WALL FRAMING", "wall"),
    ("PARTITION WALL FRAMING", "partition"),
    ("WALL CLADDING", "tile"),
    ("CEILING LINING", "ceiling"),
))
def test_authenticated_non_floor_schedule_role_no_longer_blocks_ft3_source_candidate(
    text, semantic, reverse,
):
    result = _fixture(rival_description=text, rival_semantic=semantic, reverse=reverse)
    assert result["status"] == "source_owned_material_on_original_ink_ring_candidate"
    assert result["source_authenticated_non_floor_record_ids"] == ("original-other-mark",)
    assert result["original_mark_source_record_ids"] == ("original-ft3-mark",)
    assert result["new_firm_quantities"] == 0
    assert not result["canonical_floor_finish_quantity_granted"]
    assert not result["structural_room_issuer_granted"]


@pytest.mark.parametrize("description,semantic,other", (
    ("FLOOR TILE ANOTHER FINISH", "tile", True),
    ("METAL STUD FLOOR AND WALL FRAMING", "wall", True),
    ("UNKNOWN PRODUCT", "unknown", True),
    ("METAL STUD WALL FRAMING", "wall", False),
))
def test_floor_uncertain_or_unissued_rival_still_abstains(description, semantic, other):
    result = _fixture(
        rival_description=description, rival_semantic=semantic,
        include_rival_definition=other,
    )
    assert result["status"] == "source_finished_floor_material_handoff_abstained"
    assert result["first_failure"] == "competing_source_material_codes_in_one_room"
    assert result["competing_source_material_record_ids"] == ("original-other-mark",)
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("wrong", ("wrong-identity", ""))
def test_non_matching_original_definition_record_identity_cannot_remove_rival(wrong):
    result = _fixture(
        rival_description="METAL STUD WALL FRAMING", rival_semantic="wall",
        rival_source_record_id=wrong,
    )
    assert result["status"] == "source_finished_floor_material_handoff_abstained"
    assert result["competing_source_material_record_ids"] == ("original-other-mark",)


@pytest.mark.parametrize("rival_status", (Status.ABSTAINED, Status.CONFLICT))
def test_unresolved_original_definition_cannot_remove_a_competing_mark(rival_status):
    result = _fixture(
        rival_description="METAL STUD WALL FRAMING", rival_semantic="wall",
        rival_status=rival_status,
    )
    assert result["first_failure"] == "competing_source_material_codes_in_one_room"


def test_explicit_wall_exclusion_cannot_hide_a_second_original_floor_finish():
    result = _fixture(
        rival_description="METAL STUD WALL FRAMING", rival_semantic="wall",
        extra_floor_rival=True,
    )
    assert result["status"] == "source_finished_floor_material_handoff_abstained"
    assert result["competing_source_material_record_ids"] == ("competing-ft2",)
    assert result["source_authenticated_non_floor_record_ids"] == ("original-other-mark",)
    assert result["new_firm_quantities"] == 0
