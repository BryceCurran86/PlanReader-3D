"""The native text residual census through the real producer on synthetic PDFs (no caller-built records).

Every PDF here is generated from scratch with a minimal raw builder; nothing is read from any project file.
Words in font F1/F3 carry a ToUnicode map and no embedded program, so the producer's own glyph proof leaves
them untrusted (`text_glyph_mapping_unverified`); words in the base-14 font F2 are trusted.
"""
from __future__ import annotations

import inspect
from dataclasses import asdict, replace
from typing import Mapping, Optional, Sequence

import pytest

import pb_native_text_residual_census_shadow as C
from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
    TEXT_INTEGRITY_RECEIPT_MISMATCH,
    TEXT_TRACE_AMBIGUOUS,
)
from pb_physical_opening_authority import SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE, VISIBLE_SOURCE_AUTHORITY_REQUIRED
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED
CONF = EvidenceResolutionStatus.CONFLICT
GLYPH = TEXT_GLYPH_MAPPING_UNVERIFIED
CLIP = TEXT_CLIP_STATE_UNRESOLVED
ARIAL_CLASS = "Type1/not_embedded/no_encoding/tounicode"

# --------------------------------------------------------------------------------------
# a minimal raw PDF builder (object syntax fully under the test's control)
# --------------------------------------------------------------------------------------

_SYSINFO = "/CIDSystemInfo 3 dict dup begin\n/Registry (Adobe) def\n/Ordering (UCS) def\n/Supplement 0 def\nend def"


def _pdf_bytes(objects: Mapping[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    pos = len(header)
    for number in sorted(objects):
        offsets[number] = pos
        chunk = f"{number} 0 obj\n".encode("ascii") + objects[number].encode("latin1") + b"\nendobj\n"
        chunks.append(chunk)
        pos += len(chunk)
    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        xref.append(f"{offsets[number]:010d} 00000 n \n" if number in offsets else "0000000000 00000 f \n")
    trailer = f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n"
    return b"".join(chunks) + "".join(xref).encode("ascii") + trailer.encode("ascii")


def _stream_obj(body: str) -> str:
    return f"<< /Length {len(body.encode('latin1'))} >>\nstream\n{body}\nendstream"


def _cmap(characters: str) -> str:
    codes = sorted(set(map(ord, characters)))
    mappings = "\n".join(f"<{code:02X}> <{code:04X}>" for code in codes)
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        f"{_SYSINFO}\n/CMapName /Generic def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        f"{len(codes)} beginbfchar\n{mappings}\nendbfchar\nendcmap\n"
        "CMapName currentdict /CMap defineresource pop\nend\nend"
    )


Word = tuple  # (font key, text, x, y, size)


def _page_stream(words: Sequence[Word], dx: float, dy: float, clip: bool) -> str:
    body = "\n".join(f"BT /{font} {size} Tf {x + dx} {y + dy} Td ({text}) Tj ET" for font, text, x, y, size in words)
    return f"q 10 0 m 500 0 l 10 400 l h W n\n{body}\nQ" if clip else body


def _pdf(pages: Sequence[Sequence[Word]], *, rotate: int = 0, clip: bool = False, dx: float = 0.0, dy: float = 0.0,
         extra_fonts: Optional[Mapping[str, tuple[int, str]]] = None,
         extra_objects: Optional[Mapping[int, str]] = None, crop_box: str = "") -> bytes:
    """F1 Arial and F3 Verdana carry a ToUnicode map and no program (untrusted); F2 Helvetica is base-14 (trusted)."""
    chars = "".join(text for page in pages for font, text, *_ in page if font in ("F1", "F3"))
    fonts = {
        "F1": (50, "<< /Type /Font /Subtype /Type1 /BaseFont /Arial /FirstChar 32 /LastChar 126 /ToUnicode 60 0 R >>"),
        "F2": (51, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"),
        "F3": (52, "<< /Type /Font /Subtype /Type1 /BaseFont /Verdana /FirstChar 32 /LastChar 126 /ToUnicode 60 0 R >>"),
        **(extra_fonts or {}),
    }
    font_res = " ".join(f"/{name} {num} 0 R" for name, (num, _obj) in fonts.items())
    kids = " ".join(f"{10 + 2 * i} 0 R" for i in range(len(pages)))
    objects: dict[int, str] = {
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>",
        60: _stream_obj(_cmap(chars or " ")),
    }
    for i, page in enumerate(pages):
        stream = _page_stream(page, dx, dy, clip)
        objects[10 + 2 * i] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 300] {crop_box} /Rotate {rotate} "
            f"/Resources << /Font << {font_res} >> >> /Contents {11 + 2 * i} 0 R >>")
        objects[11 + 2 * i] = f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream"
    for _name, (num, obj) in fonts.items():
        objects[num] = obj
    objects.update(extra_objects or {})
    return _pdf_bytes(objects)


# four untrusted words in two untrusted fonts, one tag-shaped; two trusted words
UNTRUSTED_WORDS = (("F1", "QXZJKW", 20, 250, 10), ("F1", "W12", 120, 250, 10), ("F3", "VVJQXZ", 20, 200, 10),
                   ("F1", "ZZQXJ", 120, 200, 10))
TRUSTED_WORDS = (("F2", "Hello", 20, 150, 10), ("F2", "Plan", 120, 150, 10))
MIXED = (UNTRUSTED_WORDS + TRUSTED_WORDS,)


def _publish(pdf: bytes, document_id: str = "census-doc", **producer_kw):
    source = SourceVisibilityProducer(producer_method="census-test", producer_version="1", **producer_kw)
    published = source.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=pdf, source_locator="memory://census.pdf")
    return source, published


