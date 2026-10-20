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

def test_actual_original_four_word_office_note_not_a_ceiling_mark():
    # SHA-pinned Maryborough RCP p9 native block212:
    # REVIEW IN OFFICE AREA (4 words). Length-only >6-word filters fail.
    a=SourceRcpWordEligibilityShadowAuthority()
    r=a.classify_word(
        document_id="source:mary",page_id="9",word_text="OFFICE",
        word_bbox=(407.0,1400.0,418.9,1450.0),
        block_text="REVIEW IN OFFICE AREA",block_index=212,
        line_index=0,word_index=2,
        plan_viewport_bbox=PLAN_VIEWPORT,
    )
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.role is RcpWordRole.GENERAL_NOTE_PROSE
    assert not r.is_eligible_for_ceiling_mark


def test_original_standalone_office_is_room_word_not_ceiling_material():
    a=SourceRcpWordEligibilityShadowAuthority()
    r=a.classify_word(
        document_id="source:mary",page_id="9",word_text="OFFICE",
        word_bbox=(295.42,1465.44,311.48,1503.56),
        block_text="OFFICE",block_index=9,line_index=0,word_index=0,
        plan_viewport_bbox=(100.,100.,1100.,1600.),
    )
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.role is RcpWordRole.NON_CEILING_LABEL
    assert not r.commercial_projection_allowed and not r.takeoff_eligible


def test_source_less_callout_is_never_corrob_without_plan_candidate():
    a=SourceRcpWordEligibilityShadowAuthority()
    r=a.classify_word(
        document_id="caller-can-invent",page_id="9",word_text="IPF1",
        word_bbox=(350.,450.,380.,460.),block_text="IPF1",
        plan_viewport_bbox=None,
    )
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert not r.is_eligible_for_ceiling_mark


def test_mixed_electrical_device_text_ipf1_not_assumed_one_ceiling_mark():
    a=SourceRcpWordEligibilityShadowAuthority()
    r=a.classify_word(
        document_id="source:mary",page_id="9",word_text="IPF1",
        word_bbox=(566.,1398.,581.,1415.),
        block_text="EX D-1 EML MS D-1 IPF1",block_index=85,line_index=5,
        plan_viewport_bbox=(100.,100.,1100.,1700.),
    )
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert r.role is RcpWordRole.GENERAL_NOTE_PROSE


def test_source_word_lexical_candidate_never_becomes_corrob_or_firm():
    a=SourceRcpWordEligibilityShadowAuthority()
    r=a.classify_word(
        document_id="unverified-original-root",page_id="9",word_text="GRID",
        word_bbox=(391.46,1500.42,416.54,1520.96),
        block_text="2400 GRID",block_index=10,line_index=1,
        plan_viewport_bbox=(100.,100.,1100.,1700.),
    )
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.is_eligible_for_ceiling_mark
    assert r.role is RcpWordRole.IN_PLAN_CEILING_ANNOTATION
    assert not r.takeoff_eligible and not r.commercial_projection_allowed
