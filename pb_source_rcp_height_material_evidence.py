"""Original PlanReader source-trusted RCP height/material candidate receipts.

Ports only the SAME-NATIVE-BLOCK consecutive-line orientation test from the
isolated Next height reader. Unlike Next raw NativeWord, text inputs must be
corroborated by the original SourceVisibilityProducer PDF text-integrity chain.
No ceiling zone, wall height, ceiling area or customer quantity is published.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Sequence

from pb_migration_contracts import stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer

_RCP_MATERIAL = re.compile(r"(?:IPF\d{1,2}|GRID|FPB|WFPB|WPB|CLD|CL0[1-9]|IP)", re.I)
_HEIGHT = re.compile(r"([1-5]\d{3}|6000)(?:\s?mm)?", re.I)
SOURCE_RCP_HEIGHT_UNAVAILABLE = "original_rcp_height_source_unavailable"
SOURCE_RCP_HEIGHT_TEXT_UNTRUSTED = "original_rcp_height_text_untrusted"


@dataclass(frozen=True)
class SourceRcpHeightMaterialCandidate:
    record_id: str
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str
    source_partition_id: str
    block_no: int
    material_line_no: int
    height_line_no: int
    material_code: str
    height_mm: int
    material_observation_id: str
    height_observation_id: str
    material_bbox_pdf_pts: tuple[float, float, float, float]
    height_bbox_pdf_pts: tuple[float, float, float, float]
    status: str = "SOURCE_TEXT_CANDIDATE_ZONE_UNRESOLVED"
    commercial_projection_allowed: bool = False
    benchmark_credit: bool = False


@dataclass(frozen=True)
class SourceRcpHeightMaterialResult:
    source_sha256: str
    page_id: str
    revision_id: str
    snapshot_id: str
    candidate_records: tuple[SourceRcpHeightMaterialCandidate, ...] = ()
    reason_codes: tuple[str, ...] = ()
    physical_ceiling_zone_authenticated: bool = False
    wall_finish_height_authenticated: bool = False
    commercial_projection_allowed: bool = False
    benchmark_credit: bool = False


def _height_mm(text: str) -> int | None:
    hit = _HEIGHT.fullmatch(text.strip())
    if hit is None:
        return None
    value = int(hit.group(1))
    return value if 1500 <= value <= 6000 else None


def _centre(word: Any) -> tuple[float, float]:
    x0, y0, x1, y1 = word.bbox
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _inside(word: Any, viewport: tuple[float, float, float, float] | None) -> bool:
    if viewport is None:
        return True
    x0, y0, x1, y1 = viewport
    a0, b0, a1, b1 = word.bbox
    return a0 >= x0 and b0 >= y0 and a1 <= x1 and b1 <= y1


def _paired(words: Sequence[Any], viewport: tuple[float, float, float, float] | None) -> tuple[tuple[Any, Any, int], ...]:
    """No raw words accepted: caller must supply text-integrity-trusted receipts.

    The helper is deliberately private. Public access always re-resolves
    producer-owned original native observations before invoking it.
    """
    trusted = [w for w in words if w.trusted and _inside(w, viewport)]
    materials = [w for w in trusted if _RCP_MATERIAL.fullmatch(w.text.strip())]
    heights = [(w, n) for w in trusted if (n := _height_mm(w.text)) is not None]
    hits: dict[str, list[Any]] = {}
    reverse: dict[str, list[str]] = {}
    for h, _n in heights:
        hx, hy = _centre(h)
        options = []
        for m in materials:
            if (
                h.page_id != m.page_id
                or h.source_partition_id != m.source_partition_id
                or h.block_no != m.block_no
                or abs(h.line_no - m.line_no) != 1
            ):
                continue
            mx, my = _centre(m)
            rotated = 7 <= hx - mx <= 30 and abs(hy - my) <= 6
            unrotated = 7 <= hy - my <= 30 and abs(hx - mx) <= 6
            if rotated or unrotated:
                options.append(m)
                reverse.setdefault(m.observation_id, []).append(h.observation_id)
        hits[h.observation_id] = options
    return tuple(
        (h, hits[h.observation_id][0], n)
        for h, n in heights
        if len(hits[h.observation_id]) == 1
        and len(reverse[hits[h.observation_id][0].observation_id]) == 1
    )


def collect_original_rcp_height_material_evidence(
    *,
    source: SourceVisibilityProducer,
    revision_id: str,
    page_id: str,
    viewport_bbox_pdf_pts: tuple[float, float, float, float] | None = None,
) -> SourceRcpHeightMaterialResult:
    """Opt-in original-app evidence: NEVER a ceiling-zone or quantity issuer."""
    if (
        type(source) is not SourceVisibilityProducer
        or type(revision_id) is not str or not revision_id
        or type(page_id) is not str or not page_id or not page_id.isascii()
        or not page_id.isdecimal() or int(page_id) < 1
    ):
        raise ValueError("original_rcp_height_selector_invalid")
    if viewport_bbox_pdf_pts is not None:
        v = viewport_bbox_pdf_pts
        if (
            type(v) is not tuple or len(v) != 4
            or any(type(x) not in (int, float) or not math.isfinite(x) for x in v)
            or v[0] >= v[2] or v[1] >= v[3]
        ):
            raise ValueError("original_rcp_height_viewport_invalid")
    published = source.published_snapshot_for_revision(revision_id)
    if published is None or published.revision.revision_id != revision_id:
        return SourceRcpHeightMaterialResult("", page_id, revision_id, "", reason_codes=(SOURCE_RCP_HEIGHT_UNAVAILABLE,))
    revision = published.revision
    snapshot_id = published.snapshot.snapshot_id
    empty = dict(source_sha256=revision.source_sha256, page_id=page_id,
                 revision_id=revision_id, snapshot_id=snapshot_id)
    if page_id not in {str(p) for p in published.coverage.decoded_pages}:
        return SourceRcpHeightMaterialResult(**empty, reason_codes=(SOURCE_RCP_HEIGHT_UNAVAILABLE,))

    # The original app owns all source bytes, clipping/overprint, font maps,
    # revision and native block/line/word receipt provenance.
    from pb_source_material_semantic_authority import _trusted_words_by_page
    try:
        words = _trusted_words_by_page(source, published).get(page_id, ())
    except (RuntimeError, ValueError, TypeError):
        return SourceRcpHeightMaterialResult(**empty, reason_codes=(SOURCE_RCP_HEIGHT_TEXT_UNTRUSTED,))
    if not words or not any(w.trusted for w in words):
        return SourceRcpHeightMaterialResult(**empty, reason_codes=(SOURCE_RCP_HEIGHT_TEXT_UNTRUSTED,))
    original_ids = [w.observation_id for w in words]
    if len(set(original_ids)) != len(original_ids):
        return SourceRcpHeightMaterialResult(**empty, reason_codes=(SOURCE_RCP_HEIGHT_TEXT_UNTRUSTED,))
    candidate_records = []
    for height, material, value in _paired(words, viewport_bbox_pdf_pts):
        payload = dict(
            document_id=revision.document_id,
            revision_id=revision_id, snapshot_id=snapshot_id,
            source_sha256=revision.source_sha256, page_id=page_id,
            source_partition_id=height.source_partition_id, block_no=height.block_no,
            material_line_no=material.line_no, height_line_no=height.line_no,
            material_code=material.text.strip().upper(), height_mm=value,
            material_observation_id=material.observation_id,
            height_observation_id=height.observation_id,
            material_bbox_pdf_pts=material.bbox, height_bbox_pdf_pts=height.bbox,
        )
        candidate_records.append(SourceRcpHeightMaterialCandidate(
            record_id=stable_contract_id("original_rcp_height_candidate", payload, digest_chars=32),
            **payload,
        ))
    candidate_records.sort(key=lambda c: (c.page_id, c.block_no, c.height_line_no, c.height_observation_id))
    if not candidate_records:
        return SourceRcpHeightMaterialResult(**empty, reason_codes=(SOURCE_RCP_HEIGHT_UNAVAILABLE,))
    return SourceRcpHeightMaterialResult(**empty, candidate_records=tuple(candidate_records))
