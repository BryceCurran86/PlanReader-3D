"""Pure-core proofs for the native text residual census shadow (no PDF, no producer)."""
from __future__ import annotations

import random
from dataclasses import fields, replace

import pytest

import pb_native_text_residual_census_shadow as C
from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_CLIPPED_BY_CLIP_REGION,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    TEXT_TRACE_AMBIGUOUS,
    TEXT_TRACE_UNAVAILABLE,
)
from pb_physical_opening_authority import VISIBLE_SOURCE_AUTHORITY_REQUIRED

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
CORR = EvidenceResolutionStatus.CORROBORATED
OWN = C.CensusOwnership("doc", "rev", "snap", "a" * 64, "7")
GLYPH = TEXT_GLYPH_MAPPING_UNVERIFIED
CLIP = TEXT_CLIP_STATE_UNRESOLVED

ARIAL = C.PageFont(5, "TrueType", "Arial", "WinAnsiEncoding", "embedded_ttf", False, "TrueType/embedded_ttf/WinAnsiEncoding/no_tounicode")
ISO = C.PageFont(6, "Type0", "ISOCPEUR", "Identity-H", "embedded_ttf", True, "Type0/embedded_ttf/Identity-H/tounicode")
HELV = C.PageFont(7, "Type1", "Helvetica", "", "not_embedded", False, "Type1/not_embedded/no_encoding/no_tounicode")
FONTS = (ARIAL, ISO, HELV)


def word(oid, bbox=(10.0, 10.0, 30.0, 20.0), *, trusted=False, reasons=(GLYPH,), receipt_reasons=None, xref=None,
         text_length=4, matches=False, ownership=OWN, status=None):
    if trusted:
        return C.WordIntegrityRecord(
            ownership, oid, bbox, True, CORR, ("producer_owned_pdf_text_integrity_resolved",), (), "known_standard_encoding",
            "proven_visible", xref, "Type1", "Helvetica", 3, None, None)
    return C.WordIntegrityRecord(
        ownership, oid, bbox, False, status or ABST, tuple(reasons),
        tuple(reasons) if receipt_reasons is None else tuple(receipt_reasons), "tounicode_glyph_unverified",
        "unresolved_or_blocked" if CLIP in reasons else "proven_visible", xref, "TrueType", "Arial", 3, text_length, matches)


def span(bbox, font="Arial", flags=0, direction=(1.0, 0.0)):
    return C.SpanRecord(tuple(float(v) for v in bbox), font, flags, direction)


def run(records, *, fonts=FONTS, spans=(), ownership=OWN, **kw):
    return C.classify_residuals(records, ownership=ownership, page_fonts=fonts, spans=spans, **kw)


# --- counts and the typed reason histograms ---------------------------------------------------------


def test_every_word_is_counted_and_every_untrusted_word_keeps_exactly_the_reason_set_the_authority_issued():
    records = [
        word("t1", trusted=True), word("t2", trusted=True),
        word("g1", reasons=(GLYPH,)), word("g2", reasons=(GLYPH,)),
        word("gc", reasons=(GLYPH, CLIP)),
        word("tu", reasons=(TEXT_TRACE_UNAVAILABLE,)),
        word("ta", reasons=(TEXT_TRACE_AMBIGUOUS,)),
    ]
    got = run(records)
    assert got.status is CAND and got.reason_codes == (C.CENSUS_PRODUCED,)
    assert (got.total_count, got.trusted_count, got.untrusted_count) == (7, 2, 5)
    assert dict(got.reason_set_histogram) == {
        (GLYPH,): 2, (CLIP, GLYPH): 1, (TEXT_TRACE_UNAVAILABLE,): 1, (TEXT_TRACE_AMBIGUOUS,): 1}
    assert [w.observation_id for w in got.untrusted_words] == ["g1", "g2", "gc", "ta", "tu"]
    assert got.standing_limits == C.STANDING_LIMITS


def test_the_reason_set_is_sorted_unique_and_independent_of_issue_order():
    forward = run([word("w", reasons=(GLYPH, CLIP, GLYPH))])
    backward = run([word("w", reasons=(CLIP, GLYPH))])
    assert forward.untrusted_words[0].reason_set == backward.untrusted_words[0].reason_set == (CLIP, GLYPH)
    assert forward.untrusted_words[0].reason_codes == (GLYPH, CLIP, GLYPH)        # as issued, nothing dropped
    assert dict(forward.reason_set_histogram) == dict(backward.reason_set_histogram) == {(CLIP, GLYPH): 1}


def test_an_untrusted_word_without_a_typed_reason_is_reported_not_hidden():
    got = run([word("w", reasons=())])
    assert got.untrusted_words[0].reason_set == (C.CENSUS_UNTYPED_UNTRUSTED_WORD,)
    assert dict(got.reason_set_histogram) == {(C.CENSUS_UNTYPED_UNTRUSTED_WORD,): 1}


