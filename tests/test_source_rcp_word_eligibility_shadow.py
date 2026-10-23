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
        source_defined_ceiling_codes=("IPF1","GRID","WFPB"),
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
        source_defined_ceiling_codes=("GRID","IPF1"),
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
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID","IPF1"),
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
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID","IPF1"),
    )
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.is_eligible_for_ceiling_mark
    assert r.role is RcpWordRole.IN_PLAN_CEILING_ANNOTATION
    assert not r.takeoff_eligible and not r.commercial_projection_allowed

def test_sha_pinned_real_original_short_note_room_word_and_grid_if_provisioned():
    # The public CI runner does not contain the private owner's architectural
    # original. Its absence must skip SOURCE verification, never imply pass.
    import os
    from pathlib import Path
    from hashlib import sha256
    import fitz
    location=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not location:
        pytest.skip("owner original source unavailable on public CI runner")
    source=Path(location).read_bytes()
    assert sha256(source).hexdigest()==os.environ["PLANREADER_MARYBOROUGH_SOURCE_SHA256"]
    with fitz.open(stream=source,filetype="pdf") as pdf:
        words=pdf[8].get_text("words")
    candidate_plan=(100.,100.,1100.,1700.)
    original_word_scope=((9,0,0,"OFFICE"),(10,1,0,"GRID"),(212,0,2,"OFFICE"))
    roles=[]
    for block_id,line_id,word_id,expected in original_word_scope:
        found=[w for w in words if (w[5],w[6],w[7])==(block_id,line_id,word_id)]
        assert len(found)==1 and found[0][4]==expected
        block=[w for w in words if w[5]==block_id]
        block.sort(key=lambda w:(w[6],w[7]))
        original_text=" ".join(str(w[4]) for w in block)
        result=SourceRcpWordEligibilityShadowAuthority().classify_word(
            document_id="source:mary-original",page_id="9",word_text=expected,
            word_bbox=tuple(float(v) for v in found[0][:4]),
            block_text=original_text,block_index=block_id,
            line_index=line_id,word_index=word_id,
            plan_viewport_bbox=candidate_plan,
            schedule_table_bboxes=(SCHEDULE_TABLE,),
            source_defined_ceiling_codes=("GRID","IPF1"),
        )
        roles.append((result.role,result.status))
        assert not result.takeoff_eligible and not result.commercial_projection_allowed
    assert roles==[
        (RcpWordRole.NON_CEILING_LABEL,EvidenceResolutionStatus.ABSTAINED),
        (RcpWordRole.IN_PLAN_CEILING_ANNOTATION,EvidenceResolutionStatus.CANDIDATE),
        (RcpWordRole.GENERAL_NOTE_PROSE,EvidenceResolutionStatus.ABSTAINED),
    ]


def test_nonfinite_source_word_bbox_abstains_before_contract_id():
    """Bad source coordinates must not crash identity normalization or serialize NaN."""
    import json

    authority = SourceRcpWordEligibilityShadowAuthority()
    for invalid in (float("nan"), float("inf"), float("-inf")):
        for axis in range(4):
            bbox = [350.0, 450.0, 380.0, 460.0]
            bbox[axis] = invalid
            kwargs = dict(
                document_id="source:untrusted-p9",
                page_id="9",
                word_text="GRID",
                word_bbox=tuple(bbox),
                block_text="GRID 2400",
                block_index=10,
                line_index=1,
                word_index=0,
                plan_viewport_bbox=(100.0, 100.0, 1100.0, 1700.0),
            )
            first = authority.classify_word(**kwargs)
            replay = authority.classify_word(**kwargs)
            assert first == replay
            assert first.status is EvidenceResolutionStatus.ABSTAINED
            assert first.role is RcpWordRole.OUT_OF_VIEWPORT
            assert not first.is_eligible_for_ceiling_mark
            assert not first.commercial_projection_allowed
            assert not first.takeoff_eligible
            assert first.bbox_pdf_pts == (0.0, 0.0, 0.0, 0.0)
            json.dumps(first.to_dict(), allow_nan=False)