def _census(source, published, pages=(1,), enabled=True, **kw):
    return C.NativeTextResidualCensusShadow(source, enabled=enabled, **kw).census(
        revision_id=published.revision.revision_id, page_ids=pages)


def _selector(published, oid):
    return ObservationSelector(published.revision.document_id, published.revision.revision_id,
                               published.revision.source_sha256, published.snapshot.snapshot_id, oid)


def _direct(source, published):
    """The authority's own answer for every native word, asked the way any consumer asks it."""
    authority = source.text_integrity_authority()
    return {oid: authority.resolve_text(_selector(published, oid)) for oid in published.text_observation_ids}


# --- gate -----------------------------------------------------------------------------------------------


def _shape(obj):
    return {k: (len(v) if isinstance(v, (dict, set, list, tuple)) else None) for k, v in sorted(vars(obj).items())
            if isinstance(v, (dict, set, list, tuple)) or hasattr(v, "keys")}


MEMO = "verified_resolution_cache"


def _state(obj):
    """Every container length and every scalar attribute (so a bumped counter is seen too)."""
    out = {}
    for key, value in sorted(vars(obj).items()):
        if isinstance(value, (dict, set, list, tuple)) or hasattr(value, "keys"):
            out[key] = len(value)
        elif isinstance(value, (bool, int, str, type(None))):
            out[key] = value
    return out


def _all_state(source):
    return {"source": _state(source), "producer": _state(source._producer), "store": _state(source._producer._store)}


def test_the_census_is_off_by_default_and_a_disabled_call_touches_nothing():
    source, published = _publish(_pdf(MIXED))
    before = (_shape(source), _shape(source._producer), _shape(source._producer._store))
    shadow = C.NativeTextResidualCensusShadow(source)
    got = shadow.census(revision_id=published.revision.revision_id, page_ids=(1,))
    assert got.status is ABST and got.reason_codes == (C.CENSUS_DISABLED,) and got.root is None and got.pages == ()
    assert got.record_id is None and got.requested_page_ids == ()
    assert (_shape(source), _shape(source._producer), _shape(source._producer._store)) == before
    # the gate is checked before anything else, so a disabled call never raises on its arguments
    assert shadow.census(revision_id=7, page_ids="x").reason_codes == (C.CENSUS_DISABLED,)


@pytest.mark.parametrize("bad", [1, 0, None, "true", [], {}])
def test_the_gate_must_be_a_strict_boolean_and_the_source_the_concrete_producer(bad):
    source, _ = _publish(_pdf(MIXED))
    with pytest.raises(ValueError):
        C.NativeTextResidualCensusShadow(source, enabled=bad)
    with pytest.raises(TypeError):
        C.NativeTextResidualCensusShadow(object(), enabled=True)
    for bound in (0, -1, True, 1.5, None, "5"):
        with pytest.raises(ValueError):
            C.NativeTextResidualCensusShadow(source, enabled=True, max_untrusted_records=bound)


def test_there_is_no_caller_channel_for_words_trust_fonts_or_regions():
    signature = inspect.signature(C.NativeTextResidualCensusShadow.census)
    assert [p for p in signature.parameters if p != "self"] == ["revision_id", "page_ids"]
    source, published = _publish(_pdf(MIXED))
    for extra in ({"words": []}, {"trusted": True}, {"font": "Arial"}, {"bbox": (0, 0, 1, 1)}):
        with pytest.raises(TypeError):
            C.NativeTextResidualCensusShadow(source, enabled=True).census(
                revision_id=published.revision.revision_id, page_ids=(1,), **extra)


# --- the residuals the producer itself leaves --------------------------------------------------------------


def test_a_page_of_only_trusted_words_has_no_residual():
    source, published = _publish(_pdf([TRUSTED_WORDS]))
    got = _census(source, published)
    assert got.status is CAND and got.reason_codes == (C.CENSUS_PRODUCED,)
    page = got.pages[0]
    assert (page.total_count, page.trusted_count, page.untrusted_count) == (2, 2, 0)
    assert page.untrusted_words == () and page.reason_set_histogram == ()


def test_glyph_unverified_words_are_reported_with_exactly_that_reason_and_their_font_and_class():
    source, published = _publish(_pdf([UNTRUSTED_WORDS[:2] + (("F1", "ZZQXJ", 20, 200, 10),)]))
    got = _census(source, published)
    page = got.pages[0]
    assert got.status is CAND and (page.total_count, page.trusted_count, page.untrusted_count) == (3, 0, 3)
    assert page.reason_set_histogram == (((GLYPH,), 3),)
    assert all(w.reason_set == (GLYPH,) and w.reason_codes == (GLYPH,) for w in page.untrusted_words)
    assert all(w.authority_status is ABST and w.clip_state == C.NO_CLIP_REASON and w.clip_reason_codes == () for w in page.untrusted_words)
    assert all(w.decode_status == "tounicode_glyph_unverified" and w.visibility_status == "proven_visible"
               for w in page.untrusted_words)
    font = page.untrusted_words[0].font
    assert font.font_label == "Arial" and font.font_class == ARIAL_CLASS and font.font_class_basis == C.CLASS_BASIS_RECEIPT_XREF
    assert font.font_sources_agree is True and font.line_direction == C.BASELINE_EAST
    assert page.page_fonts[0].base_font == "Arial" and page.page_fonts[0].has_to_unicode is True
    assert page.page_fonts[0].program == "not_embedded"
    assert page.font_reason_histogram == ((("Arial", (GLYPH,)), 3),)
    assert page.font_class_reason_histogram == (((ARIAL_CLASS, (GLYPH,)), 3),)
    assert page.clip_state_histogram == ((C.NO_CLIP_REASON, 3),)


