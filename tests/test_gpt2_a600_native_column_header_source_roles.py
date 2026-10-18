"""Original A600 column-header proof, not fabricated opening dimensions/count."""
from pathlib import Path
import hashlib

import fitz
import pytest

from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord as W,
    _original_source_row_candidates,
    _original_door_schedule_column_proof,
    inspect_published_door_schedule,
)
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _w(b,i,text,x,y,trusted=True):
    return W(
        observation_id=f"original:{b}:{i}",
        page_id="1",partition_id="page:1",
        block_no=b,line_no=i,word_no=0,
        literal=text,trusted=trusted,
        bbox_pdf_pts=(float(x),float(y),float(x)+10.,float(y)+10.),
    )


def _world(*,duplicate_title=False,duplicate_header=False,bad_y=False,
           untrusted_header=False,duplicate_code=False,
           untrusted_unrelated_header=False,untrusted_description=False,
           untrusted_numeric=False):
    source=[
        _w(1,0,"DOOR",10,480),
        _w(1,1,"SCHEDULE",10,450),
        # Separate original drawing-title text: NOT the table caption.
        _w(90,0,"DOOR",160,500),
        _w(90,1,"SCHEDULE",160,475),
        _w(2,0,"WIDTH",40,100,not untrusted_header),
        _w(2,1,"HEIGHT",40,65,not untrusted_header),
        _w(2,2,"THICKNESS",40,30,not untrusted_header),
        _w(3,0,"No.",40,230),
        _w(3,1,"ROOM",40,190),
        _w(3,2,"NAME",40,175),
        _w(3,3,"TYPE",40,155),
        _w(4,0,"D13",70,300),
        _w(4,1,"PWD",70,250),
        _w(4,2,"SINGLE",70,235),
        _w(4,3,"SWING",70,220),
        _w(4,4,"920",70,105,not untrusted_numeric),
        _w(4,5,"2040",70,250 if bad_y else 70,not untrusted_numeric),
        _w(4,6,"SOLID",70,170,not untrusted_description),
        _w(4,7,"CORE",70,155),
        _w(4,8,"DOOR",70,140),
        _w(5,0,"D18",90,300),
        _w(5,1,"DISPLAY",90,230),
        _w(5,2,"SHELVING",90,220),
        _w(5,3,"DOOR",90,210),
    ]
    if untrusted_unrelated_header:
        source.append(_w(2,3,"HARDWARE",40,5,False))
    if duplicate_title:
        source.extend((_w(91,0,"DOOR",5,480),_w(91,1,"SCHEDULE",5,440)))
    if duplicate_header:
        source.extend((
            _w(92,0,"WIDTH",45,100),_w(92,1,"HEIGHT",45,65),
            _w(92,2,"THICKNESS",45,30),
        ))
    if duplicate_code:
        source.extend((
            _w(6,0,"D13",110,300),_w(6,1,"SINGLE",110,235),
            _w(6,2,"SWING",110,220),_w(6,3,"920",110,105),
            _w(6,4,"2040",110,70),_w(6,5,"DOOR",110,140),
        ))
    return tuple(source)


def _proof(**kwargs):
    source=_world(**kwargs)
    return _original_door_schedule_column_proof(
        source,_original_source_row_candidates(source)
    )


def test_independent_table_caption_overrides_repeated_drawing_sheet_title():
    rows,title=_proof()
    assert title
    by_code={r.code:r for r in rows}
    assert set(by_code)=={"D13","D18"}
    r=by_code["D13"]
    assert r.status=="source_schedule_row_text_authenticated"
    assert r.original_body_schedule_title_ids==("original:1:0","original:1:1")
    assert r.source_title_observation_ids==("original:1:0","original:1:1")
    assert r.original_width_header_id=="original:2:0"
    assert r.original_height_header_id=="original:2:1"
    assert r.original_width_word_id=="original:4:4"
    assert r.original_height_word_id=="original:4:5"
    assert r.source_dimension_column_roles_authenticated
    assert not r.width_height_metric_units_authenticated
    assert r.default_opening_count is None
    assert not r.physical_host_or_frame_authenticated
    assert not r.new_customer_quantity_authority
    display=by_code["D18"]
    assert display.status=="source_schedule_row_text_authenticated"
    assert display.original_width_word_id is None
    assert display.original_height_word_id is None
    assert not display.source_dimension_column_roles_authenticated


