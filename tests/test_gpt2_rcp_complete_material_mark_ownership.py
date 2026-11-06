"""Source-closed RCP cannot ignore a competing finish code in same ceiling ring.

Pure source-neutral tests; no original PDF, takeoff, FIRM or frozen scores.
"""
from __future__ import annotations

from dataclasses import replace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
import pb_source_material_semantic_authority as semantic
from tools.diag_gpt2_source_rcp_geometry_shadow import (
    audit_original_rcp_source_finish_occurrence,
)

SHA = "a" * 64
ROOT = dict(
    document_id="source-document", revision_id="rev1",
    source_sha256=SHA, snapshot_id="snap1",
)


def _sources(rival_position="outside", *, reverse=False,
             malformed_rival=False, bad_requested=None):
    definition_selector = semantic.SourceMaterialDefinitionSelector(
        **ROOT, code="GRID",
    )
    occurrence_selector = semantic.SourceMaterialOccurrenceSelector(
        **ROOT, page_id="9", viewport_id="original-rcp-view",
    )
    definition = semantic.SourceMaterialDefinitionRecord(
        record_id="GRID-schedule-original", **ROOT,
        code="GRID", description="Vinyl faced plaster tile 600x1200",
        substrate="", finish="ceiling tile", semantic_finish="ceiling_grid",
        source_definition_ids=("definition-word",),
        source_page_ids=("9",),
        source_viewport_ids=("original-rcp-view",),
    )
    marked = semantic.SourceMaterialOccurrenceRecord(
        record_id="GRID-plan-source", **ROOT,
        page_id="9", viewport_id="original-rcp-view",
        code="GRID", semantic_finish="ceiling_grid",
        definition_record_id=definition.record_id,
        bbox_pdf_pts=(20., 20., 30., 30.),
        raw_text="GRID", source_evidence_id="grid-original-word",
        source_text_observation_ids=("grid-original-text",),
    )
    if bad_requested is not None:
        marked = replace(marked, **bad_requested)
    other_box = {
        "inside": (50., 20., 60., 30.),
        "crossing": (95., 20., 105., 30.),
        "outside": (120., 20., 130., 30.),
    }[rival_position]
    rival = semantic.SourceMaterialOccurrenceRecord(
        record_id="IPF1-plan-rival", **ROOT,
        page_id="9", viewport_id="original-rcp-view",
        code="IPF1", semantic_finish="plasterboard",
        definition_record_id="IPF1-schedule-original",
        bbox_pdf_pts=other_box,
        raw_text="IPF1", source_evidence_id="ipf1-original-word",
        source_text_observation_ids=(
            () if malformed_rival else ("ipf1-original-text",)
        ),
    )
    rows = (rival, marked) if reverse else (marked, rival)
    authority = semantic.SourceMaterialSemanticAuthority(
        {definition_selector.key: semantic.SourceMaterialDefinitionResult(
            status=Status.CORROBORATED, reason_codes=(),
            record=definition,
        )},
        {occurrence_selector.key: semantic.SourceMaterialOccurrenceScopeResult(
            status=Status.CORROBORATED, reason_codes=(),
            scope_complete=True, records=rows,
            source_viewport_ownership_id="original-f07-rcp-owner",
        )},
        _seal=semantic._AUTHORITY_SEAL,
    )
    rcp = {
        "status": "original_rcp_source_ink_ceiling_polygon_candidate",
        "original_source_sha256": SHA,
        "original_document_id": ROOT["document_id"],
        "original_revision_id": ROOT["revision_id"],
        "original_snapshot_id": ROOT["snapshot_id"],
        "original_rcp_page": 9,
        "original_rcp_viewport_id": "original-rcp-view",
        "source_ceiling_ink_polygon_pdf_pts": (
            (0., 0.), (100., 0.), (100., 100.), (0., 100.),
        ),
    }
    return rcp, authority, definition_selector, occurrence_selector


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("position", ["inside", "crossing", "outside"])
def test_original_ceiling_finish_census_cannot_hide_other_material_code(
    reverse, position,
):
    rcp, authority, definition_selector, occurrence_selector = _sources(
        position, reverse=reverse,
    )
    result = audit_original_rcp_source_finish_occurrence(
        rcp, authority=authority,
        definition_selector=definition_selector,
        occurrence_selector=occurrence_selector,
        original_finish_code="GRID",
    )
    if position == "outside":
        assert result["status"] == "original_rcp_material_in_ceiling_ink_candidate"
        assert result["original_source_finish_record_ids"] == ("GRID-plan-source",)
        assert not result["source_ceiling_metric_area_issued"]
    else:
        assert result["status"] == "rcp_finish_occurrence_source_unresolved"
        assert result["first_failure"] == "competing_rcp_material_codes_in_one_ceiling_zone"
        assert result["competing_original_rcp_mark_record_ids"] == ("IPF1-plan-rival",)
    assert result["new_firm_quantities"] == 0