def test_a_clip_that_cannot_be_resolved_adds_exactly_that_reason_and_the_clip_state():
    source, published = _publish(_pdf([UNTRUSTED_WORDS[:2]], clip=True))
    page = _census(source, published).pages[0]
    assert page.untrusted_count == 2
    assert page.reason_set_histogram == (((CLIP, GLYPH), 2),)
    assert all(w.clip_state == C.CLIP_STATE_UNRESOLVED and w.clip_reason_codes == (CLIP,) for w in page.untrusted_words)
    assert all(w.visibility_status == "unresolved_or_blocked" for w in page.untrusted_words)
    assert page.clip_state_histogram == ((C.CLIP_STATE_UNRESOLVED, 2),)


def test_trusted_and_untrusted_words_on_one_page_are_separated_and_the_histograms_split_by_font():
    source, published = _publish(_pdf(MIXED))
    page = _census(source, published).pages[0]
    assert (page.total_count, page.trusted_count, page.untrusted_count) == (6, 2, 4)
    assert dict(page.font_reason_histogram) == {("Arial", (GLYPH,)): 3, ("Verdana", (GLYPH,)): 1}
    assert dict(page.font_class_reason_histogram) == {(ARIAL_CLASS, (GLYPH,)): 4}
    assert {f.base_font for f in page.page_fonts} == {"Arial", "Helvetica", "Verdana"}
    assert page.untrusted_matching_opening_tag_syntax == 1                     # the one tag-shaped untrusted word
    helvetica = next(f for f in page.page_fonts if f.base_font == "Helvetica")
    assert helvetica.font_class == "Type1/not_embedded/no_encoding/no_tounicode"
    assert all(w.font.font_label in ("Arial", "Verdana") for w in page.untrusted_words)


def test_the_census_equals_an_independent_recount_of_the_authoritys_own_answers():
    source, published = _publish(_pdf(MIXED))
    direct = _direct(source, published)
    expected_untrusted = {
        oid: r for oid, r in direct.items()
        if not (r.status is EvidenceResolutionStatus.CORROBORATED and r.proposition == "trusted_pdf_text")}
    page = _census(source, published).pages[0]
    assert page.total_count == len(direct) == len(published.text_observation_ids)
    assert {w.observation_id for w in page.untrusted_words} == set(expected_untrusted)
    for w in page.untrusted_words:
        r = expected_untrusted[w.observation_id]
        assert w.reason_codes == tuple(r.reason_codes) and w.authority_status is r.status
        assert w.bbox == tuple(float(v) for v in r.receipt.geometry)
        assert w.text_length == len(r.receipt.raw_text) and w.sequence_number == r.receipt.sequence_number
        assert (w.receipt_font_xref, w.receipt_font_name) == (r.receipt.font_xref, r.receipt.font_name)


def test_tag_shaped_untrusted_words_are_counted_without_keeping_any_text():
    words = tuple(("F1", text, 20, 250 - 30 * i, 10) for i, text in enumerate(("W12", "D3", "W-07", "WINDOW", "QXZJKW")))
    source, published = _publish(_pdf([words]))
    page = _census(source, published).pages[0]
    assert page.untrusted_count == 5 and page.untrusted_matching_opening_tag_syntax == 3
    assert sorted(w.text_length for w in page.untrusted_words) == [2, 3, 4, 6, 6]
    flagged = sorted(w.text_length for w in page.untrusted_words if w.matches_opening_tag_syntax)
    assert flagged == [2, 3, 4]


def test_no_untrusted_word_text_appears_anywhere_in_the_result():
    sentinels = ("QXZJKW", "VVJQXZ", "ZZQXJ", "W12")
    source, published = _publish(_pdf(MIXED))
    got = _census(source, published)
    dumped = repr(got) + repr(asdict(got))
    for sentinel in sentinels + ("Hello", "Plan"):
        assert sentinel not in dumped, sentinel
    assert all(sentinel not in repr(atom) for page in got.pages for atom in page.evidence_atoms for sentinel in sentinels)


def test_a_receipt_that_no_longer_matches_its_observation_is_an_untrusted_conflict_word_with_that_reason():
    source, published = _publish(_pdf(MIXED))
    key = (published.snapshot.snapshot_id, next(iter(published.text_observation_ids)))
    receipt = source._text_integrity_receipts[key]
    source._text_integrity_receipts[key] = replace(receipt, raw_text="tampered-text")
    page = _census(source, published).pages[0]
    word = next(w for w in page.untrusted_words if w.observation_id == key[1])
    assert word.authority_status is CONF and word.reason_set == (TEXT_INTEGRITY_RECEIPT_MISMATCH,)
    assert word.text_length == len("tampered-text")
    assert "tampered-text" not in repr(page)


def test_overlapping_spans_of_different_fonts_keep_both_candidates_and_the_trace_ambiguity():
    words = (("F2", "Same", 40, 120, 12), ("F3", "Same", 40, 120, 12))
    source, published = _publish(_pdf([words]))
    page = _census(source, published).pages[0]
    assert page.untrusted_count == 2 and page.reason_set_histogram == (((TEXT_TRACE_AMBIGUOUS,), 2),)
    for w in page.untrusted_words:
        assert w.font.join_status == C.FONT_AMBIGUOUS and w.font.font_label == C.FONT_AMBIGUOUS
        assert w.font.candidate_fonts == ("Helvetica", "Verdana") and w.font.containing_span_count == 2
        assert w.font.font_class == C.FONT_CLASS_UNRESOLVED and w.font.font_sources_agree is None
        assert w.clip_state == C.CLIP_NOT_EVALUATED_NO_TRACE and w.receipt_font_xref is None
    assert dict(page.font_reason_histogram) == {(C.FONT_AMBIGUOUS, (TEXT_TRACE_AMBIGUOUS,)): 2}