def test_a_page_with_no_native_text_receipts_is_a_zero_census_with_its_own_reason():
    got = run([])
    assert got.status is CAND and (got.total_count, got.untrusted_count) == (0, 0)
    assert got.reason_codes == (C.CENSUS_PRODUCED, C.CENSUS_PAGE_HAS_NO_NATIVE_TEXT_RECEIPTS)
    assert got.reason_set_histogram == () and got.untrusted_words == ()


def test_only_trusted_words_leave_an_empty_residual():
    got = run([word("a", trusted=True), word("b", trusted=True)])
    assert (got.total_count, got.trusted_count, got.untrusted_count) == (2, 2, 0)
    assert got.untrusted_words == () and got.clip_state_histogram == ()


def test_status_of_a_word_is_kept_as_issued_for_conflict_and_source_failures():
    got = run([word("m", reasons=("text_integrity_receipt_mismatch",), status=CONF, receipt_reasons=(GLYPH,))])
    only = got.untrusted_words[0]
    assert only.authority_status is CONF and only.reason_set == ("text_integrity_receipt_mismatch",)
    assert only.clip_state == C.NO_CLIP_REASON      # the clip state comes from the receipt, never from the result


# --- the font join: candidates are retained and nothing is chosen ------------------------------------


def test_a_word_inside_one_span_takes_that_spans_font_and_the_class_of_the_page_font_of_that_name():
    got = run([word("w")], spans=[span((0, 0, 100, 40), font="Arial", flags=4)])
    font = got.untrusted_words[0].font
    assert font.join_status == C.SPAN_FONT_RESOLVED and font.font_label == "Arial" and font.span_flags == 4
    assert font.font_class == ARIAL.font_class and font.font_class_basis == C.CLASS_BASIS_SPAN_FONT_NAME
    assert font.candidate_fonts == ("Arial",) and font.containing_span_count == 1
    assert font.font_sources_agree is None and font.line_direction == C.BASELINE_EAST
    assert dict(got.font_reason_histogram) == {("Arial", (GLYPH,)): 1}
    assert dict(got.font_class_reason_histogram) == {(ARIAL.font_class, (GLYPH,)): 1}


def test_a_word_outside_every_span_is_font_unresolved_not_nearest_span():
    got = run([word("w", (10.0, 10.0, 30.0, 20.0))], spans=[span((31, 0, 100, 40)), span((0, 21, 100, 40), font="ISOCPEUR")])
    font = got.untrusted_words[0].font
    assert font.join_status == C.FONT_UNRESOLVED and font.font_label == C.FONT_UNRESOLVED
    assert font.candidate_fonts == () and font.font_class == C.FONT_CLASS_UNRESOLVED
    assert font.font_class_basis == C.CLASS_BASIS_NONE and font.line_direction == C.DIRECTION_UNRESOLVED
    assert dict(got.font_reason_histogram) == {(C.FONT_UNRESOLVED, (GLYPH,)): 1}


def test_spans_of_different_fonts_over_one_word_make_it_font_ambiguous_with_every_candidate_kept():
    got = run([word("w")], spans=[span((0, 0, 100, 40), font="Arial"), span((0, 0, 100, 40), font="ISOCPEUR")])
    font = got.untrusted_words[0].font
    assert font.join_status == C.FONT_AMBIGUOUS and font.font_label == C.FONT_AMBIGUOUS
    assert font.candidate_fonts == ("Arial", "ISOCPEUR") and font.containing_span_count == 2
    assert font.span_flags is None and font.font_class == C.FONT_CLASS_UNRESOLVED


def test_several_spans_of_the_same_font_are_not_an_ambiguity_because_no_choice_is_made():
    got = run([word("w")], spans=[span((0, 0, 100, 40), font="Arial"), span((5, 5, 50, 30), font="Arial")])
    font = got.untrusted_words[0].font
    assert font.join_status == C.SPAN_FONT_RESOLVED and font.font_label == "Arial" and font.containing_span_count == 2


