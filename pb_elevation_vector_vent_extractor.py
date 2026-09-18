"""Generic elevation vector vent symbol learner and extractor (Phase F.8/F.24).

Identifies physical brick/permanent ventilation openings across facade sheets:
1. Identifies explicit native ``PV`` / ``P.V`` callout labels, excluding
   drafting-legend definitions (e.g. "P.V denotes permanent vents").
2. Extracts candidate vector drawing geometry (rectangles, grille lines, paths)
   adjacent to labeled instances.
3. Learns the repeatable vector geometry signature when >= 3 independently
   labeled instances share a consistent, unambiguous signature.
4. Scans other resolved/derived elevation viewports on the sheet for matching
   unlabeled physical vent symbols.
5. Spatially deduplicates labeled symbols against their callout text so instances
   are never counted twice.
6. Fails closed against risky extrapolation if labeled instances are ambiguous,
   fewer than 3, or exhibit competing signatures.
7. Aggregates distinct physical vent occurrences into a single coherent authority.

Safety & Generic Rules:
- No benchmark names, project names, sheet IDs, or hardcoded coordinates.
- No guessing or doubling quantities from elevation symmetry alone.
- Preserves the grammatical exclusion of "<abbrev> denotes <meaning>" legends.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import fitz

from pb_viewport_segmentation import SegmentedViewport, segment_page_viewports


@dataclass(frozen=True)
class VectorVentSymbolSignature:
    """Repeatable geometric signature of a vector vent symbol."""
    width_pt: float
    height_pt: float
    aspect_ratio: float
    path_item_count: int
    has_fill: bool
    has_stroke: bool
    stroke_width: float

    def matches(
        self,
        candidate: CandidateVectorSymbol,
        dim_tol: float = 0.20,
        aspect_tol: float = 0.25,
    ) -> bool:
        """Check whether candidate matches this signature within tolerance."""
        # Check dimensions
        if self.width_pt > 0:
            w_err = abs(candidate.width_pt - self.width_pt) / self.width_pt
            if w_err > dim_tol:
                return False
        if self.height_pt > 0:
            h_err = abs(candidate.height_pt - self.height_pt) / self.height_pt
            if h_err > dim_tol:
                return False

        # Check aspect ratio
        if self.aspect_ratio > 0 and candidate.aspect_ratio > 0:
            ar_err = abs(candidate.aspect_ratio - self.aspect_ratio) / self.aspect_ratio
            if ar_err > aspect_tol:
                return False

        # Structural fill/stroke agreement
        if self.has_fill != candidate.has_fill:
            return False

        return True


@dataclass(frozen=True)
class CandidateVectorSymbol:
    """A candidate vector graphic symbol extracted from PDF vector drawings."""
    bbox: Tuple[float, float, float, float]  # (x0, y0, x1, y1)
    width_pt: float
    height_pt: float
    aspect_ratio: float
    path_item_count: int
    has_fill: bool
    has_stroke: bool
    stroke_width: float

    @property
    def centroid(self) -> Tuple[float, float]:
        return (
            (self.bbox[0] + self.bbox[2]) / 2.0,
            (self.bbox[1] + self.bbox[3]) / 2.0,
        )


@dataclass
class ElevationVentResult:
    """Extraction result for permanent / brick vents on an elevation sheet."""
    tag: str = "brick_vents"
    trade_type: str = "walls"
    description: str = ""
    quantity: float = 0.0
    unit: str = "NO"
    source_page: int = 1
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 0.88
    evidence_text: str = ""
    labeled_callout_count: int = 0
    unlabeled_vector_count: int = 0
    learned_signature: Optional[VectorVentSymbolSignature] = None
    is_vector_augmented: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def extract_verified_pv_callouts(page: fitz.Page) -> List[Tuple[float, float, float, float, str]]:
    """Extract verified permanent-vent callouts, excluding legend definitions.

    Recognizes both the abbreviated "PV"/"P.V" callout form and the
    spelled-out "Permanent Vent"/"Brick Vent" phrase form -- the legacy
    page-loop extractor this module replaced matched both
    (``\\bPV\\b|\\bPermanent Vent\\b|\\bBrick Vent\\b``); only matching the
    abbreviation would silently drop any drawing set that spells vents out
    in full without ever using "PV".

    Returns list of (x0, y0, x1, y1, matched_text).
    """
    all_words = page.get_text("words")

    def _word_at(block_no: int, line_no: int, word_no: int) -> Optional[tuple]:
        for other in all_words:
            if other[5] == block_no and other[6] == line_no and other[7] == word_no:
                return other
        return None

    def _clean(word: Optional[tuple]) -> str:
        return str(word[4]).strip().lower().rstrip(".,:;") if word is not None else ""

    verified: List[Tuple[float, float, float, float, str]] = []
    seen_spans: set = set()
    for w in all_words:
        txt = str(w[4]).strip()
        block_no, line_no, word_no = w[5], w[6], w[7]
        span_key = (block_no, line_no, word_no)
        if span_key in seen_spans:
            continue

        if re.match(r"^(?:PV|P\.V)$", txt, re.I):
            if _clean(_word_at(block_no, line_no, word_no + 1)) == "denotes":
                continue
            seen_spans.add(span_key)
            verified.append((float(w[0]), float(w[1]), float(w[2]), float(w[3]), txt))
            continue

        if txt.strip(".,:;").lower() in ("permanent", "brick"):
            next_w = _word_at(block_no, line_no, word_no + 1)
            if _clean(next_w) != "vent":
                continue
            if _clean(_word_at(block_no, line_no, word_no + 2)) == "denotes":
                continue
            seen_spans.add(span_key)
            seen_spans.add((block_no, line_no, word_no + 1))
            x0 = min(float(w[0]), float(next_w[0]))
            y0 = min(float(w[1]), float(next_w[1]))
            x1 = max(float(w[2]), float(next_w[2]))
            y1 = max(float(w[3]), float(next_w[3]))
            verified.append((x0, y0, x1, y1, f"{txt} {next_w[4]}"))
    return verified


def _extract_candidate_vector_symbols(page: fitz.Page) -> List[CandidateVectorSymbol]:
    """Extract discrete small candidate vector symbols from page drawings."""
    candidates: List[CandidateVectorSymbol] = []
    drawings = page.get_drawings()

    for d in drawings:
        d_rect = d.get("rect")
        if d_rect is None:
            continue
        items = d.get("items", [])
        has_fill = d.get("fill") is not None
        has_stroke = d.get("color") is not None
        stroke_width = float(d.get("width") or 1.0)

        # Check discrete rectangles
        for it in items:
            if it[0] == "re":
                r = it[1]
                w = float(r.width)
                h = float(r.height)
                if w <= 0 or h <= 0:
                    continue
                # Vents are physical openings, typically between 2 pt and 80 pt
                # Exclude huge framing lines, page borders, title blocks
                if 2.0 <= w <= 80.0 and 2.0 <= h <= 60.0:
                    # Exclude extreme hairline underlines (e.g. width=50, height=0.5)
                    ar = w / h if h > 0 else 1.0
                    if ar <= 12.0 and (1.0 / ar) <= 12.0:
                        candidates.append(
                            CandidateVectorSymbol(
                                bbox=(float(r.x0), float(r.y0), float(r.x1), float(r.y1)),
                                width_pt=w,
                                height_pt=h,
                                aspect_ratio=ar,
                                path_item_count=1,
                                has_fill=has_fill,
                                has_stroke=has_stroke,
                                stroke_width=stroke_width,
                            )
                        )

        # Also check whole drawing group if it represents a composite small shape/grille
        dw = float(d_rect.width)
        dh = float(d_rect.height)
        if 2.0 <= dw <= 80.0 and 2.0 <= dh <= 60.0:
            dar = dw / dh if dh > 0 else 1.0
            if dar <= 12.0 and (1.0 / dar) <= 12.0:
                # Avoid duplicate if already covered by an exact matching 're'
                already_covered = any(
                    abs(c.bbox[0] - d_rect.x0) < 1.0
                    and abs(c.bbox[1] - d_rect.y0) < 1.0
                    and abs(c.bbox[2] - d_rect.x1) < 1.0
                    and abs(c.bbox[3] - d_rect.y1) < 1.0
                    for c in candidates
                )
                if not already_covered:
                    candidates.append(
                        CandidateVectorSymbol(
                            bbox=(float(d_rect.x0), float(d_rect.y0), float(d_rect.x1), float(d_rect.y1)),
                            width_pt=dw,
                            height_pt=dh,
                            aspect_ratio=dar,
                            path_item_count=len(items),
                            has_fill=has_fill,
                            has_stroke=has_stroke,
                            stroke_width=stroke_width,
                        )
                    )

    return candidates


def _distance(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p1[0] - p2[0], p1[1] - p2[1])


def learn_vector_vent_signature(
    candidates: Sequence[CandidateVectorSymbol],
    labeled_callouts: Sequence[Tuple[float, float, float, float, str]],
    search_radius_pt: float = 40.0,
    min_labeled_instances: int = 3,
) -> Optional[VectorVentSymbolSignature]:
    """Learn repeatable vector vent symbol signature from labeled callouts.

    Rules:
    - Requires at least `min_labeled_instances` (>=3) independently labeled callouts.
    - Each labeled callout must associate with a nearby candidate symbol.
    - Labeled symbols must agree in dimensions and characteristics within tolerance.
    - If ambiguous or competing signatures exist among labeled instances, fails closed (None).
    """
    if len(labeled_callouts) < min_labeled_instances:
        return None

    # For each callout, find candidate symbols within search radius
    callout_candidates: List[List[CandidateVectorSymbol]] = []
    for c_box in labeled_callouts:
        c_center = ((c_box[0] + c_box[2]) / 2.0, (c_box[1] + c_box[3]) / 2.0)
        nearby = [
            cand for cand in candidates
            if _distance(cand.centroid, c_center) <= search_radius_pt
        ]
        callout_candidates.append(nearby)

    # If too few callouts have any candidate symbol nearby, no signature can be learned
    associated_callouts = [c for c in callout_candidates if c]
    if len(associated_callouts) < min_labeled_instances:
        return None

    # Flatten candidates associated with callouts to find clusters
    all_associated = [cand for sublist in callout_candidates for cand in sublist]
    if not all_associated:
        return None

    # Group candidates into clusters by geometry
    clusters: List[List[CandidateVectorSymbol]] = []
    for cand in all_associated:
        matched_cluster = False
        for cl in clusters:
            rep = cl[0]
            # Compare dimensions within 20%
            w_err = abs(cand.width_pt - rep.width_pt) / rep.width_pt if rep.width_pt > 0 else 1.0
            h_err = abs(cand.height_pt - rep.height_pt) / rep.height_pt if rep.height_pt > 0 else 1.0
            if w_err <= 0.20 and h_err <= 0.20 and cand.has_fill == rep.has_fill:
                cl.append(cand)
                matched_cluster = True
                break
        if not matched_cluster:
            clusters.append([cand])

    # Count how many distinct callouts support each cluster
    cluster_scores: List[Tuple[int, List[CandidateVectorSymbol]]] = []
    for cl in clusters:
        rep = cl[0]
        supporting_callout_count = 0
        for nearby in callout_candidates:
            if any(
                abs(cand.width_pt - rep.width_pt) / rep.width_pt <= 0.20
                and abs(cand.height_pt - rep.height_pt) / rep.height_pt <= 0.20
                and cand.has_fill == rep.has_fill
                for cand in nearby
            ):
                supporting_callout_count += 1
        cluster_scores.append((supporting_callout_count, cl))

    # Sort clusters by support
    cluster_scores.sort(key=lambda x: x[0], reverse=True)
    top_support, top_cluster = cluster_scores[0]

    if top_support < min_labeled_instances:
        return None

    # Check for competing signatures: if another cluster has >= 2 supporting callouts
    # and comparable support, fail closed against ambiguity
    if len(cluster_scores) > 1:
        second_support, _ = cluster_scores[1]
        if second_support >= 2 and second_support >= top_support * 0.7:
            return None

    # Build signature from top cluster
    avg_w = sum(c.width_pt for c in top_cluster) / len(top_cluster)
    avg_h = sum(c.height_pt for c in top_cluster) / len(top_cluster)
    avg_ar = avg_w / avg_h if avg_h > 0 else 1.0
    rep = top_cluster[0]

    return VectorVentSymbolSignature(
        width_pt=round(avg_w, 2),
        height_pt=round(avg_h, 2),
        aspect_ratio=round(avg_ar, 2),
        path_item_count=rep.path_item_count,
        has_fill=rep.has_fill,
        has_stroke=rep.has_stroke,
        stroke_width=rep.stroke_width,
    )


def detect_unlabeled_vent_symbols(
    candidates: Sequence[CandidateVectorSymbol],
    signature: VectorVentSymbolSignature,
    labeled_callouts: Sequence[Tuple[float, float, float, float, str]],
    elevation_viewports: Sequence[SegmentedViewport],
    page_rect: fitz.Rect,
    search_radius_pt: float = 40.0,
) -> List[CandidateVectorSymbol]:
    """Detect matching unlabeled vent symbols across elevation viewports.

    Rules:
    - Must match learned signature within tolerance.
    - Must be inside a genuinely segmented elevation viewport. There is no
      fallback to "anywhere on the page" when viewport segmentation is
      empty or unavailable: labeled callouts alone are explicit text
      evidence, but extrapolating unlabeled geometry across a whole page
      with no proven elevation boundary risks matching unrelated symbols
      (furniture, in-plan openings, schedule-table graphics) that merely
      share the learned symbol's size.
    - Must not be near any labeled callout (to avoid double-counting).
    - Deduplicates overlapping / identical symbols (< 2 pt).
    """
    callout_centers = [
        ((c[0] + c[2]) / 2.0, (c[1] + c[3]) / 2.0)
        for c in labeled_callouts
    ]

    matched_unlabeled: List[CandidateVectorSymbol] = []

    for cand in candidates:
        if not signature.matches(cand):
            continue

        # Check if cand is near any labeled callout (already paired with a label!)
        if any(_distance(cand.centroid, cc) <= search_radius_pt for cc in callout_centers):
            continue

        # Check if cand is within a genuinely segmented elevation viewport.
        # No page-wide fallback: an empty/failed segmentation means this
        # symbol's containment in a real elevation is unproven, so it is
        # never counted -- not "probably fine because it's not in the
        # margin."
        in_elevation_view = False
        for vp in elevation_viewports:
            if vp.view_type == "elevation" and vp.bounding_box:
                vx0, vy0, vx1, vy1 = vp.bounding_box
                cx, cy = cand.centroid
                if vx0 <= cx <= vx1 and vy0 <= cy <= vy1:
                    in_elevation_view = True
                    break

        if not in_elevation_view:
            continue

        # Spatial deduplication: avoid adding overlapping duplicates
        is_dup = any(
            _distance(cand.centroid, existing.centroid) < 2.0
            for existing in matched_unlabeled
        )
        if not is_dup:
            matched_unlabeled.append(cand)

    return matched_unlabeled


def extract_elevation_vector_vents(
    page: fitz.Page,
    page_num: int = 1,
) -> Optional[ElevationVentResult]:
    """Extract physical brick/permanent vents from an elevation sheet.

    Pipeline:
    1. Extract verified native PV/P.V callouts (excluding legend definitions).
    2. Check if sheet contains facade/elevation context.
    3. Segment page viewports.
    4. Extract candidate vector symbols.
    5. Attempt to learn signature from labeled instances.
    6. If signature learned: discover unlabeled instances in other elevation viewports.
    7. Spatially combine labeled callouts and unlabeled symbols into a total count.
    8. If no signature learned (no vector symbols or ambiguous): fall back to verified
       labeled callouts count (>=2).
    """
    page_text_lower = page.get_text().lower()
    is_facade_sheet = any(
        k in page_text_lower
        for k in ("elevation", "facade", "façade", "section", "schedule", "plan")
    )
    if not is_facade_sheet:
        return None

    # Step 1: Verified callouts
    labeled_callouts = extract_verified_pv_callouts(page)

    # Step 2: Segment viewports
    try:
        viewports = segment_page_viewports(page, page_number=page_num)
    except Exception:
        viewports = []

    # Step 3: Candidate vector symbols
    candidates = _extract_candidate_vector_symbols(page)

    # Step 4: Learn signature if possible
    signature = learn_vector_vent_signature(candidates, labeled_callouts)

    unlabeled_matched: List[CandidateVectorSymbol] = []
    if signature is not None:
        unlabeled_matched = detect_unlabeled_vent_symbols(
            candidates=candidates,
            signature=signature,
            labeled_callouts=labeled_callouts,
            elevation_viewports=viewports,
            page_rect=page.rect,
        )

    total_count = len(labeled_callouts) + len(unlabeled_matched)

    # Must meet threshold (>= 2) to publish a valid vent count
    if total_count < 2:
        return None

    # Compute overall bounding box
    all_boxes: List[Tuple[float, float, float, float]] = [
        (c[0], c[1], c[2], c[3]) for c in labeled_callouts
    ] + [cand.bbox for cand in unlabeled_matched]

    x0 = min(b[0] for b in all_boxes)
    y0 = min(b[1] for b in all_boxes)
    x1 = max(b[2] for b in all_boxes)
    y1 = max(b[3] for b in all_boxes)

    is_augmented = len(unlabeled_matched) > 0 and signature is not None

    if is_augmented:
        evidence = (
            f"{len(labeled_callouts)} labeled PV callouts + "
            f"{len(unlabeled_matched)} matched vector vent symbols on elevation sheet"
        )
        desc = (
            f"Precast / brick ventilation openings "
            f"({total_count} No total: {len(labeled_callouts)} labeled + {len(unlabeled_matched)} vector symbols)"
        )
        confidence = 0.92
    else:
        evidence = f"{len(labeled_callouts)} PV callouts detected on facade"
        desc = f"Permanent / brick vents ({total_count} No on page {page_num})"
        confidence = 0.88

    return ElevationVentResult(
        tag="brick_vents",
        trade_type="walls",
        description=desc,
        quantity=float(total_count),
        unit="NO",
        source_page=page_num,
        bbox=(x0, y0, x1, y1),
        confidence=confidence,
        evidence_text=evidence,
        labeled_callout_count=len(labeled_callouts),
        unlabeled_vector_count=len(unlabeled_matched),
        learned_signature=signature,
        is_vector_augmented=is_augmented,
        metadata={
            "learned_signature": signature.__dict__ if signature else None,
            "labeled_callout_count": len(labeled_callouts),
            "unlabeled_vector_count": len(unlabeled_matched),
            "viewport_count": len(viewports),
        },
    )