def test_a_word_no_span_contains_is_font_unresolved(monkeypatch):
    source, published = _publish(_pdf(MIXED))
    monkeypatch.setattr(C, "_page_spans", lambda page: ())
    page = _census(source, published).pages[0]
    assert page.untrusted_count == 4
    assert all(w.font.font_label == C.FONT_UNRESOLVED and w.font.font_class_basis == C.CLASS_BASIS_RECEIPT_XREF
               for w in page.untrusted_words)
    assert all(w.font.font_class == ARIAL_CLASS for w in page.untrusted_words)      # the receipt's own binding still names it
    assert dict(page.font_reason_histogram) == {(C.FONT_UNRESOLVED, (GLYPH,)): 4}


def test_a_rotated_page_is_read_in_its_native_frame_with_the_same_fonts_and_boxes():
    plain_source, plain_published = _publish(_pdf(MIXED, rotate=0), document_id="rot-doc")
    rot_source, rot_published = _publish(_pdf(MIXED, rotate=90), document_id="rot-doc")
    plain = _census(plain_source, plain_published).pages[0]
    rotated = _census(rot_source, rot_published).pages[0]
    assert rotated.status is CAND and rotated.untrusted_count == plain.untrusted_count == 4
    key = lambda w: (w.bbox, w.font.font_label, w.font.font_class, w.font.line_direction)    # noqa: E731
    assert sorted(map(key, rotated.untrusted_words)) == sorted(map(key, plain.untrusted_words))
    assert sorted(w.reason_set for w in rotated.untrusted_words) == sorted(w.reason_set for w in plain.untrusted_words)
    assert all(GLYPH in w.reason_set for w in rotated.untrusted_words)
    assert all(w.font.join_status == C.SPAN_FONT_RESOLVED for w in rotated.untrusted_words)
    assert {w.font.line_direction for w in rotated.untrusted_words} == {C.BASELINE_EAST}      # the native frame, not the display


# --- pages, ownership, stale and foreign inputs ------------------------------------------------------------


def _three_pages():
    return [MIXED[0], (), (("F1", "ZZQXJ", 30, 100, 10), ("F2", "Note", 30, 150, 10), ("F1", "QXZJKW", 30, 50, 10))]


def test_each_requested_page_is_censused_on_its_own_and_the_request_order_does_not_matter():
    source, published = _publish(_pdf(_three_pages()))
    forward = _census(source, published, pages=(1, 2, 3))
    backward = _census(source, published, pages=(3, 1, 2))
    assert forward == backward and forward.record_id == backward.record_id
    assert forward.status is CAND and forward.requested_page_ids == (1, 2, 3)
    counts = {p.ownership.page_id: (p.total_count, p.trusted_count, p.untrusted_count) for p in forward.pages}
    assert counts == {"1": (6, 2, 4), "2": (0, 0, 0), "3": (3, 1, 2)}
    blank = forward.pages[1]
    assert blank.status is CAND and blank.reason_codes == (C.CENSUS_PRODUCED, C.CENSUS_PAGE_HAS_NO_NATIVE_TEXT_RECEIPTS)
    assert _census(source, published, pages=(3,)).pages[0] == forward.pages[2]
    # a page's census does not depend on which other pages were asked for
    assert _census(source, published, pages=(1,)).pages[0] == forward.pages[0]
    assert all(w.ownership.page_id == "3" for w in forward.pages[2].untrusted_words)


def test_ownership_is_stamped_on_the_result_every_page_and_every_word():
    source, published = _publish(_pdf(_three_pages()))
    got = _census(source, published, pages=(1, 3))
    root = C.CensusRoot(published.revision.document_id, published.revision.revision_id,
                        published.snapshot.snapshot_id, published.revision.source_sha256)
    assert got.root == root
    for page in got.pages:
        assert page.ownership.root() == root
        assert all(w.ownership == page.ownership for w in page.untrusted_words)
        atom = page.evidence_atoms[0]
        assert (atom.document_id, atom.page_id) == (root.document_id, page.ownership.page_id)
        assert atom.metadata["revision_id"] == root.revision_id and atom.metadata["source_sha256"] == root.source_sha256
    # the same bytes under another document id give another set of ids and the same counts
    other_source, other_published = _publish(_pdf(_three_pages()), document_id="another-doc")
    other = _census(other_source, other_published, pages=(1, 3))
    assert other.record_id != got.record_id
    assert {w.record_id for p in other.pages for w in p.untrusted_words}.isdisjoint(
        {w.record_id for p in got.pages for w in p.untrusted_words})
    assert [(p.total_count, p.untrusted_count, p.reason_set_histogram) for p in other.pages] == [
        (p.total_count, p.untrusted_count, p.reason_set_histogram) for p in got.pages]


def test_a_page_the_revision_did_not_decode_abstains_that_page_and_the_rollup_but_keeps_the_good_page():
    source, published = _publish(_pdf([MIXED[0]]))
    got = _census(source, published, pages=(1, 9))
    assert got.status is ABST and got.reason_codes == (C.CENSUS_PAGE_INCOMPLETE,)
    assert [p.status for p in got.pages] == [CAND, ABST]
    assert got.pages[1].reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,) and got.pages[1].total_count == 0
    assert got.pages[0] == _census(source, published, pages=(1,)).pages[0]