def test_the_receipts_own_font_binding_names_the_class_and_is_compared_with_the_span_font():
    agree = run([word("w", xref=ARIAL.xref)], spans=[span((0, 0, 100, 40), font="Arial")])
    font = agree.untrusted_words[0].font
    assert font.font_class == ARIAL.font_class and font.font_class_basis == C.CLASS_BASIS_RECEIPT_XREF
    assert font.font_sources_agree is True
    disagree = run([word("w", xref=ISO.xref)], spans=[span((0, 0, 100, 40), font="Arial")])
    font = disagree.untrusted_words[0].font
    assert font.font_sources_agree is False and font.font_class == C.FONT_CLASS_CONFLICT
    assert font.font_label == "Arial"                         # the span label is kept, only the class is in conflict
    # an ambiguous span join still reports the receipt's class; agreement means the receipt font is among the candidates
    ambiguous = run([word("w", xref=ISO.xref)], spans=[span((0, 0, 100, 40), font="Arial"), span((0, 0, 100, 40), font="ISOCPEUR")])
    font = ambiguous.untrusted_words[0].font
    assert font.join_status == C.FONT_AMBIGUOUS and font.font_class == ISO.font_class and font.font_sources_agree is True
    foreign = run([word("w", xref=HELV.xref)], spans=[span((0, 0, 100, 40), font="Arial"), span((0, 0, 100, 40), font="ISOCPEUR")])
    assert foreign.untrusted_words[0].font.font_class == C.FONT_CLASS_CONFLICT


def test_a_receipt_font_without_a_page_font_list_entry_is_reported_as_such_and_with_no_span_it_stays_unagreed():
    got = run([word("w", xref=999)], spans=[span((0, 0, 100, 40))])
    assert got.untrusted_words[0].font.font_class == C.FONT_NOT_IN_PAGE_FONT_LIST
    bare = run([word("w", xref=ARIAL.xref)], spans=[])
    font = bare.untrusted_words[0].font
    assert font.font_class == ARIAL.font_class and font.font_sources_agree is None and font.font_label == C.FONT_UNRESOLVED


def test_the_class_of_a_span_font_name_is_unique_ambiguous_or_missing_from_the_page_list():
    twin = replace(ARIAL, xref=11)                                         # same name, same class
    other = replace(ARIAL, xref=12, program="not_embedded", font_class="TrueType/not_embedded/WinAnsiEncoding/no_tounicode")
    spans = [span((0, 0, 100, 40), font="Arial")]
    assert run([word("w")], fonts=(ARIAL, twin), spans=spans).untrusted_words[0].font.font_class == ARIAL.font_class
    assert run([word("w")], fonts=(ARIAL, other), spans=spans).untrusted_words[0].font.font_class == C.FONT_CLASS_AMBIGUOUS
    assert run([word("w")], fonts=(ISO,), spans=spans).untrusted_words[0].font.font_class == C.FONT_NOT_IN_PAGE_FONT_LIST


def test_a_span_boundary_contains_the_word_centre_inclusively():
    box = (10.0, 10.0, 30.0, 20.0)                      # centre (20, 15)
    assert run([word("w", box)], spans=[span((20, 15, 40, 40))]).untrusted_words[0].font.font_label == "Arial"
    assert run([word("w", box)], spans=[span((20.001, 0, 40, 40))]).untrusted_words[0].font.font_label == C.FONT_UNRESOLVED


def test_malformed_spans_are_ignored_and_never_contain_a_word():
    bad = [span((float("nan"), 0, 100, 40)), span((0, 0, float("inf"), 40)), span((100, 40, 0, 0))]
    got = run([word("w")], spans=bad)
    assert got.untrusted_words[0].font.font_label == C.FONT_UNRESOLVED


def test_a_huge_span_is_still_found_through_the_wide_list():
    got = run([word("w")], spans=[span((-1e7, -1e7, 1e7, 1e7), font="Arial")])
    assert got.untrusted_words[0].font.font_label == "Arial"


@pytest.mark.parametrize("name,expected", [
    ("ABCDEF+Arial", "Arial"), ("Arial", "Arial"), ("abcdef+Arial", "abcdef+Arial"), ("ABCDE+Arial", "ABCDE+Arial"),
    ("", ""), (None, ""),
])
def test_the_subset_tag_is_removed_only_when_it_is_a_subset_tag(name, expected):
    assert C.bare_font_name(name) == expected


@pytest.mark.parametrize("vector,expected", [
    ((1.0, 0.0), C.BASELINE_EAST), ((-1.0, 0.0), C.BASELINE_WEST), ((0.0, -1.0), C.BASELINE_NORTH),
    ((0.0, 1.0), C.BASELINE_SOUTH), ((0.7071, 0.7071), C.BASELINE_OBLIQUE), ((0.0, 0.0), C.DIRECTION_UNRESOLVED),
    ((float("nan"), 0.0), C.DIRECTION_UNRESOLVED), ((), C.DIRECTION_UNRESOLVED), ((5.0, 0.0), C.BASELINE_EAST),
])
def test_line_direction_classes(vector, expected):
    assert C.direction_class(vector) == expected


