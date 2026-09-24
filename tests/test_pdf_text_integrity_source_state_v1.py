"""Adversarial synthetic tests for source-state proofs in PdfTextIntegrityAuthority.

Covers the four upstream blockers that kept real native CAD text from being
trusted, plus the boundaries that must NOT relax:

1. word <-> texttrace ownership when a word is split across whole trace spans
2. ToUnicode CMaps using the standard ``N dict dup begin`` idiom
3. optional-content (OCG) visibility proven against the default configuration
4. per-text clip ownership instead of a page-global clip veto
5. independent glyph verification stays independent of ToUnicode parsing

Every PDF here is synthetic and hand-built; no benchmark source, gold value or
project identity is used.
"""
from __future__ import annotations

from typing import Mapping, Optional

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_CLIPPED_BY_CLIP_REGION,
    TEXT_GLYPH_UNICODE_MISMATCH,
    TEXT_OPTIONAL_CONTENT_OFF,
    TEXT_OPTIONAL_CONTENT_UNRESOLVED,
    TEXT_TOUNICODE_MALFORMED,
    TEXT_TRACE_AMBIGUOUS,
    TEXT_TRACE_UNAVAILABLE,
    _optional_content_reasons,
    _valid_tounicode_cmap,
    classify_native_word_integrity,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


# ---------------------------------------------------------------------------
# Minimal raw-PDF builder (keeps object syntax fully under test control)
# ---------------------------------------------------------------------------

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


_HELV = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"


def _pdf(
    stream: str,
    *,
    fonts: Optional[Mapping[str, tuple[int, str]]] = None,
    extra: Optional[Mapping[int, str]] = None,
    resources_extra: str = "",
    catalog_extra: str = "",
    rotate: int = 0,
) -> bytes:
    fonts = fonts or {"F1": (5, _HELV)}
    font_res = " ".join(f"/{name} {num} 0 R" for name, (num, _obj) in fonts.items())
    objects: dict[int, str] = {
        1: f"<< /Type /Catalog /Pages 2 0 R {catalog_extra} >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Rotate {rotate} "
            f"/Resources << /Font << {font_res} >> {resources_extra} >> /Contents 4 0 R >>"
        ),
        4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
    }
    for _name, (num, obj) in fonts.items():
        objects[num] = obj
    if extra:
        objects.update(extra)
    return _pdf_bytes(objects)


def _stream_obj(body: str) -> str:
    return f"<< /Length {len(body.encode('latin1'))} >>\nstream\n{body}\nendstream"


def _classify(pdf: bytes, *, index: int = 0):
    doc = fitz.open(stream=pdf, filetype="pdf")
    page = doc[0]
    words = page.get_text("words")
    assert words, "fixture produced no native words"
    w = words[index]
    return classify_native_word_integrity(page, {"text": w[4], "bbox": tuple(w[:4])})


def _supplied_word_decision(pdf: bytes, reference_pdf: bytes):
    """Classify a caller-supplied word whose geometry comes from a reference render.

    MuPDF already omits hidden-layer and fully clipped text from word
    extraction; this proves the authority itself also refuses such a word if a
    caller supplies one.
    """
    ref = fitz.open(stream=reference_pdf, filetype="pdf")[0].get_text("words")[0]
    page = fitz.open(stream=pdf, filetype="pdf")[0]
    return classify_native_word_integrity(page, {"text": ref[4], "bbox": tuple(ref[:4])})


def _word_texts(pdf: bytes) -> list[str]:
    return [w[4] for w in fitz.open(stream=pdf, filetype="pdf")[0].get_text("words")]


# ---------------------------------------------------------------------------
# 1. Split-span ownership
# ---------------------------------------------------------------------------

_SPLIT = "BT /F1 12 Tf 40 120 Td (Note) Tj ET BT /F1 12 Tf 65.344 120 Td (:) Tj ET"


def test_word_split_across_consecutive_whole_spans_is_owned_and_trusted() -> None:
    pdf = _pdf(_SPLIT)
    assert _word_texts(pdf) == ["Note:"]
    decision = _classify(pdf)
    assert decision.trusted, decision.reason_codes
    assert len(decision.trace_sequence_numbers) == 2
    assert decision.trace_sequence_numbers[1] == decision.trace_sequence_numbers[0] + 1


def test_split_word_is_not_owned_when_foreign_paint_separates_its_spans() -> None:
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (Note) Tj ET 0 0 1 rg 200 10 5 5 re f 0 g "
        "BT /F1 12 Tf 65.344 120 Td (:) Tj ET"
    )
    decision = _classify(pdf, index=[t for t in _word_texts(pdf)].index("Note:"))
    assert not decision.trusted
    assert TEXT_TRACE_UNAVAILABLE in decision.reason_codes