def test_unknown_stale_or_foreign_revisions_abstain():
    source, published = _publish(_pdf([MIXED[0]]))
    shadow = C.NativeTextResidualCensusShadow(source, enabled=True)
    unknown = shadow.census(revision_id="no-such-revision", page_ids=(1,))
    assert unknown.status is ABST and unknown.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,) and unknown.pages == ()
    # a revision published by another producer is not this producer's revision
    foreign_source, foreign_published = _publish(_pdf([MIXED[0]]), document_id="foreign-doc")
    foreign = shadow.census(revision_id=foreign_published.revision.revision_id, page_ids=(1,))
    assert foreign.status is ABST and foreign.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,)
    # a later revision of the same document makes the earlier one stale
    source.ingest_native_pdf_bytes(document_id=published.revision.document_id,
                                   source_bytes=_pdf([UNTRUSTED_WORDS[:1]]), source_locator="memory://census-2.pdf")
    stale = shadow.census(revision_id=published.revision.revision_id, page_ids=(1,))
    assert stale.status is ABST and stale.reason_codes == (VISIBLE_SOURCE_AUTHORITY_REQUIRED,) and stale.pages == ()


def test_source_bytes_that_fail_their_sha_check_abstain():
    source, published = _publish(_pdf([MIXED[0]]))
    store = source._producer._store
    original = store.source_bytes_by_revision[published.revision.revision_id]
    store.source_bytes_by_revision[published.revision.revision_id] = original + b"\n%tampered"
    try:
        got = _census(source, published)
    finally:
        store.source_bytes_by_revision[published.revision.revision_id] = original
    assert got.status is ABST and got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,) and got.pages == ()


@pytest.mark.parametrize("bad", [
    dict(revision_id=1), dict(revision_id=""), dict(page_ids="1"), dict(page_ids=(1, 1)), dict(page_ids=()),
    dict(page_ids=(0,)), dict(page_ids=(-2,)), dict(page_ids=(True,)), dict(page_ids=(1.0,)), dict(page_ids=("1",)),
    dict(page_ids={1}), dict(page_ids=7), dict(page_ids=None), dict(page_ids=tuple(range(1, 100))),
])
def test_malformed_requests_are_rejected_before_any_work(bad):
    source, published = _publish(_pdf([MIXED[0]]))
    args = dict(revision_id=published.revision.revision_id, page_ids=(1,))
    args.update(bad)
    before = _shape(source)
    with pytest.raises(ValueError):
        C.NativeTextResidualCensusShadow(source, enabled=True).census(**args)
    assert _shape(source) == before


def test_a_list_or_generator_of_page_ids_is_accepted():
    source, published = _publish(_pdf(_three_pages()))
    assert _census(source, published, pages=[1, 3]).requested_page_ids == (1, 3)
    assert _census(source, published, pages=(p for p in (3, 1))).requested_page_ids == (1, 3)


def test_the_work_bound_abstains_the_page_typed_without_a_partial_census():
    source, published = _publish(_pdf(_three_pages()))
    got = _census(source, published, pages=(1, 3), max_untrusted_records=3)       # page 1 has 4, page 3 has 2
    assert got.status is ABST and got.reason_codes == (C.CENSUS_PAGE_INCOMPLETE,)
    over, ok = got.pages
    assert over.status is ABST and over.reason_codes == (C.CENSUS_BUDGET_EXCEEDED,)
    assert (over.total_count, over.untrusted_count, over.untrusted_words) == (0, 0, ())
    assert ok.status is CAND and ok.untrusted_count == 2


def test_a_text_id_with_no_receipt_abstains_the_rollup_but_not_the_pages_it_cannot_place():
    source, published = _publish(_pdf(_three_pages()))
    victim = next(iter(published.text_observation_ids))
    del source._text_integrity_receipts[(published.snapshot.snapshot_id, victim)]
    got = _census(source, published, pages=(1, 3))
    assert got.status is ABST and got.reason_codes == (C.CENSUS_TEXT_RECEIPT_UNAVAILABLE,)
    assert got.text_ids_without_receipt == 1
    assert sum(p.total_count for p in got.pages) == len(published.text_observation_ids) - 1


@pytest.mark.parametrize("tamper", [dict(geometry=(0.0, 0.0, 1.0)), dict(parent_observation_id="somebody-else"),
                                    dict(geometry=(0.0, 0.0, float("nan"), 1.0))])
def test_a_receipt_that_cannot_be_placed_abstains_the_page(tamper):
    source, published = _publish(_pdf([MIXED[0]]))
    key = (published.snapshot.snapshot_id, next(iter(published.text_observation_ids)))
    source._text_integrity_receipts[key] = replace(source._text_integrity_receipts[key], **tamper)
    got = _census(source, published)
    assert got.status is ABST and got.pages[0].reason_codes == (C.CENSUS_WORD_UNPLACEABLE,)
    assert got.pages[0].total_count == 0 and got.pages[0].untrusted_words == ()


# --- determinism and invariances ---------------------------------------------------------------------------


def test_independent_producers_over_the_same_bytes_give_the_same_census():
    pdf = _pdf(_three_pages())
    first = _census(*_publish(pdf), pages=(1, 3))
    second = _census(*_publish(pdf), pages=(1, 3))
    assert first == second and first.record_id == second.record_id
    assert [p.record_id for p in first.pages] == [p.record_id for p in second.pages]