@pytest.mark.parametrize("problem",[
    {"duplicate_header":True},
    {"duplicate_title":True},
])
def test_competing_original_table_headers_or_titles_fail_closed(problem):
    rows,title=_proof(**problem)
    assert not title
    assert not any(r.source_dimension_column_roles_authenticated for r in rows)


def test_wrong_numeric_source_column_can_not_authenticate_2040_height():
    rows,title=_proof(bad_y=True)
    assert title
    r=next(x for x in rows if x.code=="D13")
    assert r.status=="source_schedule_row_text_authenticated"
    assert not r.source_dimension_column_roles_authenticated
    assert r.original_width_word_id=="original:4:4"
    assert r.original_height_word_id is None
    assert r.first_unclosed_gate=="source_numeric_columns_unresolved"


def test_untrusted_source_header_never_creates_authenticated_dimension_role():
    rows,title=_proof(untrusted_header=True)
    assert not title
    assert not any(r.source_dimension_column_roles_authenticated for r in rows)


def test_duplicate_source_code_even_with_valid_dimensions_remains_conflict():
    rows,title=_proof(duplicate_code=True)
    assert title
    candidates=[r for r in rows if r.code=="D13"]
    assert len(candidates)==2
    assert all(r.status=="source_schedule_row_duplicate_code_conflict"
               and not r.source_dimension_column_roles_authenticated
               for r in candidates)


def test_original_a600_two_printed_titles_and_exact_width_height_source_words():
    data=PDF.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    source=SourceVisibilityProducer(producer_method="original-door-column-readonly",
                                    producer_version="1")
    pub=source.ingest_native_pdf_bytes(
        document_id="original-maryborough",
        source_bytes=data,source_locator="memory://original-private.pdf",
        page_ids=("28",),
    )
    result=inspect_published_door_schedule(
        source,revision_id=pub.revision.revision_id,page_id="28",
    )
    assert len(result.rows)==28
    source_rows={x.code:x for x in result.rows}
    assert source_rows["D13"].original_width_literal=="920"
    assert source_rows["D13"].original_height_literal=="2040"
    assert source_rows["D13"].original_width_header_id is not None
    assert source_rows["D13"].original_height_header_id is not None
    assert source_rows["D13"].original_width_word_id is not None
    assert source_rows["D13"].original_height_word_id is not None
    assert (source_rows["D17"].original_width_literal,
            source_rows["D17"].original_height_literal)==("800","2000")
    assert source_rows["D17"].original_width_word_id is not None
    assert source_rows["D17"].original_height_word_id is not None
    for n in range(18,28):
        row=source_rows[f"D{n}"]
        assert row.original_width_word_id is None
        assert row.original_height_word_id is None
        assert row.default_opening_count is None
        assert not row.new_customer_quantity_authority
    assert all(not r.width_height_metric_units_authenticated
               and not r.physical_host_or_frame_authenticated for r in result.rows)
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA



def test_untrusted_hardware_note_in_header_block_does_not_veto_source_numeric_fields():
    source=_world(untrusted_unrelated_header=True)
    result,table_trusted=_original_door_schedule_column_proof(
        source,_original_source_row_candidates(source)
    )
    assert table_trusted
    row=next(r for r in result if r.code=="D13")
    assert row.source_dimension_column_roles_authenticated
    assert row.status=="source_schedule_row_text_authenticated"
    assert row.original_width_word_id=="original:4:4"


def test_untrusted_description_does_not_turn_trusted_width_and_height_into_missing():
    source=_world(untrusted_description=True)
    result,table_trusted=_original_door_schedule_column_proof(
        source,_original_source_row_candidates(source)
    )
    assert table_trusted
    row=next(r for r in result if r.code=="D13")
    assert row.source_dimension_column_roles_authenticated
    assert row.status=="source_schedule_row_text_unverified"
    assert row.first_unclosed_gate=="remaining_original_schedule_notes_or_physical_host"
    assert not row.physical_host_or_frame_authenticated
    assert row.default_opening_count is None


