"""Unit tests for Producer-Owned RCP Word and Viewport Scope Eligibility Shadow Authority.

Tests positive, negative, and ambiguity scenarios under strict evaluator separation.
"""

import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_rcp_word_eligibility_shadow import (
    RcpWordEvidence,
    RcpWordRole,
    SourceRcpWordEligibilityShadowAuthority,
)

PLAN_VIEWPORT = (100.0, 100.0, 1000.0, 1500.0)
SCHEDULE_TABLE = (1100.0, 100.0, 1500.0, 600.0)
TITLE_BLOCK = (1100.0, 1200.0, 1500.0, 1500.0)


def test_positive_in_plan_ipf1_callout():
    authority = SourceRcpWordEligibilityShadowAuthority()
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="IPF1",
        word_bbox=(350.0, 450.0, 380.0, 460.0),
        block_text="IPF1",
        block_index=9,
        line_index=0,
        word_index=0,
        plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=[SCHEDULE_TABLE],
        title_block_bboxes=[TITLE_BLOCK],
        source_defined_ceiling_codes=("IPF1","GRID","WFPB","FPB"),
    )

    assert word.status == EvidenceResolutionStatus.CANDIDATE
    assert word.role == RcpWordRole.IN_PLAN_CEILING_ANNOTATION
    assert word.is_eligible_for_ceiling_mark is True
    assert word.commercial_projection_allowed is False
    assert word.takeoff_eligible is False


def test_positive_in_plan_grid_callout():
    authority = SourceRcpWordEligibilityShadowAuthority()
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="GRID",
        word_bbox=(500.0, 600.0, 530.0, 610.0),
        block_text="GRID / 2400 CLG",
        block_index=10,
        line_index=0,
        word_index=0,
        plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=[SCHEDULE_TABLE],
        title_block_bboxes=[TITLE_BLOCK],
        source_defined_ceiling_codes=("IPF1","GRID","WFPB","FPB"),
    )

    assert word.status == EvidenceResolutionStatus.CANDIDATE
    assert word.role == RcpWordRole.IN_PLAN_CEILING_ANNOTATION
    assert word.is_eligible_for_ceiling_mark is True


def test_negative_schedule_table_cell_vetoed():
    authority = SourceRcpWordEligibilityShadowAuthority()
    # Word bbox at (1150, 200) inside SCHEDULE_TABLE
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="IPF1",
        word_bbox=(1150.0, 200.0, 1180.0, 210.0),
        block_text="IPF1",
        block_index=5,
        plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=[SCHEDULE_TABLE],
        title_block_bboxes=[TITLE_BLOCK],
    )

    assert word.status == EvidenceResolutionStatus.ABSTAINED
    assert word.role == RcpWordRole.SCHEDULE_TABLE_CELL
    assert word.is_eligible_for_ceiling_mark is False
    assert "schedule/legend table" in word.notes


def test_negative_general_note_prose_vetoed():
    authority = SourceRcpWordEligibilityShadowAuthority()
    # Word "OFFICE" inside a multi-word general specification note
    prose = "ALL CEILINGS AND SUSPENDED DUCTWORK IN OFFICE TO BE COMPLIANT WITH AS 1668.2"
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="OFFICE",
        word_bbox=(400.0, 800.0, 440.0, 810.0),
        block_text=prose,
        block_index=212,
        plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=[SCHEDULE_TABLE],
        title_block_bboxes=[TITLE_BLOCK],
    )

    assert word.status == EvidenceResolutionStatus.ABSTAINED
    assert word.role == RcpWordRole.GENERAL_NOTE_PROSE
    assert word.is_eligible_for_ceiling_mark is False
    assert "general note prose block" in word.notes


def test_negative_word_outside_plan_viewport_vetoed():
    authority = SourceRcpWordEligibilityShadowAuthority()
    # Word at (50, 50) outside PLAN_VIEWPORT (starts at x=100, y=100)
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="GRID",
        word_bbox=(50.0, 50.0, 80.0, 60.0),
        block_text="GRID",
        plan_viewport_bbox=PLAN_VIEWPORT,
    )

    assert word.status == EvidenceResolutionStatus.ABSTAINED
    assert word.role == RcpWordRole.OUT_OF_VIEWPORT
    assert word.is_eligible_for_ceiling_mark is False


