from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_TRACE_AMBIGUOUS,
)
from pb_pdf_text_source_clip_ownership_shadow import (
    PDF_TEXT_SOURCE_RECTANGULAR_CLIP_CONTAINS_WORD,
    SOURCE_CLIP_SHADOW_NOT_APPLICABLE,
    SOURCE_CLIP_SHADOW_RESOLVED_CONTAINS,
    _bind_operations_to_traces,
    _raw_text_shows,
    resolve_source_content_text_clip_shadow,
)
from pb_source_observation_authority import (
    SOURCE_HASH_MISMATCH,
    ObservationSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf_bytes(objects: Mapping[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks = [header]
    offsets: dict[int, int] = {}
    position = len(header)
    for number in sorted(objects):
        offsets[number] = position
        chunk = (
            f"{number} 0 obj\n".encode("ascii")
            + objects[number].encode("latin1")
            + b"\nendobj\n"
        )
        chunks.append(chunk)
        position += len(chunk)
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
        f"startxref\n{position}\n%%EOF\n"
    )
    return (
        b"".join(chunks)
        + "".join(xref).encode("ascii")
        + trailer.encode("ascii")
    )


def _pdf(stream: str) -> bytes:
    objects = {
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
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    }
    return _pdf_bytes(objects)


def _strict_clip_stream(
    *,
    render_mode: int = 0,
    clip: tuple[float, float, float, float] = (20, 100, 100, 40),
    text: str = "PAIR",
    text_x: float = 40,
    text_y: float = 120,
    clip_op: str = "W*",
) -> str:
    x, y, width, height = clip
    return (
        f"q {x} {y} {width} {height} re {clip_op} n "
        f"BT /F1 12 Tf {render_mode} Tr "
        f"{text_x} {text_y} Td ({text}) Tj ET Q"
    )


def _ingest(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="source-clip-shadow-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    selectors = tuple(
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in published.text_observation_ids
    )
    return producer, published, selectors


def _clip_unresolved_selector(producer, selectors):
    authority = producer.text_integrity_authority()
    for selector in selectors:
        result = authority.resolve_text(selector)
        if TEXT_CLIP_STATE_UNRESOLVED in result.reason_codes:
            return selector, result
    raise AssertionError("fixture produced no clip-unresolved text")


def test_raw_parser_accepts_only_exact_local_rectangular_clip_scope():
    for clip_op in ("W", "W*"):
        shows = _raw_text_shows(
            _strict_clip_stream(clip_op=clip_op).encode("latin1")
        )
        assert shows is not None
        assert len(shows) == 1
        assert shows[0].clip_known
        assert shows[0].active_clip_count == 1
        assert shows[0].clip_rect_pdf == (20.0, 100.0, 120.0, 140.0)
        assert shows[0].render_mode == 0


def test_raw_parser_maps_pdf_render_mode_two_as_one_source_text_show():
    shows = _raw_text_shows(
        _strict_clip_stream(render_mode=2).encode("latin1")
    )
    assert shows is not None
    assert len(shows) == 1
    assert shows[0].render_mode == 2
    assert shows[0].clip_known


def test_strict_scope_rejects_compound_path_extra_paint_nested_or_multiple_shows():
    compound = (
        "q 20 100 100 40 re 30 110 20 10 re W* n "
        "BT /F1 12 Tf 0 Tr 40 120 Td (PAIR) Tj ET Q"
    )
    extra_path = (
        "q 20 100 100 40 re W* n 0 0 5 5 re f "
        "BT /F1 12 Tf 0 Tr 40 120 Td (PAIR) Tj ET Q"
    )
    nested = (
        "q 20 100 100 40 re W* n BT /F1 12 Tf "
        "q 0 Tr 40 120 Td (PAIR) Tj Q ET Q"
    )
    two_shows = (
        "q 20 100 100 40 re W* n "
        "BT /F1 12 Tf 0 Tr 40 120 Td (A) Tj (B) Tj ET Q"
    )

    for stream in (compound, extra_path, nested, two_shows):
        shows = _raw_text_shows(stream.encode("latin1"))
        if shows is None:
            continue
        assert shows
        assert all(not show.clip_known for show in shows)


def test_nonidentity_transform_xobject_and_unbalanced_graphics_state_fail_closed():
    transformed = (
        "2 0 0 2 0 0 cm "
        + _strict_clip_stream()
    ).encode("latin1")
    invoked_form = (
        "q /Fm0 Do Q "
        + _strict_clip_stream()
    ).encode("latin1")
    unbalanced = (
        "q " + _strict_clip_stream()
    ).encode("latin1")

    assert _raw_text_shows(transformed) is None
    assert _raw_text_shows(invoked_form) is None
    assert _raw_text_shows(unbalanced) is None


def test_literal_string_content_cannot_forge_pdf_operators():
    stream = (
        "q 20 100 100 40 re W* n "
        "BT /F1 12 Tf 0 Tr 40 120 Td "
        "(q 1 2 3 4 re W n Q) Tj ET Q"
    )
    shows = _raw_text_shows(stream.encode("latin1"))
    assert shows is not None
    assert len(shows) == 1
    assert shows[0].clip_known


def test_exact_raw_show_binds_to_unique_trace_in_page_order():
    payload = _pdf(_strict_clip_stream(render_mode=0, text="ONE"))
    doc = fitz.open(stream=payload, filetype="pdf")
    page = doc[0]
    bindings = _bind_operations_to_traces(page)
    assert bindings is not None
    assert len(bindings) == 1
    show, group = bindings[0]
    assert show.render_mode == 0
    assert group.render_modes == (0,)
    assert show.clip_known
    doc.close()


def test_raw_render_mode_two_binds_to_logical_fill_stroke_trace_pair():
    payload = _pdf(_strict_clip_stream(render_mode=2, text="PAIR"))
    doc = fitz.open(stream=payload, filetype="pdf")
    page = doc[0]
    bindings = _bind_operations_to_traces(page)
    assert bindings is not None
    assert len(bindings) == 1
    show, group = bindings[0]
    assert show.render_mode == 2
    assert group.render_modes == (0, 1)
    assert len(group.sequence_numbers) == 2
    assert group.sequence_numbers[1] == group.sequence_numbers[0] + 1
    doc.close()


def test_lineage_bound_shadow_proves_containing_source_clip_without_changing_live_authority():
    payload = _pdf(_strict_clip_stream(render_mode=2, text="PAIR"))
    producer, _published, selectors = _ingest(
        payload,
        document_id="source-clip-pair",
    )
    selector, live_before = _clip_unresolved_selector(producer, selectors)
    assert TEXT_TRACE_AMBIGUOUS in live_before.reason_codes

    first = resolve_source_content_text_clip_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload,
    )
    second = resolve_source_content_text_clip_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload,
    )

    assert first == second
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert first.proposition == PDF_TEXT_SOURCE_RECTANGULAR_CLIP_CONTAINS_WORD
    assert first.reason_codes == (SOURCE_CLIP_SHADOW_RESOLVED_CONTAINS,)
    assert first.proof_id
    assert len(first.sequence_numbers) == 2
    assert first.clip_rect_pdf == (20.0, 100.0, 120.0, 140.0)
    assert first.clip_rect_page is not None

    live_after = producer.text_integrity_authority().resolve_text(selector)
    assert live_after == live_before
    assert live_after.trusted_text is None