def test_translating_every_word_moves_only_the_coordinates():
    base = _census(*_publish(_pdf(MIXED), document_id="shift-doc")).pages[0]
    for dx, dy in ((37.0, 0.0), (0.0, -41.0), (13.5, 22.25)):
        moved = _census(*_publish(_pdf(MIXED, dx=dx, dy=dy), document_id="shift-doc")).pages[0]
        assert moved.status is CAND
        assert moved.reason_set_histogram == base.reason_set_histogram
        assert moved.font_reason_histogram == base.font_reason_histogram
        assert moved.font_class_reason_histogram == base.font_class_reason_histogram
        assert moved.untrusted_matching_opening_tag_syntax == base.untrusted_matching_opening_tag_syntax
        key = lambda w: (w.font.font_label, w.reason_set, w.text_length, w.clip_state)       # noqa: E731
        by_key = {key(w): w for w in base.untrusted_words}
        assert len(by_key) == len(base.untrusted_words)
        for w in moved.untrusted_words:
            b = by_key[key(w)]
            assert w.bbox[0] == pytest.approx(b.bbox[0] + dx, abs=1e-3) and w.bbox[2] == pytest.approx(b.bbox[2] + dx, abs=1e-3)
            assert w.bbox[1] == pytest.approx(b.bbox[1] - dy, abs=1e-3) and w.bbox[3] == pytest.approx(b.bbox[3] - dy, abs=1e-3)


def test_unrelated_content_elsewhere_changes_no_existing_untrusted_word_record():
    base = _census(*_publish(_pdf(MIXED), document_id="extra-doc")).pages[0]
    more = MIXED[0] + (("F3", "LLMMNN", 300, 40, 10), ("F2", "Else", 300, 80, 10))
    bigger = _census(*_publish(_pdf([more]), document_id="extra-doc2")).pages[0]
    assert (bigger.total_count, bigger.trusted_count, bigger.untrusted_count) == (
        base.total_count + 2, base.trusted_count + 1, base.untrusted_count + 1)
    strip = lambda w: (w.bbox, w.reason_set, w.font, w.clip_state, w.text_length)               # noqa: E731
    now = {strip(w) for w in bigger.untrusted_words}
    assert {strip(w) for w in base.untrusted_words} <= now


@pytest.mark.parametrize("flag", [False, True])
def test_under_either_value_of_the_opt_in_the_census_equals_the_authoritys_own_answers(flag):
    """The opt-in decides how many words the authority trusts; the census must follow it exactly, never add to it."""
    source, published = _publish(_pdf(MIXED), document_id="flag-doc", source_native_finish_text_shadow=flag)
    direct = _direct(source, published)
    untrusted = {oid: r for oid, r in direct.items()
                 if not (r.status is EvidenceResolutionStatus.CORROBORATED and r.proposition == "trusted_pdf_text")}
    page = _census(source, published).pages[0]
    assert page.status is CAND and page.total_count == len(direct)
    assert {w.observation_id for w in page.untrusted_words} == set(untrusted)
    assert page.trusted_count == len(direct) - len(untrusted)
    assert {w.observation_id: w.reason_codes for w in page.untrusted_words} == {
        oid: tuple(r.reason_codes) for oid, r in untrusted.items()}


# --- the producer is untouched ------------------------------------------------------------------------------


def test_the_census_changes_no_state_of_the_producer_and_no_answer_of_its_text_authority():
    pdf = _pdf(_three_pages())
    source, published = _publish(pdf)
    store = source._producer._store
    # a cold memo (as after a large ingest evicts verified hints): the verified-read memo is a disposable
    # acceleration hint that every text read refills, so start from empty to make its growth observable
    getattr(store, MEMO).clear()
    state_before = _all_state(source)
    tables = ("revisions", "snapshots", "observations", "record_fingerprints", "source_bytes_by_revision",
              "coverage_by_revision", "current_revision_by_document", "snapshot_observation_id_sets",
              "source_snapshot_by_revision", "verified_source_integrity_by_revision", "committed_record_ids")
    tables_before = {name: dict(getattr(store, name)) if hasattr(getattr(store, name), "keys") else set(getattr(store, name))
                     for name in tables}
    receipts_before = dict(source._text_integrity_receipts)
    published_before = source.published_snapshot_for_revision(published.revision.revision_id)
    memo_before = set(getattr(store, MEMO))

    got = _census(source, published, pages=(1, 2, 3))
    assert got.status is CAND

    state_after = _all_state(source)
    # the producer's verified-read memo is the ONE thing a text read fills (it is a disposable acceleration hint);
    # it did grow here, so the exemption below is a measured fact and not an assumption
    memo_after = set(getattr(store, MEMO))
    assert memo_after > memo_before
    for part in state_before:
        wanted, got_state = dict(state_before[part]), dict(state_after[part])
        if part == "store":
            wanted.pop(MEMO), got_state.pop(MEMO)
        assert got_state == wanted, part
    assert source._physical_opening_authority_cache is None and source._physical_scale_producer_cache is None
    assert dict(source._text_integrity_receipts) == receipts_before
    assert source.published_snapshot_for_revision(published.revision.revision_id) == published_before
    for name in tables:
        current = getattr(store, name)
        assert (dict(current) if hasattr(current, "keys") else set(current)) == tables_before[name], name
    # no answer of the text authority differs from the one an independent, never-censused producer gives
    fresh_source, fresh_published = _publish(pdf)
    summarise = lambda r: (r.status, r.proposition, r.reason_codes, r.receipt)               # noqa: E731
    fresh = {oid: summarise(r) for oid, r in _direct(fresh_source, fresh_published).items()}
    assert {oid: summarise(r) for oid, r in _direct(source, published).items()} == fresh


