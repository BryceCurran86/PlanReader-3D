"""Original-PDF source declared area FIRM handoff; not construction publication."""
from hashlib import sha256

import fitz

from pb_gpt1_native_architectural_area_schedule import (\n    issue_native_scheduled_areas, _native_word_has_painted_glyphs,\n)


def _original_like_source(*, changes=None, pages=2):
    doc = fitz.open()
    try:
        for i in range(pages):
            p = doc.new_page(width=1190, height=842)
            p.insert_text((300, 700), "AREA CALCULATIONS", fontsize=8)
            values = ["RESIDENCE", "193.24 m2", "ALFRESCO", "28.10 m2",
                      "PORCH", "3.02 m2", "TOTAL:", "224.36 m2"]
            if changes and i in changes:
                position, value = changes[i]
                values[position] = value
            p.insert_textbox(
                fitz.Rect(300, 716, 550, 810),
                "\n".join(values), fontsize=8, lineheight=1.15,
            )
        return doc.tobytes()
    finally:
        doc.close()


def _issue(raw):
    return issue_native_scheduled_areas(
        raw, expected_sha256=sha256(raw).hexdigest(),
        project_id="source-neutral-original-test", workspace_id=10,
    )


def test_two_repeated_schedule_sheets_issue_only_three_source_firm_quantities():
    raw = _original_like_source()
    report = _issue(raw)
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY", report.reason_codes
    assert len(report.rows) == len(report.quantities) == 3
    assert report.repeated_source_pages == (1, 2)
    assert [float(q.value) for q in report.quantities] == [193.24, 28.10, 3.02]
    assert float(report.total_m2) == 224.36
    assert all(q.status == "firm" and q.family == "architectural_scheduled_area"
               and q.unit == "m2" for q in report.quantities)
    assert report.sealed_run is not None
    assert report.customer_release_allowed is False
    assert report.canonical_physical_floor_bound is False
    assert all(q.metadata["commercial_projection_allowed"] is False
               and q.metadata["canonical_physical_floor_owner_authenticated"] is False
               for q in report.quantities)
    assert _issue(raw) == report


def test_single_schedule_is_one_set_not_one_per_repeated_page():
    raw = _original_like_source(pages=1)
    report = _issue(raw)
    assert report.status == "SOURCE_FIRM_HANDOFF_ONLY"
    assert len(report.quantities) == 3
    assert report.repeated_source_pages == (1,)


def test_different_original_second_sheet_printed_area_fails_closed():
    raw = _original_like_source(changes={1: (1, "193.25 m2")})
    report = _issue(raw)
    assert report.status == "ABSTAIN"
    assert report.quantities == ()
    assert report.sealed_run is None


def test_missing_source_numeric_or_rollup_fails_closed():
    for replacement in ("not on drawing", "999.99 m2"):
        raw = _original_like_source(changes={0: (7, replacement)}, pages=1)
        report = _issue(raw)
        assert report.status == "ABSTAIN"
        assert report.quantities == ()


def test_missing_separate_component_value_not_accepted():
    raw = _original_like_source(changes={0: (3, "UNMEASURED")}, pages=1)
    assert _issue(raw).quantities == ()


def test_sha_gate_rejects_original_source_substitution():
    raw = _original_like_source()
    denied = issue_native_scheduled_areas(
        raw, expected_sha256="0" * 64,
        project_id="source-neutral-original-test", workspace_id=10,
    )
    assert denied.status == "ABSTAIN"
    assert denied.quantities == ()


def test_source_document_not_promoted_for_empty_project_or_invalid_scope():
    raw = _original_like_source()
    report = issue_native_scheduled_areas(
        raw, expected_sha256=sha256(raw).hexdigest(),
        project_id="", workspace_id=10,
    )
    assert report.status == "ABSTAIN"
    assert report.quantities == ()

def _word_and_trace(*, word="AREA", shift=0, opacity=1.0, mode=0):
    native = (10.0, 20.0, 30.0, 30.0, word, 0, 0, 0)
    chars = tuple(
        (ord(letter), index, (10.0 + index * 5 + shift, 30.0),
         (10.0 + index * 5 + shift, 20.0,
          15.0 + index * 5 + shift, 30.0))
        for index, letter in enumerate(word)
    )
    return native, {"type": mode, "opacity": opacity, "chars": chars}


def test_native_word_each_glyph_exactly_overlaps_original_pdf_word():
    word, trace = _word_and_trace()
    assert _native_word_has_painted_glyphs(word, (trace,))


def test_lookalike_word_drawn_elsewhere_is_not_source_ownership():
    word, displaced = _word_and_trace(shift=300)
    assert not _native_word_has_painted_glyphs(word, (displaced,))


def test_invisible_paint_or_stroked_text_cannot_authenticate_area():
    for parameters in ({"opacity": 0.0}, {"opacity": 0.5}, {"mode": 3}):
        word, trace = _word_and_trace(**parameters)
        assert not _native_word_has_painted_glyphs(word, (trace,))


def test_same_source_word_painted_twice_abstains_as_ambiguous():
    word, trace = _word_and_trace()
    assert not _native_word_has_painted_glyphs(word, (trace, trace))


def test_native_glyph_identity_not_merely_equal_area_or_text_length():
    word, trace = _word_and_trace()
    invalid = dict(trace)
    invalid["chars"] = tuple(
        (ord("X"), *glyph[1:]) if idx == 2 else glyph
        for idx, glyph in enumerate(trace["chars"])
    )
    assert not _native_word_has_painted_glyphs(word, (invalid,))


def test_malformed_native_paint_never_raises_or_grants_proof():
    word, trace = _word_and_trace()
    for forged in ({"type": 0, "opacity": 1.0, "chars": ((65,),)},
                   {"type": 0, "opacity": 1.0, "chars": "AREA"}, {}):
        assert not _native_word_has_painted_glyphs(word, (forged,))
