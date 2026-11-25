"""Item 22: Unmarked opening native figure-line dimension witness shadow.

Proves opening width/height dimension witnesses for UNMARKED openings (no printed
D/W schedule mark) directly from native vector figure lines:
- A dimension rail parallel to the opening jamb axis;
- Two perpendicular witness/extension lines connecting the rail endpoints to the
  two proven opening jambs;
- Producer-trusted numeric figure text bound to that exact rail.

Strictly abstains on ambiguous or non-opening-scoped dimensions:
- Overall wall/room chain dimensions whose witness lines extend outside the jambs;
- Proximity-only floating numbers lacking figure-line & dual-witness topology;
- Competing parallel rails with conflicting values;
- Unlabeled dual-axis pairs or non-numeric/ambiguous text;
- Cross-viewport or cross-revision lines.
Never converts raw PDF gap to millimetres when no figure line exists.
Pure Euclidean geometry -> invariant under rotation and translation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Sequence


_ANGLE_TOL_DEG = 5.0
_JAMB_ATTACH_TOL_PTS = 3.5
_RAIL_ENDPOINT_TOL_PTS = 3.5
_TEXT_RAIL_DIST_TOL_PTS = 14.0
_DIM_CONFLICT_TOL_MM = 2.0

_SINGLE_MM_RE = re.compile(r"^\s*(\d{3,5}(?:\.\d+)?)\s*(mm)?\s*$", re.IGNORECASE)
_SINGLE_M_RE = re.compile(r"^\s*(\d+(?:\.\d{1,3}))\s*m\s*$", re.IGNORECASE)
_AMBIGUOUS_TEXT_RE = re.compile(r"[x×/\-±~]|approx|typ|min|max|tbc|eq|varies", re.IGNORECASE)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _seg_unit(p0: tuple[float, float], p1: tuple[float, float]) -> tuple[float, float, float]:
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        return (0.0, 0.0, 0.0)
    return (dx / length, dy / length, length)


def _angle_deg(u: tuple[float, float], v: tuple[float, float]) -> float:
    dot = abs(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))
    return math.degrees(math.acos(dot))


def _point_to_seg_dist(pt: tuple[float, float], a: tuple[float, float], b: tuple[float, float]) -> float:
    vx, vy = b[0] - a[0], b[1] - a[1]
    l2 = vx * vx + vy * vy
    if l2 <= 1e-12:
        return _dist(pt, a)
    t = max(0.0, min(1.0, ((pt[0] - a[0]) * vx + (pt[1] - a[1]) * vy) / l2))
    return _dist(pt, (a[0] + t * vx, a[1] + t * vy))


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class FigureLineageRef:
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str

    def normalized(self) -> tuple[str, str, str, str, str]:
        return (
            _clean(self.document_id),
            _clean(self.revision_id),
            _clean(self.source_sha256).lower(),
            _clean(self.page_id),
            _clean(self.viewport_id),
        )

    def is_valid(self) -> bool:
        return all(bool(v) for v in self.normalized())


@dataclass(frozen=True)
class UnmarkedOpeningTarget:
    opening_id: str
    lineage: FigureLineageRef
    jamb_a_pt: tuple[float, float]
    jamb_b_pt: tuple[float, float]


@dataclass(frozen=True)
class NativeVectorSegment:
    segment_id: str
    p0: tuple[float, float]
    p1: tuple[float, float]
    lineage: FigureLineageRef


@dataclass(frozen=True)
class TrustedFigureText:
    text_id: str
    text: str
    center_pt: tuple[float, float]
    lineage: FigureLineageRef
    text_integrity_trusted: bool = True


@dataclass(frozen=True)
class UnmarkedOpeningFigureWitnessResult:
    witness_id: str
    opening_id: str
    proven: bool
    abstained: bool
    axis: str
    value_mm: float | None
    rail_segment_id: str | None
    witness_segment_ids: tuple[str, ...]
    text_observation_id: str | None
    blocking_reasons: tuple[str, ...]
    gap_scale_conversion_forbidden: bool = True
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "witness_id": self.witness_id,
            "opening_id": self.opening_id,
            "proven": self.proven,
            "abstained": self.abstained,
            "axis": self.axis,
            "value_mm": self.value_mm,
            "rail_segment_id": self.rail_segment_id,
            "witness_segment_ids": list(self.witness_segment_ids),
            "text_observation_id": self.text_observation_id,
            "blocking_reasons": list(self.blocking_reasons),
            "gap_scale_conversion_forbidden": True,
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def parse_unambiguous_figure_mm(text: str) -> tuple[float | None, str | None]:
    """Parse a single unambiguous numeric dimension figure in mm."""
    cleaned = _clean(text)
    if not cleaned:
        return (None, "empty_figure_text")
    if _AMBIGUOUS_TEXT_RE.search(cleaned):
        return (None, "ambiguous_figure_text")
    m_mm = _SINGLE_MM_RE.match(cleaned)
    if m_mm:
        val = float(m_mm.group(1))
        if 150.0 <= val <= 20000.0:
            return (round(val, 2), None)
        return (None, "out_of_range_opening_figure")
    m_m = _SINGLE_M_RE.match(cleaned)
    if m_m:
        val = float(m_m.group(1)) * 1000.0
        if 150.0 <= val <= 20000.0:
            return (round(val, 2), None)
        return (None, "out_of_range_opening_figure")
    return (None, "unparseable_figure_text")


def prove_unmarked_opening_figure_witness_shadow(
    opening: UnmarkedOpeningTarget,
    segments: Sequence[NativeVectorSegment],
    texts: Sequence[TrustedFigureText],
    *,
    axis_label: str = "width",
) -> UnmarkedOpeningFigureWitnessResult:
    """Prove unmarked opening width/height witness from native figure lines or abstain."""
    opening_id = _clean(opening.opening_id)
    if not opening_id:
        raise ValueError("opening_id is required")
    if not opening.lineage.is_valid():
        raise ValueError("opening.lineage must be valid")

    ux, uy, span = _seg_unit(opening.jamb_a_pt, opening.jamb_b_pt)
    if span <= 1e-6:
        raise ValueError("opening jamb span must be positive")
    axis = (ux, uy)
    normal = (-uy, ux)
    center = (
        (opening.jamb_a_pt[0] + opening.jamb_b_pt[0]) * 0.5,
        (opening.jamb_a_pt[1] + opening.jamb_b_pt[1]) * 0.5,
    )
    half_span = span * 0.5
    open_lin = opening.lineage.normalized()

    reasons: list[str] = []

    local_segs = [s for s in segments if s.lineage.is_valid() and s.lineage.normalized() == open_lin]
    local_texts = [t for t in texts if t.lineage.is_valid() and t.lineage.normalized() == open_lin]

    if len(local_segs) < len(segments) or len(local_texts) < len(texts):
        reasons.append("cross_viewport_or_lineage_primitives_ignored")

    # Classify candidate rails (parallel to opening axis) and candidate witness lines (perpendicular)
    rails: list[NativeVectorSegment] = []
    witness_lines: list[NativeVectorSegment] = []
    for s in local_segs:
        su_x, su_y, slen = _seg_unit(s.p0, s.p1)
        if slen <= 1e-6:
            continue
        ang_axis = _angle_deg((su_x, su_y), axis)
        ang_norm = _angle_deg((su_x, su_y), normal)
        if ang_axis <= _ANGLE_TOL_DEG:
            rails.append(s)
        elif ang_norm <= _ANGLE_TOL_DEG:
            witness_lines.append(s)

    proven_candidates: list[tuple[str, tuple[str, str], str, float]] = []

    for rail in rails:
        # Project rail endpoints onto opening axis
        a0 = (rail.p0[0] - center[0]) * axis[0] + (rail.p0[1] - center[1]) * axis[1]
        a1 = (rail.p1[0] - center[0]) * axis[0] + (rail.p1[1] - center[1]) * axis[1]
        r_min, r_max = min(a0, a1), max(a0, a1)
        # Rail endpoints MUST match opening jambs [-half_span, +half_span] tightly.
        # Reject overall wall/room chain rails that span beyond the opening jambs!
        if abs(r_min - (-half_span)) > _RAIL_ENDPOINT_TOL_PTS or abs(r_max - half_span) > _RAIL_ENDPOINT_TOL_PTS:
            reasons.append("overall_chain_dimension_not_opening_scoped")
            continue

        # Identify which rail endpoint corresponds to jamb_a vs jamb_b
        ep_a = rail.p0 if _dist(rail.p0, opening.jamb_a_pt) <= _dist(rail.p1, opening.jamb_a_pt) else rail.p1
        ep_b = rail.p1 if ep_a is rail.p0 else rail.p0

        # Require TWO visible perpendicular witness lines: one connecting ep_a <-> jamb_a,
        # and one connecting ep_b <-> jamb_b.
        w_a = [
            w for w in witness_lines
            if _point_to_seg_dist(ep_a, w.p0, w.p1) <= _RAIL_ENDPOINT_TOL_PTS
            and _point_to_seg_dist(opening.jamb_a_pt, w.p0, w.p1) <= _JAMB_ATTACH_TOL_PTS
        ]
        w_b = [
            w for w in witness_lines
            if _point_to_seg_dist(ep_b, w.p0, w.p1) <= _RAIL_ENDPOINT_TOL_PTS
            and _point_to_seg_dist(opening.jamb_b_pt, w.p0, w.p1) <= _JAMB_ATTACH_TOL_PTS
        ]
        if not w_a or not w_b:
            reasons.append("missing_dual_jamb_witness_lines")
            continue

        # Find figure texts bound to this rail
        ru_x, ru_y, rlen = _seg_unit(rail.p0, rail.p1)
        bound_texts: list[TrustedFigureText] = []
        for t in local_texts:
            d = _point_to_seg_dist(t.center_pt, rail.p0, rail.p1)
            proj = (t.center_pt[0] - rail.p0[0]) * ru_x + (t.center_pt[1] - rail.p0[1]) * ru_y
            if d <= _TEXT_RAIL_DIST_TOL_PTS and -4.0 <= proj <= rlen + 4.0:
                bound_texts.append(t)

        if not bound_texts:
            reasons.append("figure_line_missing_bound_text")
            continue
        if len(bound_texts) > 1:
            reasons.append("multiple_competing_texts_on_single_figure_rail")
            continue

        txt = bound_texts[0]
        if not txt.text_integrity_trusted:
            reasons.append("untrusted_figure_text_integrity_rejected")
            continue

        val_mm, parse_err = parse_unambiguous_figure_mm(txt.text)
        if parse_err is not None or val_mm is None:
            reasons.append(parse_err or "ambiguous_figure_text")
            continue

        proven_candidates.append(
            (rail.segment_id, tuple(sorted((w_a[0].segment_id, w_b[0].segment_id))), txt.text_id, val_mm)
        )

    final_reasons: list[str] = []
    resolved_val: float | None = None
    resolved_rail: str | None = None
    resolved_witnesses: tuple[str, ...] = ()
    resolved_text: str | None = None

    if not proven_candidates:
        if local_texts and not rails:
            final_reasons.append("proximity_only_dimension_forbidden")
        final_reasons.extend(reasons)
        if not final_reasons:
            final_reasons.append("no_opening_figure_line_witness_found")
    else:
        vals = [c[3] for c in proven_candidates]
        if max(vals) - min(vals) > _DIM_CONFLICT_TOL_MM:
            final_reasons.append("conflicting_figure_line_dimensions")
        else:
            # Deterministic canonical selection when multiple identical corroborating rails agree
            proven_candidates.sort(key=lambda c: (c[0], c[2]))
            resolved_rail, resolved_witnesses, resolved_text, resolved_val = proven_candidates[0]

    dedup = tuple(dict.fromkeys(final_reasons))
    proven = resolved_val is not None and not dedup
    payload = {
        "opening_id": opening_id,
        "axis": _clean(axis_label) or "width",
        "proven": proven,
        "value_mm": resolved_val if proven else None,
        "rail_segment_id": resolved_rail if proven else None,
        "witness_segment_ids": list(resolved_witnesses) if proven else [],
        "text_observation_id": resolved_text if proven else None,
        "blocking_reasons": list(dedup),
    }
    digest = _canonical_sha(payload)
    return UnmarkedOpeningFigureWitnessResult(
        witness_id=f"unmarked_fig_witness_{digest[:16]}",
        opening_id=opening_id,
        proven=proven,
        abstained=not proven,
        axis=_clean(axis_label) or "width",
        value_mm=resolved_val if proven else None,
        rail_segment_id=resolved_rail if proven else None,
        witness_segment_ids=resolved_witnesses if proven else (),
        text_observation_id=resolved_text if proven else None,
        blocking_reasons=dedup,
        gap_scale_conversion_forbidden=True,
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