def test_spans_that_disagree_on_direction_leave_the_direction_unresolved():
    got = run([word("w")], spans=[span((0, 0, 100, 40), direction=(1.0, 0.0)), span((0, 0, 100, 40), direction=(0.0, -1.0))])
    assert got.untrusted_words[0].font.line_direction == C.DIRECTION_UNRESOLVED


def test_font_class_labels_are_structural_only():
    assert C.font_class_of("TrueType", "embedded_ttf", "", False) == "TrueType/embedded_ttf/no_encoding/no_tounicode"
    assert C.font_class_of("", "not_embedded", "WinAnsiEncoding", True) == "subtype_unknown/not_embedded/WinAnsiEncoding/tounicode"
    assert C.font_class_of("Type0", "embedded_cff", "Identity-H", None).endswith("/tounicode_unreadable")
    assert [C.program_class(x) for x in ("n/a", "", None, "TTF", "cff")] == [
        "not_embedded", "not_embedded", "not_embedded", "embedded_ttf", "embedded_cff"]


# --- the clip state comes from the receipt's own reasons ----------------------------------------------


@pytest.mark.parametrize("reasons,state,codes", [
    ((GLYPH,), C.NO_CLIP_REASON, ()),
    ((GLYPH, CLIP), C.CLIP_STATE_UNRESOLVED, (CLIP,)),
    ((TEXT_CLIPPED_BY_CLIP_REGION,), C.CLIP_CLIPPED, (TEXT_CLIPPED_BY_CLIP_REGION,)),
    ((CLIP, TEXT_CLIPPED_BY_CLIP_REGION), C.CLIP_UNRESOLVED_AND_CLIPPED, (CLIP, TEXT_CLIPPED_BY_CLIP_REGION)),
    ((TEXT_TRACE_UNAVAILABLE,), C.CLIP_NOT_EVALUATED_NO_TRACE, ()),
    ((TEXT_TRACE_AMBIGUOUS,), C.CLIP_NOT_EVALUATED_NO_TRACE, ()),
    ((), C.NO_CLIP_REASON, ()),
])
def test_clip_state_is_read_from_the_issued_reason_codes(reasons, state, codes):
    assert C.clip_state_of(reasons) == (state, codes)
    got = run([word("w", reasons=(GLYPH,), receipt_reasons=reasons)])
    assert got.untrusted_words[0].clip_state == state and got.untrusted_words[0].clip_reason_codes == codes
    assert dict(got.clip_state_histogram) == {state: 1}


# --- no text, ever --------------------------------------------------------------------------------------


def test_no_record_has_a_field_that_could_hold_word_text():
    for cls in (C.UntrustedWord, C.WordIntegrityRecord, C.PageResidualCensus, C.NativeTextResidualCensus, C.FontJoin):
        names = {f.name for f in fields(cls)}
        assert not {"text", "raw_text", "trusted_text", "normalized_tag", "tag", "label"} & names, cls


def test_the_opening_tag_counter_and_text_length_are_the_only_things_kept_of_an_untrusted_words_text():
    got = run([word("a", text_length=3, matches=True), word("b", text_length=11, matches=False),
               word("c", text_length=0, matches=True), word("d", trusted=True)])
    assert got.untrusted_matching_opening_tag_syntax == 2
    assert {w.observation_id: (w.text_length, w.matches_opening_tag_syntax) for w in got.untrusted_words} == {
        "a": (3, True), "b": (11, False), "c": (0, True)}


def test_a_word_record_is_validated_so_a_trusted_word_cannot_carry_text_counters_and_an_untrusted_one_must():
    kw = dict(ownership=OWN, observation_id="w", bbox=(0.0, 0.0, 1.0, 1.0), reason_codes=(), receipt_reason_codes=(),
              decode_status="", visibility_status="", receipt_font_xref=None, receipt_font_subtype="",
              receipt_font_name="", sequence_number=None)
    with pytest.raises(ValueError):
        C.WordIntegrityRecord(trusted=True, authority_status=CORR, text_length=3, matches_opening_tag_syntax=False, **kw)
    with pytest.raises(ValueError):
        C.WordIntegrityRecord(trusted=True, authority_status=ABST, text_length=None, matches_opening_tag_syntax=None, **kw)
    with pytest.raises(ValueError):
        C.WordIntegrityRecord(trusted=False, authority_status=ABST, text_length=None, matches_opening_tag_syntax=None, **kw)
    with pytest.raises(ValueError):
        C.WordIntegrityRecord(trusted=False, authority_status=ABST, text_length=-1, matches_opening_tag_syntax=False, **kw)
    with pytest.raises(ValueError):
        C.WordIntegrityRecord(trusted=False, authority_status=ABST, text_length=2, matches_opening_tag_syntax=1, **kw)
    for bad_box in ((0.0, 0.0, 1.0), (0.0, 0.0, float("nan"), 1.0), (0.0, 0.0, float("inf"), 1.0), ("a", 0, 1, 1)):
        with pytest.raises(ValueError):
            C.WordIntegrityRecord(**{**kw, "bbox": bad_box}, trusted=False, authority_status=ABST, text_length=2,
                                  matches_opening_tag_syntax=False)
    ints = C.WordIntegrityRecord(**{**kw, "bbox": (0, 0, 4, 2)}, trusted=False, authority_status=ABST, text_length=2,
                                 matches_opening_tag_syntax=False)
    assert ints.bbox == (0.0, 0.0, 4.0, 2.0) and all(type(v) is float for v in ints.bbox)
    with pytest.raises(ValueError):
        C.WordIntegrityRecord(**{**kw, "observation_id": ""}, trusted=False, authority_status=ABST, text_length=2,
                              matches_opening_tag_syntax=False)


