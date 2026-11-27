"""Default-off generic dimension-witness + title-scale ratio corroboration shadow (A05).

Designed for drawing viewports that lack a graphic scale bar (where
``PhysicalScaleProducer`` abstains with ``physical_scale_bar_unavailable``),
while strictly enforcing conflict vetoing and typed-negative non-wall guard
prerequisites before any downstream promotion:

- A text scale ratio (e.g., ``1:100``) NEVER mints physical scale by itself.
- Scale requires either:
  1. >= 2 independent agreeing figured dimension witnesses (within 1.5% relative
     spread across ``mm_per_point``) with zero conflicting ratios; OR
  2. >= 1 figured dimension witness corroborated by an agreeing explicit scale
     ratio (within 2.0% relative difference) with zero conflicting ratios.
- Conflicting dimension witnesses, conflicting scale ratios, cross-revision/SHA
  mismatches, or non-finite/non-positive spans fail closed (``CONFLICT`` / ``ABSTAINED``).
- Explicitly declares ``requires_typed_negative_ink_guard = True`` (per Claude
  `#7215432212` / MAX `#7216380821`: never promote a separation band without a
  non-wall typed negative ink guard), ``shadow_only = True``, and
  ``commercial_authority_granted = False``.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from statistics import median
from typing import Mapping, Optional, Sequence

from pb_figured_dimension_authority import (
    DimensionParseError,
    parse_figured_dimension_mm,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_native_dimension_cap_evidence import compile_native_dimension_cap_components
from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1

SCHEMA_VERSION = "1.0.0"

_POINTS_PER_MM_AT_1_1 = POINTS_PER_METRE_AT_1_1 / 1000.0
_MAX_WITNESS_SPREAD_REL = 0.015  # 1.5% max spread across agreeing dimension witnesses
_MAX_RATIO_DIFF_REL = 0.02       # 2.0% max difference against explicit scale ratio
_MIN_SCALE_DENOMINATOR = 1.0
_MAX_SCALE_DENOMINATOR = 5000.0


@dataclass(frozen=True)
class FiguredDimensionScaleWitness:
    """One source-owned figured dimension chain/segment span inside a viewport."""

    witness_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    pdf_span_pts: float
    figured_mm: float
    axis: str = "unknown"  # "horizontal" | "vertical" | "diagonal" | "unknown"

    def implied_mm_per_point(self) -> Optional[float]:
        if (
            isinstance(self.pdf_span_pts, bool)
            or isinstance(self.figured_mm, bool)
            or not (math.isfinite(self.pdf_span_pts) and math.isfinite(self.figured_mm))
            or self.pdf_span_pts <= 0.0
            or self.figured_mm <= 0.0
        ):
            return None
        return float(self.figured_mm) / float(self.pdf_span_pts)


@dataclass(frozen=True)
class DimensionWitnessScaleShadowResult:
    """Default-off shadow scale corroboration result for one viewport scope."""

    status: EvidenceResolutionStatus
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    mm_per_point: Optional[float]
    implied_scale_denominator: Optional[float]
    corroborating_witness_ids: tuple[str, ...]
    corroborating_ratio_denominators: tuple[float, ...]
    reason_codes: tuple[str, ...]
    requires_typed_negative_ink_guard: bool = True
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def _ratio_to_mm_per_point(denominator: float) -> float:
    return float(denominator) / _POINTS_PER_MM_AT_1_1


def _mm_per_point_to_denominator(mm_per_point: float) -> float:
    return float(mm_per_point) * _POINTS_PER_MM_AT_1_1


def corroborate_dimension_witness_scale_shadow(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    page_id: str,
    viewport_id: str,
    dimension_witnesses: Sequence[FiguredDimensionScaleWitness],
    explicit_scale_ratios: Sequence[float] = (),
) -> DimensionWitnessScaleShadowResult:
    """Corroborate viewport physical scale from figured dimension witnesses & optional ratios."""

    def _blocked(status: EvidenceResolutionStatus, *reasons: str) -> DimensionWitnessScaleShadowResult:
        return DimensionWitnessScaleShadowResult(
            status=status,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            mm_per_point=None,
            implied_scale_denominator=None,
            corroborating_witness_ids=(),
            corroborating_ratio_denominators=(),
            reason_codes=tuple(dict.fromkeys(reasons)),
        )

    valid_ratios: list[float] = []
    for raw_r in explicit_scale_ratios:
        if isinstance(raw_r, bool) or not math.isfinite(float(raw_r)):
            continue
        val = float(raw_r)
        if _MIN_SCALE_DENOMINATOR <= val <= _MAX_SCALE_DENOMINATOR:
            valid_ratios.append(round(val, 6))
    distinct_ratios = tuple(sorted(set(valid_ratios)))
    if len(distinct_ratios) > 1:
        # Conflicting explicit scale ratios in the same viewport veto immediately.
        if (distinct_ratios[-1] - distinct_ratios[0]) / distinct_ratios[0] > _MAX_RATIO_DIFF_REL:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                "conflicting_explicit_scale_ratios",
            )

    scoped_witnesses: list[tuple[str, float]] = []
    for w in dimension_witnesses:
        if (
            w.document_id != document_id
            or w.revision_id != revision_id
            or w.source_sha256.lower() != source_sha256.lower()
            or w.page_id != page_id
            or w.viewport_id != viewport_id
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                "dimension_witness_scope_or_revision_mismatch",
            )
        mpp = w.implied_mm_per_point()
        if mpp is None:
            continue
        denom = _mm_per_point_to_denominator(mpp)
        if not (_MIN_SCALE_DENOMINATOR <= denom <= _MAX_SCALE_DENOMINATOR):
            continue
        scoped_witnesses.append((w.witness_id, mpp))

    if not scoped_witnesses:
        # Text ratios alone NEVER mint physical scale authority.
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "dimension_witnesses_unavailable",
        )

    mpps = [m for _wid, m in scoped_witnesses]
    lo, hi = min(mpps), max(mpps)
    if (hi - lo) / lo > _MAX_WITNESS_SPREAD_REL:
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            "conflicting_dimension_witness_scales",
        )

    med_mpp = float(median(mpps))
    implied_denom = _mm_per_point_to_denominator(med_mpp)

    if distinct_ratios:
        ref_ratio = distinct_ratios[0]
        ref_mpp = _ratio_to_mm_per_point(ref_ratio)
        if abs(med_mpp - ref_mpp) / ref_mpp > _MAX_RATIO_DIFF_REL:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                "dimension_witness_vs_explicit_ratio_conflict",
            )
        return DimensionWitnessScaleShadowResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            page_id=page_id,
            viewport_id=viewport_id,
            mm_per_point=round(med_mpp, 9),
            implied_scale_denominator=round(implied_denom, 4),
            corroborating_witness_ids=tuple(sorted(wid for wid, _ in scoped_witnesses)),
            corroborating_ratio_denominators=distinct_ratios,
            reason_codes=("dimension_witness_corroborated_by_explicit_ratio",),
        )

    if len(scoped_witnesses) < 2:
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "single_dimension_witness_without_corroborating_ratio",
        )

    return DimensionWitnessScaleShadowResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        page_id=page_id,
        viewport_id=viewport_id,
        mm_per_point=round(med_mpp, 9),
        implied_scale_denominator=round(implied_denom, 4),
        corroborating_witness_ids=tuple(sorted(wid for wid, _ in scoped_witnesses)),
        corroborating_ratio_denominators=(),
        reason_codes=("multi_dimension_witness_scale_corroborated",),
    )


def extract_dimension_witnesses_from_native_components(
    *,
    segments: Mapping[str, Sequence[float]],
    words: Sequence[Mapping[str, object]],
    document_id: str,
    revision_id: str,
    source_sha256: str,
    page_id: str,
    viewport_id: str,
) -> tuple[FiguredDimensionScaleWitness, ...]:
    """Extract FiguredDimensionScaleWitness objects from native dimension cap components.

    Reuses ``compile_native_dimension_cap_components`` (no duplicate dimension
    topology engine) and ``parse_figured_dimension_mm``.
    """
    word_by_id = {str(w["id"]): w for w in words if "id" in w}
    components = compile_native_dimension_cap_components(segments=segments, words=words)
    witnesses: list[FiguredDimensionScaleWitness] = []
    for idx, (line_ids, word_id, _covered) in enumerate(components):
        word = word_by_id.get(str(word_id))
        if word is None:
            continue
        raw_text = str(word.get("text") or "").strip()
        if not raw_text:
            continue
        try:
            figured_mm = parse_figured_dimension_mm(raw_text)
        except (DimensionParseError, ValueError, TypeError):
            continue
        if not math.isfinite(figured_mm) or figured_mm <= 0.0:
            continue
        pts: list[tuple[float, float]] = []
        axis_vec: Optional[tuple[float, float]] = None
        for sid in line_ids:
            seg = segments.get(sid)
            if not seg or len(seg) != 4:
                continue
            x0, y0, x1, y1 = map(float, seg)
            if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                continue
            dx, dy = x1 - x0, y1 - y0
            seg_len = math.hypot(dx, dy)
            if seg_len > 1e-6 and axis_vec is None:
                axis_vec = (dx / seg_len, dy / seg_len)
            pts.append((x0, y0))
            pts.append((x1, y1))
        if axis_vec is None or len(pts) < 2:
            continue
        ux, uy = axis_vec
        projections = [px * ux + py * uy for px, py in pts]
        span_pts = max(projections) - min(projections)
        if not math.isfinite(span_pts) or span_pts <= 1e-3:
            continue
        if abs(uy) <= 0.05:
            axis_label = "horizontal"
        elif abs(ux) <= 0.05:
            axis_label = "vertical"
        else:
            axis_label = "diagonal"
        witnesses.append(
            FiguredDimensionScaleWitness(
                witness_id=f"dim_cap:{page_id}:{viewport_id}:{word_id}:{idx}",
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                page_id=page_id,
                viewport_id=viewport_id,
                pdf_span_pts=round(span_pts, 6),
                figured_mm=round(figured_mm, 4),
                axis=axis_label,
            )
        )
    return tuple(witnesses)


__all__ = [
    "DimensionWitnessScaleShadowResult",
    "FiguredDimensionScaleWitness",
    "SCHEMA_VERSION",
    "corroborate_dimension_witness_scale_shadow",
    "extract_dimension_witnesses_from_native_components",
]
