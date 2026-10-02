from __future__ import annotations

from copy import deepcopy

import pytest

import pb_pdf_text_integrity_authority as authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_TOUNICODE_OR_KNOWN_ENCODING_REQUIRED,
    TEXT_TRACE_AMBIGUOUS,
    _exact_fill_stroke_overprint_pair,
    classify_native_word_integrity,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


class _FakePage:
    def __init__(self, spans, bboxlog):
        self._spans = list(spans)
        self._bboxlog = list(bboxlog)
        self.bboxlog_calls = 0

    def get_texttrace(self):
        return list(self._spans)

    def get_bboxlog(self):
        self.bboxlog_calls += 1
        return list(self._bboxlog)


def _chars(text: str, *, glyph_delta: int = 0):
    out = []
    for index, char in enumerate(text):
        left = 10.0 + index * 5.0
        out.append(
            (
                ord(char),
                ord(char) + glyph_delta,
                (left, 20.0),
                (left, 20.0, left + 4.0, 30.0),
            )
        )
    return tuple(out)


def _span(
    *,
    text="PAIR",
    seqno=10,
    render_mode=0,
    font="Helvetica",
    bbox=(10.0, 20.0, 30.0, 30.0),
    opacity=1.0,
    layer="",
    glyph_delta=0,
):
    return {
        "chars": _chars(text, glyph_delta=glyph_delta),
        "seqno": seqno,
        "type": render_mode,
        "font": font,
        "bbox": bbox,
        "opacity": opacity,
        "layer": layer,
    }


def _page(**overrides):
    fill = _span()
    stroke = _span(seqno=11, render_mode=1)
    for key, value in overrides.items():
        target, field = key.split("__", 1)
        (fill if target == "fill" else stroke)[field] = value
    bboxlog = [
        ("ignore", (0.0, 0.0, 0.0, 0.0))
        for _ in range(max(int(fill["seqno"]), int(stroke["seqno"])) + 1)
    ]
    bboxlog[int(fill["seqno"])] = ("fill-text", fill["bbox"])
    bboxlog[int(stroke["seqno"])] = ("stroke-text", stroke["bbox"])
    return _FakePage((fill, stroke), bboxlog)


_WORD = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}


def test_exact_pair_reuses_cached_bboxlog_without_replaying_page_render():
    page = _page()

    first = _exact_fill_stroke_overprint_pair(page, _WORD, tuple(page._spans))
    second = _exact_fill_stroke_overprint_pair(page, _WORD, tuple(page._spans))

    assert first is not None
    assert second is not None
    assert page.bboxlog_calls == 1


def test_exact_pair_identity_proof_is_deterministic_and_non_mutating():
    page = _page()
    before = deepcopy(_WORD)

    first = _exact_fill_stroke_overprint_pair(page, _WORD, tuple(page._spans))
    second = _exact_fill_stroke_overprint_pair(
        _FakePage(tuple(reversed(page._spans)), page._bboxlog),
        _WORD,
        tuple(reversed(page._spans)),
    )

    assert first is not None
    assert second is not None
    assert tuple(int(s["seqno"]) for s in first) == (10, 11)
    assert tuple(int(s["seqno"]) for s in second) == (10, 11)
    assert _WORD == before


@pytest.mark.parametrize(
    "page",
    [
        _page(stroke__type=0),
        _page(fill__type=1),
        _page(stroke__seqno=12),
        _page(stroke__font="Times-Roman"),
        _page(stroke__chars=_chars("PAIR", glyph_delta=1)),
        _page(stroke__chars=_chars("PAXR")),
        _page(stroke__bbox=(10.0, 20.0, 30.01, 30.0)),
        _page(stroke__opacity=0.99),
        _page(stroke__layer="Other Layer"),
    ],
)
def test_nonidentical_or_noncomplementary_pairs_never_remove_ambiguity(page):
    assert _exact_fill_stroke_overprint_pair(
        page,
        _WORD,
        tuple(page._spans),
    ) is None