def test_the_only_memo_the_census_fills_is_the_one_every_text_consumer_fills():
    pdf = _pdf(_three_pages())
    census_source, census_published = _publish(pdf)
    _census(census_source, census_published, pages=(1, 2, 3))
    consumer_source, consumer_published = _publish(pdf)
    _direct(consumer_source, consumer_published)
    assert set(census_source._producer._store.verified_resolution_cache) == set(consumer_source._producer._store.verified_resolution_cache)
    assert _shape(census_source) == _shape(consumer_source) and _shape(census_source._producer) == _shape(consumer_source._producer)


def test_positive_control_the_state_check_does_see_a_consumer_filling_the_producers_memos():
    """The equalities above are only meaningful if an ordinary consumer call WOULD change that state."""
    import fitz

    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    for y in (100.0, 105.52):
        page.draw_line((50, y), (150, y), color=(0, 0, 0), width=0.48)
        page.draw_line((170, y), (270, y), color=(0, 0, 0), width=0.48)
    page.draw_line((150, 100), (150, 105.52), color=(0, 0, 0), width=0.48)       # two jambs make a gap candidate
    page.draw_line((170, 100), (170, 105.52), color=(0, 0, 0), width=0.48)
    page.insert_text((20, 250), "Hello", fontsize=10, fontname="helv")
    source, published = _publish(doc.tobytes())
    assert published.visible_observation_ids and published.text_observation_ids
    _census(source, published)
    before = _shape(source)
    authority = source.physical_opening_authority()
    for oid in published.visible_observation_ids:
        authority.prove_existence(_selector(published, oid))
    assert _shape(source) != before


def test_a_second_census_is_identical_to_the_first_so_nothing_was_learned_or_cached_between_calls():
    source, published = _publish(_pdf(_three_pages()))
    shadow = C.NativeTextResidualCensusShadow(source, enabled=True)
    first = shadow.census(revision_id=published.revision.revision_id, page_ids=(1, 2, 3))
    state = _all_state(source)
    again = shadow.census(revision_id=published.revision.revision_id, page_ids=(3, 2, 1))
    assert first == again and _all_state(source) == state


# --- defects found in review: each test below fails on the earlier implementation ----------------------------


# the words of the repository's own glyph-unverified elevation fixture, set the same way (F1 = Arial with a
# ToUnicode map and no font program), so the census is checked against the construction the repo already pins
ELEVATION = (("F1", "WINDOW", 25, 180, 10), ("F1", "ELEVATIONS", 90, 180, 10), ("F1", "W1", 145, 90, 9),
             ("F1", "3000", 140, 150, 8), ("F1", "2400", 65, 88, 7), ("F1", "NOT", 220, 180, 6),
             ("F1", "REQUIRED", 245, 180, 6))


@pytest.mark.parametrize("clip,expected", [(False, (GLYPH,)), (True, (CLIP, GLYPH))])
def test_the_repositorys_glyph_unverified_elevation_construction_gives_exactly_its_known_reasons(clip, expected):
    source, published = _publish(_pdf([ELEVATION], clip=clip))
    page = _census(source, published).pages[0]
    assert (page.total_count, page.trusted_count, page.untrusted_count) == (7, 0, 7)
    assert page.reason_set_histogram == ((expected, 7),)
    assert all(w.reason_set == expected for w in page.untrusted_words)
    assert page.untrusted_matching_opening_tag_syntax == 1                       # W1 only; 3000 and 2400 are dimensions
    assert sorted(w.text_length for w in page.untrusted_words) == [2, 3, 4, 4, 6, 8, 10]
    assert page.clip_state_histogram == (((C.CLIP_STATE_UNRESOLVED if clip else C.NO_CLIP_REASON), 7),)


@pytest.mark.parametrize("field", ["document_id", "revision_id", "source_sha256"])
def test_a_receipt_of_another_document_revision_or_source_is_never_censused_as_this_pages_word(field):
    source, published = _publish(_pdf(_three_pages()))
    key = (published.snapshot.snapshot_id, sorted(published.text_observation_ids)[0])
    source._text_integrity_receipts[key] = replace(source._text_integrity_receipts[key], **{field: "foreign-" + field})
    got = _census(source, published, pages=(1, 3))
    foreign_page = next(p for p in got.pages if p.reason_codes == (C.CENSUS_FOREIGN_RECORD,))
    assert foreign_page.status is ABST and foreign_page.total_count == 0 and foreign_page.untrusted_words == ()
    assert got.status is ABST and got.reason_codes == (C.CENSUS_PAGE_INCOMPLETE,)


@pytest.mark.parametrize("tamper", [
    dict(raw_text=b"bytes"), dict(raw_text=None), dict(font_xref="5"), dict(font_xref=True), dict(sequence_number=1.5),
    dict(geometry=(0.0, 0.0, "x", 1.0)), dict(geometry=(0.0, 0.0, float("inf"), 1.0))])
def test_a_receipt_with_malformed_fields_abstains_the_page_instead_of_raising(tamper):
    source, published = _publish(_pdf([MIXED[0]]))
    key = (published.snapshot.snapshot_id, sorted(published.text_observation_ids)[0])
    source._text_integrity_receipts[key] = replace(source._text_integrity_receipts[key], **tamper)
    got = _census(source, published)
    # an untrusted receipt whose text is not a str would also make the authority itself disagree; either way the
    # page is reported typed, never censused with a guessed length or a coerced box
    page = got.pages[0]
    assert page.status is ABST and page.reason_codes == (C.CENSUS_WORD_UNPLACEABLE,)
    assert page.total_count == 0 and page.untrusted_words == ()