def test_negative_title_block_metadata_vetoed():
    authority = SourceRcpWordEligibilityShadowAuthority()
    # Word at (1200, 1300) inside TITLE_BLOCK
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="OFFICE",
        word_bbox=(1200.0, 1300.0, 1250.0, 1310.0),
        block_text="OFFICE",
        plan_viewport_bbox=PLAN_VIEWPORT,
        title_block_bboxes=[TITLE_BLOCK],
    )

    assert word.status == EvidenceResolutionStatus.ABSTAINED
    assert word.role == RcpWordRole.TITLE_BLOCK_METADATA
    assert word.is_eligible_for_ceiling_mark is False


def test_negative_degenerate_bbox_fails_closed():
    authority = SourceRcpWordEligibilityShadowAuthority()
    word = authority.classify_word(
        document_id="doc_mary",
        page_id="9",
        word_text="IPF1",
        word_bbox=(100.0, 100.0, 100.0, 100.0),  # zero width and height
        block_text="IPF1",
        plan_viewport_bbox=PLAN_VIEWPORT,
    )

    assert word.status == EvidenceResolutionStatus.ABSTAINED
    assert word.is_eligible_for_ceiling_mark is False
    assert "Degenerate" in word.notes

def test_original_short_mechanical_note_does_not_become_office_ceiling():
    authority = SourceRcpWordEligibilityShadowAuthority()
    note = authority.classify_word(
        document_id="source-doc",page_id="9",word_text="OFFICE",
        word_bbox=(407.0,1400.,418.,1420.),
        block_text="REVIEW IN OFFICE AREA",
        block_index=212,plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("IPF1","GRID","FPB","WFPB"),
    )
    assert note.status is EvidenceResolutionStatus.ABSTAINED
    assert note.role == RcpWordRole.OTHER_PLAN_TEXT
    assert not note.is_eligible_for_ceiling_mark


def test_caller_unscoped_grid_and_schedule_text_do_not_authenticate_source():
    authority = SourceRcpWordEligibilityShadowAuthority()
    for kwargs in [
        dict(plan_viewport_bbox=None,schedule_table_bboxes=(SCHEDULE_TABLE,),
             source_defined_ceiling_codes=("GRID",)),
        dict(plan_viewport_bbox=PLAN_VIEWPORT,schedule_table_bboxes=(),
             source_defined_ceiling_codes=("GRID",)),
        dict(plan_viewport_bbox=PLAN_VIEWPORT,schedule_table_bboxes=(SCHEDULE_TABLE,),
             source_defined_ceiling_codes=()),
    ]:
        word=authority.classify_word(
            document_id="made-up-doc",page_id="9",word_text="GRID",
            word_bbox=(500.,600.,530.,610.),block_text="GRID 2400",
            **kwargs,
        )
        assert word.status is EvidenceResolutionStatus.ABSTAINED
        assert word.is_eligible_for_ceiling_mark is False


def test_foreign_or_ordinary_room_word_never_relabels_as_material_code():
    authority=SourceRcpWordEligibilityShadowAuthority()
    word=authority.classify_word(
        document_id="d",page_id="9",word_text="OFFICE",
        word_bbox=(500.,600.,530.,610.),block_text="OFFICE",
        plan_viewport_bbox=PLAN_VIEWPORT,schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID","IPF1"),
    )
    assert word.role is RcpWordRole.OTHER_PLAN_TEXT
    assert word.status is EvidenceResolutionStatus.ABSTAINED


def test_original_valid_grid_height_callout_remains_candidate_not_firm():
    authority=SourceRcpWordEligibilityShadowAuthority()
    word=authority.classify_word(
        document_id="d",page_id="9",word_text="GRID",
        word_bbox=(500.,600.,530.,610.),block_text="GRID / 2400 CLG",
        plan_viewport_bbox=PLAN_VIEWPORT,schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID",),
    )
    assert word.status is EvidenceResolutionStatus.CANDIDATE
    assert word.is_eligible_for_ceiling_mark is True
    assert not word.takeoff_eligible and not word.commercial_projection_allowed


def test_nonfinite_pdf_word_box_fails_closed():
    authority=SourceRcpWordEligibilityShadowAuthority()
    word=authority.classify_word(
        document_id="d",page_id="9",word_text="GRID",
        word_bbox=(float("nan"),600.,530.,610.),block_text="GRID",
        plan_viewport_bbox=PLAN_VIEWPORT,schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID",),
    )
    assert word.status is EvidenceResolutionStatus.ABSTAINED