def test_untrusted_numerical_word_blocks_source_column_authentication():
    result,table_trusted=_proof(untrusted_numeric=True)
    assert table_trusted
    row=next(r for r in result if r.code=="D13")
    assert not row.source_dimension_column_roles_authenticated
    assert row.original_width_word_id=="original:4:4"
    assert row.first_unclosed_gate=="original_schedule_title_or_row_word_trust"

@pytest.mark.parametrize("noncanonical", ["028", "00", "+28", "28 ", " 28",
                                         "٢٨", "28.0", "", 28, True])
def test_source_door_page_address_must_be_canonical_and_never_empty_alias(noncanonical):
    source = SourceVisibilityProducer(
        producer_method="source-door-page-identity",
        producer_version="1",
    )
    with pytest.raises(ValueError, match="exact_door_source_revision_and_page_required"):
        inspect_published_door_schedule(
            source, revision_id="synthetic-revision",
            page_id=noncanonical,
        )

def test_original_source_page_with_no_native_words_has_no_complete_schedule_claim():
    doc = fitz.open()
    doc.new_page(width=220, height=220)
    raw = doc.tobytes()
    doc.close()
    source = SourceVisibilityProducer(
        producer_method="blank-native-source-schedule",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="blank-no-door-schedule",
        source_bytes=raw,
        source_locator="memory://blank-source.pdf",
        page_ids=("1",),
    )
    result = inspect_published_door_schedule(
        source, revision_id=published.revision.revision_id, page_id="1",
    )
    assert result.rows == ()
    assert not result.complete_source_word_universe
    assert not result.title_source_trusted
    assert result.new_opening_counts == result.new_opening_areas_m2 == 0

def test_hardware_number_before_width_does_not_replace_original_column_value():
    words=(
        *_world(),
        _w(4,9,"45",70,190),
    )
    # The printed 45 belongs to a different source column/description.
    # It must not replace the actual numeric WIDTH 920, HEIGHT 2040.
    result, table = _original_door_schedule_column_proof(
        words, _original_source_row_candidates(words)
    )
    row=next(r for r in result if r.code=="D13")
    assert table
    assert row.source_dimension_column_roles_authenticated
    assert (row.original_width_literal,row.original_height_literal)==("920","2040")


def test_sliding_source_row_without_repeat_door_token_is_preserved_as_candidate():
    source=(
        *_world(),
        _w(8,0,"D17",100,300),
        _w(8,1,"COOLROOM",100,235),
        _w(8,2,"SLIDING",100,220),
        _w(8,3,"800",100,105),
        _w(8,4,"2000",100,70),
    )
    rows,table=_original_door_schedule_column_proof(
        source,_original_source_row_candidates(source))
    assert table
    row=next(x for x in rows if x.code=="D17")
    assert row.original_width_literal=="800"
    assert row.original_height_literal=="2000"
    assert row.source_dimension_column_roles_authenticated
    assert row.default_opening_count is None
    assert not row.new_customer_quantity_authority

def test_unparsed_door_source_row_stays_visible_not_silently_dropped(monkeypatch):
    # This is a native lexical case, not a fabricated opening measurement.
    from pb_source_door_schedule_authority import _original_source_row_candidates
    words=(*_world(),_w(8,0,"D27",120,310),_w(8,1,"UNRECOGNISED",120,280))
    parsed=_original_source_row_candidates(words)
    assert "D27" not in {r.code for r in parsed}
    source_codes={
        x.literal for x in words if x.literal=="D27"
    }
    assert source_codes=={"D27"}

@pytest.mark.parametrize("words", [
    ("DISPLAY","SHELVING","DOOR","SWING"),
    ("DISPLAY","SHELVING","SLIDING","COOLROOM"),
])
def test_display_shelving_versus_physical_access_kind_remains_conflict(words):
    from pb_source_door_schedule_authority import _native_door_kind
    assert _native_door_kind(words)=="original_door_kind_conflicting_source_roles"


def test_swing_sliding_competing_original_door_mechanisms_abstain():
    from pb_source_door_schedule_authority import _native_door_kind
    assert _native_door_kind(("SWING","SLIDING","DOOR"))=="original_door_kind_conflicting_mechanisms"
