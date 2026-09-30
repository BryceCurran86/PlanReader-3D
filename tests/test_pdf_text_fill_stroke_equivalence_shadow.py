from __future__ import annotations

import ast
from copy import deepcopy
from pathlib import Path
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_fill_stroke_equivalence_shadow import (
    FILL_STROKE_SHADOW_NOT_APPLICABLE,
    FILL_STROKE_SHADOW_PAIR_CONFLICT,
    FILL_STROKE_SHADOW_RESOLVED,
    FILL_STROKE_SHADOW_VISIBILITY_BLOCKED,
    PDF_TEXT_FILL_STROKE_EQUIVALENT,
    classify_fill_stroke_text_pair_shadow,
    resolve_fill_stroke_text_pair_shadow,
)
from pb_pdf_text_integrity_authority import TEXT_TRACE_AMBIGUOUS
from pb_source_observation_authority import (
    ObservationSelector,
    SOURCE_HASH_MISMATCH,
)
from pb_source_visibility_authority import SourceVisibilityProducer


class _FakePage:
    def __init__(self, spans, bboxlog):
        self._spans = list(spans)
        self._bboxlog = list(bboxlog)

    def get_texttrace(self):
        return list(self._spans)

    def get_bboxlog(self):
        return list(self._bboxlog)


def _chars(text: str, *, glyph_delta: int = 0):
    chars = []
    x = 10.0
    for index, char in enumerate(text):
        left = x + index * 5.0
        chars.append(
            (
                ord(char),
                ord(char) + glyph_delta,
                (left, 20.0),
                (left, 20.0, left + 4.0, 30.0),
            )
        )
    return tuple(chars)


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


def _pair_page(**overrides):
    fill = _span()
    stroke = _span(seqno=11, render_mode=1)
    for key, value in overrides.items():
        target, field = key.split("__", 1)
        if target == "fill":
            fill[field] = value
        elif target == "stroke":
            stroke[field] = value
        else:
            raise AssertionError(target)
    return _FakePage(
        (fill, stroke),
        [
            ("ignore", (0.0, 0.0, 0.0, 0.0))
            for _ in range(10)
        ]
        + [
            ("fill-text", (10.0, 20.0, 30.0, 30.0)),
            ("stroke-text", (10.0, 20.0, 30.0, 30.0)),
        ],
    )


def _visible(monkeypatch):
    import pb_pdf_text_fill_stroke_equivalence_shadow as shadow

    monkeypatch.setattr(
        shadow,
        "_visibility_status",
        lambda _page, _bbox, span: (
            "proven_visible",
            (),
            int(span["seqno"]),
        ),
    )


def test_exact_fill_stroke_pair_resolves_without_text_authority_promotion(
    monkeypatch,
):
    _visible(monkeypatch)
    page = _pair_page()
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}
    before = deepcopy(word)

    result = classify_fill_stroke_text_pair_shadow(page, word)

    assert result.equivalent
    assert result.reason_codes == (FILL_STROKE_SHADOW_RESOLVED,)
    assert result.sequence_numbers == (10, 11)
    assert result.render_modes == (0, 1)
    assert result.bboxlog_kinds == ("fill-text", "stroke-text")
    assert result.font_name == "Helvetica"
    assert result.opacity == 1.0
    assert word == before


def test_input_order_does_not_change_exact_pair(monkeypatch):
    _visible(monkeypatch)
    base = _pair_page()
    reversed_page = _FakePage(
        tuple(reversed(base._spans)),
        base._bboxlog,
    )
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}

    first = classify_fill_stroke_text_pair_shadow(base, word)
    second = classify_fill_stroke_text_pair_shadow(reversed_page, word)

    assert first == second
    assert first.equivalent


