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
from tools.gpt3_original_source_preflight import _stable_original_digest


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
class NativeSegment:
    ref: str
    kind: str
    x1: float
    y1: float
    x2: float
    y2: float


@dataclass(frozen=True)
class NativePage:
    source_sha256: str
    page_index: int
    words: tuple[NativeWord, ...]
    rectangles: tuple[NativeRectangle, ...]
    segments: tuple[NativeSegment, ...]


def authenticated_pdf_snapshot(pdf_path: str | Path) -> tuple[str, bytes, tuple[int, ...]]:
    """Hash identity, then parse only the bytes that still match that digest."""
    path = Path(pdf_path)
    try:
        digest, identity = _stable_original_digest(path)
    except (OSError, ValueError) as exc:
        raise SourceConflict("source_identity_unavailable") from exc
    try:
        source_bytes = path.read_bytes()
    except OSError as exc:
        raise SourceConflict("source_changed_during_read") from exc
    if sha256(source_bytes).hexdigest() != digest:
        raise SourceConflict("source_changed_during_read")
    return digest, source_bytes, identity


def confirm_source_snapshot(pdf_path: str | Path, digest: str, identity: tuple[int, ...]) -> None:
    path = Path(pdf_path)
    try:
        unchanged = _stable_original_digest(path) == (digest, identity)
    except (OSError, ValueError) as exc:
        raise SourceConflict("source_changed_during_read") from exc
    if not unchanged:
        raise SourceConflict("source_changed_during_read")


def load_native_page(pdf_path: str | Path, page_index: int) -> NativePage:
    """Get actual typed native primitives and immutable original PDF SHA."""
    import fitz

    path = Path(pdf_path)
    if type(page_index) is not int or page_index < 0:
        raise SourceConflict("page_index_invalid")
    digest, source_bytes, identity = authenticated_pdf_snapshot(path)
    # The parser must consume the exact authenticated snapshot. A second
    # pathname open can read a replacement with the same size and mtime.
    with fitz.open(stream=source_bytes, filetype="pdf") as document:
        if page_index >= len(document):
            raise SourceConflict("page_not_in_source")
        extracted = extract_native_page(document[page_index])
    confirm_source_snapshot(path, digest, identity)
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
    segments = tuple(
        NativeSegment(
            ref=str(s["id"]), kind=str(s.get("kind", "")),
            x1=float(s["x1"]), y1=float(s["y1"]),
            x2=float(s["x2"]), y2=float(s["y2"]),
        ) for s in extracted["segments"]
    )
    if len(set(w.ref for w in words)) != len(words):
        raise SourceConflict("duplicate_native_word_identity")
    if len(set(r.ref for r in rectangles)) != len(rectangles):
        raise SourceConflict("duplicate_native_rectangle_identity")
    if len(set(s.ref for s in segments)) != len(segments):
        raise SourceConflict("duplicate_native_segment_identity")
    return NativePage(digest, page_index, words, rectangles, segments)


def inspect_page(page: NativePage, *, include_segments: bool = False) -> dict[str, Any]:
    """Native refs; segment detail opt-in for large plan drawings."""
    data = {
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "rectangles": [asdict(r) for r in page.rectangles],
        "words": [asdict(w) for w in page.words],
        "segment_count": len(page.segments),
    }
    if include_segments:
        data["segments"] = [asdict(s) for s in page.segments]
    return data


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


def _axis_word_refs(row: Mapping[str, Any], singular: str, plural: str) -> tuple[str, ...]:
    """One reviewed figure or an ordered unique hash-chain of figures on that axis."""
    if plural in row:
        raw = row[plural]
        if type(raw) is not list or not raw or any(type(item) is not str or not item.strip() for item in raw):
            raise SourceConflict("axis_word_refs_invalid")
        if singular in row:
            raise SourceConflict("duplicate_axis_word_receipt_form")
        refs = tuple(item.strip() for item in raw)
        if len(set(refs)) != len(refs):
            raise SourceConflict("source_word_receipt_reused")
        return refs
    return (_required_text(row, singular),)


