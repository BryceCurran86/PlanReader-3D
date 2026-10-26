"""Fail-closed whole-original A600 door schedule table membership; NO takeoff."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import os
from pathlib import Path
import random

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_schedule_authority import SourceDoorScheduleWord as W
from pb_gpt2_original_a600_table_row_scope_shadow import (
    classify_original_door_table_row_scope_shadow,
    audit_published_original_door_table_row_scope_shadow,
)

SHA='b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007'


def _w(block,line,word,text,x,y,*,trusted=True):
    return W(
        observation_id=f'sha-owned-native:{block}:{line}:{word}',
        page_id='1',partition_id='page:1',block_no=block,line_no=line,
        word_no=word,literal=text,trusted=trusted,
        bbox_pdf_pts=(float(x),float(y),float(x)+12.0,float(y)+12.0),
    )


def _original_like_words(*, extra_table_d17=False, drop_no=False,
                         competing_valid_caption=False, spoof_detail=False,
                         untrusted_code=False):
    words=[
        _w(1,0,0,'DOOR',10,400),_w(1,0,1,'SCHEDULE',10,375),
        # An unrelated drawing title is on the opposite side of the header.
        _w(20,0,0,'DOOR',600,400),_w(20,0,1,'SCHEDULE',600,375),
        _w(2,0,0,'No.',200,300),
        _w(2,1,0,'ROOM',200,270),_w(2,1,1,'NAME',200,245),
        _w(2,2,0,'TYPE',200,200),
        _w(3,0,0,'WIDTH',200,160),_w(3,1,0,'HEIGHT',200,120),
        _w(3,2,0,'THICKNESS',200,80),
        _w(4,0,0,'D17',650,302,trusted=not untrusted_code),
        _w(4,1,0,'FREEZER',650,270),
        _w(4,2,0,'SLIDING',650,210),_w(4,2,1,'DOOR',650,185),
        _w(4,3,0,'800',650,160),_w(4,4,0,'2000',650,120),
        _w(5,0,0,'D13',690,302),_w(5,1,0,'PWD',690,270),
        _w(5,2,0,'SINGLE',690,210),_w(5,2,1,'SWING',690,185),
        _w(5,3,0,'920',690,160),_w(5,4,0,'2040',690,120),
        # The SAME original code is printed in a drawing detail.
        _w(6,0,0,'D17',80,1000),_w(6,1,0,'DETAIL',80,950),
    ]
    if drop_no:
        words=[x for x in words if x.literal!='No.']
    if extra_table_d17:
        words.extend((
            _w(7,0,0,'D17',720,302),_w(7,1,0,'FREEZER',720,270),
            _w(7,2,0,'SLIDING',720,210),_w(7,2,1,'DOOR',720,185),
        ))
    if competing_valid_caption:
        words.extend((_w(8,0,0,'DOOR',12,410),_w(8,0,1,'SCHEDULE',12,385)))
    if spoof_detail:
        words.extend((
            _w(9,0,0,'D17',90,1100),_w(9,1,0,'FREEZER',90,1050),
            _w(9,2,0,'SLIDING',90,1000),_w(9,2,1,'DOOR',90,975),
        ))
    return tuple(words)


def _run(words=None):
    return classify_original_door_table_row_scope_shadow(
        _original_like_words() if words is None else words,
        source_sha256='a'*64,revision_id='synthetic-source-rev',
        snapshot_id='synthetic-snapshot',page_id='1',
    )


def test_true_schedule_row_remains_candidate_despite_an_original_detail_same_code():
    result=_run()
    codes={r.code:r for r in result.decisions}
    assert result.source_table_geometry_candidate_only
    assert codes['D17'].original_table_native_blocks==(4,)
    assert codes['D17'].original_other_native_blocks==(6,)
    assert codes['D17'].status is EvidenceResolutionStatus.CANDIDATE
    assert codes['D13'].original_table_native_blocks==(5,)
    assert codes['D13'].status is EvidenceResolutionStatus.CANDIDATE
    assert not any((result.physical_opening_issued,result.source_metric_opening_area_issued,
                    result.commercial_projection_allowed))
    assert not any(r.original_opening_count_granted or r.firm_quantity_issued
                   for r in result.decisions)


def test_two_real_source_table_rows_one_code_abstain():
    codes={r.code:r for r in _run(_original_like_words(extra_table_d17=True)).decisions}
    assert codes['D17'].original_table_native_blocks==(4,7)
    assert codes['D17'].status is EvidenceResolutionStatus.ABSTAINED
    assert codes['D17'].first_unclosed_gate=='duplicate_original_schedule_table_rows'
    assert codes['D13'].status is EvidenceResolutionStatus.CANDIDATE


def test_full_lookalike_detail_still_not_a_true_table_duplicate():
    result=_run(_original_like_words(spoof_detail=True))
    d17=next(r for r in result.decisions if r.code=='D17')
    assert d17.original_table_native_blocks==(4,)
    assert d17.original_other_native_blocks==(6,9)
    assert d17.source_table_row_candidate_only


@pytest.mark.parametrize('bad', [{'drop_no':True}, {'competing_valid_caption':True}])
def test_missing_or_ambiguous_original_table_header_never_grants_row_scope(bad):
    result=_run(_original_like_words(**bad))
    assert not result.source_table_geometry_candidate_only
    assert not any(r.source_table_row_candidate_only for r in result.decisions)
    assert all(r.status is EvidenceResolutionStatus.ABSTAINED for r in result.decisions)


def test_untrusted_source_code_can_not_win_lexical_owner():
    result=_run(_original_like_words(untrusted_code=True))
    assert next(r for r in result.decisions if r.code=='D17').status is EvidenceResolutionStatus.ABSTAINED


def test_census_is_input_order_and_unrelated_content_invariant():
    src=list(_original_like_words())
    initial=_run(tuple(src))
    random.Random(71).shuffle(src)
    assert _run(tuple(src))==initial
    src.extend((_w(999,0,0,'UNRELATED',1100,1150),
                _w(999,0,1,'NOTE',1100,1100)))
    assert _run(tuple(src))==initial


def test_duplicate_source_word_address_and_nan_geometry_rejected():
    src=_original_like_words()
    with pytest.raises(ValueError,match='duplicate'):
        _run(src+(replace(src[0],observation_id='other-observation'),))
    with pytest.raises(ValueError,match='malformed'):
        _run(src+(replace(_w(90,0,0,'D99',10,10),bbox_pdf_pts=(0.,0.,float('nan'),2.)),))


@pytest.mark.parametrize('page', ['01','', '٠١','-1','one',1,None])
def test_untrusted_page_identifier_cannot_alias_published_native_scope(page):
    with pytest.raises(ValueError,match='identity'):
        classify_original_door_table_row_scope_shadow(
            _original_like_words(),source_sha256='a'*64,
            revision_id='s',snapshot_id='s',page_id=page)


def test_sha_owned_real_original_28_table_and_six_foreign_detail_blocks_if_available():
    loc=os.environ.get('PLANREADER_MARYBOROUGH_ORIGINAL_PDF')
    if not loc:
        pytest.skip('private original PDF not mounted on public CI; no source pass claimed')
    import fitz
    content=Path(loc).read_bytes()
    assert sha256(content).hexdigest()==SHA
    with fitz.open(stream=content,filetype='pdf') as document:
        raw=document[27].get_text('words',sort=False)
    # Native geometry CENSUS only: fabricated trust flag in this test cannot
    # authenticate glyphs. The adapter independently uses producer receipts.
    words=tuple(W(observation_id=f'raw-geometry:{x[5]}:{x[6]}:{x[7]}',
                  page_id='28',partition_id='page:28',
                  block_no=x[5],line_no=x[6],word_no=x[7],literal=str(x[4]),
                  trusted=True,bbox_pdf_pts=tuple(float(v) for v in x[:4]))
                for x in raw)
    result=classify_original_door_table_row_scope_shadow(
        words,source_sha256=SHA,revision_id='raw-source-geometry-only',
        snapshot_id='raw-source-geometry-only',page_id='28')
    assert result.source_table_geometry_candidate_only
    assert sum(len(d.original_table_native_blocks) for d in result.decisions)==28
    assert sum(len(d.original_other_native_blocks) for d in result.decisions)==6
    assert {f'D{i:02d}' for i in range(1,29)} <= {d.code for d in result.decisions}
    # The additional original 'D3' note is NOT an alias for scheduled 'D03'.
    note=next(d for d in result.decisions if d.code=='D3')
    assert note.status is EvidenceResolutionStatus.ABSTAINED
    assert note.original_table_native_blocks==()
    for code in ('D13','D16','D17'):
        record=next(d for d in result.decisions if d.code==code)
        assert len(record.original_table_native_blocks)==1
        assert len(record.original_other_native_blocks)==1
        assert record.status is EvidenceResolutionStatus.CANDIDATE
        assert not record.customer_projection_allowed
    # The original includes five more same-code words INSIDE other native
    # blocks (illustration notes). Preserve these as separately addressable
    # observations instead of dropping or counting them as installed doors.
    assert sum(len(d.original_code_observation_ids) for d in result.decisions)==39
    assert len(result.all_original_code_native_blocks)==38
    assert sha256(Path(loc).read_bytes()).hexdigest()==SHA


def test_an_unrelated_sentence_can_mention_the_door_code_without_creating_a_new_door():
    note=(_w(600,0,0,'REVIEW',950,900),_w(600,0,1,'D17',980,900))
    baseline=_run()
    result=_run(_original_like_words()+note)
    before=next(d for d in baseline.decisions if d.code=='D17')
    after=next(d for d in result.decisions if d.code=='D17')
    assert after.original_table_native_blocks==before.original_table_native_blocks
    assert after.original_other_native_blocks==before.original_other_native_blocks
    assert len(after.original_code_observation_ids)==len(before.original_code_observation_ids)+1
    assert not after.original_opening_count_granted


@pytest.mark.parametrize('untrusted_field', ['FREEZER', 'SLIDING', '800', '2000'])
def test_original_row_with_untrusted_semantics_is_not_source_eligible(untrusted_field):
    # Existing source-door row parser marks complete_native_row_text_trusted
    # false when even ONE field's glyph/clip evidence is unresolved.
    # A trusted Dxx code alone cannot make the full table row a source owner.
    original=_original_like_words()
    damaged=tuple(
        replace(word,trusted=False)
        if word.block_no==4 and word.literal==untrusted_field else word
        for word in original
    )
    result=_run(damaged)
    codes={row.code:row for row in result.decisions}
    assert codes['D17'].status is EvidenceResolutionStatus.ABSTAINED
    assert not codes['D17'].source_table_row_candidate_only
    assert codes['D17'].first_unclosed_gate=='original_schedule_row_semantic_words_untrusted'
    # The other independent row and foreign same-code DETAIL remain intact.
    assert codes['D13'].status is EvidenceResolutionStatus.CANDIDATE
    assert codes['D17'].original_other_native_blocks==(6,)
    assert not result.physical_opening_issued

def test_untrusted_second_original_schedule_caption_is_still_a_competitor():
    # An untrusted second native caption is NOT permission to elect the
    # remaining trusted title and publish apparently unique table rows.
    src=_original_like_words()
    untrusted_competitor=(
        _w(808,0,0,'DOOR',12,420,trusted=True),
        _w(808,0,1,'SCHEDULE',12,385,trusted=False),
    )
    result=_run(src+untrusted_competitor)
    assert not result.source_table_geometry_candidate_only
    assert not result.source_title_observation_ids
    assert all(row.status is EvidenceResolutionStatus.ABSTAINED for row in result.decisions)
    assert not any(row.source_table_row_candidate_only for row in result.decisions)
    assert not result.physical_opening_issued


def _published_synthetic_original_source(monkeypatch, schedule_words, *, plan_words=()):
    """Real source-producer revision/snapshot, synthetic typed word universe.

    The monkeypatch substitutes ONLY a generated source-neutral observation
    fixture; this is not a private-PDF text-integrity certification.
    """
    import fitz
    import pb_source_door_schedule_authority as schedule_module
    import pb_source_plan_door_correspondence_authority as plan_module
    from pb_source_visibility_authority import SourceVisibilityProducer

    document=fitz.open()
    document.new_page(width=400,height=400)
    document.new_page(width=400,height=400)
    raw=document.tobytes()
    document.close()
    source=SourceVisibilityProducer(
        producer_method="gpt2-a600-table-publisher-integration-synthetic",
        producer_version="1",
    )
    published=source.ingest_native_pdf_bytes(
        document_id="source-neutral-table-plan",
        source_bytes=raw,
        source_locator="memory://synthetic-source-only.pdf",
        page_ids=("1","2"),
    )
    monkeypatch.setattr(
        schedule_module,"_producer_owned_native_words",
        lambda issuer,snapshot,page_id:
            tuple(schedule_words) if page_id=="1" else tuple(plan_words),
    )
    monkeypatch.setattr(
        plan_module,"_producer_owned_native_words",
        lambda issuer,snapshot,page_id:
            tuple(schedule_words) if page_id=="1" else tuple(plan_words),
    )
    return source,published


def test_actual_published_schedule_to_plan_consumer_distinguishes_detail_code(monkeypatch):
    """Foreign DETAIL D17 never creates a duplicate table ROW or door count."""
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    code=W(
        observation_id="independent-plan-native:D17",page_id="2",
        partition_id="page:2",block_no=99,line_no=0,word_no=0,
        literal="D17",trusted=True,
        bbox_pdf_pts=(20.0,20.0,32.0,32.0),
    )
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words(),plan_words=(code,),
    )
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    rows={r.code:r for r in schedule.rows}
    assert schedule.original_table_row_scope_authenticated
    assert schedule.complete_source_word_universe
    assert rows["D17"].status=="source_schedule_row_text_authenticated"
    assert rows["D17"].native_block_no==4
    assert "D17" not in schedule.unparsed_original_door_codes
    assert "sha-owned-native:6:0:0" in schedule.original_detail_code_observation_ids
    assert schedule.new_opening_counts==schedule.new_opening_areas_m2==0
    result=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=pub.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    pair=next(p for p in result.pairs if p.code=="D17")
    assert pair.source_code_correspondence_proven
    assert pair.schedule_source_row_status=="source_schedule_row_text_authenticated"
    assert pair.first_unclosed_gate=="physical_door_symbol_host_and_customer_scope_unproven"
    assert not pair.physical_door_symbol_bound
    assert not pair.structural_host_bound
    assert pair.opening_count is None
    assert pair.installed_opening_area_m2 is None
    assert not pair.customer_quantity_authorized
    assert result.new_opening_counts==result.new_opening_area_quantities==0


def test_actual_published_schedule_retains_true_duplicate_row_veto(monkeypatch):
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words(extra_table_d17=True),
    )
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    matches=[r for r in schedule.rows if r.code=="D17"]
    assert len(matches)==2
    assert all(r.status=="source_schedule_row_duplicate_code_conflict"
               for r in matches)
    # The complete SOURCE table census must be false even though both
    # duplicated printed rows individually parsed, not just D17's own row.
    assert not schedule.complete_source_word_universe
    assert schedule.original_table_row_scope_authenticated
    assert schedule.new_opening_counts==schedule.new_opening_areas_m2==0


@pytest.mark.parametrize("problem",(
    {"drop_no":True},
    {"competing_valid_caption":True},
))
def test_actual_publisher_does_not_trust_missing_or_rival_table_scope(
    monkeypatch,problem,
):
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words(**problem),
    )
    result=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert not result.original_table_row_scope_authenticated
    assert not result.complete_source_word_universe
    assert result.new_opening_counts==result.new_opening_areas_m2==0


def test_original_private_source_publisher_table_census_if_provisioned():
    loc=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not loc:
        pytest.skip("original private source not available in public CI")
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    original=Path(loc).read_bytes()
    assert sha256(original).hexdigest()==SHA
    producer=SourceVisibilityProducer(
        producer_method="gpt2-private-original-schedule-review",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    publication=producer.ingest_native_pdf_bytes(
        document_id="maryborough-original-a600",
        source_bytes=original,
        source_locator="memory://private-original.pdf",
        page_ids=("28",),
    )
    result=inspect_published_door_schedule(
        producer,
        revision_id=publication.revision.revision_id,
        page_id="28",
    )
    assert result.source_sha256==SHA
    assert result.snapshot_id==publication.snapshot.snapshot_id
    assert set(result.all_original_source_codes)=={
        f"D{i:02d}" for i in range(1,29)
    }
    assert len(result.rows)==28
    assert result.new_opening_counts==result.new_opening_areas_m2==0
    # A private-original positive must prove table membership and the
    # COMPLETE source census, not merely a plausible 28-row lexical parse.
    # A skipped/failed source authority gate is never a passing release test.
    assert result.original_table_row_scope_authenticated
    assert result.complete_source_word_universe
    assert "D13" not in result.unparsed_original_door_codes
    assert "D16" not in result.unparsed_original_door_codes
    assert "D17" not in result.unparsed_original_door_codes
    assert len(result.original_detail_code_observation_ids)>=6
    assert all(row.status!="source_schedule_row_duplicate_code_conflict"
               for row in result.rows)
    assert sha256(Path(loc).read_bytes()).hexdigest()==SHA


def test_second_dcode_inside_true_schedule_row_is_unparsed_and_blocks_consumer(
    monkeypatch,
):
    # Non-first original word in true TABLE row cannot disappear from the
    # complete publisher's D-code universe. Unrelated DETAIL codes do not
    # participate, even where the same lettering appears.
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    original=_original_like_words()
    conflict=_w(4,5,0,"D99",650,100)
    code=W(
        observation_id="original-plan:D17",page_id="2",
        partition_id="page:2",block_no=99,line_no=0,word_no=0,
        literal="D17",trusted=True,
        bbox_pdf_pts=(20.0,20.0,32.0,32.0),
    )
    source,pub=_published_synthetic_original_source(
        monkeypatch,original+(conflict,),plan_words=(code,),
    )
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    # The underlying native row parser already rejects any block having
    # two D-codes, so D17 MUST NOT appear as a constructed row. Both the
    # unparsed primary and its hidden second code remain explicit blockers.
    assert not any(row.code=="D17" for row in schedule.rows)
    assert {"D17","D99"} <= set(schedule.unparsed_original_door_codes)
    # The typed COMPLETE native Dxx code census cannot silently drop
    # a second source word merely because row construction abstained.
    assert {"D17","D99"} <= set(schedule.all_original_source_codes)
    assert not schedule.complete_source_word_universe
    assert schedule.original_table_row_scope_authenticated
    assert schedule.original_detail_code_observation_ids==(
        "sha-owned-native:6:0:0",
    )
    paired=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=pub.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    d17=next(x for x in paired.pairs if x.code=="D17")
    assert not d17.source_code_correspondence_proven
    assert d17.first_unclosed_gate=="original_schedule_competing_unparsed_code"
    assert not paired.source_schedule_observation_universe_complete
    assert paired.new_opening_counts==paired.new_opening_area_quantities==0




@pytest.mark.parametrize("inside_table", [True, False])
def test_nonleading_dcode_in_separate_native_block_reaches_real_schedule_consumer(
    monkeypatch, inside_table,
):
    """A NOTE/D99 block in TABLE must veto D13; a foreign DETAIL must not."""
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    # The code is NOT block-leading. Its own source bbox, rather than the
    # NOTE's bbox or a nearest-row guess, establishes table membership.
    x, y = (690, 302) if inside_table else (80, 1000)
    extra = (
        _w(72, 0, 0, "NOTE", x - 35, y),
        _w(72, 0, 1, "D99", x, y),
    )
    plan_tag = W(
        observation_id="original-plan:D13", page_id="2",
        partition_id="page:2", block_no=93, line_no=0, word_no=0,
        literal="D13", trusted=True,
        bbox_pdf_pts=(20.0, 20.0, 32.0, 32.0),
    )
    original = _original_like_words() + extra
    shadow = _run(original)
    d99 = next(row for row in shadow.decisions if row.code == "D99")
    assert d99.original_code_observation_ids == ("sha-owned-native:72:0:1",)
    assert d99.original_table_native_blocks == ((72,) if inside_table else ())
    assert not d99.source_table_row_candidate_only
    source, published = _published_synthetic_original_source(
        monkeypatch, original, plan_words=(plan_tag,),
    )
    schedule = inspect_published_door_schedule(
        source, revision_id=published.revision.revision_id, page_id="1",
    )
    assert schedule.original_table_row_scope_authenticated
    assert schedule.complete_source_word_universe is (not inside_table)
    assert ("D99" in schedule.unparsed_original_door_codes) is inside_table
    assert "D99" in schedule.all_original_source_codes
    paired = inspect_published_plan_and_schedule_door_codes(
        source, revision_id=published.revision.revision_id,
        plan_page_id="2", schedule_page_id="1",
    )
    d13 = next(row for row in paired.pairs if row.code == "D13")
    assert paired.source_schedule_observation_universe_complete is (not inside_table)
    assert d13.source_code_correspondence_proven is (not inside_table)
    assert paired.eligible_printed_code_pair_count == (0 if inside_table else 1)
    assert paired.new_opening_counts == paired.new_opening_area_quantities == 0
    assert not d13.customer_quantity_authorized

def test_drawing_detail_multiple_original_codes_remains_foreign_source_not_table(
    monkeypatch,
):
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    # Source block 6 is OUTSIDE table, and must retain its secondary native
    # code rather than contaminating the 28-row A600 source membership.
    detail_second=_w(6,2,0,"D27",80,900)
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words()+(detail_second,),
    )
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert schedule.complete_source_word_universe
    assert not schedule.unparsed_original_door_codes
    assert next(row for row in schedule.rows if row.code=="D17").status==(
        "source_schedule_row_text_authenticated"
    )
    assert schedule.original_detail_code_observation_ids==(
        "sha-owned-native:6:0:0","sha-owned-native:6:2:0",
    )
    assert schedule.new_opening_counts==schedule.new_opening_areas_m2==0


def test_real_published_consumer_cannot_claim_complete_table_if_another_code_is_duplicated(
    monkeypatch,
):
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    plan_tag=W(
        observation_id="original-plan:D13",page_id="2",
        partition_id="page:2",block_no=93,line_no=0,word_no=0,
        literal="D13",trusted=True,
        bbox_pdf_pts=(20.0,20.0,32.0,32.0),
    )
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words(extra_table_d17=True),
        plan_words=(plan_tag,),
    )
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert "D17" not in schedule.unparsed_original_door_codes
    assert len([row for row in schedule.rows if row.code=="D17"])==2
    assert not schedule.complete_source_word_universe
    paired=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=pub.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    assert not paired.source_schedule_observation_universe_complete
    d13=next(x for x in paired.pairs if x.code=="D13")
    assert not d13.source_code_correspondence_proven
    assert d13.first_unclosed_gate=="original_schedule_row_or_universe_unverified"
    assert paired.eligible_printed_code_pair_count==0
    assert paired.new_opening_counts==paired.new_opening_area_quantities==0


def test_generic_door_code_lexeme_preserves_real_one_digit_rows():
    # Native source role, not digit padding, decides TABLE versus DETAIL.
    from pb_source_door_schedule_authority import _DOOR_CODE
    for code in ("D1", "D3", "D03", "D28", "D100"):
        assert _DOOR_CODE.fullmatch(code)
    for malformed in ("D0", "D00", "D000", "D03A"):
        assert not _DOOR_CODE.fullmatch(malformed)


@pytest.mark.parametrize("code", ("D1", "D3"))
def test_genuine_single_digit_table_row_retained_with_foreign_same_code_detail(monkeypatch, code):
    """A source-authenticated TABLE D1/D3 cannot be erased by a DETAIL D1/D3."""
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    in_table=(
        _w(70,0,0,code,735,302),
        _w(70,1,0,"FOYER",735,270),
        _w(70,2,0,"SWING",735,210),
        _w(70,3,0,"920",735,160),
        _w(70,4,0,"2040",735,120),
    )
    foreign=(_w(71,0,0,code,80,1000),_w(71,1,0,"DETAIL",80,950))
    original=_original_like_words()+in_table+foreign
    source,pub=_published_synthetic_original_source(monkeypatch,original)
    result=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert result.original_table_row_scope_authenticated
    assert result.complete_source_word_universe
    assert code in result.all_original_source_codes
    assert code not in result.unparsed_original_door_codes
    assert "sha-owned-native:71:0:0" in result.original_detail_code_observation_ids
    assert next(row for row in result.rows if row.code==code).status==(
        "source_schedule_row_text_authenticated"
    )
    shadow=_run(original)
    decision=next(d for d in shadow.decisions if d.code==code)
    assert decision.original_table_native_blocks==(70,)
    assert decision.original_other_native_blocks==(71,)
    assert decision.status is EvidenceResolutionStatus.CANDIDATE
    assert decision.source_table_row_candidate_only
    paired=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=pub.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    assert paired.source_schedule_observation_universe_complete
    missing=next(p for p in paired.pairs if p.code==code)
    assert not missing.source_code_correspondence_proven
    assert missing.first_unclosed_gate=="original_plan_door_tag_missing"
    assert result.new_opening_counts==result.new_opening_areas_m2==0
    assert paired.new_opening_counts==paired.new_opening_area_quantities==0


@pytest.mark.parametrize("code", ("D1", "D3"))
def test_genuine_single_digit_plan_and_table_code_correspond_without_count(monkeypatch, code):
    """The real source-published plan consumer accepts syntax, not door existence."""
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    in_table=(
        _w(70,0,0,code,735,302),_w(70,1,0,"FOYER",735,270),
        _w(70,2,0,"SWING",735,210),_w(70,3,0,"920",735,160),
        _w(70,4,0,"2040",735,120),
    )
    foreign=(_w(71,0,0,code,80,1000),_w(71,1,0,"DETAIL",80,950))
    plan=(W(
        observation_id="source-plan:"+code,page_id="2",partition_id="page:2",
        block_no=100,line_no=0,word_no=0,literal=code,trusted=True,
        bbox_pdf_pts=(20.0,20.0,32.0,32.0),
    ),)
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words()+in_table+foreign,plan_words=plan,
    )
    result=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=pub.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    pair=next(row for row in result.pairs if row.code==code)
    assert pair.source_code_correspondence_proven
    assert pair.first_unclosed_gate=="physical_door_symbol_host_and_customer_scope_unproven"
    assert not pair.physical_door_symbol_bound
    assert not pair.structural_host_bound
    assert pair.opening_count is None
    assert pair.installed_opening_area_m2 is None
    assert not pair.customer_quantity_authorized
    assert result.eligible_printed_code_pair_count==1
    assert result.new_opening_counts==result.new_opening_area_quantities==0


@pytest.mark.parametrize("bad", ("D0", "D00"))
def test_malformed_zero_door_code_inside_table_still_blocks_census(monkeypatch,bad):
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    malformed=(
        _w(70,0,0,bad,735,302),_w(70,1,0,"FOYER",735,270),
        _w(70,2,0,"SWING",735,210),_w(70,3,0,"920",735,160),
        _w(70,4,0,"2040",735,120),
    )
    source,pub=_published_synthetic_original_source(
        monkeypatch,_original_like_words()+malformed,
    )
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert bad in schedule.unparsed_original_door_codes
    assert bad not in schedule.all_original_source_codes
    assert not schedule.complete_source_word_universe
    assert not any(row.code==bad for row in schedule.rows)
    shadow=_run(_original_like_words()+malformed)
    decision=next(d for d in shadow.decisions if d.code==bad)
    assert decision.status is EvidenceResolutionStatus.ABSTAINED
    assert decision.first_unclosed_gate=="noncanonical_door_code_inside_printed_table"
    assert schedule.new_opening_counts==schedule.new_opening_areas_m2==0


def test_unpadded_d3_secondary_word_in_real_table_row_blocks_completeness(monkeypatch):
    """The second native table word must not evade the Dxx code census."""
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    original=_original_like_words()+(_w(4,5,0,"D3",655,302),)
    source,pub=_published_synthetic_original_source(monkeypatch,original)
    schedule=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert "D3" in schedule.unparsed_original_door_codes
    assert not schedule.complete_source_word_universe
    assert not any(row.code=="D3" for row in schedule.rows)
    assert schedule.new_opening_counts==schedule.new_opening_areas_m2==0


def test_foreign_d3_outside_table_remains_source_receipt_not_phantom_pair(monkeypatch):
    """Foreign D3 stays in the full native census, not an installed door."""
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    original=_original_like_words()+(
        _w(71,0,0,"D3",80,1000),
        _w(71,1,0,"CONTRAST",80,950),
    )
    source,pub=_published_synthetic_original_source(monkeypatch,original)
    result=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="1",
    )
    assert result.original_table_row_scope_authenticated
    assert result.complete_source_word_universe
    assert "D3" not in result.unparsed_original_door_codes
    assert "D3" in result.all_original_source_codes
    assert "sha-owned-native:71:0:0" in result.original_detail_code_observation_ids
    paired=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=pub.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    assert "D3" not in {row.code for row in paired.pairs}
    assert paired.source_schedule_observation_universe_complete
    assert result.new_opening_counts==result.new_opening_areas_m2==0
    assert paired.new_opening_counts==paired.new_opening_area_quantities==0


def test_plan_d3_without_authenticated_schedule_row_remains_unresolved(monkeypatch):
    """A plan D3 is not silently deleted, nor upgraded from a foreign detail."""
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    canonical=W(
        observation_id="original-plan:D17",page_id="2",
        partition_id="page:2",block_no=100,line_no=0,word_no=0,
        literal="D17",trusted=True,
        bbox_pdf_pts=(20.0,20.0,32.0,32.0),
    )
    foreign=W(
        observation_id="original-plan:detail-D3",page_id="2",
        partition_id="page:2",block_no=101,line_no=0,word_no=0,
        literal="D3",trusted=True,
        bbox_pdf_pts=(35.0,20.0,47.0,32.0),
    )
    source,published=_published_synthetic_original_source(
        monkeypatch,_original_like_words(),plan_words=(foreign,canonical),
    )
    result=inspect_published_plan_and_schedule_door_codes(
        source,revision_id=published.revision.revision_id,
        plan_page_id="2",schedule_page_id="1",
    )
    codes={item.code:item for item in result.pairs}
    assert "D3" in codes
    assert "D3" in result.unresolved_codes
    assert not codes["D3"].source_code_correspondence_proven
    assert codes["D3"].first_unclosed_gate=="original_schedule_row_missing_or_competing"
    assert codes["D17"].source_code_correspondence_proven
    assert codes["D17"].first_unclosed_gate=="physical_door_symbol_host_and_customer_scope_unproven"
    assert result.source_plan_observation_universe_complete
    assert result.source_schedule_observation_universe_complete
    assert result.eligible_printed_code_pair_count==1
    assert result.new_opening_counts==result.new_opening_area_quantities==0
    assert not codes["D17"].customer_quantity_authorized


def test_private_original_a110_plan_to_a600_schedule_same_snapshot_if_provisioned():
    """Original two-sheet code receipts are complete, not installed opening counts.

    The source producer must retain all native words on p7 and p28 while an
    unpadded p28 drawing D3 stays outside schedule/plan code correspondence.
    """
    loc=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not loc:
        pytest.skip("original private source not available in public CI")
    import fitz
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_source_plan_door_correspondence_authority import (
        inspect_published_plan_and_schedule_door_codes,
    )
    from pb_source_door_schedule_authority import _DOOR_CODE
    content=Path(loc).read_bytes()
    assert sha256(content).hexdigest()==SHA
    with fitz.open(stream=content,filetype="pdf") as pdf:
        plan_words=pdf[6].get_text("words",sort=False)
        schedule_words=pdf[27].get_text("words",sort=False)
    canonical={f"D{i:02d}" for i in range(1,29)}
    actual_plan=[str(w[4]) for w in plan_words if _DOOR_CODE.fullmatch(str(w[4]))]
    assert len(actual_plan)==28
    assert set(actual_plan)==canonical
    assert canonical <= {str(w[4]) for w in schedule_words}
    assert any(str(w[4])=="D3" for w in schedule_words)
    producer=SourceVisibilityProducer(
        producer_method="gpt2-private-original-cross-sheet-lexical-review",
        producer_version="1",
        source_native_finish_text_shadow=True,
    )
    publication=producer.ingest_native_pdf_bytes(
        document_id="maryborough-original-a110-a600",
        source_bytes=content,
        source_locator="memory://private-original.pdf",
        page_ids=("7","28"),
    )
    result=inspect_published_plan_and_schedule_door_codes(
        producer,revision_id=publication.revision.revision_id,
        plan_page_id="7",schedule_page_id="28",
    )
    assert result.source_sha256==SHA
    assert result.snapshot_id==publication.snapshot.snapshot_id
    assert result.source_plan_observation_universe_complete
    # The real two-sheet consumer must authenticate at least one source
    # code pair; a zero-positive source graph is NOT an original replay pass.
    # This remains source text correspondence, never an installed door.
    assert result.source_schedule_observation_universe_complete
    assert result.eligible_printed_code_pair_count > 0
    assert canonical <= {row.code for row in result.pairs}
    assert "D3" not in {row.code for row in result.pairs}
    assert all(row.opening_count is None and
               row.installed_opening_area_m2 is None and
               not row.customer_quantity_authorized for row in result.pairs)
    assert result.new_opening_counts==result.new_opening_area_quantities==0
    assert result.frozen_benchmark_accuracy is None
