"""Existing PDF source publisher owns all A600 door words, not guessed counts."""
from pathlib import Path
import hashlib

import fitz
import pytest

from pb_source_visibility_authority import SourceVisibilityProducer
from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord as W,
    _original_source_row_candidates as rows,
    inspect_published_door_schedule,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _word(block,index,literal,trusted=True):
    return W(
        observation_id=f"source-word:{block}:{index}",
        page_id="28",partition_id="page:28",
        block_no=block,line_no=0,word_no=index,
        literal=literal,trusted=trusted,
    )


def _row(block,words,trusted=True):
    return tuple(_word(block,i,s,trusted) for i,s in enumerate(words))


def test_synthetic_authenticated_native_schedule_source_never_signs_host_count():
    words=(
        *_row(1,["DOOR","SCHEDULE"]),
        *_row(2,["D13","PWD","SINGLE","SWING","920","2040","SOLID","CORE","DOOR"]),
        *_row(3,["D17","FREEZER","SLIDING","DOOR","800","2000","COOLROOM","CONTRACTOR"]),
        *_row(4,["D18","FREEZER","AS","PER","MANUFACTURER","DISPLAY","SHELVING","DOOR"]),
    )
    result=rows(words)
    assert len(result)==3
    r={x.code:x for x in result}
    assert r["D13"].status=="source_schedule_row_text_authenticated"
    assert (r["D13"].original_width_literal,r["D13"].original_height_literal)==("920","2040")
    assert r["D17"].door_kind_candidate=="coolroom_access_sliding"
    assert r["D17"].original_width_literal=="800"
    assert r["D18"].door_kind_candidate=="manufacturer_display_shelving"
    assert r["D18"].original_width_literal is None
    assert r["D18"].original_height_literal is None
    assert all(x.source_title_observation_ids==("source-word:1:0","source-word:1:1")
               for x in result)
    assert all(x.width_height_metric_units_authenticated is False
               and x.default_opening_count is None
               and not x.physical_host_or_frame_authenticated
               and not x.new_customer_quantity_authority for x in result)


def test_untrusted_source_title_or_row_never_mints_schedule_source_authority():
    title_untrusted=(
        *_row(1,["DOOR","SCHEDULE"],False),
        *_row(2,["D13","PWD","SINGLE","SWING","920","2040","SOLID","CORE","DOOR"]),
    )
    result=rows(title_untrusted)
    assert len(result)==1
    assert result[0].status=="source_schedule_row_text_unverified"
    assert result[0].first_unclosed_gate=="original_schedule_title_or_row_word_trust"
    code_untrusted=(
        *_row(1,["DOOR","SCHEDULE"]),
        *_row(2,["D13","PWD","SINGLE","SWING","920","2040","SOLID","CORE","DOOR"],False),
    )
    assert not rows(code_untrusted)[0].complete_native_row_text_trusted


def test_duplicate_source_door_code_and_unrelated_note_never_issue_unique_row():
    evidence=(
        *_row(1,["DOOR","SCHEDULE"]),
        *_row(2,["D13","PWD","SINGLE","SWING","920","2040","DOOR"]),
        *_row(3,["D13","PWD","SINGLE","SWING","920","2040","DOOR"]),
        *_row(4,["1.","NOTES","D3","DOOR","HARDWARE"]),
        *_row(5,["D01"]),
    )
    result=rows(evidence)
    assert len(result)==2
    assert all(x.code=="D13" and x.status=="source_schedule_row_duplicate_code_conflict"
               and not x.new_customer_quantity_authority for x in result)


def test_original_a600_full_producer_receipt_census_keeps_all_28_source_rows():
    data=ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    source=SourceVisibilityProducer(producer_method="original-a600-source-audit",
                                    producer_version="1")
    pub=source.ingest_native_pdf_bytes(
        document_id="original-maryborough-read-only",
        source_bytes=data,source_locator="memory://private-original.pdf",
        page_ids=("28",),
    )
    result=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="28",
    )
    expected={f"D{i:02d}" for i in range(1,29)}
    assert set(result.all_original_source_codes)==expected
    assert len(result.rows)==28
    assert result.source_sha256==SHA
    assert result.snapshot_id==pub.snapshot.snapshot_id
    door={x.code:x for x in result.rows}
    assert door["D17"].door_kind_candidate=="coolroom_access_sliding"
    assert (door["D17"].original_width_literal,
            door["D17"].original_height_literal)==("800","2000")
    for number in range(18,28):
        r=door[f"D{number}"]
        assert r.door_kind_candidate=="manufacturer_display_shelving"
        assert r.original_width_literal is None and r.original_height_literal is None
    assert all(x.default_opening_count is None
               and not x.physical_host_or_frame_authenticated
               and not x.new_customer_quantity_authority for x in result.rows)
    assert result.new_opening_counts==result.new_opening_areas_m2==0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_original_source_input_must_be_the_same_published_revision_page():
    doc=fitz.open()
    p=doc.new_page(width=350,height=350)
    p.insert_text((30,30),"DOOR SCHEDULE")
    p.insert_text((30,210),"D13 PWD SINGLE SWING 920 2040 SOLID CORE DOOR")
    data=doc.tobytes()
    doc.close()
    source=SourceVisibilityProducer(producer_method="source-test",
                                    producer_version="1")
    publication=source.ingest_native_pdf_bytes(document_id="test-source",
        source_bytes=data,source_locator="memory://test.pdf",
        page_ids=("1",))
    with pytest.raises(ValueError,match="source_door_revision_not_producer_owned"):
        inspect_published_door_schedule(source,revision_id="foreign-revision",page_id="1")
    with pytest.raises(ValueError,match="source_door_page_not_in_published_source_coverage"):
        inspect_published_door_schedule(source,
            revision_id=publication.revision.revision_id,page_id="2")
    with pytest.raises(ValueError,match="exact_door_source_revision_and_page_required"):
        inspect_published_door_schedule(source,
            revision_id=publication.revision.revision_id,page_id="0")
    with pytest.raises(TypeError,match="door_source_requires_existing_visibility_producer"):
        inspect_published_door_schedule(object(),
            revision_id=publication.revision.revision_id,page_id="1")
    valid=inspect_published_door_schedule(source,
        revision_id=publication.revision.revision_id,page_id="1")
    assert valid.new_opening_counts==0 and valid.new_opening_areas_m2==0