def _measure_one(
    page: NativePage, row: Mapping[str, Any], *,
    expected_basis: str = "internal_finished_wall_face",
    trade: str = "floor_finish",
    finish_page: NativePage | None = None,
) -> dict[str, Any]:
    words = {w.ref: w for w in page.words}
    rects = {r.ref: r for r in page.rectangles}
    if row.get("boundary_basis") != expected_basis:
        raise SourceConflict("reviewed_surface_boundary_not_confirmed") if trade != "floor_finish" else SourceConflict("internal_finished_face_not_confirmed")
    source_edges: tuple[str, ...] = ()
    if "boundary_segment_refs" in row:
        from .polygon import source_polygon
        polygon = source_polygon(page, row["boundary_segment_refs"])
        geometry_ref = polygon.ref
        source_edges = polygon.segment_refs
        bbox = polygon.bbox
        x0, y0, x1, y1 = bbox
        fraction = Decimal(str(polygon.area_pt2 / ((x1 - x0) * (y1 - y0))))
    else:
        geometry_ref = _required_text(row, "rectangle_ref")
        if geometry_ref not in rects:
            raise SourceConflict("native_finished_face_rectangle_missing")
        bbox = rects[geometry_ref].bbox
        x0, y0, x1, y1 = bbox
        fraction = Decimal("1")
    if not all(math.isfinite(v) for v in bbox) or x1 <= x0 or y1 <= y0:
        raise SourceConflict("closed_native_room_face_invalid")
    width_refs = _axis_word_refs(row, "width_word_ref", "width_word_refs")
    height_refs = _axis_word_refs(row, "height_word_ref", "height_word_refs")
    label_ref = _required_text(row, "room_label_word_ref")
    finish_ref = _required_text(row, "finish_word_ref")
    plan_refs = (*width_refs, *height_refs, label_ref)
    if len(set(plan_refs)) != len(plan_refs):
        raise SourceConflict("source_word_receipt_reused")
    if any(value not in words for value in plan_refs):
        raise SourceConflict("native_word_receipt_missing")
    width_chain = [words[ref] for ref in width_refs]
    height_chain = [words[ref] for ref in height_refs]
    label_word = words[label_ref]
    rcp_receipt: dict[str, Any] | None = None
    if finish_page is None:
        refs = (*plan_refs, finish_ref)
        if len(set(refs)) != len(refs):
            raise SourceConflict("source_word_receipt_reused")
        if finish_ref not in words:
            raise SourceConflict("native_word_receipt_missing")
        finish_word = words[finish_ref]
        if not _inside(label_word.bbox, bbox) or not _inside(finish_word.bbox, bbox):
            raise SourceConflict("room_or_finish_not_inside_selected_face")
    else:
        if trade != "ceiling_finish" or expected_basis != "source_owned_ceiling_zone":
            raise SourceConflict("cross_sheet_finish_only_valid_for_ceiling")
        if (
            finish_page.source_sha256 != page.source_sha256
            or finish_page.page_index == page.page_index
            or row.get("rcp_cross_sheet_correspondence_reviewed") is not True
        ):
            raise SourceConflict("cross_sheet_ceiling_source_or_review_missing")
        if not _inside(label_word.bbox, bbox):
            raise SourceConflict("room_label_not_inside_plan_ceiling_zone")
        rcp_words = {word.ref: word for word in finish_page.words}
        if finish_ref not in rcp_words:
            raise SourceConflict("rcp_finish_word_not_owned_by_source_page")
        finish_word = rcp_words[finish_ref]
        from .rcp_zone_scope import propose_rcp_source_zone_rectangles
        rcp_zones = propose_rcp_source_zone_rectangles(finish_page)[
            "source_zone_rectangle_candidates"
        ]
        owning = [
            zone for zone in rcp_zones
            if zone["source_rectangle_ref"] == row.get("rcp_source_rectangle_ref")
            and finish_ref in zone["material_word_refs"]
        ]
        if len(owning) != 1:
            raise SourceConflict("cross_sheet_ceiling_rcp_zone_not_uniquely_source_owned")
        from .height_evidence import validate_height_receipt
        receipts = [
            receipt for receipt in owning[0]["callout_receipts"]
            if receipt["material_word_ref"] == finish_ref
            and (
                row.get("rcp_height_word_ref") is None
                or receipt["height_word_ref"] == row.get("rcp_height_word_ref")
            )
        ]
        if len(receipts) != 1:
            raise SourceConflict("cross_sheet_ceiling_height_material_pair_not_unique")
        rcp_receipt = validate_height_receipt(finish_page, receipts[0])
        # Neither PDF-native coordinate position nor a reviewer flag proves
        # the ceiling polygon. The plan's separately authenticated two axes
        # and geometry below remain mandatory, and the output stays a draft.
    # Every chain word must sit on the actual indicated axis; mere equal numeric
    # product or unattached project metadata cannot select an axis.
    for width_word in width_chain:
        hcx = (width_word.bbox[0] + width_word.bbox[2]) / 2
        hcy = (width_word.bbox[1] + width_word.bbox[3]) / 2
        if not (x0 <= hcx <= x1 and (abs(hcy - y0) <= 32 or abs(hcy - y1) <= 32)):
            raise SourceConflict("horizontal_dimension_axis_unbound")
    for height_word in height_chain:
        vcx = (height_word.bbox[0] + height_word.bbox[2]) / 2
        vcy = (height_word.bbox[1] + height_word.bbox[3]) / 2
        if not (y0 <= vcy <= y1 and (abs(vcx - x0) <= 32 or abs(vcx - x1) <= 32)):
            raise SourceConflict("vertical_dimension_axis_unbound")
    width_mm = sum((_figured_mm(word) for word in width_chain), Decimal("0"))
    height_mm = sum((_figured_mm(word) for word in height_chain), Decimal("0"))
    shape_ratio = Decimal(str((x1 - x0) / (y1 - y0)))
    figure_ratio = width_mm / height_mm
    if abs(shape_ratio / figure_ratio - 1) > Decimal("0.05"):
        raise SourceConflict("figured_axes_do_not_match_native_face_shape")
    finish = finish_word.text.strip().upper()
    if not re.fullmatch(r"[A-Z][A-Z0-9-]{1,15}", finish):
        raise SourceConflict("finish_code_not_source_owned")
    area = (width_mm * height_mm * fraction / Decimal("1000000"))
    if source_edges:
        area = area.quantize(Decimal("0.000001"))
    room_id = _required_text(row, "room_id")
    evidence = {
        "room_label_word_ref": label_ref,
        "finish_word_ref": finish_ref,
    }
    if finish_page is not None:
        evidence.update({
            "finish_source_page_index": finish_page.page_index,
            "rcp_source_rectangle_ref": row["rcp_source_rectangle_ref"],
            "rcp_height_source_receipt": rcp_receipt,
            "cross_sheet_correspondence_reviewed": True,
        })
    if len(width_refs) == 1:
        evidence["width_word_ref"] = width_refs[0]
    else:
        evidence["width_word_refs"] = list(width_refs)
    if len(height_refs) == 1:
        evidence["height_word_ref"] = height_refs[0]
    else:
        evidence["height_word_refs"] = list(height_refs)
    # Reviewer-authenticated binding creates a measurable draft, NOT source-
    # independent commercial/FIRM authority. Do not publish directly to JobHub.
    if finish_page is None:
        # Preserve historical draft row identity byte-for-byte for
        # existing single-page floors, ceilings and other measurements.
        trace = "|".join((
            page.source_sha256, str(page.page_index), geometry_ref,
            *refs, room_id, trade,
        ))
    else:
        trace = "|".join((
            page.source_sha256, str(page.page_index), geometry_ref,
            *plan_refs, str(finish_page.page_index), finish_ref,
            str(row.get("rcp_source_rectangle_ref", "")), room_id, trade,
        ))
    return {
        "row_id": sha256(trace.encode("utf-8")).hexdigest()[:24],
        "room_id": room_id,
        "room_label": label_word.text.strip(),
        "finish_code": finish,
        "trade": trade,
        "quantity": format(area.normalize(), "f"),
        "unit": "m2",
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "geometry_ref": geometry_ref,
        "evidence_refs": {**evidence, **({"boundary_segment_refs": list(source_edges)} if source_edges else {})},
        "boundary_basis": expected_basis,
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
    geometry_claims = [
        ("polygon", tuple(sorted(str(ref) for ref in r["boundary_segment_refs"])))
        if "boundary_segment_refs" in r else ("rectangle", _required_text(r, "rectangle_ref"))
        for r in rows
    ]
    if len(set(ids)) != len(ids) or len(set(geometry_claims)) != len(geometry_claims):
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