def test_valid_original_bbox_still_only_receives_lexical_candidate():
    authority = SourceRcpWordEligibilityShadowAuthority()
    result = authority.classify_word(
        document_id="source:untrusted-p9",
        page_id="9",
        word_text="GRID",
        word_bbox=(350.0, 450.0, 380.0, 460.0),
        block_text="GRID 2400",
        block_index=10,
        line_index=1,
        word_index=0,
        plan_viewport_bbox=(100.0, 100.0, 1100.0, 1700.0),
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID","IPF1"),
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert not result.takeoff_eligible
    assert not result.commercial_projection_allowed


@pytest.mark.parametrize("block",(
    "GRID OFFICE", "OFFICE GRID", "GRID GRID", "GRID IPF1",
    "IPF1 GRID", "GRID WFPB 2400", "WFPB GRID 2400",
))
def test_same_native_block_foreign_room_or_competing_code_abstains(block):
    a=SourceRcpWordEligibilityShadowAuthority()
    for word in block.split():
        if word not in ("GRID","IPF1","WFPB"):
            continue
        r=a.classify_word(
            document_id="synthetic-source-only",page_id="9",
            word_text=word,word_bbox=(390.,430.,415.,450.),
            block_text=block,plan_viewport_bbox=PLAN_VIEWPORT,
            schedule_table_bboxes=(SCHEDULE_TABLE,),
            source_defined_ceiling_codes=("GRID","IPF1","WFPB"),
        )
        assert r.status is EvidenceResolutionStatus.ABSTAINED
        assert not r.is_eligible_for_ceiling_mark
        assert not r.commercial_projection_allowed


@pytest.mark.parametrize("missing",("viewport","schedule","definitions"))
def test_unissued_original_scope_never_promotes_lexical_grid(missing):
    kw=dict(
        document_id="caller-not-issuer",page_id="9",
        word_text="GRID",word_bbox=(390.,430.,415.,450.),
        block_text="GRID 2400",
        plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID",),
    )
    kw[dict(viewport="plan_viewport_bbox",schedule="schedule_table_bboxes",
            definitions="source_defined_ceiling_codes")[missing]]=None if missing=="viewport" else ()
    r=SourceRcpWordEligibilityShadowAuthority().classify_word(**kw)
    assert r.status is EvidenceResolutionStatus.ABSTAINED
    assert not r.is_eligible_for_ceiling_mark


def test_generic_schedule_defined_ceiling_code_has_no_project_hardcode():
    r=SourceRcpWordEligibilityShadowAuthority().classify_word(
        document_id="different-synthetic-project",page_id="1",
        word_text="CL03",word_bbox=(390.,430.,415.,450.),
        block_text="CL03 2700 CLG",plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("CL03",),
    )
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert r.is_eligible_for_ceiling_mark
    assert not r.commercial_projection_allowed and not r.takeoff_eligible


def test_foreign_unissued_ceiling_code_never_uses_original_lexeme_list():
    for code in ("IPF1","GRID","WFPB","FPB","IP"):
        r=SourceRcpWordEligibilityShadowAuthority().classify_word(
            document_id="source-independent",page_id="1",
            word_text=code,word_bbox=(390.,430.,415.,450.),
            block_text=code,plan_viewport_bbox=PLAN_VIEWPORT,
            schedule_table_bboxes=(SCHEDULE_TABLE,),
            source_defined_ceiling_codes=(),
        )
        assert r.status is EvidenceResolutionStatus.ABSTAINED
        assert not r.is_eligible_for_ceiling_mark


@pytest.mark.parametrize("bad_bbox",[
    (True,450.0,380.0,460.0),
    (350.0,False,380.0,460.0),
    ("350",450.0,380.0,460.0),
    (350.0,450.0,380.0),
    (350.0,450.0,380.0,460.0,1.0),
    (350.0,450.0,None,460.0),
    None,
    350.0,
    (10**1000,450.0,380.0,460.0),
])
def test_malformed_caller_source_bbox_is_safe_deterministic_abstention(bad_bbox):
    import json
    a=SourceRcpWordEligibilityShadowAuthority()
    options=dict(
        document_id="untrusted-native-glyph",page_id="9",
        word_text="GRID",word_bbox=bad_bbox,block_text="GRID 2400",
        plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID",),
        block_index=10,line_index=1,word_index=0,
    )
    x=a.classify_word(**options)
    y=a.classify_word(**options)
    assert x==y
    assert x.status is EvidenceResolutionStatus.ABSTAINED
    assert x.role is RcpWordRole.OUT_OF_VIEWPORT
    assert x.bbox_pdf_pts==(0.0,0.0,0.0,0.0)
    assert not x.is_eligible_for_ceiling_mark
    assert not x.takeoff_eligible and not x.commercial_projection_allowed
    json.dumps(x.to_dict(),allow_nan=False)


def test_exact_native_numeric_bbox_still_only_candidate_with_schedule_scope():
    r=SourceRcpWordEligibilityShadowAuthority().classify_word(
        document_id="synthetic-original",page_id="9",
        word_text="GRID",word_bbox=(350,450,380,460),
        block_text="GRID 2400",plan_viewport_bbox=PLAN_VIEWPORT,
        schedule_table_bboxes=(SCHEDULE_TABLE,),
        source_defined_ceiling_codes=("GRID",),
    )
    assert r.status is EvidenceResolutionStatus.CANDIDATE
    assert not r.takeoff_eligible and not r.commercial_projection_allowed