def test_which_typed_failure_a_page_reports_does_not_depend_on_the_producers_id_order(monkeypatch):
    from pb_pdf_text_integrity_authority import PdfTextIntegrityAuthority

    source, published = _publish(_pdf([MIXED[0]]))
    ids = sorted(published.text_observation_ids)
    # two different defects: the smaller id has a foreign receipt, the larger one an unplaceable box
    first, last = (published.snapshot.snapshot_id, ids[0]), (published.snapshot.snapshot_id, ids[-1])
    source._text_integrity_receipts[first] = replace(source._text_integrity_receipts[first], document_id="foreign")
    source._text_integrity_receipts[last] = replace(source._text_integrity_receipts[last], geometry=(0.0, 0.0, 1.0))
    forward = _census(source, published).pages[0]
    original = PdfTextIntegrityAuthority.observation_ids_with_receipt_page
    monkeypatch.setattr(PdfTextIntegrityAuthority, "observation_ids_with_receipt_page",
                        lambda self, snapshot_id, observation_ids, page_id: tuple(reversed(original(
                            self, snapshot_id, observation_ids, page_id))))
    backward = _census(source, published).pages[0]
    assert forward.reason_codes == backward.reason_codes == (C.CENSUS_FOREIGN_RECORD,)
    assert forward == backward


def test_a_page_with_only_trusted_words_still_reports_its_own_font_list():
    source, published = _publish(_pdf([TRUSTED_WORDS]))
    page = _census(source, published).pages[0]
    assert page.untrusted_count == 0
    assert [(f.base_font, f.program) for f in page.page_fonts] == [
        ("Arial", "not_embedded"), ("Helvetica", "not_embedded"), ("Verdana", "not_embedded")]


_TYPE3 = {"T3": (53, "<< /Type /Font /Subtype /Type3 /FontBBox [0 0 600 700] /FontMatrix [0.001 0 0 0.001 0 0] "
                     "/CharProcs << /q 70 0 R /x 71 0 R >> /Encoding << /Type /Encoding /Differences [113 /q 120 /x] >> "
                     "/FirstChar 113 /LastChar 120 /Widths [600 0 0 0 0 0 0 600] /Resources << >> >>")}
_TYPE3_PROCS = {70: _stream_obj("600 0 0 0 600 700 d1\n0 0 600 700 re f"),
                71: _stream_obj("600 0 0 0 600 700 d1\n0 0 600 700 re f")}


def test_a_type3_font_is_listed_as_glyph_procedures_and_its_word_is_still_counted_untrusted():
    pdf = _pdf([(("T3", "qxqx", 20, 100, 20), ("F2", "Hello", 20, 150, 10))], extra_fonts=_TYPE3, extra_objects=_TYPE3_PROCS)
    source, published = _publish(pdf)
    page = _census(source, published).pages[0]
    entry = next(f for f in page.page_fonts if f.subtype == "Type3")
    assert entry.program == C.PROGRAM_TYPE3_GLYPH_PROCEDURES and entry.font_class.startswith("Type3/type3_glyph_procedures/")
    direct = _direct(source, published)
    untrusted = {oid: r for oid, r in direct.items()
                 if not (r.status is EvidenceResolutionStatus.CORROBORATED and r.proposition == "trusted_pdf_text")}
    assert untrusted and {w.observation_id for w in page.untrusted_words} == set(untrusted)
    assert all(w.reason_codes == tuple(untrusted[w.observation_id].reason_codes) for w in page.untrusted_words)
    assert all(w.text_length == 4 for w in page.untrusted_words)


def test_the_census_reads_a_pages_fonts_only_through_the_immutable_source_bytes(monkeypatch):
    """Tampering with the producer's bytes after publication is caught by the SHA check, never silently read."""
    source, published = _publish(_pdf([MIXED[0]]))
    store = source._producer._store
    original = store.source_bytes_by_revision[published.revision.revision_id]
    store.source_bytes_by_revision[published.revision.revision_id] = original.replace(b"Arial", b"Brial")
    try:
        got = _census(source, published)
    finally:
        store.source_bytes_by_revision[published.revision.revision_id] = original
    assert got.reason_codes == (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,) and got.pages == ()


@pytest.mark.parametrize("rotate", [0, 90, 270])
def test_a_page_with_a_crop_box_is_joined_in_the_same_frame_the_producers_receipts_use(rotate):
    source, published = _publish(_pdf(MIXED, rotate=rotate, crop_box="/CropBox [50 40 350 260]"), document_id="crop-doc")
    page = _census(source, published).pages[0]
    assert page.status is CAND and page.untrusted_count >= 1
    # every word is placed by the same extraction that produced the receipt, so no word silently takes a span
    # of a shifted frame: each is either joined to a span whose font the receipt itself confirms, or unresolved
    assert all(w.font.join_status == C.SPAN_FONT_RESOLVED and w.font.font_sources_agree is True for w in page.untrusted_words)


def test_the_census_is_identical_under_different_hash_seeds():
    """Python's string hash seed must not reach any id, order or histogram."""
    import subprocess
    import sys
    from pathlib import Path

    here = Path(__file__).resolve().parent
    code = ";".join([
        "import sys; sys.path[:0] = [%r, %r]" % (str(here), str(here.parent)),
        "import test_native_text_residual_census_shadow_producer as T",
        "source, published = T._publish(T._pdf(T._three_pages()), document_id='seed-doc')",
        "got = T._census(source, published, pages=(1, 2, 3))",
        "print(got.record_id, [p.record_id for p in got.pages], [w.record_id for p in got.pages for w in p.untrusted_words])",
    ])
    outputs = set()
    for seed in ("0", "1", "271828"):
        done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=900,
                              env={**__import__("os").environ, "PYTHONHASHSEED": seed})
        assert done.returncode == 0, done.stderr
        outputs.add(done.stdout.strip().splitlines()[-1])
    assert len(outputs) == 1
