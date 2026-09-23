"""Corroborated support-count evidence for named secondary plan areas.

This module resolves a support count only from a deliberately strong spatial
pattern on an architectural plan:

1. two independent, parallel figured-dimension chains describe the same
   repeated bay sequence and therefore the same N+1 support count;
2. a named secondary area (currently a verandah/veranda) sits spatially
   between those two chains; and
3. a short, explicit support specification (pole/column/pillar/post/pier)
   sits adjacent to the corroborating chain pair in the same horizontal band.

A page-wide support keyword or a flat repeated-number run is insufficient.
Conflicting chains, missing semantic labels, structural-note prose, or
ambiguous candidates fail closed. No benchmark IDs, expected counts, project
names, or project-specific dimensions are used here.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import re
from typing import Any, Iterable, Optional, Sequence, Tuple

from pb_dimension_chain_evidence_extractor import extract_dimension_chains_from_page
from pb_structural_bay_pillar_count import derive_support_count_from_bay_chain


BBox = Tuple[float, float, float, float]


@dataclass(frozen=True)
class SecondaryAreaSupportEvidence:
    """Resolved, spatially corroborated support evidence."""

    zone_type: str
    support_kind: str
    support_count: int
    bay_count: int
    bay_spans_m: Tuple[float, ...]
    source_pages: Tuple[int, ...]
    chain_ids: Tuple[str, ...]
    zone_bbox: BBox
    support_bbox: BBox
    zone_text: str
    support_text: str
    support_symbol_ids: Tuple[str, ...] = ()
    evidence_mode: str = "text_specification"
    confidence: float = 0.94


@dataclass(frozen=True)
class _TextBlock:
    text: str
    bbox: BBox


@dataclass(frozen=True)
class _BayChain:
    chain_id: str
    support_count: int
    bay_count: int
    bay_spans_m: Tuple[float, ...]
    bbox: BBox


@dataclass(frozen=True)
class _PhysicalSupportGlyph:
    glyph_id: str
    bbox: BBox
    center_x: float
    center_y: float
    width: float
    height: float


def _center_x(bbox: BBox) -> float:
    return (bbox[0] + bbox[2]) / 2.0


def _center_y(bbox: BBox) -> float:
    return (bbox[1] + bbox[3]) / 2.0


def _horizontal_overlap(a: BBox, b: BBox) -> float:
    return max(0.0, min(a[2], b[2]) - max(a[0], b[0]))


def _chain_bbox(chain: Any) -> Optional[BBox]:
    boxes = [obs.bbox for obs in chain.observations if obs.bbox is not None]
    if not boxes:
        return None
    return (
        min(float(b[0]) for b in boxes),
        min(float(b[1]) for b in boxes),
        max(float(b[2]) for b in boxes),
        max(float(b[3]) for b in boxes),
    )


def _text_blocks(page: Any) -> list[_TextBlock]:
    records: list[_TextBlock] = []
    for block in page.get_text("blocks") or []:
        text = " ".join(str(block[4]).split()).strip()
        if not text:
            continue
        records.append(
            _TextBlock(
                text=text,
                bbox=tuple(float(v) for v in block[:4]),
            )
        )
    return records


def _zone_type(text: str) -> Optional[str]:
    if re.search(r"\bveranda(?:h)?\b", text, re.IGNORECASE):
        return "verandah"
    return None


def _support_kind(text: str) -> Optional[str]:
    """Return a support noun only for a short explicit support specification.

    Numbered structural notes such as ``02. 40mm to columns above ground`` are
    intentionally rejected. A genuine support label must be short and carry
    either material/section language or a figured size.
    """
    normalized = " ".join(text.split())
    if len(normalized.split()) > 12:
        return None
    if re.match(r"^\s*\d{1,2}\s*[.)]", normalized):
        return None

    noun_match = re.search(
        r"\b(poles?|columns?|pillars?|posts?|piers?)\b",
        normalized,
        re.IGNORECASE,
    )
    if noun_match is None:
        return None

    has_spec = bool(
        re.search(
            r"\b(?:RHS|SHS|CHS|G\.?\s*I\.?|steel|timber|concrete|masonry)\b|"
            r"\b\d+(?:\.\d+)?\s*mm\b",
            normalized,
            re.IGNORECASE,
        )
    )
    if not has_spec:
        return None

    noun = noun_match.group(1).lower()
    if noun.endswith("s"):
        noun = noun[:-1]
    return noun


def _bay_chains(dimension_chains: Sequence[Any]) -> list[_BayChain]:
    resolved: list[_BayChain] = []
    for chain in dimension_chains:
        if str(getattr(chain, "orientation", "")).lower() != "horizontal":
            continue
        values = tuple(float(obs.value_m) for obs in chain.observations if obs.value_m > 0)
        # This authority-sensitive path deliberately requires at least three
        # bays. Two equal dimensions are too easy to encounter coincidentally.
        bay_result = derive_support_count_from_bay_chain(values, min_bays=3)
        if bay_result.status != "resolved" or bay_result.support_count is None:
            continue
        bbox = _chain_bbox(chain)
        if bbox is None:
            continue
        resolved.append(
            _BayChain(
                chain_id=str(chain.chain_id),
                support_count=int(bay_result.support_count),
                bay_count=int(bay_result.bay_count or len(values)),
                bay_spans_m=tuple(float(v) for v in bay_result.bay_spans_m),
                bbox=bbox,
            )
        )
    return resolved


def _same_repeated_bays(a: _BayChain, b: _BayChain) -> bool:
    if a.support_count != b.support_count or a.bay_count != b.bay_count:
        return False
    if len(a.bay_spans_m) != len(b.bay_spans_m):
        return False
    for av, bv in zip(a.bay_spans_m, b.bay_spans_m):
        mean = (abs(av) + abs(bv)) / 2.0
        if mean <= 0 or abs(av - bv) / mean > 0.03:
            return False

    aw = a.bbox[2] - a.bbox[0]
    bw = b.bbox[2] - b.bbox[0]
    if aw <= 0 or bw <= 0:
        return False
    overlap = _horizontal_overlap(a.bbox, b.bbox)
    if overlap / min(aw, bw) < 0.80:
        return False
    width_ratio = aw / bw
    return 0.80 <= width_ratio <= 1.25


def _candidate_evidence(
    *,
    page_height: float,
    zone: _TextBlock,
    zone_type: str,
    support: _TextBlock,
    support_kind: str,
    a: _BayChain,
    b: _BayChain,
    source_page: int,
) -> Optional[SecondaryAreaSupportEvidence]:
    upper, lower = sorted((a, b), key=lambda chain: _center_y(chain.bbox))
    if not _same_repeated_bays(upper, lower):
        return None

    vertical_gap = lower.bbox[1] - upper.bbox[3]
    if vertical_gap <= 0 or vertical_gap > max(95.0, page_height * 0.20):
        return None

    shared_x0 = max(upper.bbox[0], lower.bbox[0])
    shared_x1 = min(upper.bbox[2], lower.bbox[2])
    if shared_x1 <= shared_x0:
        return None

    # The named secondary area must actually sit between the corroborating
    # chain rows and within their common horizontal extent.
    zone_cx = _center_x(zone.bbox)
    zone_cy = _center_y(zone.bbox)
    if not (upper.bbox[3] <= zone_cy <= lower.bbox[1]):
        return None
    if not (shared_x0 <= zone_cx <= shared_x1):
        return None

    # The support specification must be adjacent to either chain in the same
    # horizontal band. This excludes remote general notes containing words like
    # "columns" from lending semantic authority to the bay geometry.
    support_cx = _center_x(support.bbox)
    if not (shared_x0 <= support_cx <= shared_x1 + (shared_x1 - shared_x0) * 0.10):
        return None
    vertical_distance = min(
        abs(support.bbox[1] - upper.bbox[3]),
        abs(support.bbox[3] - upper.bbox[1]),
        abs(support.bbox[1] - lower.bbox[3]),
        abs(support.bbox[3] - lower.bbox[1]),
    )
    if vertical_distance > max(35.0, page_height * 0.08):
        return None

    return SecondaryAreaSupportEvidence(
        zone_type=zone_type,
        support_kind=support_kind,
        support_count=upper.support_count,
        bay_count=upper.bay_count,
        bay_spans_m=upper.bay_spans_m,
        source_pages=(source_page,),
        chain_ids=(upper.chain_id, lower.chain_id),
        zone_bbox=zone.bbox,
        support_bbox=support.bbox,
        zone_text=zone.text,
        support_text=support.text,
    )


def _physical_support_glyphs(
    page: Any,
    *,
    source_page: int,
) -> list[_PhysicalSupportGlyph]:
    """Return conservative producer-visible filled square/rectangular support glyphs.

    This is geometry candidate generation only. A glyph becomes support evidence
    only after a named secondary zone and an independently figured repeated-bay
    chain corroborate its complete N+1 instance row.
    """
    page_width = float(page.rect.width)
    page_height = float(page.rect.height)
    scale_ref = max(1.0, min(page_width, page_height))
    min_side = scale_ref * 0.00035
    max_side = scale_ref * 0.02

    glyphs: list[_PhysicalSupportGlyph] = []
    for index, drawing in enumerate(page.get_drawings() or ()):
        rect = drawing.get("rect")
        fill = drawing.get("fill")
        if rect is None or fill is None:
            continue
        width = float(rect.width)
        height = float(rect.height)
        if (
            width < min_side
            or height < min_side
            or width > max_side
            or height > max_side
        ):
            continue
        if max(width, height) / min(width, height) > 1.20:
            continue

        kinds = tuple(str(item[0]) for item in (drawing.get("items") or ()))
        rectangular_path = (
            kinds == ("re",)
            or (len(kinds) == 4 and all(kind == "l" for kind in kinds))
        )
        if not rectangular_path:
            continue

        bbox = (
            float(rect.x0),
            float(rect.y0),
            float(rect.x1),
            float(rect.y1),
        )
        glyphs.append(
            _PhysicalSupportGlyph(
                glyph_id=f"page:{source_page}:drawing:{index}",
                bbox=bbox,
                center_x=(bbox[0] + bbox[2]) / 2.0,
                center_y=(bbox[1] + bbox[3]) / 2.0,
                width=width,
                height=height,
            )
        )
    return glyphs


def _physical_support_evidence(
    *,
    page: Any,
    source_page: int,
    zone: _TextBlock,
    zone_type: str,
    bay: _BayChain,
    source_chain: Any,
) -> Optional[SecondaryAreaSupportEvidence]:
    """Bind a complete row of physical support glyphs to one repeated bay chain.

    Positive evidence requires all of the following from the same source page:
    - a named secondary zone;
    - at least three figured adjacent bays in one chain;
    - exactly N+1 same-size physical square/rectangular glyphs in one row;
    - glyph spacings proportional to the figured bay values; and
    - each dimension text centred between the corresponding physical glyph pair.

    The physical glyphs prove instances. The figured chain only corroborates their
    structural relationship; N+1 is never emitted from dimensions alone.
    """
    observations = list(getattr(source_chain, "observations", ()) or ())
    if len(observations) != bay.bay_count or bay.bay_count < 3:
        return None
    if any(getattr(obs, "bbox", None) is None for obs in observations):
        return None

    label_centers = [
        (float(obs.bbox[0]) + float(obs.bbox[2])) / 2.0
        for obs in observations
    ]
    if any(
        right <= left
        for left, right in zip(label_centers, label_centers[1:])
    ):
        return None

    label_gaps = [
        right - left
        for left, right in zip(label_centers, label_centers[1:])
    ]
    if not label_gaps:
        return None
    sorted_label_gaps = sorted(label_gaps)
    median_label_gap = sorted_label_gaps[len(sorted_label_gaps) // 2]
    if median_label_gap <= 0.0:
        return None

    expected_left = label_centers[0] - label_gaps[0] / 2.0
    expected_right = label_centers[-1] + label_gaps[-1] / 2.0
    horizontal_margin = median_label_gap * 0.15
    chain_y = sum(
        (float(obs.bbox[1]) + float(obs.bbox[3])) / 2.0
        for obs in observations
    ) / len(observations)

    page_height = float(page.rect.height)
    glyphs = [
        glyph
        for glyph in _physical_support_glyphs(page, source_page=source_page)
        if expected_left - horizontal_margin
        <= glyph.center_x
        <= expected_right + horizontal_margin
        and abs(glyph.center_y - chain_y) <= page_height * 0.04
    ]
    if len(glyphs) < bay.support_count:
        return None

    zone_cx = _center_x(zone.bbox)
    zone_cy = _center_y(zone.bbox)
    matched_rows: dict[Tuple[str, ...], tuple[_PhysicalSupportGlyph, ...]] = {}

    for seed in glyphs:
        y_tol = max(page_height * 0.002, seed.height * 1.5)
        row = [
            glyph
            for glyph in glyphs
            if abs(glyph.center_y - seed.center_y) <= y_tol
            and abs(glyph.width - seed.width) / max(seed.width, glyph.width) <= 0.10
            and abs(glyph.height - seed.height) / max(seed.height, glyph.height) <= 0.10
        ]
        row = sorted(row, key=lambda glyph: glyph.center_x)
        if len(row) != bay.support_count:
            continue

        glyph_gaps = [
            right.center_x - left.center_x
            for left, right in zip(row, row[1:])
        ]
        if len(glyph_gaps) != bay.bay_count or any(gap <= 0.0 for gap in glyph_gaps):
            continue

        ratios = [
            gap / span
            for gap, span in zip(glyph_gaps, bay.bay_spans_m)
            if span > 0.0
        ]
        if len(ratios) != bay.bay_count:
            continue
        ratio_mean = sum(ratios) / len(ratios)
        if ratio_mean <= 0.0:
            continue
        if max(abs(value - ratio_mean) / ratio_mean for value in ratios) > 0.05:
            continue

        # The printed figured dimension must sit at the midpoint of the same
        # physical pair it measures. This prevents an unrelated repeated symbol
        # row elsewhere on the sheet from borrowing a convenient number chain.
        midpoint_ok = True
        for index, label_x in enumerate(label_centers):
            physical_midpoint = (
                row[index].center_x + row[index + 1].center_x
            ) / 2.0
            tolerance = max(
                row[index].width * 2.0,
                glyph_gaps[index] * 0.08,
            )
            if abs(label_x - physical_midpoint) > tolerance:
                midpoint_ok = False
                break
        if not midpoint_ok:
            continue

        row_y = sum(glyph.center_y for glyph in row) / len(row)
        if abs(zone_cy - row_y) > page_height * 0.08:
            continue
        if not (
            row[0].center_x - horizontal_margin
            <= zone_cx
            <= row[-1].center_x + horizontal_margin
        ):
            continue

        ids = tuple(glyph.glyph_id for glyph in row)
        matched_rows[ids] = tuple(row)

    if len(matched_rows) != 1:
        return None

    ids, row = next(iter(matched_rows.items()))
    support_bbox = (
        min(glyph.bbox[0] for glyph in row),
        min(glyph.bbox[1] for glyph in row),
        max(glyph.bbox[2] for glyph in row),
        max(glyph.bbox[3] for glyph in row),
    )
    return SecondaryAreaSupportEvidence(
        zone_type=zone_type,
        support_kind="physical_support",
        support_count=bay.support_count,
        bay_count=bay.bay_count,
        bay_spans_m=bay.bay_spans_m,
        source_pages=(source_page,),
        chain_ids=(bay.chain_id,),
        zone_bbox=zone.bbox,
        support_bbox=support_bbox,
        zone_text=zone.text,
        support_text="",
        support_symbol_ids=ids,
        evidence_mode="physical_symbol",
        confidence=0.97,
    )


def extract_secondary_area_support_evidence_from_page(
    page: Any,
    *,
    source_page: int,
    dimension_chains: Optional[Sequence[Any]] = None,
) -> Optional[SecondaryAreaSupportEvidence]:
    """Resolve one unambiguous corroborated secondary-area support line."""
    blocks = _text_blocks(page)
    zones = [(block, zt) for block in blocks if (zt := _zone_type(block.text))]
    supports = [
        (block, kind)
        for block in blocks
        if (kind := _support_kind(block.text)) is not None
    ]
    if not zones:
        return None

    chains = list(dimension_chains) if dimension_chains is not None else extract_dimension_chains_from_page(
        page,
        page_num=source_page,
        view_id=f"page_{source_page}",
    )
    bays = _bay_chains(chains)
    if not bays:
        return None

    page_height = float(page.rect.height)
    candidates: list[SecondaryAreaSupportEvidence] = []

    # Existing text-specification path: two independent dimension chains plus
    # a short explicit support specification.
    if supports and len(bays) >= 2:
        for i, first in enumerate(bays):
            for second in bays[i + 1 :]:
                if not _same_repeated_bays(first, second):
                    continue
                for zone, zt in zones:
                    for support, kind in supports:
                        evidence = _candidate_evidence(
                            page_height=page_height,
                            zone=zone,
                            zone_type=zt,
                            support=support,
                            support_kind=kind,
                            a=first,
                            b=second,
                            source_page=source_page,
                        )
                        if evidence is not None:
                            candidates.append(evidence)

    # Physical-instance path: one figured repeated-bay chain is sufficient only
    # when the drawing itself independently contains the complete N+1 row of
    # matching support glyphs at that named secondary zone.
    source_by_id = {str(chain.chain_id): chain for chain in chains}
    for bay in bays:
        source_chain = source_by_id.get(bay.chain_id)
        if source_chain is None:
            continue
        for zone, zt in zones:
            evidence = _physical_support_evidence(
                page=page,
                source_page=source_page,
                zone=zone,
                zone_type=zt,
                bay=bay,
                source_chain=source_chain,
            )
            if evidence is not None:
                candidates.append(evidence)

    if not candidates:
        return None

    semantic_keys = {(c.zone_type, c.support_count) for c in candidates}
    if len(semantic_keys) != 1:
        return None

    # Two different physical instance universes with the same count are still
    # ambiguous. Count agreement alone is not permission to choose one.
    physical_sets = {
        tuple(c.support_symbol_ids)
        for c in candidates
        if c.evidence_mode == "physical_symbol"
    }
    if len(physical_sets) > 1:
        return None

    chain_lookup = {b.chain_id: b for b in bays}

    def proximity(candidate: SecondaryAreaSupportEvidence) -> float:
        chain_pair = [
            chain_lookup[cid]
            for cid in candidate.chain_ids
            if cid in chain_lookup
        ]
        if not chain_pair:
            return float("inf")
        return sum(
            abs(_center_y(chain.bbox) - _center_y(candidate.zone_bbox))
            for chain in chain_pair
        )

    # When a complete physical instance row agrees with text-specification
    # evidence, prefer the physical row because it proves instance existence.
    return min(
        candidates,
        key=lambda candidate: (
            0 if candidate.evidence_mode == "physical_symbol" else 1,
            proximity(candidate),
        ),
    )


def resolve_document_secondary_area_support_evidence(
    evidences: Iterable[SecondaryAreaSupportEvidence],
) -> Optional[SecondaryAreaSupportEvidence]:
    """Resolve repeated page evidence only when all pages agree.

    A multi-building package can legitimately contain different verandah
    support counts. Such a document is ambiguous for the current single-tag
    takeoff model and therefore remains unresolved rather than choosing one.
    """
    rows = list(evidences)
    if not rows:
        return None
    keys = {(row.zone_type, row.support_count) for row in rows}
    if len(keys) != 1:
        return None

    physical_sets = {
        tuple(row.support_symbol_ids)
        for row in rows
        if row.evidence_mode == "physical_symbol"
    }
    if len(physical_sets) > 1:
        return None

    chosen = max(rows, key=lambda row: row.confidence)
    pages = tuple(sorted({page for row in rows for page in row.source_pages}))
    chain_ids = tuple(dict.fromkeys(cid for row in rows for cid in row.chain_ids))
    support_symbol_ids = tuple(
        dict.fromkeys(
            symbol_id
            for row in rows
            for symbol_id in row.support_symbol_ids
        )
    )
    evidence_modes = {row.evidence_mode for row in rows}
    evidence_mode = (
        next(iter(evidence_modes))
        if len(evidence_modes) == 1
        else "corroborated_mixed"
    )
    return replace(
        chosen,
        source_pages=pages,
        chain_ids=chain_ids,
        support_symbol_ids=support_symbol_ids,
        evidence_mode=evidence_mode,
    )