def test_unique_text_clip_can_be_proven_without_resolving_other_text_blockers():
    payload = _pdf(_strict_clip_stream(render_mode=0, text="ONE"))
    producer, _published, selectors = _ingest(
        payload,
        document_id="source-clip-single",
    )
    selector, live = _clip_unresolved_selector(producer, selectors)

    result = resolve_source_content_text_clip_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload,
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PDF_TEXT_SOURCE_RECTANGULAR_CLIP_CONTAINS_WORD
    assert result.sequence_numbers
    assert TEXT_CLIP_STATE_UNRESOLVED in result.live_text_reason_codes
    # The shadow proves only clipping; it never rewrites the stored authority.
    assert producer.text_integrity_authority().resolve_text(selector) == live


def test_shadow_is_not_applicable_when_live_clip_state_is_already_resolved():
    payload = _pdf("BT /F1 12 Tf 40 120 Td (ONE) Tj ET")
    producer, _published, selectors = _ingest(
        payload,
        document_id="source-clip-not-applicable",
    )
    assert selectors

    result = resolve_source_content_text_clip_shadow(
        source_visibility_producer=producer,
        selector=selectors[0],
        source_bytes=payload,
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None
    assert result.reason_codes == (SOURCE_CLIP_SHADOW_NOT_APPLICABLE,)


def test_source_hash_mismatch_fails_closed():
    payload = _pdf(_strict_clip_stream(render_mode=2, text="PAIR"))
    producer, _published, selectors = _ingest(
        payload,
        document_id="source-clip-hash",
    )
    selector, _live = _clip_unresolved_selector(producer, selectors)

    result = resolve_source_content_text_clip_shadow(
        source_visibility_producer=producer,
        selector=selector,
        source_bytes=payload + b"tampered",
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proposition is None
    assert result.proof_id is None
    assert result.reason_codes == (SOURCE_HASH_MISMATCH,)


def test_shadow_module_is_not_imported_by_live_or_structural_paths():
    for path in (
        Path("pb_pdf_text_integrity_authority.py"),
        Path("pb_source_visibility_authority.py"),
        Path("pb_structural_member_definition_source_shadow.py"),
        Path("pb_structural_member_registration_producer.py"),
        Path("pb_planreader_pdf_extractor.py"),
    ):
        tree = ast.parse(path.read_text())
        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert "pb_pdf_text_source_clip_ownership_shadow" not in imports


def test_shadow_module_has_no_benchmark_or_commercial_dependencies():
    tree = ast.parse(
        Path("pb_pdf_text_source_clip_ownership_shadow.py").read_text()
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