def test_fill_fill_and_stroke_stroke_stay_conflicted(monkeypatch):
    _visible(monkeypatch)
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}

    fill_fill = _pair_page(stroke__type=0)
    stroke_stroke = _pair_page(fill__type=1)

    assert not classify_fill_stroke_text_pair_shadow(
        fill_fill,
        word,
    ).equivalent
    assert not classify_fill_stroke_text_pair_shadow(
        stroke_stroke,
        word,
    ).equivalent


def test_nonconsecutive_pair_stays_conflicted(monkeypatch):
    _visible(monkeypatch)
    page = _pair_page(stroke__seqno=12)
    page._bboxlog.append(("stroke-text", (10.0, 20.0, 30.0, 30.0)))
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}

    result = classify_fill_stroke_text_pair_shadow(page, word)

    assert not result.equivalent
    assert result.reason_codes == (FILL_STROKE_SHADOW_PAIR_CONFLICT,)


def test_font_glyph_text_bbox_opacity_and_layer_mismatches_fail_closed(
    monkeypatch,
):
    _visible(monkeypatch)
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}
    cases = (
        _pair_page(stroke__font="Times-Roman"),
        _pair_page(
            stroke__chars=_chars("PAIR", glyph_delta=1),
        ),
        _pair_page(
            stroke__chars=_chars("PAXR"),
        ),
        _pair_page(
            stroke__bbox=(10.0, 20.0, 30.01, 30.0),
        ),
        _pair_page(stroke__opacity=0.99),
        _pair_page(stroke__layer="Other Layer"),
    )

    for page in cases:
        result = classify_fill_stroke_text_pair_shadow(page, word)
        assert not result.equivalent
        assert result.reason_codes in (
            (FILL_STROKE_SHADOW_PAIR_CONFLICT,),
            (FILL_STROKE_SHADOW_NOT_APPLICABLE,),
        )


def test_three_competing_traces_remain_ambiguous(monkeypatch):
    _visible(monkeypatch)
    base = _pair_page()
    third = _span(seqno=12, render_mode=0)
    page = _FakePage(
        (*base._spans, third),
        (
            *base._bboxlog,
            ("fill-text", (10.0, 20.0, 30.0, 30.0)),
        ),
    )
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}

    result = classify_fill_stroke_text_pair_shadow(page, word)

    assert not result.equivalent
    assert result.reason_codes == (FILL_STROKE_SHADOW_NOT_APPLICABLE,)


def test_visibility_failure_on_either_trace_blocks_pair(monkeypatch):
    import pb_pdf_text_fill_stroke_equivalence_shadow as shadow

    def visibility(_page, _bbox, span):
        if int(span["type"]) == 1:
            return (
                "unresolved_or_blocked",
                ("text_clip_state_unresolved",),
                int(span["seqno"]),
            )
        return "proven_visible", (), int(span["seqno"])

    monkeypatch.setattr(shadow, "_visibility_status", visibility)
    page = _pair_page()
    word = {"text": "PAIR", "bbox": (10.0, 20.0, 30.0, 30.0)}

    result = classify_fill_stroke_text_pair_shadow(page, word)

    assert not result.equivalent
    assert FILL_STROKE_SHADOW_VISIBILITY_BLOCKED in result.reason_codes
    assert "text_clip_state_unresolved" in result.reason_codes


def _pdf_bytes(objects: Mapping[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    position = len(header)
    for number in sorted(objects):
        offsets[number] = position
        body = objects[number].encode("latin1")
        chunk = (
            f"{number} 0 obj\n".encode("ascii")
            + body
            + b"\nendobj\n"
        )
        chunks.append(chunk)
        position += len(chunk)

    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        if number in offsets:
            xref.append(f"{offsets[number]:010d} 00000 n \n")
        else:
            xref.append("0000000000 00000 f \n")
    trailer = (
        f"trailer\n<< /Size {size} /Root 1 0 R >>\n"
        f"startxref\n{position}\n%%EOF\n"
    )
    return (
        b"".join(chunks)
        + "".join(xref).encode("ascii")
        + trailer.encode("ascii")
    )


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
                "/Resources << /Font << /F1 5 0 R >> >> "
                "/Contents 4 0 R >>"
            ),
            4: (
                f"<< /Length {len(stream.encode('latin1'))} >>\n"
                f"stream\n{stream}\nendstream"
            ),
            5: (
                "<< /Type /Font /Subtype /Type1 "
                "/BaseFont /Helvetica >>"
            ),
        }
    )