def test_two_equally_valid_span_chains_for_one_word_are_ambiguous_not_ranked() -> None:
    pdf = _pdf(_SPLIT + " " + _SPLIT)
    idx = _word_texts(pdf).index("Note:")
    decision = _classify(pdf, index=idx)
    assert not decision.trusted
    assert TEXT_TRACE_AMBIGUOUS in decision.reason_codes


def test_split_word_is_blocked_when_any_owned_span_fails_its_own_checks() -> None:
    bad_cmap = "begincmap /CMapType 2 def GARBAGE endcmap"
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (Note) Tj ET BT /F2 12 Tf 65.344 120 Td (:) Tj ET",
        fonts={
            "F1": (5, _HELV),
            "F2": (6, "<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /ToUnicode 7 0 R >>"),
        },
        extra={7: _stream_obj(bad_cmap)},
    )
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_TOUNICODE_MALFORMED in decision.reason_codes


def test_word_that_begins_mid_span_is_owned_by_a_contiguous_character_run() -> None:
    # "200" in one text operation, "mm thick" in the next: the word "200mm"
    # ends part-way through the second span.
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (200) Tj ET BT /F1 12 Tf 60.016 120 Td (mm thick) Tj ET"
    )
    words = _word_texts(pdf)
    assert "200mm" in words
    decision = _classify(pdf, index=words.index("200mm"))
    assert decision.trusted, decision.reason_codes
    assert len(decision.trace_sequence_numbers) == 2


def test_word_that_ends_mid_span_is_owned_by_a_contiguous_character_run() -> None:
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (see r) Tj ET BT /F1 12 Tf 65.348 120 Td (.) Tj ET "
        "BT /F1 12 Tf 68.68 120 Td (c) Tj ET"
    )
    words = _word_texts(pdf)
    target = [w for w in words if w.startswith("r.")]
    assert target, words
    assert _classify(pdf, index=words.index(target[0])).trusted


def test_overprinted_foreign_character_inside_the_word_box_is_a_blend_not_owned() -> None:
    pdf = _pdf(_SPLIT + " BT /F1 12 Tf 47 120 Td (X) Tj ET")
    words = _word_texts(pdf)
    for index, text in enumerate(words):
        decision = _classify(pdf, index=index)
        if "Note" in text or ":" in text:
            assert not decision.trusted, (text, decision.reason_codes)


def test_split_word_ownership_is_translation_invariant() -> None:
    shifted = _pdf(
        "BT /F1 12 Tf 90 60 Td (Note) Tj ET BT /F1 12 Tf 115.344 60 Td (:) Tj ET"
    )
    assert _classify(shifted).trusted


# ---------------------------------------------------------------------------
# 2. ToUnicode CMap with the standard `dict dup begin` idiom
# ---------------------------------------------------------------------------

def _cmap(*, sysinfo: str, mappings: str = "<39> <0039>\n<30> <0030>", count: int = 2) -> str:
    return (
        "/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
        f"{sysinfo}\n/CMapName /Generic def\n/CMapType 2 def\n"
        "1 begincodespacerange\n<00> <FF>\nendcodespacerange\n"
        f"{count} beginbfchar\n{mappings}\nendbfchar\nendcmap\n"
        "CMapName currentdict /CMap defineresource pop\nend\nend"
    )


_SYSINFO_DUP = "/CIDSystemInfo 3 dict dup begin\n/Registry (Adobe) def\n/Ordering (UCS) def\n/Supplement 0 def\nend def"


def _tounicode_pdf(cmap: str, text: str = "900") -> bytes:
    return _pdf(
        f"BT /F1 12 Tf 40 120 Td ({text}) Tj ET",
        fonts={"F1": (5, "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /ToUnicode 6 0 R >>")},
        extra={6: _stream_obj(cmap)},
    )


def test_valid_cmap_with_dict_dup_begin_idiom_validates() -> None:
    assert _valid_tounicode_cmap(_cmap(sysinfo=_SYSINFO_DUP).encode("latin1"))
    decision = _classify(_tounicode_pdf(_cmap(sysinfo=_SYSINFO_DUP)))
    assert decision.decode_status == "validated_tounicode", decision.reason_codes
    assert decision.trusted, decision.reason_codes


