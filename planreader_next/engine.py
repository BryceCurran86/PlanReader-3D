"""Small, default-off, source-bound PlanReader measurement vertical slice.

Reuses the existing native PDF extractor rather than creating another PDF parser.
This package is not a replacement for production quantity issuers, signatures,
opening topology, scale calibration or the frozen V2 evaluator.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from pathlib import Path
import math
import re
from typing import Any, Mapping, Sequence

from pb_vector_geometry_v130 import extract_native_page, native_word_primitive_ref


class SourceConflict(ValueError):
    """Missing, stale or ambiguous source ownership. Never becomes a quantity."""


@dataclass(frozen=True)
class NativeWord:
    ref: str
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class NativeRectangle:
    ref: str
    bbox: tuple[float, float, float, float]
    clip_known: bool


@dataclass(frozen=True)
class NativePage:
    source_sha256: str
    page_index: int
    words: tuple[NativeWord, ...]
    rectangles: tuple[NativeRectangle, ...]


def _digest(path: Path) -> str:
    h = sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_native_page(pdf_path: str | Path, page_index: int) -> NativePage:
    """Get actual typed native primitives and immutable original PDF SHA."""
    import fitz

    path = Path(pdf_path)
    if type(page_index) is not int or page_index < 0:
        raise SourceConflict("page_index_invalid")
    before = path.stat()
    digest = _digest(path)
    with fitz.open(path) as document:
        if page_index >= len(document):
            raise SourceConflict("page_not_in_source")
        extracted = extract_native_page(document[page_index])
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise SourceConflict("source_changed_during_read")
    words = tuple(
        NativeWord(
            ref=native_word_primitive_ref(w),
            text=str(w["text"]),
            bbox=tuple(float(x) for x in w["bbox"]),
        )
        for w in extracted["words"]
    )
    rectangles = tuple(
        NativeRectangle(
            ref=f"rect:p{r['path_index']}:i{r['item_index']}",
            bbox=tuple(float(x) for x in r["bbox"]),
            clip_known=bool(r.get("clip_known")),
        )
        for r in extracted["rects"]
    )
    if len(set(w.ref for w in words)) != len(words):
        raise SourceConflict("duplicate_native_word_identity")
    if len(set(r.ref for r in rectangles)) != len(rectangles):
        raise SourceConflict("duplicate_native_rectangle_identity")
    return NativePage(digest, page_index, words, rectangles)


def inspect_page(page: NativePage) -> dict[str, Any]:
    """Reference inventory to help a reviewer select exact native evidence."""
    return {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "rectangles": [asdict(r) for r in page.rectangles],
        "words": [asdict(w) for w in page.words],
    }


def _inside(inner: tuple[float, ...], outer: tuple[float, ...]) -> bool:
    x = (inner[0] + inner[2]) / 2
    y = (inner[1] + inner[3]) / 2
    return outer[0] < x < outer[2] and outer[1] < y < outer[3]


def _figured_mm(word: NativeWord) -> Decimal:
    # Do not interpret 1:100 scales, arbitrary areas, or inferred millimetres.
    token = word.text.strip().replace(",", "")
    match = re.fullmatch(r"([1-9]\d{2,4})(?:\s?mm)?", token, re.I)
    if not match:
        raise SourceConflict("figured_dimension_word_unavailable")
    return Decimal(match.group(1))


def _required_text(row: Mapping[str, Any], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SourceConflict(f"{key}_missing")
    return value.strip()


def _get(mapping: Mapping[str, Any], key: str, reason: str) -> Any:
    ref = _required_text(mapping, key)
    if ref not in mapping["_all_refs"]:
        raise SourceConflict(reason)
    return mapping["_all_refs"][ref]


def _measure_one(page: NativePage, row: Mapping[str, Any]) -> dict[str, Any]:
    words = {w.ref: w for w in page.words}
    rects = {r.ref: r for r in page.rectangles}
    rect_ref = _required_text(row, "rectangle_ref")
    if rect_ref not in rects:
        raise SourceConflict("native_finished_face_rectangle_missing")
    if row.get("boundary_basis") != "internal_finished_wall_face":
        raise SourceConflict("internal_finished_face_not_confirmed")
    rect = rects[rect_ref]
    x0, y0, x1, y1 = rect.bbox
    if not all(math.isfinite(v) for v in rect.bbox) or x1 <= x0 or y1 <= y0:
        raise SourceConflict("closed_native_room_rectangle_invalid")
    refs = {
        key: _required_text(row, key)
        for key in ("width_word_ref", "height_word_ref", "room_label_word_ref", "finish_word_ref")
    }
    if len(set(refs.values())) != len(refs):
        raise SourceConflict("source_word_receipt_reused")
    if any(value not in words for value in refs.values()):
        raise SourceConflict("native_word_receipt_missing")
    width_word, height_word = words[refs["width_word_ref"]], words[refs["height_word_ref"]]
    label_word, finish_word = words[refs["room_label_word_ref"]], words[refs["finish_word_ref"]]
    if not _inside(label_word.bbox, rect.bbox) or not _inside(finish_word.bbox, rect.bbox):
        raise SourceConflict("room_or_finish_not_inside_selected_face")
    # A word near the actual indicated axis is required; mere equal numeric
    # product or unattached project metadata cannot select an axis.
    hcx = (width_word.bbox[0] + width_word.bbox[2]) / 2
    hcy = (width_word.bbox[1] + width_word.bbox[3]) / 2
    vcx = (height_word.bbox[0] + height_word.bbox[2]) / 2
    vcy = (height_word.bbox[1] + height_word.bbox[3]) / 2
    if not (x0 <= hcx <= x1 and (abs(hcy - y0) <= 32 or abs(hcy - y1) <= 32)):
        raise SourceConflict("horizontal_dimension_axis_unbound")
    if not (y0 <= vcy <= y1 and (abs(vcx - x0) <= 32 or abs(vcx - x1) <= 32)):
        raise SourceConflict("vertical_dimension_axis_unbound")
    width_mm, height_mm = _figured_mm(width_word), _figured_mm(height_word)
    shape_ratio = Decimal(str((x1 - x0) / (y1 - y0)))
    figure_ratio = width_mm / height_mm
    if abs(shape_ratio / figure_ratio - 1) > Decimal("0.05"):
        raise SourceConflict("figured_axes_do_not_match_native_face_shape")
    finish = finish_word.text.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{1,15}", finish):
        raise SourceConflict("finish_code_not_source_owned")
    area = width_mm * height_mm / Decimal("1000000")
    room_id = _required_text(row, "room_id")
    # Reviewer-authenticated binding creates a measurable draft, NOT source-
    # independent commercial/FIRM authority. Do not publish directly to JobHub.
    trace = "|".join((
        page.source_sha256, str(page.page_index), rect_ref, *refs.values(), room_id,
    ))
    return {
        "row_id": sha256(trace.encode("utf-8")).hexdigest()[:24],
        "room_id": room_id,
        "room_label": label_word.text.strip(),
        "finish_code": finish,
        "trade": "floor_finish",
        "quantity": format(area.normalize(), "f"),
        "unit": "m2",
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "geometry_ref": rect_ref,
        "evidence_refs": refs,
        "boundary_basis": "internal_finished_wall_face",
        "status": "MEASURED_DRAFT_REVIEW_REQUIRED",
        "commercial_publishable": False,
        "benchmark_credit": False,
    }


def measure_page(page: NativePage, selection: Mapping[str, Any]) -> dict[str, Any]:
    """Fail-closed, one room -> one independent quantity; no gold or defaults."""
    if selection.get("source_sha256") != page.source_sha256:
        raise SourceConflict("source_sha256_mismatch")
    if selection.get("page_index") != page.page_index:
        raise SourceConflict("source_page_mismatch")
    project_id = _required_text(selection, "project_id")
    revision_id = _required_text(selection, "revision_id")
    rows = selection.get("rooms")
    if not isinstance(rows, list):
        raise SourceConflict("rooms_selection_invalid")
    ids = [_required_text(r, "room_id") for r in rows]
    rectangles = [_required_text(r, "rectangle_ref") for r in rows]
    if len(set(ids)) != len(ids) or len(set(rectangles)) != len(rectangles):
        raise SourceConflict("duplicate_room_or_physical_face")
    quantities, abstentions = [], []
    for row in rows:
        try:
            quantities.append(_measure_one(page, row))
        except (SourceConflict, TypeError, ValueError, InvalidOperation, ZeroDivisionError) as exc:
            abstentions.append({"room_id": row["room_id"], "reason_code": str(exc) if isinstance(exc, SourceConflict) else "invalid_room_observation"})
    return {
        "schema_version": "0.1.0",
        "project_id": project_id,
        "revision_id": revision_id,
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "quantities": quantities,
        "abstentions": abstentions,
        "commercial_publishable": False,
        "official_score": None,
    }
