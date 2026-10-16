"""Original-PDF rotated source clip/texttrace parity census, read-only shadow.

In-memory /Rotate normalization is a *representation parity experiment*, not
permission for PdfTextIntegrityAuthority to trust text. It never modifies PDF
bytes or producer, never publishes a clip grant or any construction quantity.
"""
from __future__ import annotations

import hashlib
import json

import fitz


def _serial(value):
    try:
        if isinstance(value, (list, tuple)):
            return [_serial(x) for x in value]
        if isinstance(value, dict):
            return {str(k): _serial(v) for k, v in value.items()}
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        return repr(value)
    except Exception:
        return "<unserializable_native_source>"


def _snapshot(page):
    """Hash the exact inputs the existing PDF clip-stack builder consumes."""
    digest = hashlib.sha256()
    drawings = page.get_drawings(extended=True) or ()
    clip_count = 0
    for index, drawing in enumerate(drawings):
        kind = str(drawing.get("type") or "")
        record = (
            index, kind, drawing.get("seqno"), drawing.get("level"),
            drawing.get("scissor") if kind == "clip" else None,
            drawing.get("items") if kind == "clip" else None,
        )
        digest.update(json.dumps(_serial(record), sort_keys=True).encode("utf-8"))
        digest.update(b"\n")
        if kind == "clip":
            clip_count += 1
    draw_hash = digest.hexdigest()
    word_records = [
        tuple(_serial(word[:8])) for word in page.get_text("words")
        if len(word) >= 8
    ]
    word_hash = hashlib.sha256(
        json.dumps(word_records, sort_keys=True).encode("utf-8")
    ).hexdigest()
    traces = []
    for row in page.get_texttrace():
        traces.append(_serial((
            row.get("seqno"), row.get("type"), row.get("font"),
            row.get("bbox"), row.get("chars"),
            row.get("opacity"), row.get("layer"),
        )))
    trace_hash = hashlib.sha256(
        json.dumps(traces, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        "extended_source_path_or_clip_count": len(drawings),
        "native_clip_record_count": clip_count,
        "native_word_count": len(word_records),
        "texttrace_span_count": len(traces),
        "clip_hierarchy_and_exact_clip_geometry_sha256": draw_hash,
        "native_text_word_tuple_sha256": word_hash,
        "renderer_texttrace_glyph_span_sha256": trace_hash,
    }


def comparison_gate(left: dict, right: dict) -> str:
    """Even exact parity is NOT an actual clip-ownership/trust grant."""
    return (
        "exact_native_representation_parity_candidate_not_text_trust"
        if left == right
        else "rotated_native_text_or_clip_representation_conflict"
    )


def audit_original_rotated_native_clip_parity(
    source_bytes: bytes, *, expected_sha256: str, page_numbers: tuple[int, ...],
):
    if type(source_bytes) is not bytes:
        raise TypeError("original_source_pdf_bytes_required")
    actual_hash = hashlib.sha256(source_bytes).hexdigest()
    if type(expected_sha256) is not str or actual_hash != expected_sha256:
        raise ValueError("original_source_sha_mismatch")
    if (type(page_numbers) is not tuple or not page_numbers
            or len(set(page_numbers)) != len(page_numbers)
            or any(type(n) is not int or n < 1 for n in page_numbers)):
        raise ValueError("exact_source_page_numbers_required")
    rows = []
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        for number in page_numbers:
            if number > len(document):
                raise ValueError("original_source_page_out_of_range")
            page = document[number - 1]
            original_rotation = int(page.rotation)
            source_before = _snapshot(page)
            # No saved document update; this instance was created from bytes.
            try:
                page.set_rotation(0)
                native_zero = _snapshot(page)
            finally:
                page.set_rotation(original_rotation)
            restored = _snapshot(page)
            gate = comparison_gate(source_before, native_zero)
            rows.append({
                "original_pdf_page_one_based": number,
                "original_source_rotation_degrees": original_rotation,
                "source_original_rotation_snapshot": source_before,
                "in_memory_zero_rotation_snapshot": native_zero,
                "restored_original_rotation_snapshot": restored,
                "first_parity_gate": gate,
                "in_memory_original_rotation_restored": original_rotation == int(page.rotation),
                "source_native_snapshot_restored": source_before == restored,
                "native_pdf_clip_stack_text_authority_granted": False,
                "native_pdf_unicode_glyph_authority_granted": False,
                "renderer_paint_clip_visibility_proven": False,
            })
    return {
        "original_source_sha256": actual_hash,
        "original_source_bytes_after": hashlib.sha256(source_bytes).hexdigest(),
        "original_source_bytes_unchanged": True,
        "source_page_parity_rows": rows,
        "diagnostic_only": True,
        "new_native_text_trust_grants": 0,
        "new_material_definitions": 0,
        "new_source_room_owners": 0,
        "new_quantities": 0,
        "new_commercial_rows": 0,
    }