@pytest.mark.parametrize(
    "sysinfo",
    [
        # dup outside the exact `<int> dict dup begin` idiom
        "/CIDSystemInfo 3 dict begin dup /Registry (Adobe) def end def",
        # non-numeric operand: not the structural idiom
        "/CIDSystemInfo /Three dict dup begin /Registry (Adobe) def end def",
        # dup with no following begin
        "/CIDSystemInfo 3 dict dup def",
        # unrelated stack operator
        "/CIDSystemInfo 3 dict exch begin /Registry (Adobe) def end def",
    ],
)
def test_dup_or_other_stack_operators_outside_the_idiom_stay_malformed(sysinfo: str) -> None:
    cmap = _cmap(sysinfo=sysinfo)
    assert not _valid_tounicode_cmap(cmap.encode("latin1"))
    decision = _classify(_tounicode_pdf(cmap))
    assert not decision.trusted
    assert TEXT_TOUNICODE_MALFORMED in decision.reason_codes


def test_unknown_cmap_operator_still_abstains_even_alongside_valid_dup() -> None:
    cmap = _cmap(sysinfo=_SYSINFO_DUP).replace("endcmap", "GARBAGE\nendcmap")
    assert not _valid_tounicode_cmap(cmap.encode("latin1"))
    assert TEXT_TOUNICODE_MALFORMED in _classify(_tounicode_pdf(cmap)).reason_codes


def test_cmap_count_mismatch_still_malformed_with_dup_present() -> None:
    cmap = _cmap(sysinfo=_SYSINFO_DUP, count=5)
    assert not _valid_tounicode_cmap(cmap.encode("latin1"))


# ---------------------------------------------------------------------------
# 5. Glyph/Unicode verification stays independent of ToUnicode parsing
# ---------------------------------------------------------------------------

def test_structurally_valid_tounicode_that_lies_about_glyphs_is_blocked() -> None:
    # Code <39> renders the glyph '9' but the CMap claims it is U+0038 ('8').
    lying = _cmap(sysinfo=_SYSINFO_DUP, mappings="<39> <0038>\n<30> <0030>")
    assert _valid_tounicode_cmap(lying.encode("latin1"))  # parser is satisfied ...
    decision = _classify(_tounicode_pdf(lying))
    assert not decision.trusted  # ... the independent glyph check is not
    assert TEXT_GLYPH_UNICODE_MISMATCH in decision.reason_codes
    assert decision.decode_status == "tounicode_glyph_mismatch"


# ---------------------------------------------------------------------------
# 3. Optional content
# ---------------------------------------------------------------------------

_OC_TEXT = "/OC /oc1 BDC BT /F1 12 Tf 40 120 Td (900) Tj ET EMC"
_OCG = "<< /Type /OCG /Name (Layer A) >>"


def _oc_pdf(
    d_config: str,
    *,
    ocgs: str = "[7 0 R]",
    stream: str = _OC_TEXT,
    properties: str = "/Properties << /oc1 7 0 R >>",
    extra: Optional[Mapping[int, str]] = None,
) -> bytes:
    objs = {7: _OCG}
    if extra:
        objs.update(extra)
    return _pdf(
        stream,
        extra=objs,
        resources_extra=properties,
        catalog_extra=f"/OCProperties << /OCGs {ocgs} /D << {d_config} >> >>",
    )


def test_ocg_explicitly_on_in_default_config_is_trusted() -> None:
    decision = _classify(_oc_pdf("/BaseState /ON"))
    assert decision.trusted, decision.reason_codes


def test_ocg_on_via_basestate_off_plus_on_array_is_trusted() -> None:
    decision = _classify(_oc_pdf("/BaseState /OFF /ON [7 0 R]"))
    assert decision.trusted, decision.reason_codes


def test_ocg_explicitly_off_is_never_trusted() -> None:
    off = _oc_pdf("/BaseState /ON /OFF [7 0 R]")
    on = _oc_pdf("/BaseState /ON")
    assert _word_texts(off) == []  # the extractor already omits the hidden layer
    decision = _supplied_word_decision(off, on)
    assert not decision.trusted
    assert TEXT_TRACE_UNAVAILABLE in decision.reason_codes