# --- ownership, duplicates, the work bound ---------------------------------------------------------------


@pytest.mark.parametrize("field,value", [
    ("document_id", "other-doc"), ("revision_id", "other-rev"), ("snapshot_id", "other-snap"),
    ("source_sha256", "b" * 64), ("page_id", "8"),
])
def test_a_record_of_any_other_document_revision_snapshot_source_or_page_abstains_the_whole_page(field, value):
    foreign = replace(OWN, **{field: value})
    got = run([word("a"), word("b", ownership=foreign)])
    assert got.status is ABST and got.reason_codes == (C.CENSUS_FOREIGN_RECORD,)
    assert (got.total_count, got.untrusted_count, got.untrusted_words, got.reason_set_histogram) == (0, 0, (), ())
    assert got.ownership == OWN


def test_duplicate_observation_ids_abstain_rather_than_double_count():
    got = run([word("a"), word("a")])
    assert got.status is ABST and got.reason_codes == (C.CENSUS_DUPLICATE_OBSERVATION,)
    assert run([word("a"), word("a", trusted=True)]).reason_codes == (C.CENSUS_DUPLICATE_OBSERVATION,)


def test_the_work_bound_abstains_typed_and_never_returns_a_partial_census():
    records = [word(f"u{i}") for i in range(6)] + [word("t", trusted=True)]
    assert run(records, max_untrusted_records=6).status is CAND                       # exactly at the bound
    over = run(records, max_untrusted_records=5)
    assert over.status is ABST and over.reason_codes == (C.CENSUS_BUDGET_EXCEEDED,)
    assert (over.total_count, over.trusted_count, over.untrusted_count, over.untrusted_words) == (0, 0, 0, ())
    # trusted words never count against the bound
    assert run([word(f"t{i}", trusted=True) for i in range(50)], max_untrusted_records=1).status is CAND
    for bad in (0, -1, True, 1.5, "3", None):
        with pytest.raises(ValueError):
            run(records, max_untrusted_records=bad)


def test_records_must_be_word_integrity_records():
    with pytest.raises(TypeError):
        run([{"observation_id": "a"}])


# --- invariances: order, translation, unrelated content ---------------------------------------------------


def _scene():
    records = [word(f"u{i}", (10.0 + 40 * i, 10.0, 40.0 + 40 * i, 20.0), reasons=(GLYPH, CLIP) if i % 3 == 0 else (GLYPH,),
                    matches=i % 2 == 0, text_length=i) for i in range(9)]
    records += [word(f"t{i}", (10.0 + 40 * i, 60.0, 40.0 + 40 * i, 70.0), trusted=True) for i in range(5)]
    spans = [span((5.0 + 40 * i, 5.0, 45.0 + 40 * i, 25.0), font="Arial" if i % 2 else "ISOCPEUR") for i in range(9)]
    return records, spans


def test_the_census_does_not_depend_on_the_order_of_records_spans_or_fonts():
    records, spans = _scene()
    first = run(records, spans=spans)
    for seed in range(5):
        rng = random.Random(seed)
        shuffled_records, shuffled_spans, shuffled_fonts = list(records), list(spans), list(FONTS)
        rng.shuffle(shuffled_records), rng.shuffle(shuffled_spans), rng.shuffle(shuffled_fonts)
        again = run(shuffled_records, spans=shuffled_spans, fonts=shuffled_fonts)
        assert again == first and again.record_id == first.record_id
    assert first.page_fonts == tuple(sorted(FONTS, key=lambda f: f.xref))


