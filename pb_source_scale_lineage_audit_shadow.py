"""Item 23: Scale lineage audit shadow (dimension chains, scale bars, viewport calibrations).

Audits viewport-scoped scale lineage across three geometric/textual inputs on the
same authenticated `(document_id, revision_id, source_sha256, page_id, viewport_id)`:
1. Dimension-chain witnesses (explicit figured span in mm vs measured PDF pts,
   tagged with X/Y/oblique axis orientation)
2. Graphic scale-bar witnesses (tick-bar or block-bar physical span vs PDF pts)
3. Printed ratio / NTS annotations (corroboration or explicit Not-To-Scale veto)

Enforces strict no-guessed-scale invariants:
- Printed ratio alone (e.g., `1:100`) without geometric corroboration from a
  scale bar or >= 2 consistent dimension-chain spans NEVER calibrates scale;
- Any `NTS` / `NOT TO SCALE` / `DO NOT SCALE` notice in the viewport vetoes scale;
- Anisotropic X vs Y scale drift (> 1.5%) fails closed;
- Dimension-chain internal scatter (> 1.5%) or scale-bar vs chain conflict (> 2.0%)
  fails closed;
- Viewports on the same page remain strictly isolated (no page-wide scale bleed).

Shadow-only; never grants scale or commercial authority and contains zero
job-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Sequence


MM_PER_PT_AT_1_TO_1 = 25.4 / 72.0
_CHAIN_SCATTER_REL_TOL = 0.015
_AXIS_ANISOTROPY_REL_TOL = 0.015
_BAR_VS_CHAIN_REL_TOL = 0.02
_RATIO_CORROBORATION_REL_TOL = 0.02

_NTS_RE = re.compile(
    r"\b(?:nts|n\.t\.s\.|not\s+to\s+scale|do\s+not\s+scale|schematic\s+only|diagrammatic\s+only)\b",
    re.IGNORECASE,
)
_RATIO_RE = re.compile(r"\b1\s*:\s*(\d{1,5})\b")


def _clean(value: object) -> str:
    return str(value or "").strip()


def _pos(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0.0 else None


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class ScaleLineageRef:
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
class DimensionChainScaleWitness:
    witness_id: str
    lineage: ScaleLineageRef
    axis: str  # "x" | "y" | "oblique"
    span_pts: float
    figured_mm: float
    text_integrity_trusted: bool = True


@dataclass(frozen=True)
class GraphicScaleBarWitness:
    bar_id: str
    lineage: ScaleLineageRef
    bar_kind: str  # "tick_bar" | "block_bar"
    span_pts: float
    physical_span_mm: float
    residual_pt: float = 0.0


@dataclass(frozen=True)
class PrintedScaleNoteWitness:
    note_id: str
    lineage: ScaleLineageRef
    raw_text: str


@dataclass(frozen=True)
class ViewportScaleLineageAuditResult:
    audit_id: str
    viewport_id: str
    calibrated: bool
    abstained: bool
    mm_per_pt: float | None
    equivalent_ratio: float | None
    calibration_sources: tuple[str, ...]
    supporting_witness_ids: tuple[str, ...]
    rejected_witness_ids: tuple[str, ...]
    ratio_corroborated: bool
    printed_ratios_seen: tuple[float, ...]
    blocking_reasons: tuple[str, ...]
    guessed_scale_forbidden: bool = True
    scale_authority_granted: bool = False
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "viewport_id": self.viewport_id,
            "calibrated": self.calibrated,
            "abstained": self.abstained,
            "mm_per_pt": self.mm_per_pt,
            "equivalent_ratio": self.equivalent_ratio,
            "calibration_sources": list(self.calibration_sources),
            "supporting_witness_ids": list(self.supporting_witness_ids),
            "rejected_witness_ids": list(self.rejected_witness_ids),
            "ratio_corroborated": self.ratio_corroborated,
            "printed_ratios_seen": list(self.printed_ratios_seen),
            "blocking_reasons": list(self.blocking_reasons),
            "guessed_scale_forbidden": True,
            "scale_authority_granted": False,
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def audit_viewport_scale_lineage_shadow(
    target_lineage: ScaleLineageRef,
    *,
    dimension_chains: Sequence[DimensionChainScaleWitness] = (),
    scale_bars: Sequence[GraphicScaleBarWitness] = (),
    printed_notes: Sequence[PrintedScaleNoteWitness] = (),
    require_dual_chain_without_bar: bool = True,
) -> ViewportScaleLineageAuditResult:
    """Audit viewport scale lineage from dimension chains, scale bars, and printed notes."""
    if not target_lineage.is_valid():
        raise ValueError("target_lineage must be complete")

    tgt = target_lineage.normalized()
    reasons: list[str] = []
    supporting: list[str] = []
    rejected: list[str] = []
    cal_sources: list[str] = []

    # 1. Inspect printed scale notes for NTS veto and ratio annotations
    printed_ratios: list[float] = []
    for note in printed_notes:
        nid = _clean(note.note_id) or "<note>"
        if not note.lineage.is_valid() or note.lineage.normalized() != tgt:
            rejected.append(nid)
            reasons.append("cross_viewport_scale_bleed_rejected")
            continue
        raw = _clean(note.raw_text)
        if _NTS_RE.search(raw):
            rejected.append(nid)
            reasons.append("not_to_scale_viewport_rejected")
            continue
        for match in _RATIO_RE.finditer(raw):
            denom = float(match.group(1))
            if 1.0 <= denom <= 10000.0:
                printed_ratios.append(denom)
                supporting.append(nid)

    # 2. Validate dimension chain witnesses (same exact viewport lineage only)
    chain_rates: list[tuple[str, str, float]] = []
    for cw in dimension_chains:
        cid = _clean(cw.witness_id) or "<chain>"
        if not cw.lineage.is_valid() or cw.lineage.normalized() != tgt:
            rejected.append(cid)
            reasons.append("cross_viewport_scale_bleed_rejected")
            continue
        if not cw.text_integrity_trusted:
            rejected.append(cid)
            reasons.append("untrusted_dimension_chain_text_rejected")
            continue
        sp = _pos(cw.span_pts)
        mm = _pos(cw.figured_mm)
        if sp is None or mm is None:
            rejected.append(cid)
            reasons.append("invalid_dimension_chain_span")
            continue
        rate = mm / sp
        axis = _clean(cw.axis).lower() or "oblique"
        chain_rates.append((cid, axis, rate))
        supporting.append(cid)

    chain_mm_per_pt: float | None = None
    if chain_rates:
        rates = [r for _, _, r in chain_rates]
        mean_chain = sum(rates) / len(rates)
        rel_scatter = (max(rates) - min(rates)) / max(mean_chain, 1e-9)
        if rel_scatter > _CHAIN_SCATTER_REL_TOL:
            reasons.append("dimension_chain_scale_scatter_exceeded")
        # Check X vs Y anisotropy if both axes present
        x_rates = [r for _, ax, r in chain_rates if ax == "x"]
        y_rates = [r for _, ax, r in chain_rates if ax == "y"]
        if x_rates and y_rates:
            mx = sum(x_rates) / len(x_rates)
            my = sum(y_rates) / len(y_rates)
            aniso = abs(mx - my) / max((mx + my) * 0.5, 1e-9)
            if aniso > _AXIS_ANISOTROPY_REL_TOL:
                reasons.append("anisotropic_axis_scale_drift_rejected")
        if "dimension_chain_scale_scatter_exceeded" not in reasons and "anisotropic_axis_scale_drift_rejected" not in reasons:
            chain_mm_per_pt = mean_chain
            cal_sources.append("dimension_chain")

    # 3. Validate graphic scale bars (same exact viewport lineage only)
    bar_rates: list[tuple[str, float]] = []
    for bar in scale_bars:
        bid = _clean(bar.bar_id) or "<bar>"
        if not bar.lineage.is_valid() or bar.lineage.normalized() != tgt:
            rejected.append(bid)
            reasons.append("cross_viewport_scale_bleed_rejected")
            continue
        sp = _pos(bar.span_pts)
        mm = _pos(bar.physical_span_mm)
        if sp is None or mm is None or not math.isfinite(bar.residual_pt) or bar.residual_pt > 2.0:
            rejected.append(bid)
            reasons.append("invalid_graphic_scale_bar")
            continue
        bar_rates.append((bid, mm / sp))
        supporting.append(bid)

    bar_mm_per_pt: float | None = None
    if bar_rates:
        brs = [r for _, r in bar_rates]
        mean_bar = sum(brs) / len(brs)
        if (max(brs) - min(brs)) / max(mean_bar, 1e-9) > _BAR_VS_CHAIN_REL_TOL:
            reasons.append("conflicting_graphic_scale_bars_rejected")
        else:
            bar_mm_per_pt = mean_bar
            cal_sources.append("graphic_scale_bar")

    # 4. Reconcile geometric scale sources (NEVER accept printed ratio alone!)
    resolved_mm_per_pt: float | None = None
    if chain_mm_per_pt is not None and bar_mm_per_pt is not None:
        rel_diff = abs(chain_mm_per_pt - bar_mm_per_pt) / max((chain_mm_per_pt + bar_mm_per_pt) * 0.5, 1e-9)
        if rel_diff > _BAR_VS_CHAIN_REL_TOL:
            reasons.append("scale_source_conflict_rejected")
        else:
            resolved_mm_per_pt = round((chain_mm_per_pt + bar_mm_per_pt) * 0.5, 6)
    elif bar_mm_per_pt is not None:
        resolved_mm_per_pt = round(bar_mm_per_pt, 6)
    elif chain_mm_per_pt is not None:
        if require_dual_chain_without_bar and len(chain_rates) < 2:
            reasons.append("single_dimension_chain_uncorroborated")
        else:
            resolved_mm_per_pt = round(chain_mm_per_pt, 6)
    else:
        if printed_ratios:
            reasons.append("ratio_only_without_geometric_proof_rejected")
        elif "not_to_scale_viewport_rejected" not in reasons:
            reasons.append("no_geometric_scale_evidence_available")

    # 5. Cross-check printed ratio against geometrically proven scale (catches A1->A3 print shrink!)
    ratio_corroborated = False
    unique_ratios = tuple(sorted(set(printed_ratios)))
    if resolved_mm_per_pt is not None and unique_ratios:
        equiv_ratio = resolved_mm_per_pt / MM_PER_PT_AT_1_TO_1
        if len(unique_ratios) > 1:
            reasons.append("conflicting_printed_ratios_in_viewport")
        else:
            printed_r = unique_ratios[0]
            rel_ratio_diff = abs(equiv_ratio - printed_r) / max(printed_r, 1.0)
            if rel_ratio_diff <= _RATIO_CORROBORATION_REL_TOL:
                ratio_corroborated = True
            else:
                reasons.append("printed_ratio_disagrees_with_geometric_scale")

    dedup = tuple(dict.fromkeys(reasons))
    # Ignore non-fatal cross-viewport rejections ONLY if the caller specifically passed mixed-page
    # items? No — for strict audit safety, cross-viewport bleed in the same input bundle is recorded
    # as a blocking audit error if no clean viewport isolation occurred; wait: if a viewport has clean
    # witnesses AND caller filtered or mixed foreign witnesses, rejecting foreign ones while still
    # surfacing them in rejected_witness_ids should block ONLY if the viewport itself is compromised.
    # Let's keep cross_viewport_scale_bleed_rejected as a hard audit failure so callers MUST scope
    # per viewport cleanly!
    calibrated = resolved_mm_per_pt is not None and not dedup
    eq_ratio_out = (
        round(resolved_mm_per_pt / MM_PER_PT_AT_1_TO_1, 3)
        if (calibrated and resolved_mm_per_pt is not None)
        else None
    )

    payload = {
        "viewport_id": target_lineage.viewport_id,
        "calibrated": calibrated,
        "mm_per_pt": resolved_mm_per_pt if calibrated else None,
        "calibration_sources": sorted(set(cal_sources)) if calibrated else [],
        "supporting_witness_ids": sorted(set(supporting)),
        "rejected_witness_ids": sorted(set(rejected)),
        "ratio_corroborated": ratio_corroborated,
        "blocking_reasons": list(dedup),
    }
    digest = _canonical_sha(payload)
    return ViewportScaleLineageAuditResult(
        audit_id=f"scale_lineage_audit_{digest[:16]}",
        viewport_id=target_lineage.viewport_id,
        calibrated=calibrated,
        abstained=not calibrated,
        mm_per_pt=resolved_mm_per_pt if calibrated else None,
        equivalent_ratio=eq_ratio_out,
        calibration_sources=tuple(sorted(set(cal_sources))) if calibrated else (),
        supporting_witness_ids=tuple(sorted(set(supporting))),
        rejected_witness_ids=tuple(sorted(set(rejected))),
        ratio_corroborated=ratio_corroborated,
        printed_ratios_seen=unique_ratios,
        blocking_reasons=dedup,
        guessed_scale_forbidden=True,
        scale_authority_granted=False,
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
