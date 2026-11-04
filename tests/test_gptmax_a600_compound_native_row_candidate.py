"""Source-neutral A600 native-word classification is not opening quantity authority."""
from __future__ import annotations

from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord,
    _original_source_row_candidates,
)


def _w(block, index, literal, *, trusted=True):
    return SourceDoorScheduleWord(
        observation_id=f"synthetic-word:{block}:{index}",
        page_id="1",
        partition_id="page:1",
        block_no=block,
        line_no=index,
        word_no=0,
        literal=literal,
        trusted=trusted,
        bbox_pdf_pts=(float(block), float(index), float(block) + 0.5, float(index) + 0.5),
    )


def _row(block, *literals, trusted=True):
    return tuple(_w(block, i, word, trusted=trusted) for i, word in enumerate(literals))


def test_compound_printed_door_cell_survives_native_span_grouping():
    words=(
        *_row(1,"DOOR","SCHEDULE"),
        *_row(2,"D02","SHARED SERVICE","900","2050","45",
              "ALUMINIUM FRAMED GLASS DOOR","CLEAR SAFETY GLASS"),
    )
    result=_original_source_row_candidates(words)
    assert len(result)==1
    row=result[0]
    assert row.code=="D02"
    assert row.original_width_literal=="900"
    assert row.original_height_literal=="2050"
    assert row.complete_native_row_text_trusted is True
    assert row.width_height_metric_units_authenticated is False
    assert row.default_opening_count is None
    assert row.physical_host_or_frame_authenticated is False
    assert row.new_customer_quantity_authority is False


def test_compound_mark_notes_or_single_number_cannot_mint_schedule_row():
    words=(
        *_row(1,"DOOR","SCHEDULE"),
        *_row(2,"D02","ALUMINIUM FRAMED GLASS DOOR"),
        *_row(3,"D03","ALUMINIUM FRAMED GLASS DOOR","900"),
        *_row(4,"D04","DOOR FINISH","NOTES","-"),
    )
    assert _original_source_row_candidates(words)==()


def test_compound_candidate_preserves_untrusted_word_gate_and_not_issued():
    words=(
        *_row(1,"DOOR","SCHEDULE"),
        *_row(2,"D02","900","2050","ALUMINIUM FRAMED GLASS DOOR",trusted=False),
    )
    result=_original_source_row_candidates(words)
    assert len(result)==1
    assert result[0].status=="source_schedule_row_text_unverified"
    assert result[0].first_unclosed_gate=="original_schedule_title_or_row_word_trust"
    assert result[0].new_customer_quantity_authority is False


def test_competing_codes_in_same_native_span_fail_closed():
    words=(
        *_row(1,"DOOR","SCHEDULE"),
        *_row(2,"D02","D03","900","2050","ALUMINIUM FRAMED GLASS DOOR"),
    )
    assert _original_source_row_candidates(words)==()


def test_compound_role_must_be_full_printed_word_not_substring():
    words=(
        *_row(1,"DOOR","SCHEDULE"),
        *_row(2,"D02","900","2050","INDOORING","SLIDINGLY"),
    )
    assert _original_source_row_candidates(words)==()