@pytest.mark.parametrize("dx,dy", [(0.0, 0.0), (1234.5, -987.25), (-0.37, 0.11), (31.99, 32.01), (1e5, 1e5)])
def test_translating_the_page_content_changes_only_the_coordinates(dx, dy):
    records, spans = _scene()
    base = run(records, spans=spans)
    moved_records = [replace(r, bbox=(r.bbox[0] + dx, r.bbox[1] + dy, r.bbox[2] + dx, r.bbox[3] + dy)) for r in records]
    moved_spans = [replace(s, bbox=(s.bbox[0] + dx, s.bbox[1] + dy, s.bbox[2] + dx, s.bbox[3] + dy)) for s in spans]
    moved = run(moved_records, spans=moved_spans)
    assert moved.status is CAND
    for a, b in zip(base.untrusted_words, moved.untrusted_words):
        assert (a.observation_id, a.reason_set, a.font, a.clip_state) == (b.observation_id, b.reason_set, b.font, b.clip_state)
    assert moved.reason_set_histogram == base.reason_set_histogram and moved.font_reason_histogram == base.font_reason_histogram
    assert moved.font_class_reason_histogram == base.font_class_reason_histogram
    assert moved.untrusted_matching_opening_tag_syntax == base.untrusted_matching_opening_tag_syntax


def test_unrelated_far_away_content_does_not_change_any_existing_word_record():
    records, spans = _scene()
    base = run(records, spans=spans)
    extra_records = records + [word("far-u", (9000.0, 9000.0, 9020.0, 9010.0), reasons=(TEXT_TRACE_UNAVAILABLE,)),
                               word("far-t", (9100.0, 9000.0, 9120.0, 9010.0), trusted=True)]
    extra_spans = spans + [span((8990.0, 8990.0, 9200.0, 9020.0), font="Courier")]
    bigger = run(extra_records, spans=extra_spans)
    assert (bigger.total_count, bigger.trusted_count, bigger.untrusted_count) == (base.total_count + 2, base.trusted_count + 1, base.untrusted_count + 1)
    by_id = {w.observation_id: w for w in bigger.untrusted_words}
    for w in base.untrusted_words:
        assert by_id[w.observation_id] == w
    assert by_id["far-u"].font.font_label == "Courier"


def test_replay_is_deterministic_and_the_input_is_not_mutated():
    records, spans = _scene()
    records_before, spans_before = list(records), list(spans)
    first, again = run(records, spans=spans), run(records, spans=spans)
    assert first == again and first.record_id == again.record_id
    assert records == records_before and spans == spans_before


# --- ownership is part of every id ------------------------------------------------------------------------


@pytest.mark.parametrize("field,value", [
    ("document_id", "other-doc"), ("revision_id", "other-rev"), ("snapshot_id", "other-snap"),
    ("source_sha256", "b" * 64), ("page_id", "8"),
])
def test_every_ownership_field_changes_every_page_and_word_id_and_is_stamped_on_every_record(field, value):
    records, spans = _scene()
    base = run(records, spans=spans)
    other_own = replace(OWN, **{field: value})
    other = run([replace(r, ownership=other_own) for r in records], spans=spans, ownership=other_own)
    assert other.record_id != base.record_id
    assert {w.record_id for w in other.untrusted_words}.isdisjoint({w.record_id for w in base.untrusted_words})
    assert all(w.ownership == other_own for w in other.untrusted_words) and other.ownership == other_own
    atom = other.evidence_atoms[0]
    assert (atom.document_id, atom.page_id) == (other_own.document_id, other_own.page_id)
    assert (atom.metadata["revision_id"], atom.metadata["snapshot_id"], atom.metadata["source_sha256"]) == (
        other_own.revision_id, other_own.snapshot_id, other_own.source_sha256)


def test_the_page_record_id_depends_on_content_not_only_on_ownership():
    records, spans = _scene()
    assert run(records, spans=spans).record_id != run(records[:-1], spans=spans).record_id
    assert run(records, spans=spans).record_id != run(records, spans=[]).record_id


# --- grants ----------------------------------------------------------------------------------------------


def test_every_grant_flag_is_false_enforced_and_listed_in_every_atom():
    records, spans = _scene()
    page = run(records, spans=spans)
    top = C.assemble_census(OWN.root(), [7], [page], 0)
    assert top.status is CAND
    for record in (page, top):
        assert record.shadow_only is True
        for flag in C._GRANT_FLAGS:
            assert getattr(record, flag) is False
            with pytest.raises(ValueError):
                replace(record, **{flag: True})
        with pytest.raises(ValueError):
            replace(record, shadow_only=False)
    assert {"takeoff_eligible", "deduction_authority", "existence_record_issued", "trusted_text_granted",
            "text_identity_granted", "text_trust_changed"} <= set(C._GRANT_FLAGS)
    atom = page.evidence_atoms[0]
    assert all(atom.metadata[flag] is False for flag in C._GRANT_FLAGS)
    assert atom.status is CAND and atom.kind == "unknown" and atom.method == C.RESIDUAL_CENSUS_METHOD and atom.bbox is None


