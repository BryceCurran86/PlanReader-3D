"""Test support for secondary-footprint / verandah authority red-team.

Fixtures only. No production secondary-footprint authority is defined here.

Reuse existing F.23 evidence and multi-space geometry seams. Do not invent a
second scale resolver, QuantityEvidence vocabulary, or caller self-seal.

Future production contract (expected-RED until implemented):
``pb_secondary_footprint_authority`` with sealed producer lookup, e.g.
``SecondaryFootprintAuthority.resolve(selector)`` / ``evaluate_redteam_attack``.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from typing import Any, Optional

import fitz
import pytest

from pb_multi_space_footprint_geometry import (
    FootprintStatus,
    MultiSpaceFootprintBuilder,
    resolve_external_envelope_perimeter_m,
)
from pb_secondary_footprint_evidence import (
    SecondaryFootprintEvidence,
    resolve_secondary_footprint_width_m,
)

AUTHORITY_MODULE = "pb_secondary_footprint_authority"
BASE_SHA = "da7a62fad2aae51bf5f35e890c14f05c4bfab8f9"

_EDGE_FRACTIONS = {
    "top": (0.5, 0.08),
    "bottom": (0.5, 0.92),
    "left": (0.12, 0.45),
    "right": (0.88, 0.55),
}


@dataclass(frozen=True)
class CallerSecondaryWidthProbe:
    """Caller-minted verandah width claim — must never self-certify authority."""

    width_m: float
    label: str
    page_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    is_authenticated: bool = False
    complete: bool = False
    snapshot_id: str = ""


@dataclass(frozen=True)
class SecondaryFootprintSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    secondary_space_id: str


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _draw_vertical_depth(
    page: fitz.Page,
    *,
    x: float,
    y0: float,
    y1: float,
    text: str,
    fontsize: float,
    include_witness_at_y0: bool = True,
    include_witness_at_y1: bool = True,
) -> None:
    page.draw_line((x, y0), (x, y1))
    if include_witness_at_y0:
        page.draw_line((x - 18, y0), (x + 18, y0))
    if include_witness_at_y1:
        page.draw_line((x - 18, y1), (x + 18, y1))
    page.insert_text((x + 5, (y0 + y1) / 2.0), text, fontsize=fontsize, rotate=90)


def _draw_horizontal_depth(
    page: fitz.Page,
    *,
    y: float,
    x0: float,
    x1: float,
    text: str,
    fontsize: float,
    include_witness_at_x0: bool = True,
    include_witness_at_x1: bool = True,
) -> None:
    page.draw_line((x0, y), (x1, y))
    if include_witness_at_x0:
        page.draw_line((x0, y - 18), (x0, y + 18))
    if include_witness_at_x1:
        page.draw_line((x1, y - 18), (x1, y + 18))
    page.insert_text(((x0 + x1) / 2.0 - 12, y - 4), text, fontsize=fontsize)


def verandah_plan_pdf_bytes(
    *,
    edge: str = "bottom",
    depth_text: str = "1800",
    label_text: str = "VERANDAH",
    include_depth: bool = True,
    parallel_thickness_text: str | None = None,
    second_depth_text: str | None = None,
    omit_witnesses: bool = False,
    omit_main_boundary_witness: bool = False,
    omit_outer_boundary_witness: bool = False,
    regex_only_prose: str | None = None,
    dx: float = 0.0,
    dy: float = 0.0,
    scale: float = 1.0,
) -> bytes:
    """Synthetic floor-plan PDF for F.23 / authority red-team (gold-free)."""

    page_w, page_h = 640.0, 460.0
    doc = fitz.open()
    page = doc.new_page(width=page_w * scale, height=page_h * scale)
    fs = 10.0 * scale
    fx0, fy0 = 30.0 * scale + dx, 30.0 * scale + dy
    fx1, fy1 = fx0 + 280.0 * scale, fy0 + 280.0 * scale
    page.draw_rect(fitz.Rect(fx0, fy0, fx1, fy1))
    width = fx1 - fx0
    height = fy1 - fy0
    page.insert_text((fx0 + 0.10 * width, fy0 + 0.50 * height), "150 5,700 150", fontsize=fs)
    page.insert_text((fx0 + 0.10 * width, fy1 - 8.0 * scale), "GROUND FLOOR PLAN", fontsize=fs)

    x_frac, y_frac = _EDGE_FRACTIONS[edge]
    label_width = fitz.get_text_length(label_text, fontsize=fs)
    label_x = fx0 + x_frac * width - label_width / 2.0
    label_y = fy0 + y_frac * height
    page.insert_text((label_x, label_y), label_text, fontsize=fs)
    label_cx = label_x + label_width / 2.0
    label_cy = label_y - fs * 0.35

    if include_depth and edge in ("top", "bottom"):
        span = 36.0 * scale
        if edge == "bottom":
            y1 = label_cy - 4.0 * scale
            y0 = y1 - span
        else:
            y0 = label_cy + 4.0 * scale
            y1 = y0 + span
        x = label_cx
        if omit_witnesses:
            page.draw_line((x, y0), (x, y1))
            page.insert_text((x + 5, (y0 + y1) / 2.0), depth_text, fontsize=fs, rotate=90)
        else:
            include_y0 = (
                (not omit_main_boundary_witness)
                if edge == "bottom"
                else (not omit_outer_boundary_witness)
            )
            include_y1 = (
                (not omit_outer_boundary_witness)
                if edge == "bottom"
                else (not omit_main_boundary_witness)
            )
            _draw_vertical_depth(
                page,
                x=x,
                y0=y0,
                y1=y1,
                text=depth_text,
                fontsize=fs,
                include_witness_at_y0=include_y0,
                include_witness_at_y1=include_y1,
            )
        if second_depth_text is not None:
            _draw_vertical_depth(
                page,
                x=x + 55.0 * scale,
                y0=y0,
                y1=y1,
                text=second_depth_text,
                fontsize=fs,
            )
        if parallel_thickness_text is not None:
            ty = label_cy - 2.0 * scale if edge == "bottom" else label_cy + 2.0 * scale
            page.draw_line((label_cx - 20 * scale, ty), (label_cx + 20 * scale, ty))
            page.draw_line((label_cx - 20 * scale, ty - 10), (label_cx - 20 * scale, ty + 10))
            page.draw_line((label_cx + 20 * scale, ty - 10), (label_cx + 20 * scale, ty + 10))
            page.insert_text((label_cx - 10 * scale, ty - 3), parallel_thickness_text, fontsize=fs)

    if include_depth and edge in ("left", "right"):
        span = 36.0 * scale
        if edge == "left":
            x0 = label_cx + 4.0 * scale
            x1 = x0 + span
        else:
            x1 = label_cx - 4.0 * scale
            x0 = x1 - span
        y = label_cy
        if omit_witnesses:
            page.draw_line((x0, y), (x1, y))
            page.insert_text(((x0 + x1) / 2.0 - 10, y - 4), depth_text, fontsize=fs)
        else:
            include_x0 = (
                (not omit_main_boundary_witness)
                if edge == "left"
                else (not omit_outer_boundary_witness)
            )
            include_x1 = (
                (not omit_outer_boundary_witness)
                if edge == "left"
                else (not omit_main_boundary_witness)
            )
            _draw_horizontal_depth(
                page,
                y=y,
                x0=x0,
                x1=x1,
                text=depth_text,
                fontsize=fs,
                include_witness_at_x0=include_x0,
                include_witness_at_x1=include_x1,
            )
        if second_depth_text is not None:
            _draw_horizontal_depth(
                page,
                y=y + 40.0 * scale,
                x0=x0,
                x1=x1,
                text=second_depth_text,
                fontsize=fs,
            )

    if regex_only_prose:
        page.insert_text((fx0 + 10, fy0 + 20), regex_only_prose, fontsize=fs)

    payload = _reopen(doc).tobytes()
    return payload


def resolve_f23_width(pdf_bytes: bytes, *, page_num: int = 1) -> Optional[SecondaryFootprintEvidence]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    try:
        return resolve_secondary_footprint_width_m(doc[0], page_num=page_num)
    finally:
        doc.close()


def build_compound_with_caller_width(
    *,
    main_length_m: float = 16.0,
    main_width_m: float = 8.0,
    verandah_width_m: float | None = 2.0,
) -> Any:
    """Document current builder behavior: caller float can yield CONFIRMED."""

    builder = MultiSpaceFootprintBuilder()
    builder.add_main_room(length_m=main_length_m, width_m=main_width_m)
    builder.add_verandah(
        length_m=main_length_m,
        width_m=verandah_width_m,
        adjacency="front",
        label="Verandah",
    )
    return builder.build()


def dpc_envelope_from_footprint(footprint) -> Any:
    wall_rect = round(2.0 * (16.0 + 8.0), 2)
    return resolve_external_envelope_perimeter_m(
        external_perimeter_m=footprint.external_perimeter_m,
        footprint_status=footprint.status,
        fallback_wall_perimeter_m=wall_rect,
    )


def require_secondary_footprint_authority():
    spec = importlib.util.find_spec(AUTHORITY_MODULE)
    if spec is None:
        pytest.fail(f"{AUTHORITY_MODULE} not implemented on main {BASE_SHA}")
    return importlib.import_module(AUTHORITY_MODULE)


def resolve_authenticated_secondary_width(
    *,
    selector: SecondaryFootprintSelector,
    evidence: SecondaryFootprintEvidence | None = None,
    probe: CallerSecondaryWidthProbe | None = None,
    **context: Any,
) -> Any:
    mod = require_secondary_footprint_authority()
    resolve = getattr(mod, "resolve_secondary_footprint_width", None)
    if resolve is None:
        authority_cls = getattr(mod, "SecondaryFootprintAuthority", None)
        if authority_cls is None:
            pytest.fail("SecondaryFootprintAuthority / resolve_secondary_footprint_width missing")
        authority = authority_cls()
        resolve = getattr(authority, "resolve", None)
        if resolve is None:
            pytest.fail("SecondaryFootprintAuthority.resolve missing")
        return resolve(selector, evidence=evidence, probe=probe, **context)
    return resolve(selector=selector, evidence=evidence, probe=probe, **context)


def evaluate_redteam_attack(*, attack_id: str, **context: Any) -> Any:
    mod = require_secondary_footprint_authority()
    evaluate = getattr(mod, "evaluate_redteam_attack", None)
    if evaluate is None:
        pytest.fail(f"{AUTHORITY_MODULE}.evaluate_redteam_attack missing")
    return evaluate(attack_id=attack_id, **context)


def assert_no_authority_module() -> None:
    assert importlib.util.find_spec(AUTHORITY_MODULE) is None


__all__ = [
    "AUTHORITY_MODULE",
    "BASE_SHA",
    "CallerSecondaryWidthProbe",
    "FootprintStatus",
    "SecondaryFootprintSelector",
    "assert_no_authority_module",
    "build_compound_with_caller_width",
    "dpc_envelope_from_footprint",
    "evaluate_redteam_attack",
    "require_secondary_footprint_authority",
    "resolve_authenticated_secondary_width",
    "resolve_f23_width",
    "verandah_plan_pdf_bytes",
]
