"""Reusable original-app door policy: source boundaries, not per-door coding."""
from __future__ import annotations

from dataclasses import replace
import hashlib
import os
from pathlib import Path

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_original_door_head_wall_default import (
    _assess_source_row, collect_original_door_head_wall_defaults as collect,
)
from pb_source_door_schedule_authority import (
    SourceDoorScheduleResult, SourceDoorScheduleWord,
    _original_door_schedule_column_proof, _original_source_row_candidates,
    inspect_published_door_schedule,
)
from pb_source_rcp_height_material_evidence import (
    SourceRcpHeightMaterialCandidate, collect_original_rcp_height_material_evidence,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_structural_door_threshold_wall_continuity_authority import (
    StructuralDoorThresholdWallContinuityAuthority,
)
from tests.test_gpt2_a600_native_column_header_source_roles import _world


def fixture(code="D13"):
    words = tuple(replace(w, literal=code) if w.literal == "D13" else w for w in _world())
    rows, title = _original_door_schedule_column_proof(words, _original_source_row_candidates(words))
    schedule = SourceDoorScheduleResult(
        source_sha256="a" * 64, revision_id="revision", snapshot_id="snapshot",
        page_id="1", rows=rows, all_original_source_codes=(code, "D18"),
        title_source_trusted=title, complete_source_word_universe=True,
    )
    return schedule, words


def assess(schedule, words, code="D13", **kw):
    return _assess_source_row(document_id="doc", schedule=schedule,
                              door_code=code, words=words, **kw)


def pair(**kw):
    fields = dict(record_id="rcp-pair", document_id="doc", revision_id="revision",
                  snapshot_id="snapshot", source_sha256="a" * 64, page_id="2",
                  source_partition_id="page:2", block_no=1, material_line_no=0,
                  height_line_no=1, material_code="GRID", height_mm=2400,
                  material_observation_id="material", height_observation_id="height",
                  material_bbox_pdf_pts=(0., 0., 4., 4.), height_bbox_pdf_pts=(12., 0., 17., 4.))
    fields.update(kw)
    return SourceRcpHeightMaterialCandidate(**fields)


@pytest.mark.parametrize("code", ["D01", "D02", "D07", "D08", "D09", "D29", "D90"])
def test_one_policy_works_for_arbitrary_schedule_codes_without_per_door_geometry(code):
    sch, words = fixture(code)
    result = assess(sch, words, code)
    assert result.status is S.CANDIDATE and result.wall_above_frame_presumed
    assert result.schedule_leaf_height_literal == "2040"
    assert result.frame_top_mm is result.wall_above_frame_mm is None
    assert result.door_opening_remains_open_below_frame
    assert not result.room_ceiling_binding_authenticated
    assert not result.physical_host_authenticated
    assert not result.commercial_projection_allowed and not result.takeoff_eligible
    assert not result.benchmark_credit


def test_rcp_height_is_an_audited_selector_not_a_frame_top_or_room_binding():
    sch, words = fixture()
    result = assess(sch, words, selected_pair=pair(), pair_requested=True)
    assert result.wall_above_frame_presumed
    assert result.selected_ceiling_height_mm == 2400
    assert result.frame_top_mm is result.wall_above_frame_mm is None
    assert not result.room_ceiling_binding_authenticated
    assert not result.commercial_projection_allowed
    for invalid in (None, pair(source_sha256="b"*64), pair(snapshot_id="foreign"),
                    pair(document_id="foreign"), pair(revision_id="foreign")):
        r = assess(sch, words, selected_pair=invalid, pair_requested=True)
        assert r.status is S.ABSTAINED and not r.wall_above_frame_presumed


@pytest.mark.parametrize("height", [2040, 2000])
def test_leaf_meeting_or_exceeding_selected_ceiling_requires_review(height):
    sch, words = fixture()
    r = assess(sch, words, selected_pair=pair(height_mm=height), pair_requested=True)
    assert r.status is S.ABSTAINED
    assert r.frame_top_mm is r.wall_above_frame_mm is None
    assert not r.wall_above_frame_presumed


@pytest.mark.parametrize("phrase", [
    ("NO", "WALL", "ABOVE"), ("OPEN", "TO", "CEILING"),
    ("FULL", "HEIGHT"), ("GLAZED", "TRANSOM"), ("OPEN", "TRANSOM"),
    ("PARTITION", "STOPS", "BELOW", "CEILING"),
])
def test_exact_trusted_native_row_exception_prevents_presumed_wall(phrase):
    sch, words = fixture()
    row = next(r for r in sch.rows if r.code == "D13")
    notes = tuple(SourceDoorScheduleWord(
        observation_id=f"note:{i}", page_id="1", partition_id="page:1",
        block_no=row.native_block_no, line_no=20, word_no=i,
        literal=text, trusted=True,
    ) for i, text in enumerate(phrase))
    row = replace(row, observation_ids=(*row.observation_ids, *(w.observation_id for w in notes)))
    sch = replace(sch, rows=tuple(row if r.code == row.code else r for r in sch.rows))
    r = assess(sch, (*words, *notes))
    assert r.status is S.CANDIDATE and not r.wall_above_frame_presumed
    assert set(r.exception_source_ids) == {w.observation_id for w in notes}
    assert not r.commercial_projection_allowed


def test_foreign_or_untrusted_row_note_and_repeated_code_do_not_pass():
    sch, words = fixture()
    row = next(r for r in sch.rows if r.code == "D13")
    for bad in (
        replace(sch, title_source_trusted=False),
        replace(sch, unparsed_original_door_codes=("D13",)),
        replace(sch, rows=(*sch.rows, row)),
        replace(sch, rows=tuple(replace(r, complete_native_row_text_trusted=False)
                                if r.code == "D13" else r for r in sch.rows)),
    ):
        assert assess(bad, words).status is S.ABSTAINED
    for bad_words in (
        tuple(w for w in words if w.observation_id != row.original_height_word_id),
        tuple(replace(w, trusted=False) if w.observation_id == row.original_height_word_id else w
              for w in words),
        tuple(replace(w, page_id="2") if w.observation_id == row.original_height_word_id else w
              for w in words),
    ):
        assert assess(sch, bad_words).status is S.ABSTAINED
    assert assess(sch, words, "D18").status is S.ABSTAINED  # display shelving is not a frame
    assert assess(sch, words, "D99").status is S.ABSTAINED


def test_order_determinism_no_mutation_and_distinct_policy_identity():
    sch, words = fixture()
    before = (sch, words)
    a = assess(sch, words)
    b = assess(replace(sch, rows=tuple(reversed(sch.rows))), tuple(reversed(words)))
    assert a == b and (sch, words) == before
    sch2, words2 = fixture("D29")
    assert assess(sch2, words2, "D29").record_id != a.record_id


def test_public_entry_does_not_accept_supplied_frames_schedules_or_exception_ids():
    with pytest.raises(TypeError):
        collect(source=None, revision_id="rev", schedule_page_id="1", enabled=True,
                frame_top_mm=2100, frame_top_source_id="invented-source-id")
    with pytest.raises(TypeError):
        collect(source=None, revision_id="rev", schedule_page_id="1", enabled=True,
                schedule=fixture()[0])
    with pytest.raises(TypeError):
        collect(source=None, revision_id="rev", schedule_page_id="1", enabled=True,
                exception_source_id="invented-note")
    with pytest.raises(TypeError, match="requires_source_producer"):
        collect(source=object(), revision_id="rev", schedule_page_id="1", enabled=True)


def test_default_off_isolates_existing_structural_path_and_requires_boolean():
    authority = StructuralDoorThresholdWallContinuityAuthority()
    assert authority.assess_all_scheduled_door_heads(
        source=None, revision_id="not-read", schedule_page_id="1") == ()
    for flag in (1, "yes", None):
        with pytest.raises(TypeError, match="requires_bool"):
            collect(source=None, revision_id="not-read", schedule_page_id="1", enabled=flag)


def test_actual_generated_pdf_missing_schedule_and_foreign_revision_fail_closed():
    doc = fitz.open()
    doc.new_page()
    raw = doc.tobytes()
    doc.close()
    source = SourceVisibilityProducer(producer_method="generated-door-policy", producer_version="1")
    pub = source.ingest_native_pdf_bytes(
        document_id="generated", source_bytes=raw, source_locator="memory://blank.pdf", page_ids=("1",))
    assert collect(source=source, revision_id=pub.revision.revision_id,
                   schedule_page_id="1", enabled=True) == ()
    with pytest.raises(ValueError, match="revision_not_producer_owned"):
        collect(source=source, revision_id="foreign", schedule_page_id="1", enabled=True)
    with pytest.raises(ValueError, match="unknown_schedule_code"):
        collect(source=source, revision_id=pub.revision.revision_id, schedule_page_id="1",
                ceiling_pair_ids_by_door={"D99": "invented"}, enabled=True)


def test_genuine_original_schedule_census_uses_the_same_policy_for_all_source_doors():
    named = os.environ.get("PLANREADER_ORIGINAL_MARYBOROUGH")
    if not named:
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN: private original not provided")
    path = Path(named)
    original = path.read_bytes()
    sha = hashlib.sha256(original).hexdigest()
    assert sha == "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    source = SourceVisibilityProducer(
        producer_method="original-generic-door-head-policy", producer_version="1",
        source_native_finish_text_shadow=True,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id="original-generic-door-head-policy", source_bytes=original,
        source_locator=str(path), page_ids=("9", "28"),
    )
    sch = inspect_published_door_schedule(source, revision_id=pub.revision.revision_id, page_id="28")
    values = StructuralDoorThresholdWallContinuityAuthority().assess_all_scheduled_door_heads(
        source=source, revision_id=pub.revision.revision_id, schedule_page_id="28", enabled=True)
    assert {r.door_code for r in values} == set(sch.all_original_source_codes)
    by_code = {r.door_code: r for r in values}
    assert all(by_code[code].wall_above_frame_presumed for code in ("D07", "D08", "D09"))
    assert all(by_code[code].status is S.ABSTAINED for code in sch.unparsed_original_door_codes)
    assert all(not r.commercial_projection_allowed and not r.benchmark_credit
               and r.frame_top_mm is r.wall_above_frame_mm is None for r in values)
    candidates = collect_original_rcp_height_material_evidence(
        source=source, revision_id=pub.revision.revision_id, page_id="9").candidate_records
    selector = next(r.record_id for r in candidates if r.height_mm == 2400)
    selectors = {"D07": selector}
    linked = collect(source=source, revision_id=pub.revision.revision_id, schedule_page_id="28",
                     ceiling_page_ids=("9",), ceiling_pair_ids_by_door=selectors, enabled=True)
    assert next(r for r in linked if r.door_code == "D07").ceiling_height_pair_id == selector
    assert all(not r.room_ceiling_binding_authenticated for r in linked)
    assert selectors == {"D07": selector}
    forged = collect(source=source, revision_id=pub.revision.revision_id, schedule_page_id="28",
                     ceiling_page_ids=("9",), ceiling_pair_ids_by_door={"D07": "foreign-receipt"}, enabled=True)
    assert next(r for r in forged if r.door_code == "D07").status is S.ABSTAINED
    assert hashlib.sha256(path.read_bytes()).hexdigest() == sha
