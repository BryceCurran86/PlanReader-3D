"""Native schedule words alone never mint FT2/FT3 source definitions."""
from types import SimpleNamespace

from tools.diag_gpt2_ft3_native_text_integrity_firstgate import (
    native_finish_schedule_text_first_gates,
)


def word(text, *, block, no=0, trusted=True, reasons=(), page="11",
         partition="native-original-11"):
    return SimpleNamespace(
        text=text, block_no=block, line_no=0, word_no=no,
        page_id=page, source_partition_id=partition,
        observation_id=f"native-{partition}-{block}-{no}",
        trusted=trusted, reason_codes=tuple(reasons),
    )


def test_distinct_source_native_ft2_ft3_rows_do_not_authenticate_finish():
    words = (
        word("INTERNAL", block=239, no=0),
        word("FINISHES", block=239, no=1),
        word("SCHEDULE", block=239, no=2),
        word("FT2", block=243),
        word("STOCKTON WHITE", block=243, no=1),
        word("FT3", block=244, trusted=False,
             reasons=("text_glyph_mapping_unverified",)),
        word("DURA GREY R12", block=244, no=1, trusted=False,
             reasons=("text_clip_state_unresolved",)),
        word("FT1", block=242),
    )
    report = native_finish_schedule_text_first_gates(words)
    assert report["source_page_id"] == "11"
    assert len(report["native_internal_finish_schedule_title_blocks_diagnostic_only"]) == 1
    ft2 = report["native_material_code_first_gates_diagnostic_only"]["FT2"]
    ft3 = report["native_material_code_first_gates_diagnostic_only"]["FT3"]
    assert ft2["first_unclosed_gate"] == (
        "native_words_trusted_but_material_definition_unverified"
    )
    assert ft3["first_unclosed_gate"] == (
        "original_native_material_row_text_integrity_unproven"
    )
    row = ft3["native_row_blocks_diagnostic_only"][0]
    assert row["original_native_block_no"] == 244
    assert row["source_integrity_untrusted_word_count"] == 2
    assert row["untrusted_source_first_reasons"] == {
        "text_clip_state_unresolved": 1,
        "text_glyph_mapping_unverified": 1,
    }
    assert ft3["new_material_definition_authenticated"] is False
    assert ft3["new_material_occurrence_published"] is False
    assert report["new_material_occurrences_published"] is False


def test_duplicate_ft3_blocks_cannot_choose_one_native_row():
    words = (word("FT3", block=244),
             word("FT3", block=300, partition="other-native-partition"))
    result = native_finish_schedule_text_first_gates(words)
    ft3 = result["native_material_code_first_gates_diagnostic_only"]["FT3"]
    assert ft3["first_unclosed_gate"] == "multiple_original_native_material_code_blocks"
    assert len(ft3["native_row_blocks_diagnostic_only"]) == 2
    assert ft3["new_material_definition_authenticated"] is False


def test_missing_or_untrusted_native_source_text_stays_negative():
    for rows in (
        (),
        (word("FT3", block=244, page="12"),),
        (word("FT3", block=244, no=0, trusted=False,
              reasons=("text_trace_unavailable",)),),
    ):
        report = native_finish_schedule_text_first_gates(rows)
        ft3 = report["native_material_code_first_gates_diagnostic_only"]["FT3"]
        assert ft3["first_unclosed_gate"] in (
            "original_native_material_code_block_missing",
            "original_native_material_row_text_integrity_unproven",
        )
        assert ft3["new_material_definition_authenticated"] is False
        assert report["native_schedule_definition_authenticated_by_this_report"] is False


def test_corrupt_source_word_identity_is_not_a_native_receipt():
    invalid = word("FT3", block=244)
    invalid.word_no = 0.5
    report = native_finish_schedule_text_first_gates((invalid,))
    assert report["native_material_code_first_gates_diagnostic_only"]["FT3"][
        "first_unclosed_gate"
    ] == "original_native_material_code_block_missing"
