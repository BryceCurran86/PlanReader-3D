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


def test_opt_in_native_raster_source_proves_exact_door_code_without_quantity(monkeypatch):
    from pb_source_door_schedule_authority import (
        _producer_owned_native_words, _raster_corroborated_schedule_words,
        inspect_published_door_schedule,
    )
    from test_raster_text_corroboration_authority_v1 import (
        _Setup, _both, _glyph_unverified_pdf,
    )

    setup = _Setup(_glyph_unverified_pdf([("D02", 40, 120)]), _both("D02"))
    words = _producer_owned_native_words(setup.svp, setup.published, "1")
    assert len(words) == 1 and words[0].literal == "D02"
    assert words[0].trusted is False

    upgraded = _raster_corroborated_schedule_words(
        setup.svp, setup.published, words, raster_text_producer=setup.producer,
    )
    assert upgraded[0].trusted is True
    assert upgraded[0].observation_id == words[0].observation_id
    assert upgraded[0].raster_text_receipt_id
    assert words[0].trusted is False  # immutable native record

    original = inspect_published_door_schedule(
        setup.svp, revision_id=setup.published.revision.revision_id, page_id="1",
    )
    from pb_raster_text_corroboration_authority import RasterTextCorroborationProducer
    monkeypatch.setattr(
        RasterTextCorroborationProducer, "from_source_visibility_producer",
        lambda source: setup.producer if source is setup.svp else object(),
    )
    optional = inspect_published_door_schedule(
        setup.svp, revision_id=setup.published.revision.revision_id, page_id="1",
        raster_text_source_shadow=True,
    )
    # Source-proven code alone does NOT mint a row without role/table cells.
    assert original.rows == optional.rows == ()
    assert original.unparsed_original_door_codes == ("D02",)
    assert optional.unparsed_original_door_codes == ("D02",)
    assert optional.new_opening_counts == optional.new_opening_areas_m2 == 0
    assert optional.title_source_trusted is False
    assert optional.complete_source_word_universe is False


def test_opt_in_native_raster_source_rejects_wrong_reading_and_foreign_owner():
    import pytest
    from pb_source_door_schedule_authority import (
        _producer_owned_native_words, _raster_corroborated_schedule_words,
    )
    from test_raster_text_corroboration_authority_v1 import (
        _Setup, _both, _glyph_unverified_pdf,
    )

    data = _glyph_unverified_pdf([("D02", 40, 120)])
    setup = _Setup(data, _both("D03"))
    words = _producer_owned_native_words(setup.svp, setup.published, "1")
    bad = _raster_corroborated_schedule_words(
        setup.svp, setup.published, words, raster_text_producer=setup.producer,
    )
    assert bad == words
    other = _Setup(data, _both("D02"))
    with pytest.raises(ValueError, match="raster_source_schedule_producer_mismatch"):
        _raster_corroborated_schedule_words(
            setup.svp, setup.published, words,
            raster_text_producer=other.producer,
        )
    with pytest.raises(TypeError, match="raster_text_producer must be source-owned"):
        _raster_corroborated_schedule_words(
            setup.svp, setup.published, words,
            raster_text_producer=object(),
        )


def test_source_corroborated_raster_receipt_is_retained_as_row_lineage():
    from dataclasses import replace
    source_words = (
        *_row(1, "DOOR", "SCHEDULE"),
        *_row(2, "D02", "ROOM", "SWING", "900", "2050", "DOOR"),
    )
    selected = tuple(
        replace(w, raster_text_receipt_id="raster-verified-receipt")
        if w.literal == "D02" else w
        for w in source_words
    )
    result = _original_source_row_candidates(selected)
    assert len(result) == 1
    assert result[0].source_raster_text_receipt_ids == (
        "raster-verified-receipt",
    )
    assert result[0].width_height_metric_units_authenticated is False
    assert result[0].physical_host_or_frame_authenticated is False
    assert result[0].new_customer_quantity_authority is False


def test_raster_schedule_text_does_not_upgrade_unrelated_non_door_note():
    from pb_source_door_schedule_authority import (
        _producer_owned_native_words, _raster_corroborated_schedule_words,
    )
    from test_raster_text_corroboration_authority_v1 import (
        _Setup, _both, _glyph_unverified_pdf,
    )
    setup = _Setup(
        _glyph_unverified_pdf([("UNRELATED", 40, 120)]),
        _both("UNRELATED"),
    )
    words = _producer_owned_native_words(setup.svp, setup.published, "1")
    upgraded = _raster_corroborated_schedule_words(
        setup.svp, setup.published, words, raster_text_producer=setup.producer,
    )
    assert upgraded == words


def test_live_schedule_source_shadow_is_bool_not_test_ocr_injection():
    import pytest
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_source_door_schedule_authority import inspect_published_door_schedule
    import fitz
    pdf = fitz.open()
    pdf.new_page(width=200,height=200)
    data = pdf.tobytes()
    pdf.close()
    source = SourceVisibilityProducer(producer_method="a600-opt-in-type-guard",
                                      producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="a600-type-guard",source_bytes=data,
        source_locator="memory://synthetic.pdf",page_ids=("1",),
    )
    with pytest.raises(TypeError,match="raster_text_source_shadow must be bool"):
        inspect_published_door_schedule(
            source,revision_id=published.revision.revision_id,page_id="1",
            raster_text_source_shadow="true",
        )