def test_untrusted_competing_rcp_material_scope_abstains_even_outside_zone():
    rcp, authority, definition_selector, occurrence_selector = _sources(
        "outside", malformed_rival=True,
    )
    result = audit_original_rcp_source_finish_occurrence(
        rcp, authority=authority,
        definition_selector=definition_selector,
        occurrence_selector=occurrence_selector,
        original_finish_code="GRID",
    )
    assert result["first_failure"] == "other_rcp_finish_mark_source_lineage_unresolved"
    assert result["new_firm_quantities"] == 0


@pytest.mark.parametrize("bad", [None, "pretend", (), ((0,0),(0,0),(0,0))])
def test_invalid_caller_rcp_ring_cannot_become_ceiling_material_candidate(bad):
    rcp, authority, definition_selector, occurrence_selector = _sources()
    rcp["source_ceiling_ink_polygon_pdf_pts"] = bad
    result = audit_original_rcp_source_finish_occurrence(
        rcp, authority=authority,
        definition_selector=definition_selector,
        occurrence_selector=occurrence_selector,
        original_finish_code="GRID",
    )
    assert result["status"] == "rcp_finish_occurrence_source_unresolved"
    assert result["first_failure"] == "original_rcp_ink_polygon_invalid"
    assert result["new_firm_quantities"] == 0



@pytest.mark.parametrize(("changed", "reason"), [
    ({"document_id": "foreign-document"}, "source_rcp_mark_ancestry_conflict"),
    ({"record_id": " GRID-mark "}, "source_rcp_mark_ancestry_conflict"),
    ({"source_text_observation_ids": ()}, "source_rcp_mark_ancestry_conflict"),
    ({"source_text_observation_ids": ("word", "word")}, "source_rcp_mark_ancestry_conflict"),
    ({"source_text_observation_ids": (" GRID ",)}, "source_rcp_mark_ancestry_conflict"),
    ({"bbox_pdf_pts": (float("nan"), 20., 30., 30.)}, "original_rcp_mark_geometry_invalid"),
    ({"bbox_pdf_pts": (20., 20., float("inf"), 30.)}, "original_rcp_mark_geometry_invalid"),
    ({"bbox_pdf_pts": ("20", 20., 30., 30.)}, "original_rcp_mark_geometry_invalid"),
    ({"bbox_pdf_pts": (True, 20., 30., 30.)}, "original_rcp_mark_geometry_invalid"),
    ({"bbox_pdf_pts": (20., 20., 20., 30.)}, "original_rcp_mark_geometry_invalid"),
    ({"bbox_pdf_pts": (20., 20., 30.)}, "original_rcp_mark_geometry_invalid"),
])
def test_requested_grid_mark_must_keep_own_original_document_text_and_bbox(
    changed, reason,
):
    rcp, authority, definition_selector, occurrence_selector = _sources(
        "outside", bad_requested=changed,
    )
    result = audit_original_rcp_source_finish_occurrence(
        rcp, authority=authority,
        definition_selector=definition_selector,
        occurrence_selector=occurrence_selector,
        original_finish_code="GRID",
    )
    if reason is not None:
        assert result["first_failure"] == reason
        assert result["status"] == "rcp_finish_occurrence_source_unresolved"
    else:
        # Numeric formatting alone is not physical scale authority.
        assert result["status"] == "original_rcp_material_in_ceiling_ink_candidate"
    assert result["new_firm_quantities"] == 0