@pytest.mark.parametrize("status", [CONF, CORR, EvidenceResolutionStatus.RAW])
def test_only_candidate_or_abstained_can_be_issued(status):
    page = run([word("a")])
    with pytest.raises(ValueError):
        replace(page, status=status)
    top = C.assemble_census(OWN.root(), [7], [page], 0)
    with pytest.raises(ValueError):
        replace(top, status=status)


def test_a_candidate_cannot_be_forged_over_counts_it_does_not_account_for():
    page = run([word("a"), word("b", trusted=True)])
    for bad in (dict(trusted_count=0), dict(total_count=5), dict(untrusted_count=2),
                dict(reason_set_histogram=()), dict(untrusted_matching_opening_tag_syntax=3),
                dict(untrusted_words=page.untrusted_words + page.untrusted_words)):
        with pytest.raises(ValueError):
            replace(page, **bad)
    with pytest.raises(ValueError):
        replace(page, status=ABST)                      # an abstained page carries no census data
    foreign = replace(page.untrusted_words[0], ownership=replace(OWN, page_id="9"))
    with pytest.raises(ValueError):
        replace(page, untrusted_words=(foreign,))


def test_the_result_types_cannot_be_mistaken_for_an_existence_record_or_a_host_or_scale_result():
    names = {f.name for cls in (C.PageResidualCensus, C.NativeTextResidualCensus, C.UntrustedWord) for f in fields(cls)}
    assert not ({"aperture_bbox_pt", "structural_pattern", "host_candidate_id", "existence_record", "source_geometry",
                 "host_wall_id", "area_m2", "scale", "quantity", "count", "trusted_text"} & names)
    assert "existence_record_issued" in names          # explicitly a False grant flag, never a record


# --- the roll-up -------------------------------------------------------------------------------------------


def test_the_rollup_is_a_candidate_only_when_every_requested_page_has_a_candidate_census():
    p7 = run([word("a")])
    p8_own = replace(OWN, page_id="8")
    p8 = run([word("b", ownership=p8_own)], ownership=p8_own)
    top = C.assemble_census(OWN.root(), [8, 7], [p8, p7], 0)
    assert top.status is CAND and top.reason_codes == (C.CENSUS_PRODUCED,)
    assert top.requested_page_ids == (7, 8) and [p.ownership.page_id for p in top.pages] == ["7", "8"]
    assert top == C.assemble_census(OWN.root(), [7, 8], [p7, p8], 0) and top.record_id == C.assemble_census(OWN.root(), [7, 8], [p7, p8], 0).record_id
    # a missing page, an abstained page, a text id without a receipt: abstain, never a partial pass
    assert C.assemble_census(OWN.root(), [7, 8], [p7], 0).reason_codes == (C.CENSUS_PAGE_INCOMPLETE,)
    gap = C.abstained_page(p8_own, VISIBLE_SOURCE_AUTHORITY_REQUIRED)
    broken = C.assemble_census(OWN.root(), [7, 8], [p7, gap], 0)
    assert broken.status is ABST and broken.reason_codes == (C.CENSUS_PAGE_INCOMPLETE,)
    assert [p.status for p in broken.pages] == [CAND, ABST]                       # the good page is still reported
    orphan = C.assemble_census(OWN.root(), [7], [p7], 2)
    assert orphan.status is ABST and orphan.reason_codes == (C.CENSUS_TEXT_RECEIPT_UNAVAILABLE,)
    assert C.assemble_census(None, [7], [], 0).reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    assert C.assemble_census(None, [7], [], 0).record_id is None


def test_the_rollup_cannot_be_forged_into_a_candidate():
    p7 = run([word("a")])
    top = C.assemble_census(OWN.root(), [7], [p7], 0)
    with pytest.raises(ValueError):
        replace(top, text_ids_without_receipt=1)
    with pytest.raises(ValueError):
        replace(top, requested_page_ids=(7, 8))
    with pytest.raises(ValueError):
        replace(top, root=replace(OWN.root(), snapshot_id="other"))
    with pytest.raises(ValueError):
        replace(top, pages=(C.abstained_page(OWN, C.CENSUS_BUDGET_EXCEEDED),))
    with pytest.raises(ValueError):
        replace(top, pages=())


def test_a_foreign_page_inside_the_rollup_is_not_hidden():
    p7 = run([word("a")])
    foreign_own = replace(OWN, revision_id="other-rev", page_id="8")
    p8 = run([word("b", ownership=foreign_own)], ownership=foreign_own)
    top = C.assemble_census(OWN.root(), [7, 8], [p7, p8], 0)
    assert top.status is ABST and top.reason_codes == (C.CENSUS_FOREIGN_RECORD,)
    assert [p.ownership.revision_id for p in top.pages] == ["rev", "other-rev"]      # nothing is dropped or relabelled