def _ingest_pair_pdf():
    payload = _fill_stroke_pdf()
    producer = SourceVisibilityProducer(
        producer_method="fill-stroke-shadow-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="fill-stroke-shadow",
        source_bytes=payload,
        source_locator="memory://fill-stroke-shadow.pdf",
    )
    return payload, producer, published


def _selectors(published):
    return [
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in published.text_observation_ids
    ]


def test_live_authority_stays_ambiguous_while_shadow_can_resolve_pair():
    payload, producer, published = _ingest_pair_pdf()
    authority = producer.text_integrity_authority()
    selectors = _selectors(published)
    assert selectors

    live_results = [authority.resolve_text(selector) for selector in selectors]
    ambiguous = [
        (selector, result)
        for selector, result in zip(selectors, live_results)
        if TEXT_TRACE_AMBIGUOUS in result.reason_codes
    ]
    assert ambiguous

    selector, live = ambiguous[0]
    assert live.status is not EvidenceResolutionStatus.CORROBORATED
    assert live.trusted_text is None

    shadow = resolve_fill_stroke_text_pair_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload,
    )
    assert shadow.status is EvidenceResolutionStatus.CORROBORATED
    assert shadow.proposition == PDF_TEXT_FILL_STROKE_EQUIVALENT
    assert shadow.pair_id
    assert shadow.raw_text == "PAIR"
    assert shadow.sequence_numbers[1] == shadow.sequence_numbers[0] + 1
    assert set(shadow.render_modes) == {0, 1}
    assert set(shadow.bboxlog_kinds) == {"fill-text", "stroke-text"}
    assert TEXT_TRACE_AMBIGUOUS in shadow.live_text_reason_codes

    live_again = authority.resolve_text(selector)
    assert live_again == live
    assert live_again.trusted_text is None


def test_shadow_pair_id_is_deterministic_and_lineage_bound():
    payload, producer, published = _ingest_pair_pdf()
    selector = next(
        selector
        for selector in _selectors(published)
        if TEXT_TRACE_AMBIGUOUS
        in producer.text_integrity_authority()
        .resolve_text(selector)
        .reason_codes
    )

    first = resolve_fill_stroke_text_pair_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload,
    )
    second = resolve_fill_stroke_text_pair_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload,
    )

    assert first == second
    assert first.pair_id


def test_source_hash_mismatch_fails_closed():
    payload, producer, published = _ingest_pair_pdf()
    selector = _selectors(published)[0]

    result = resolve_fill_stroke_text_pair_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload + b"tampered",
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proposition is None
    assert result.pair_id is None
    assert result.reason_codes == (SOURCE_HASH_MISMATCH,)


def test_shadow_module_is_not_imported_by_live_text_or_structural_paths():
    paths = (
        Path("pb_pdf_text_integrity_authority.py"),
        Path("pb_source_visibility_authority.py"),
        Path("pb_structural_member_definition_source_shadow.py"),
        Path("pb_structural_member_registration_producer.py"),
        Path("pb_planreader_pdf_extractor.py"),
    )
    for path in paths:
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert (
            "pb_pdf_text_fill_stroke_equivalence_shadow"
            not in imports
        )


def test_shadow_module_has_no_benchmark_or_commercial_dependencies():
    tree = ast.parse(
        Path(
            "pb_pdf_text_fill_stroke_equivalence_shadow.py"
        ).read_text()
    )
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")

    forbidden = ("benchmark", "gold", "jobhub", "takeoff")
    assert not any(
        any(token in name.lower() for token in forbidden)
        for name in imports
    )
