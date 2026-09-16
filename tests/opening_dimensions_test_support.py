"""Test support for opening-dimension authority red-team (fixtures only).

No production dimension resolver is defined here. Fixtures build synthetic PDF
bytes and document ownership selectors for fail-closed / expected-RED tests.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Sequence

import fitz

from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_visibility_authority import SourceVisibilityProducer


BASE_SHA = "507c57db16be515e2432c695341bdea1e71b3fd7"

# Known unsafe legacy default from pb_opening_deduction_v175.parse_opening_dimensions.
LEGACY_DEFAULT_HEIGHT_MM = 2040.0
LEGACY_DEFAULT_WIDTH_MM = 820.0


@dataclass(frozen=True)
class OpeningDimensionProbe:
    """Caller-facing probe record — must never self-certify dimension authority."""

    opening_id: str
    width_mm: float | None
    height_mm: float | None
    tag: str
    page_id: str
    document_id: str
    geometry: tuple[float, float, float, float]
    source_ids: tuple[str, ...]


def transform_point(
    point: tuple[float, float],
    *,
    angle_deg: float = 0.0,
    scale: float = 1.0,
    offset: tuple[float, float] = (0.0, 0.0),
) -> tuple[float, float]:
    angle = math.radians(angle_deg)
    x, y = point
    xr = scale * (x * math.cos(angle) - y * math.sin(angle)) + offset[0]
    yr = scale * (x * math.sin(angle) + y * math.cos(angle)) + offset[1]
    return (xr, yr)


def visible_opening_pdf_bytes(
    *,
    angle_deg: float = 0.0,
    scale: float = 1.0,
    offset: tuple[float, float] = (0.0, 0.0),
    extra_text: Sequence[str] = (),
    dimension_text: str | None = None,
    dimension_anchor: tuple[float, float] = (100.0, 80.0),
) -> bytes:
    """Six-segment visible opening + optional nearby dimension text (not witnesses)."""

    segments = (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    )
    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    for first, second in segments:
        a = transform_point(first, angle_deg=angle_deg, scale=scale, offset=offset)
        b = transform_point(second, angle_deg=angle_deg, scale=scale, offset=offset)
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    for index, text in enumerate(extra_text):
        page.insert_text((30, 40 + 18 * index), text)
    if dimension_text:
        anchor = transform_point(
            dimension_anchor, angle_deg=angle_deg, scale=scale, offset=offset
        )
        page.insert_text(fitz.Point(*anchor), dimension_text)
    payload = doc.tobytes()
    doc.close()
    return payload


def figure_witness_opening_pdf_bytes(
    *,
    width_label: str = "900",
    with_witness_lines: bool = True,
    obstructing_furniture: bool = False,
) -> bytes:
    """Opening gap with optional horizontal dim line + vertical witnesses on jambs."""

    doc = fitz.open()
    page = doc.new_page(width=700, height=700)
    # Wall continuation + jambs (same topology as G17 visible positive).
    for a, b in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    if with_witness_lines:
        # Dimension line spanning jambs + short witness ticks.
        page.draw_line(
            fitz.Point(100.0, 70.0), fitz.Point(140.0, 70.0), color=(0, 0, 0), width=0.5
        )
        page.draw_line(
            fitz.Point(100.0, 70.0), fitz.Point(100.0, 100.0), color=(0, 0, 0), width=0.5
        )
        page.draw_line(
            fitz.Point(140.0, 70.0), fitz.Point(140.0, 100.0), color=(0, 0, 0), width=0.5
        )
        page.insert_text(fitz.Point(112.0, 65.0), width_label)
    else:
        page.insert_text(fitz.Point(112.0, 65.0), width_label)
    if obstructing_furniture:
        page.draw_rect(fitz.Rect(110.0, 75.0, 130.0, 95.0), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def schedule_only_pdf_bytes(rows: Iterable[str]) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((40, 40), "DOOR SCHEDULE")
    for index, row in enumerate(rows):
        page.insert_text((40, 70 + 20 * index), row)
    payload = doc.tobytes()
    doc.close()
    return payload


def ingest_visible(payload: bytes, *, document_id: str):
    producer = SourceVisibilityProducer(
        producer_method="opening-dimension-redteam",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=payload,
        source_locator=f"memory://{document_id}.pdf",
    )
    visibility = producer.authority()
    physical = PhysicalOpeningAuthority(visibility)
    return producer, published, visibility, physical


def assert_dimension_capability_locked(
    physical: PhysicalOpeningAuthority | None = None,
) -> None:
    caps = (physical or PhysicalOpeningAuthority).capabilities()
    assert caps["opening_dimensions"] is False
    assert caps["physical_opening_existence"] is True
    assert caps["physical_opening_identity"] is True
    assert caps["host_binding"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False