def test_ocg_off_state_yields_the_specific_off_reason_when_the_layer_is_traced() -> None:
    off = fitz.open(stream=_oc_pdf("/BaseState /ON /OFF [7 0 R]"), filetype="pdf")[0]
    assert _optional_content_reasons(off, {"layer": "Layer A"}) == (TEXT_OPTIONAL_CONTENT_OFF,)
    base_off = fitz.open(stream=_oc_pdf("/BaseState /OFF"), filetype="pdf")[0]
    assert _optional_content_reasons(base_off, {"layer": "Layer A"}) == (TEXT_OPTIONAL_CONTENT_OFF,)
    on = fitz.open(stream=_oc_pdf("/BaseState /OFF /ON [7 0 R]"), filetype="pdf")[0]
    assert _optional_content_reasons(on, {"layer": "Layer A"}) == ()
    assert _optional_content_reasons(on, {"layer": "Not A Registered Layer"}) == (
        TEXT_OPTIONAL_CONTENT_UNRESOLVED,
    )


def test_ocg_not_registered_in_oc_properties_is_unresolved() -> None:
    decision = _classify(_oc_pdf("/BaseState /ON", ocgs="[]"))
    assert not decision.trusted
    assert TEXT_OPTIONAL_CONTENT_UNRESOLVED in decision.reason_codes


def test_auto_state_array_makes_visibility_unresolved() -> None:
    decision = _classify(_oc_pdf("/BaseState /ON /AS [<< /Event /View /OCGs [7 0 R] /Category [/View] >>]"))
    assert not decision.trusted
    assert TEXT_OPTIONAL_CONTENT_UNRESOLVED in decision.reason_codes


def test_membership_dictionary_is_unresolved_not_guessed() -> None:
    pdf = _oc_pdf(
        "/BaseState /ON",
        properties="/Properties << /oc1 8 0 R >>",
        extra={8: "<< /Type /OCMD /OCGs [7 0 R] /P /AllOn >>"},
    )
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_OPTIONAL_CONTENT_UNRESOLVED in decision.reason_codes


def test_unrelated_off_layer_on_the_page_prevents_a_nesting_free_proof() -> None:
    # Text sits in ON layer A; a second layer B referenced by the page is OFF.
    # Ancestry of the text's marked-content stack is not proven here, so the
    # page-wide proof cannot vouch for it. Fail closed, not open.
    pdf = _pdf(
        _OC_TEXT,
        extra={7: _OCG, 8: "<< /Type /OCG /Name (Layer B) >>"},
        resources_extra="/Properties << /oc1 7 0 R /oc2 8 0 R >>",
        catalog_extra="/OCProperties << /OCGs [7 0 R 8 0 R] /D << /BaseState /ON /OFF [8 0 R] >> >>",
    )
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_OPTIONAL_CONTENT_UNRESOLVED in decision.reason_codes


def test_text_outside_any_optional_content_is_not_affected_by_ocg_machinery() -> None:
    pdf = _pdf(
        "BT /F1 12 Tf 40 120 Td (900) Tj ET",
        extra={7: _OCG},
        catalog_extra="/OCProperties << /OCGs [7 0 R] /D << /BaseState /ON /OFF [7 0 R] >> >>",
    )
    assert _classify(pdf).trusted


# ---------------------------------------------------------------------------
# 4. Per-text clip ownership
# ---------------------------------------------------------------------------

_TXT = "BT /F1 12 Tf 40 120 Td (900) Tj ET"
_DOT = "0 0 5 5 re f"


def test_text_wholly_inside_an_exact_rectangular_clip_is_trusted() -> None:
    pdf = _pdf(f"q 20 100 100 40 re W n {_DOT} {_TXT} {_DOT} Q")
    assert _classify(pdf).trusted


def test_unrelated_small_clip_closed_before_text_does_not_poison_it() -> None:
    pdf = _pdf(f"q 200 10 50 20 re W n {_DOT} Q {_DOT} {_TXT} {_DOT}")
    decision = _classify(pdf)
    assert decision.trusted, decision.reason_codes


def test_text_partially_outside_its_active_clip_stays_blocked() -> None:
    # Clip x 30..50 covers only part of the word (x 40..60), same-level paint on both sides.
    pdf = _pdf(f"q 30 100 20 40 re W n {_DOT} {_TXT} {_DOT} Q")
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_CLIPPED_BY_CLIP_REGION in decision.reason_codes


def test_text_wholly_outside_its_active_clip_stays_blocked() -> None:
    clipped = _pdf(f"q 200 10 50 20 re W n {_DOT} {_TXT} {_DOT} Q")
    assert _word_texts(clipped) == []  # the extractor already drops fully clipped text
    decision = _supplied_word_decision(clipped, _pdf(_TXT))
    assert not decision.trusted
    assert TEXT_CLIPPED_BY_CLIP_REGION in decision.reason_codes


