"""Test support for opening-universe completeness red-team (fixtures only).

No production completeness authority is defined here. Probes and synthetic
universes exist to attack self-certification. Reuses SourceDecodeCoverageRecord
/ EvidenceResolutionStatus vocabulary — does not invent a second framework.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Sequence

import fitz

from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import (
    SourceDecodeCoverageRecord,
    SourceObservationProducer,
)


BASE_SHA = "62a161519e617cdf9ce23069820dbf7c68aaf521"
SHA_A = "a" * 64
SHA_B = "b" * 64


@dataclass(frozen=True)
class CallerCompletenessProbe:
    """Caller-minted completeness claim — must never self-certify authority."""

    is_complete: bool
    snapshot_id: str
    opening_ids: tuple[str, ...]
    wall_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    search_radius_m: float | None = None
    index_hit_count: int | None = None
    semantic_filter_applied: bool = False


@dataclass(frozen=True)
class IndexedPrimitive:
    primitive_id: str
    page_id: str
    geometry: tuple[float, float, float, float]
    layer: str = ""
    clip_known: bool = True
    clip_present: bool = False
    clip: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class UniverseEnumerationClaim:
    """Local enumeration view. Completeness is a claim, never a proof."""

    primitives: tuple[IndexedPrimitive, ...]
    claimed_complete: bool
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_ids: tuple[str, ...]
    viewport_id: str | None
    coverage_state: str
    xobject_traversal_truncated: bool = False
    optional_content_state: str = "known_visible"  # known_visible | ambiguous | unavailable


def coverage_record(
    *,
    document_id: str = "doc-univ",
    revision_id: str = "R1",
    total_pages: int = 1,
    decoded_pages: Sequence[int] = (0,),
    failed_pages: Sequence[int] = (),
) -> SourceDecodeCoverageRecord:
    failed = tuple(failed_pages)
    return SourceDecodeCoverageRecord(
        document_id=document_id,
        revision_id=revision_id,
        total_pages=total_pages,
        decoded_pages=tuple(decoded_pages),
        failed_pages=failed,
        state="complete" if not failed else "partial",
    )


def two_opening_page_pdf_bytes() -> bytes:
    """Page with two visible opening-like gaps (competitors)."""

    doc = fitz.open()
    page = doc.new_page(width=700, height=500)
    # Opening A at x=100–140
    for a, b in (
        ((20.0, 100.0), (100.0, 100.0)),
        ((140.0, 100.0), (220.0, 100.0)),
        ((20.0, 110.0), (100.0, 110.0)),
        ((140.0, 110.0), (220.0, 110.0)),
        ((100.0, 100.0), (100.0, 110.0)),
        ((140.0, 100.0), (140.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    # Opening B (competitor) at x=300–340
    for a, b in (
        ((240.0, 100.0), (300.0, 100.0)),
        ((340.0, 100.0), (420.0, 100.0)),
        ((240.0, 110.0), (300.0, 110.0)),
        ((340.0, 110.0), (420.0, 110.0)),
        ((300.0, 100.0), (300.0, 110.0)),
        ((340.0, 100.0), (340.0, 110.0)),
    ):
        page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def ingest_source(pdf_bytes: bytes, *, document_id: str = "doc-univ"):
    producer = SourceObservationProducer(
        producer_method="opening_universe_completeness_redteam",
        producer_version="v1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=pdf_bytes,
        source_locator=f"memory://{document_id}",
    )
    return producer, published


def snapshot_echo_hash(snapshot_id: str) -> str:
    """Caller-echo of a snapshot id — not a completeness proof."""

    return hashlib.sha256(snapshot_id.encode("utf-8")).hexdigest()


def assert_completeness_capability_locked(
    physical: PhysicalOpeningAuthority | None = None,
) -> None:
    caps = (
        physical.capabilities()
        if physical is not None
        else PhysicalOpeningAuthority.capabilities()
    )
    assert caps["opening_universe_complete"] is False
    assert caps["host_binding"] is False
    assert caps["opening_dimensions"] is False
    assert caps["physical_void"] is False
    assert caps["net_wall_area"] is False


def shuffle_primitives(
    primitives: Sequence[IndexedPrimitive], seed: int = 11
) -> list[IndexedPrimitive]:
    import random

    items = list(primitives)
    random.Random(seed).shuffle(items)
    return items


def split_collinear_equivalent(
    primitive: IndexedPrimitive,
) -> tuple[IndexedPrimitive, IndexedPrimitive]:
    """Two collinear halves — authenticated equivalence must not inflate universe."""

    x0, y0, x1, y1 = primitive.geometry
    mid_x = (x0 + x1) / 2.0
    mid_y = (y0 + y1) / 2.0
    left = IndexedPrimitive(
        primitive_id=f"{primitive.primitive_id}:a",
        page_id=primitive.page_id,
        geometry=(x0, y0, mid_x, mid_y),
        layer=primitive.layer,
        clip_known=primitive.clip_known,
        clip_present=primitive.clip_present,
        clip=primitive.clip,
    )
    right = IndexedPrimitive(
        primitive_id=f"{primitive.primitive_id}:b",
        page_id=primitive.page_id,
        geometry=(mid_x, mid_y, x1, y1),
        layer=primitive.layer,
        clip_known=primitive.clip_known,
        clip_present=primitive.clip_present,
        clip=primitive.clip,
    )
    return left, right


FULL_PAGE_PRIMITIVES: tuple[IndexedPrimitive, ...] = (
    IndexedPrimitive("seg-1", "page-1", (20.0, 100.0, 100.0, 100.0)),
    IndexedPrimitive("seg-2", "page-1", (140.0, 100.0, 220.0, 100.0)),
    IndexedPrimitive("seg-3", "page-1", (100.0, 100.0, 100.0, 110.0)),
    IndexedPrimitive("seg-4", "page-1", (140.0, 100.0, 140.0, 110.0)),
    IndexedPrimitive("seg-5", "page-1", (240.0, 100.0, 300.0, 100.0)),
    IndexedPrimitive("seg-6", "page-1", (340.0, 100.0, 420.0, 100.0)),
)