# --- defects found in review: each test below fails on the earlier implementation ----------------------------


def test_a_type3_font_is_a_glyph_procedure_font_not_an_unembedded_one():
    assert C.program_class("n/a", "Type3") == C.PROGRAM_TYPE3_GLYPH_PROCEDURES
    assert C.program_class("", " type3 ") == C.PROGRAM_TYPE3_GLYPH_PROCEDURES
    assert C.program_class("n/a", "Type1") == C.PROGRAM_NOT_EMBEDDED == "not_embedded"
    assert C.program_class("ttf", "Type3") == C.PROGRAM_TYPE3_GLYPH_PROCEDURES      # the subtype decides, not the extension
    assert C.program_class("ttf", "TrueType") == "embedded_ttf"
    label = C.font_class_of("Type3", C.program_class("n/a", "Type3"), "", False)
    assert label == "Type3/type3_glyph_procedures/no_encoding/no_tounicode"


def test_a_candidate_page_census_cannot_carry_a_histogram_that_only_has_the_right_total():
    page = run([word("a"), word("b", reasons=(GLYPH, CLIP)), word("c", trusted=True)], spans=[span((0, 0, 100, 40))])
    assert page.untrusted_count == 2
    swapped = (((GLYPH,), 1), ((CLIP, GLYPH), 1))
    assert page.reason_set_histogram == tuple(sorted(swapped))
    forged = {
        "reason_set_histogram": (((GLYPH,), 2),),                                        # right total, wrong tally
        "font_reason_histogram": ((("Arial", (GLYPH,)), 2),),
        "font_class_reason_histogram": (((ARIAL.font_class, (GLYPH,)), 2),),
        "clip_state_histogram": ((C.NO_CLIP_REASON, 2),),
    }
    for name, value in forged.items():
        assert sum(n for _, n in value) == page.untrusted_count
        assert getattr(page, name) != value
        with pytest.raises(ValueError):
            replace(page, **{name: value})
    with pytest.raises(ValueError):
        replace(page, trusted_count=-1, total_count=1)


def test_every_counter_kept_of_an_untrusted_word_is_part_of_its_id():
    base = run([word("w", text_length=3, matches=False)]).untrusted_words[0]
    assert run([word("w", text_length=4, matches=False)]).untrusted_words[0].record_id != base.record_id
    assert run([word("w", text_length=3, matches=True)]).untrusted_words[0].record_id != base.record_id
    assert run([word("w", text_length=3, matches=False, xref=ARIAL.xref)]).untrusted_words[0].record_id != base.record_id
    # the receipt's reasons and the reasons exactly as issued are kept on the record, so they are in its id even
    # when they change neither the reason set nor the clip state
    assert run([word("w", text_length=3, matches=False, receipt_reasons=(GLYPH, "text_unicode_untrusted"))]
               ).untrusted_words[0].record_id != base.record_id
    assert run([word("w", reasons=(GLYPH, GLYPH), text_length=3, matches=False)]).untrusted_words[0].record_id != base.record_id
    assert run([word("w", text_length=3, matches=False)]).untrusted_words[0].record_id == base.record_id
    again = replace(word("w", text_length=3, matches=False), decode_status="other")
    assert run([again]).untrusted_words[0].record_id != base.record_id


def test_a_word_box_near_the_float_limit_neither_crashes_nor_gains_a_font():
    huge = word("w", (1.5e308, 0.0, 1.7e308, 1.0))
    assert run([huge]).untrusted_words[0].font.join_status == C.FONT_UNRESOLVED
    inside = run([huge], spans=[span((1.0e308, -1.0, 1.75e308, 5.0), font="Arial")])
    assert inside.untrusted_words[0].font.font_label == "Arial"
    just_beyond = run([huge], spans=[span((1.0e308, -1.0, 1.55e308, 5.0), font="Arial")])       # centre 1.6e308 is outside
    assert just_beyond.untrusted_words[0].font.join_status == C.FONT_UNRESOLVED


def test_the_reason_set_never_borrows_a_reason_from_the_receipt_or_the_clip_state():
    """The clip state is read from the receipt, the reason set from the authority's result: neither fills the other."""
    got = run([word("w", reasons=(GLYPH,), receipt_reasons=(GLYPH, CLIP, TEXT_CLIPPED_BY_CLIP_REGION))])
    only = got.untrusted_words[0]
    assert only.reason_set == (GLYPH,) and only.clip_state == C.CLIP_UNRESOLVED_AND_CLIPPED
    assert only.clip_reason_codes == (CLIP, TEXT_CLIPPED_BY_CLIP_REGION)