def test_clip_between_neighbouring_paints_that_may_apply_and_excludes_text_is_unresolved() -> None:
    # Clip sits between the neighbouring paths; PDF structure alone cannot say
    # whether the text is inside it. May-apply + does-not-contain => not proven.
    pdf = _pdf(f"{_DOT} q 30 100 20 40 re W n {_TXT} Q {_DOT}")
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_CLIP_STATE_UNRESOLVED in decision.reason_codes


def test_clip_between_neighbouring_paints_that_contains_text_cannot_hide_it() -> None:
    pdf = _pdf(f"{_DOT} q 20 100 100 40 re W n {_TXT} Q {_DOT}")
    assert _classify(pdf).trusted


def test_non_rectangular_clip_is_unresolved_even_when_bbox_contains_text() -> None:
    triangle = "q 20 100 m 200 100 l 20 190 l h W n"
    pdf = _pdf(f"{triangle} {_DOT} {_TXT} {_DOT} Q")
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_CLIP_STATE_UNRESOLVED in decision.reason_codes


def test_nested_clips_all_containing_text_are_trusted() -> None:
    pdf = _pdf(f"q 10 90 200 100 re W n q 20 100 100 40 re W n {_DOT} {_TXT} {_DOT} Q Q")
    assert _classify(pdf).trusted


def test_nested_inner_clip_that_excludes_text_blocks_it() -> None:
    pdf = _pdf(f"q 10 90 200 100 re W n q 30 100 20 40 re W n {_DOT} {_TXT} {_DOT} Q Q")
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_CLIPPED_BY_CLIP_REGION in decision.reason_codes


def test_clip_proof_is_translation_and_scale_invariant() -> None:
    a = _pdf(f"q 20 100 100 40 re W n {_DOT} {_TXT} {_DOT} Q")
    b = _pdf(
        "q 20 100 100 40 re W n 0 0 5 5 re f "
        "BT /F1 60 Tf 40 120 Td (900) Tj ET 0 0 5 5 re f Q"
    )
    c = _pdf("q 30 100 20 40 re W n 0 0 5 5 re f BT /F1 24 Tf 40 120 Td (900) Tj ET 0 0 5 5 re f Q")
    assert _classify(a).trusted
    assert TEXT_CLIPPED_BY_CLIP_REGION in _classify(c).reason_codes
    # b: enlarged text no longer fits the same clip -> must be blocked, not trusted
    assert not _classify(b).trusted


def test_rotated_page_with_clips_fails_closed() -> None:
    pdf = _pdf(f"q 20 100 100 40 re W n {_DOT} {_TXT} {_DOT} Q", rotate=90)
    decision = _classify(pdf)
    assert not decision.trusted
    assert TEXT_CLIP_STATE_UNRESOLVED in decision.reason_codes


# ---------------------------------------------------------------------------
# Determinism, non-mutation, and stale lineage
# ---------------------------------------------------------------------------

def test_classification_is_deterministic_and_does_not_mutate_inputs() -> None:
    pdf = _pdf(_SPLIT)
    doc = fitz.open(stream=pdf, filetype="pdf")
    page = doc[0]
    w = page.get_text("words")[0]
    word = {"text": w[4], "bbox": tuple(w[:4])}
    snapshot = dict(word)
    first = classify_native_word_integrity(page, word)
    second = classify_native_word_integrity(page, word)
    assert first == second
    assert word == snapshot


def _ingest(pdf: bytes, document_id: str):
    producer = SourceVisibilityProducer(producer_method="text-source-state-test", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=pdf, source_locator=f"memory://{document_id}.pdf"
    )
    return published, producer.text_integrity_authority()


def _selectors(published, **overrides):
    out = []
    for oid in published.text_observation_ids:
        args = dict(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        args.update(overrides)
        out.append(ObservationSelector(**args))
    return out


def test_split_word_is_trusted_end_to_end_through_the_producer_authority() -> None:
    published, authority = _ingest(_pdf(_SPLIT), "split-e2e")
    results = [authority.resolve_text(s) for s in _selectors(published)]
    assert [r.trusted_text for r in results] == ["Note:"]
    assert results[0].status is EvidenceResolutionStatus.CORROBORATED
    assert len(results[0].receipt.trace_sequence_numbers) == 2


def test_stale_lineage_selector_cannot_reach_a_trusted_split_word_receipt() -> None:
    published, authority = _ingest(_pdf(_SPLIT), "split-stale")
    for selector in _selectors(published, snapshot_id="snapshot-that-does-not-exist"):
        result = authority.resolve_text(selector)
        assert result.status is not EvidenceResolutionStatus.CORROBORATED
        assert result.trusted_text is None
