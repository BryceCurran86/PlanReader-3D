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


@dataclass(frozen=True)
class SourceRcpExistingCeilingHeightLink:
    """Additional height witness on an *already issued* ceiling correspondence.

    This is NOT a new commercial quantity or an assertion about neighbouring
    walls. A caller cannot supply an arbitrary correspondence or native word.
    """
    status: str
    reason_codes: tuple[str, ...]
    canonical_ceiling_id: str = ""
    correspondence_record_id: str = ""
    source_height_record_id: str = ""
    source_sha256: str = ""
    height_mm: int | None = None
    material_code: str = ""
    physical_zone_area_reissued: bool = False
    wall_finish_height_authenticated: bool = False
    commercial_projection_allowed: bool = False
    benchmark_credit: bool = False


def _bbox_fully_in(inner: tuple[float, ...], outer: tuple[float, ...]) -> bool:
    return (
        len(inner) == 4 and len(outer) == 4
        and all(math.isfinite(float(v)) for v in (*inner, *outer))
        and inner[0] >= outer[0] and inner[1] >= outer[1]
        and inner[2] <= outer[2] and inner[3] <= outer[3]
        and inner[0] < inner[2] and inner[1] < inner[3]
        and outer[0] < outer[2] and outer[1] < outer[3]
    )


def bind_original_rcp_height_to_issued_ceiling(
    *,
    source: SourceVisibilityProducer,
    correspondence: Any,
) -> SourceRcpExistingCeilingHeightLink:
    """Cross-check one trusted RCP callout against a *registered*, existing ceiling.

    Explicit opt-in adapter, never a substitute for the legacy original
    ceiling customer issuer. All source words are re-resolved from current
    original PDF source integrity; a forged caller-supplied candidate cannot
    be used as a height receipt.
    """
    from pb_source_cross_view_floor_correspondence_shadow import (
        SourceCrossViewCeilingCorrespondenceRecord,
        get_authenticated_ceiling_correspondence,
    )
    from pb_migration_contracts import EvidenceResolutionStatus

    def blocked(code: str) -> SourceRcpExistingCeilingHeightLink:
        return SourceRcpExistingCeilingHeightLink(status="ABSTAIN", reason_codes=(code,))

    if type(source) is not SourceVisibilityProducer:
        return blocked("original_rcp_height_source_unavailable")
    if type(correspondence) is not SourceCrossViewCeilingCorrespondenceRecord:
        return blocked("original_rcp_ceiling_correspondence_not_source_issued")
    cr = correspondence
    if (
        get_authenticated_ceiling_correspondence(cr.snapshot_id, cr.record_id) is not cr
        or cr.status is not EvidenceResolutionStatus.CORROBORATED
        or cr.commercial_projection_allowed is not True
        or cr.takeoff_eligible is not True
        or cr.authority_blockers
        or not cr.source_sha256 or not cr.document_id
        or not cr.revision_id or not cr.snapshot_id
        or not cr.canonical_ceiling_id or not cr.physical_room_id
        or not cr.source_room_face_record_id
        or type(cr.support_page_id) is not str
        or type(cr.finish_code) is not str or not cr.finish_code
        or type(cr.ceiling_height_mm) not in (int, float)
        or not math.isfinite(cr.ceiling_height_mm)
    ):
        return blocked("original_rcp_ceiling_correspondence_not_source_issued")
    published = source.published_snapshot_for_revision(cr.revision_id)
    if (
        published is None
        or published.revision.document_id != cr.document_id
        or published.revision.source_sha256 != cr.source_sha256
        or published.snapshot.snapshot_id != cr.snapshot_id
        or published.revision.revision_id != cr.revision_id
    ):
        return blocked("original_rcp_ceiling_source_snapshot_mismatch")
    if (
        len(cr.support_dimension_box_pdf_pts) != 4
        or any(not math.isfinite(v) for v in cr.support_dimension_box_pdf_pts)
        or cr.support_dimension_box_pdf_pts[0] >= cr.support_dimension_box_pdf_pts[2]
        or cr.support_dimension_box_pdf_pts[1] >= cr.support_dimension_box_pdf_pts[3]
    ):
        return blocked("original_rcp_ceiling_region_geometry_unavailable")
    receipt = collect_original_rcp_height_material_evidence(
        source=source, revision_id=cr.revision_id, page_id=cr.support_page_id,
    )
    if receipt.reason_codes:
        return blocked("original_rcp_ceiling_height_text_unavailable")
    options = [
        r for r in receipt.candidate_records
        if _bbox_fully_in(r.material_bbox_pdf_pts, cr.support_dimension_box_pdf_pts)
        and _bbox_fully_in(r.height_bbox_pdf_pts, cr.support_dimension_box_pdf_pts)
    ]
    if len(options) != 1:
        return blocked("original_rcp_ceiling_height_zone_not_unique")
    pair = options[0]
    if (
        pair.material_code != cr.finish_code.strip().upper()
        or float(pair.height_mm) != float(cr.ceiling_height_mm)
    ):
        return blocked("original_rcp_ceiling_height_material_source_conflict")
    return SourceRcpExistingCeilingHeightLink(
        status="AUTHENTICATED_EXISTING_CEILING_RCP_HEIGHT_SOURCE",
        reason_codes=("source_height_matched_issued_ceiling_region",),
        canonical_ceiling_id=cr.canonical_ceiling_id,
        correspondence_record_id=cr.record_id,
        source_height_record_id=pair.record_id,
        source_sha256=cr.source_sha256,
        height_mm=pair.height_mm,
        material_code=pair.material_code,
    )
