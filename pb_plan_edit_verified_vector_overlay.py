"""Verified per-sheet PDF vector change overlays for PlanReader review revisions.

A drawing change is only visibly projected when an independent server-owned
PDF-primitive witness finds the original vector stroke on the exact target page.
A producer supplies a page-specific source->PDF projection of the NEW geometry,
supported by independent source/callout/transform receipts. Never infer an
elevation from plan coordinates, or erase/overwrite original drafting.

Draws the revised vector in an explicitly marked *PROPOSED* review overlay.
The original drawing remains an immutable underlying source of truth.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from typing import Sequence

import fitz

_MAX_POINTS = 2
_MAX_COORD = 100_000.0
_TOLERANCE_PT = 0.25


def _point(value: object) -> tuple[float, float]:
    if (type(value) is not tuple or len(value) != 2 or
        any(type(x) not in (int, float) or not isfinite(x) or
            abs(x) > _MAX_COORD for x in value)):
        raise ValueError("source_vector_point_invalid")
    return (float(value[0]), float(value[1]))


def _line(value: object) -> tuple[tuple[float, float], tuple[float, float]]:
    if type(value) is not tuple or len(value) != _MAX_POINTS:
        raise ValueError("source_vector_line_invalid")
    a, b = _point(value[0]), _point(value[1])
    if hypot(a[0] - b[0], a[1] - b[1]) < _TOLERANCE_PT:
        raise ValueError("source_vector_degenerate_line")
    return a, b


@dataclass(frozen=True)
class VerifiedPageLineOverlay:
    page_index: int
    page_label: str
    native_geometry_ref: str
    canonical_object_id: str
    original_pdf_segment: tuple[tuple[float, float], tuple[float, float]]
    proposed_pdf_segment: tuple[tuple[float, float], tuple[float, float]]
    original_source_receipt_id: str
    transform_receipt_id: str
    model_correction_receipt_id: str
    producer_accepted: bool
    # Page drawing and model edits cannot be approximated by browser values.
    projection_kind: str  # source_verified_plan OR source_verified_elevation

    def __post_init__(self) -> None:
        if type(self.page_index) is not int or self.page_index < 0:
            raise ValueError("verified_overlay_page_index_invalid")
        for name in (
            "page_label", "native_geometry_ref", "canonical_object_id",
            "original_source_receipt_id", "transform_receipt_id",
            "model_correction_receipt_id",
        ):
            v = getattr(self, name)
            if type(v) is not str or not v.strip() or len(v) > 256:
                raise ValueError(f"verified_overlay_{name}_required")
        if len({self.original_source_receipt_id, self.transform_receipt_id,
                self.model_correction_receipt_id}) != 3:
            raise ValueError("verified_overlay_receipts_not_independent")
        if self.producer_accepted is not True or self.projection_kind not in (
            "source_verified_plan", "source_verified_elevation"
        ):
            raise ValueError("verified_overlay_source_projection_missing")
        original = _line(self.original_pdf_segment)
        proposed = _line(self.proposed_pdf_segment)
        if (
            all(hypot(x[0] - y[0], x[1] - y[1]) <= _TOLERANCE_PT
                for x, y in zip(original, proposed)) or
            all(hypot(x[0] - y[0], x[1] - y[1]) <= _TOLERANCE_PT
                for x, y in zip(original, reversed(proposed)))
        ):
            raise ValueError("verified_overlay_no_geometry_change")


def _same_line(
    left: tuple[tuple[float, float], tuple[float, float]],
    right: tuple[tuple[float, float], tuple[float, float]],
) -> bool:
    return any(
        all(hypot(a[0] - b[0], a[1] - b[1]) <= _TOLERANCE_PT
            for a, b in zip(left, oriented))
        for oriented in (right, tuple(reversed(right)))
    )


def original_pdf_line_count(page: fitz.Page,
                            segment: tuple[tuple[float, float], tuple[float, float]]) -> int:
    """Require a unique vector source stroke, not OCR or guessed bitmap edge."""
    original = _line(segment)
    matches = 0
    for path in page.get_drawings():
        # Masked, zero-width, invisible, dashed, or non-stroked paths are not
        # robustly attributable to the physical primitive without more proof.
        if path.get("type") not in ("s", "fs") or (
            path.get("stroke_opacity", 1.0) < 0.98
        ):
            continue
        for item in path.get("items", ()):
            if len(item) != 3 or item[0] != "l":
                continue
            a, b = item[1], item[2]
            found = ((float(a.x), float(a.y)), (float(b.x), float(b.y)))
            if _same_line(original, found):
                matches += 1
                if matches > 1:
                    return matches
    return matches


def validate_verified_overlays(
    document: fitz.Document, links: Sequence[object],
    overlays: tuple[VerifiedPageLineOverlay, ...],
    *,
    canonical_object_id: str,
    revision_command_id: str,
) -> tuple[VerifiedPageLineOverlay, ...]:
    if type(overlays) is not tuple or len(overlays) != len(links) or not overlays:
        raise ValueError("not_all_related_pages_have_vector_projection")
    pages = {link.page_index: link for link in links}
    if len(pages) != len(links) or set(pages) != {o.page_index for o in overlays}:
        raise ValueError("cross_page_overlay_coverage_mismatch")
    if len({o.page_index for o in overlays}) != len(overlays):
        raise ValueError("duplicate_page_vector_overlay")
    for overlay in overlays:
        if type(overlay) is not VerifiedPageLineOverlay:
            raise ValueError("untrusted_vector_overlay_type")
        link = pages[overlay.page_index]
        if (overlay.page_label != link.page_label or
            overlay.native_geometry_ref != link.native_geometry_ref or
            overlay.canonical_object_id != canonical_object_id or
            overlay.model_correction_receipt_id != revision_command_id):
            raise ValueError("vector_overlay_source_page_or_command_mismatch")
        page = document[overlay.page_index]
        if page.rotation != 0:
            # A registered rotation/derotation mapping must be supplied by a
            # producer before permitting geometry overlays on rotated sheets.
            raise ValueError("rotated_page_vector_projection_unregistered")
        for point in (*overlay.original_pdf_segment, *overlay.proposed_pdf_segment):
            if not page.rect.contains(fitz.Point(*point)):
                raise ValueError("vector_overlay_outside_pdf_page")
        if original_pdf_line_count(page, overlay.original_pdf_segment) != 1:
            raise ValueError("original_native_pdf_line_not_uniquely_verified")
    return overlays


def draw_page_vector_overlay(page: fitz.Page,
                             patch: VerifiedPageLineOverlay,
                             revision_label: str) -> None:
    """Reversible coloured layer; no removal of source strokes or quantities."""
    a, b = patch.proposed_pdf_segment
    # Keep original drafting visible beneath the proposal. Draw the revised
    # line exactly ONCE: repeated Shape.finish() in one shape can duplicate
    # vector path records in PyMuPDF and would break native-line lineage.
    shape = page.new_shape()
    shape.draw_line(fitz.Point(*a), fitz.Point(*b))
    shape.finish(color=(0.02, 0.39, 0.78), width=2.4)
    shape.commit(overlay=True)
    point = fitz.Point((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    rect = fitz.Rect(point.x - 62, point.y - 22, point.x + 62, point.y - 4)
    rect.intersect(page.rect)
    if rect.width >= 25 and rect.height >= 8:
        stamp = page.add_freetext_annot(
            rect, f"{revision_label}: PROPOSED VECTOR (REVIEW)",
            fontsize=5, fontname="Helv", text_color=(0.01, 0.32, 0.70),
            fill_color=(0.94, 0.96, 1.0),
        )
        stamp.set_info(title="PlanReader source-verified vector study",
                       subject=revision_label,
                       content="Proposed vector overlay. Original PDF drafting preserved.")
        stamp.update()