def test_third_competing_trace_never_removes_ambiguity():
    base = _page()
    third = _span(seqno=12, render_mode=0)
    assert _exact_fill_stroke_overprint_pair(
        base,
        _WORD,
        (*base._spans, third),
    ) is None


def test_exact_pair_still_requires_both_spans_to_pass_visibility(monkeypatch):
    page = _page()

    monkeypatch.setattr(
        authority,
        "_decode_status",
        lambda _page, _span, _text: (
            "validated",
            (),
            5,
            "Type1",
            "Helvetica",
        ),
    )

    def visibility(_page, _subject, span, **_kwargs):
        if int(span["type"]) == 1:
            return (
                "unresolved_or_blocked",
                (TEXT_CLIP_STATE_UNRESOLVED,),
                int(span["seqno"]),
            )
        return "proven_visible", (), int(span["seqno"])

    monkeypatch.setattr(authority, "_visibility_status", visibility)
    decision = classify_native_word_integrity(page, _WORD)

    assert not decision.trusted
    assert TEXT_CLIP_STATE_UNRESOLVED in decision.reason_codes
    assert TEXT_TRACE_AMBIGUOUS not in decision.reason_codes
    assert decision.trace_sequence_numbers == (10, 11)


def test_exact_pair_still_requires_both_spans_to_pass_decode(monkeypatch):
    page = _page()

    def decode(_page, span, _text):
        if int(span["type"]) == 1:
            return (
                "unresolved_encoding",
                (TEXT_TOUNICODE_OR_KNOWN_ENCODING_REQUIRED,),
                5,
                "TrueType",
                "Unknown",
            )
        return "validated", (), 5, "Type1", "Helvetica"

    monkeypatch.setattr(authority, "_decode_status", decode)
    monkeypatch.setattr(
        authority,
        "_visibility_status",
        lambda _page, _subject, span, **_kwargs: (
            "proven_visible",
            (),
            int(span["seqno"]),
        ),
    )

    decision = classify_native_word_integrity(page, _WORD)
    assert not decision.trusted
    assert TEXT_TOUNICODE_OR_KNOWN_ENCODING_REQUIRED in decision.reason_codes
    assert TEXT_TRACE_AMBIGUOUS not in decision.reason_codes


def _pdf_bytes(objects):
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets = {}
    pos = len(header)
    for number in sorted(objects):
        offsets[number] = pos
        body = objects[number].encode("latin1")
        chunk = f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"
        chunks.append(chunk)
        pos += len(chunk)
    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        xref.append(
            f"{offsets[number]:010d} 00000 n \n"
            if number in offsets
            else "0000000000 00000 f \n"
        )
    trailer = (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{pos}\n%%EOF\n"
    )
    return b"".join(chunks) + "".join(xref).encode("ascii") + trailer.encode("ascii")


def _fill_stroke_pdf() -> bytes:
    stream = (
        "0 g 0 G "
        "BT /F1 12 Tf 0 Tr 40 120 Td (PAIR) Tj ET "
        "BT /F1 12 Tf 1 Tr 40 120 Td (PAIR) Tj ET"
    )
    return _pdf_bytes(
        {
            1: "<< /Type /Catalog /Pages 2 0 R >>",
            2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            3: (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] "
                "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>"
            ),
            4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
            5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        }
    )


def test_exact_pair_promotes_only_through_producer_owned_native_lineage():
    payload = _fill_stroke_pdf()
    producer = SourceVisibilityProducer(
        producer_method="live-fill-stroke-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="live-fill-stroke",
        source_bytes=payload,
        source_locator="memory://live-fill-stroke.pdf",
    )
    authority_obj = producer.text_integrity_authority()

    results = []
    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        results.append(authority_obj.resolve_text(selector))

    trusted = [r for r in results if r.trusted_text == "PAIR"]
    assert trusted
    assert trusted[0].status is EvidenceResolutionStatus.CORROBORATED
    assert trusted[0].receipt.trace_sequence_numbers
    assert len(trusted[0].receipt.trace_sequence_numbers) == 2
    assert TEXT_TRACE_AMBIGUOUS not in trusted[0].reason_codes
