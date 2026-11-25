"""Item 20: Source garage/panel door host and dimension evidence shadow.

Authenticates garage, panel-lift, sectional overhead, roller, and tilt door
host-wall continuity and explicit source dimensions (schedule, callout, or
elevation) while strictly forbidding standard 2040 mm external pedestrian door
height assumptions on garage openings.

Shadow-only evidence module: never grants commercial or measurement authority
and contains zero job-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Sequence


STANDARD_EXTERNAL_DOOR_HEIGHT_MM = 2040.0
_DIM_CONFLICT_TOLERANCE_MM = 5.0
_GEOMETRY_WIDTH_REL_TOL = 0.12
_GEOMETRY_WIDTH_ABS_TOL_MM = 150.0

_VALID_BASES = frozenset(
    {
        "clear_opening",
        "structural_opening",
        "rough_opening",
        "frame_dimension",
        "leaf_dimension",
        "unknown_basis",
    }
)

_GARAGE_KIND_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "panel_lift_door",
        re.compile(r"\bpanel[\s\-]*lift(?:\s+garage)?\s+door\b|\bpanel\s+door\b", re.IGNORECASE),
    ),
    (
        "sectional_overhead_door",
        re.compile(r"\bsectional(?:\s+overhead)?(?:\s+garage)?\s+door\b|\boverhead\s+garage\s+door\b", re.IGNORECASE),
    ),
    (
        "roller_shutter_door",
        re.compile(r"\broller\s+(?:shutter|door)\b|\bauto(?:matic)?\s+roller\s+door\b", re.IGNORECASE),
    ),
    (
        "tilt_garage_door",
        re.compile(r"\btilt(?:\-up|\s+panel)?(?:\s+garage)?\s+door\b", re.IGNORECASE),
    ),
    (
        "garage_door_generic",
        re.compile(r"\bgarage\s+(?:auto(?:matic)?\s+)?door\b|\bdouble\s+garage\s+door\b|\bsingle\s+garage\s+door\b", re.IGNORECASE),
    ),
)

_PEDESTRIAN_DOOR_EXCLUSION_RE = re.compile(
    r"\b(?:entry|front|hinged|swing|sliding\s+glass|cavity\s+slider|personnel|pa\s+door|pedestrian|internal\s+door)\b",
    re.IGNORECASE,
)

# Explicit labeled width/height pairs e.g. "4800W x 2100H", "2100H x 4800W", "W4800 x H2400"
_LABELED_W_FIRST_RE = re.compile(
    r"\b(?P<w>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*(?:w|wide|width)\s*[x×]\s*"
    r"(?P<h>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*(?:h|high|height)\b",
    re.IGNORECASE,
)
_LABELED_H_FIRST_RE = re.compile(
    r"\b(?P<h>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*(?:h|high|height)\s*[x×]\s*"
    r"(?P<w>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*(?:w|wide|width)\b",
    re.IGNORECASE,
)
_PREFIX_W_FIRST_RE = re.compile(
    r"\b(?:w|width)\s*[:=]?\s*(?P<w>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*[x×,/]\s*"
    r"(?:h|height)\s*[:=]?\s*(?P<h>\d{4}(?:\.\d+)?)\s*(?:mm)?\b",
    re.IGNORECASE,
)
_PREFIX_H_FIRST_RE = re.compile(
    r"\b(?:h|height)\s*[:=]?\s*(?P<h>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*[x×,/]\s*"
    r"(?:w|width)\s*[:=]?\s*(?P<w>\d{4}(?:\.\d+)?)\s*(?:mm)?\b",
    re.IGNORECASE,
)
# Unlabeled pair e.g. "4800 x 2100" or "2100 x 4800" (disambiguated only if order declared or axis unambiguous)
_BARE_PAIR_RE = re.compile(
    r"\b(?P<a>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*[x×]\s*(?P<b>\d{4}(?:\.\d+)?)\s*(?:mm)?\b",
    re.IGNORECASE,
)
# Single explicitly labeled axis e.g. "4800W" or "4800 WIDE"
_WIDTH_ONLY_RE = re.compile(
    r"\b(?:(?:w|width)\s*[:=]?\s*(?P<w1>\d{4}(?:\.\d+)?)|(?P<w2>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*(?:w|wide|width))\b",
    re.IGNORECASE,
)
_HEIGHT_ONLY_RE = re.compile(
    r"\b(?:(?:h|height)\s*[:=]?\s*(?P<h1>\d{4}(?:\.\d+)?)|(?P<h2>\d{4}(?:\.\d+)?)\s*(?:mm)?\s*(?:h|high|height))\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _finite_pos(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0.0:
        return None
    return v


def _canonical_sha(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SourceLineageRef:
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str

    def is_valid(self) -> bool:
        return all(
            bool(_clean(v))
            for v in (
                self.document_id,
                self.revision_id,
                self.source_sha256,
                self.page_id,
                self.viewport_id,
            )
        )

    def normalized_tuple(self) -> tuple[str, str, str, str, str]:
        return (
            _clean(self.document_id),
            _clean(self.revision_id),
            _clean(self.source_sha256).lower(),
            _clean(self.page_id),
            _clean(self.viewport_id),
        )


@dataclass(frozen=True)
class GarageDoorHostWitness:
    """Verified structural host-wall continuity around a garage door aperture."""

    opening_id: str
    lineage: SourceLineageRef
    start_host_wall_id: str
    end_host_wall_id: str
    jamb_cap_ids: tuple[str, ...]
    aperture_span_pts: float
    native_label_text: str
    calibrated_mm_per_pt: float | None = None
    coplanar_host_walls_verified: bool = True
    is_exterior_wall_host: bool = True


@dataclass(frozen=True)
class GarageDoorDimensionWitness:
    """Source dimension witness for a garage/panel door (callout, schedule, or elevation)."""

    witness_id: str
    source_kind: str  # "plan_callout" | "schedule_row" | "elevation_dimension" | "assumed_default"
    lineage: SourceLineageRef
    linked_opening_id: str
    width_mm: float | None = None
    height_mm: float | None = None
    raw_callout_text: str = ""
    dimension_basis: str = "unknown_basis"
    bare_pair_order: str | None = None  # "w_x_h" or "h_x_w" when column/header defines order
    is_default_assumption: bool = False
    allows_cross_page_same_revision: bool = False


@dataclass(frozen=True)
class GaragePanelDoorDimensionEvidence:
    evidence_id: str
    opening_id: str
    garage_door_kind: str | None
    host_authenticated: bool
    dimension_authenticated: bool
    abstained: bool
    width_mm: float | None
    height_mm: float | None
    dimension_basis: str | None
    aperture_geometry_width_mm: float | None
    supporting_witness_ids: tuple[str, ...]
    rejected_witness_ids: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    standard_door_2040_fallback_blocked: bool = True
    commercial_authority_granted: bool = False
    measurement_authorized: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "opening_id": self.opening_id,
            "garage_door_kind": self.garage_door_kind,
            "host_authenticated": self.host_authenticated,
            "dimension_authenticated": self.dimension_authenticated,
            "abstained": self.abstained,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "dimension_basis": self.dimension_basis,
            "aperture_geometry_width_mm": self.aperture_geometry_width_mm,
            "supporting_witness_ids": list(self.supporting_witness_ids),
            "rejected_witness_ids": list(self.rejected_witness_ids),
            "blocking_reasons": list(self.blocking_reasons),
            "standard_door_2040_fallback_blocked": True,
            "commercial_authority_granted": False,
            "measurement_authorized": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def classify_garage_door_kind(label_text: str) -> str | None:
    """Classify a printed garage/panel door description without job-specific names."""
    cleaned = _clean(label_text)
    if not cleaned:
        return None
    for kind, pattern in _GARAGE_KIND_PATTERNS:
        if pattern.search(cleaned):
            return kind
    return None


def parse_garage_door_callout_dimensions(
    callout_text: str,
    *,
    bare_pair_order: str | None = None,
) -> tuple[float | None, float | None, str | None]:
    """Parse explicit width/height (mm) from a printed garage door callout.

    Returns ``(width_mm, height_mm, ambiguity_reason)``.
    Bare unlabeled ``A x B`` pairs are accepted only when ``bare_pair_order``
    is explicitly ``"w_x_h"`` or ``"h_x_w"``, or when one value is >= 2700 mm
    and the other is in [1800, 2650] mm (standard wide vehicle opening where
    height vs width cannot realistically swap without explicit height label).
    Otherwise bare pairs fail closed as ``ambiguous_unlabeled_dimension_pair``.
    """
    text = _clean(callout_text)
    if not text:
        return (None, None, None)

    for regex in (_LABELED_W_FIRST_RE, _PREFIX_W_FIRST_RE):
        m = regex.search(text)
        if m:
            return (float(m.group("w")), float(m.group("h")), None)

    for regex in (_LABELED_H_FIRST_RE, _PREFIX_H_FIRST_RE):
        m = regex.search(text)
        if m:
            return (float(m.group("w")), float(m.group("h")), None)

    bare = _BARE_PAIR_RE.search(text)
    if bare:
        a = float(bare.group("a"))
        b = float(bare.group("b"))
        order = _clean(bare_pair_order).lower()
        if order == "w_x_h":
            return (a, b, None)
        if order == "h_x_w":
            return (b, a, None)
        return (None, None, "ambiguous_unlabeled_dimension_pair")

    w_match = _WIDTH_ONLY_RE.search(text)
    h_match = _HEIGHT_ONLY_RE.search(text)
    width_val = float(w_match.group("w1") or w_match.group("w2")) if w_match else None
    height_val = float(h_match.group("h1") or h_match.group("h2")) if h_match else None
    return (width_val, height_val, None)


def evaluate_garage_panel_door_dimension_shadow(
    host: GarageDoorHostWitness,
    dimension_witnesses: Sequence[GarageDoorDimensionWitness],
) -> GaragePanelDoorDimensionEvidence:
    """Authenticate garage/panel door host + explicit dimensions and block 2040 mm fallback."""
    opening_id = _clean(host.opening_id)
    if not opening_id:
        raise ValueError("opening_id is required")

    reasons: list[str] = []
    supporting_ids: list[str] = []
    rejected_ids: list[str] = []

    label_text = _clean(host.native_label_text)
    garage_kind = classify_garage_door_kind(label_text)
    if garage_kind is None:
        if _PEDESTRIAN_DOOR_EXCLUSION_RE.search(label_text):
            reasons.append("not_a_garage_or_panel_door")
        else:
            reasons.append("missing_garage_door_label_evidence")

    # Authenticate structural host-wall continuity
    host_ok = True
    if not host.lineage.is_valid():
        host_ok = False
        reasons.append("invalid_host_lineage")
    if not _clean(host.start_host_wall_id) or not _clean(host.end_host_wall_id):
        host_ok = False
        reasons.append("unhosted_garage_opening_rejected")
    elif _clean(host.start_host_wall_id) == _clean(host.end_host_wall_id):
        host_ok = False
        reasons.append("degenerate_single_host_wall_rejected")
    if len(tuple(_clean(c) for c in host.jamb_cap_ids if _clean(c))) < 2:
        host_ok = False
        reasons.append("missing_dual_jamb_cap_witness")
    if not host.coplanar_host_walls_verified:
        host_ok = False
        reasons.append("non_coplanar_garage_host_walls")
    span_pts = _finite_pos(host.aperture_span_pts)
    if span_pts is None:
        host_ok = False
        reasons.append("invalid_aperture_span_pts")

    mm_per_pt = _finite_pos(host.calibrated_mm_per_pt)
    geom_width_mm = (
        round(span_pts * mm_per_pt, 2)
        if (span_pts is not None and mm_per_pt is not None)
        else None
    )

    host_doc, host_rev, host_sha, host_page, host_vp = host.lineage.normalized_tuple()

    widths: list[tuple[str, float, str]] = []
    heights: list[tuple[str, float, str]] = []
    bases: set[str] = set()

    for witness in dimension_witnesses:
        wid = _clean(witness.witness_id) or "<unnamed>"
        source_kind = _clean(witness.source_kind).lower()

        # Hard policy block: never accept assumed/default 2040 mm pedestrian door heights
        if witness.is_default_assumption or source_kind in {
            "assumed_default",
            "assumed_standard_external_door_height",
            "default_external_door_2040",
        }:
            rejected_ids.append(wid)
            reasons.append("assumed_2040_door_height_rejected_for_garage_door")
            continue

        if _clean(witness.linked_opening_id) != opening_id:
            rejected_ids.append(wid)
            reasons.append("dimension_witness_opening_id_mismatch")
            continue

        if not witness.lineage.is_valid():
            rejected_ids.append(wid)
            reasons.append("dimension_witness_invalid_lineage")
            continue

        w_doc, w_rev, w_sha, w_page, w_vp = witness.lineage.normalized_tuple()
        if (w_doc, w_rev, w_sha) != (host_doc, host_rev, host_sha):
            rejected_ids.append(wid)
            reasons.append("cross_revision_or_document_transfer_rejected")
            continue

        # Plan callouts MUST share the same page & viewport as the host opening.
        # Schedules & elevations may live on another page within the same authenticated
        # document revision when explicitly marked allows_cross_page_same_revision=True.
        if source_kind == "plan_callout":
            if (w_page, w_vp) != (host_page, host_vp):
                rejected_ids.append(wid)
                reasons.append("cross_viewport_transfer_rejected")
                continue
        elif source_kind in {"schedule_row", "elevation_dimension"}:
            if (w_page, w_vp) != (host_page, host_vp) and not witness.allows_cross_page_same_revision:
                rejected_ids.append(wid)
                reasons.append("cross_page_witness_unlinked")
                continue
        else:
            rejected_ids.append(wid)
            reasons.append("unsupported_dimension_witness_source_kind")
            continue

        basis = _clean(witness.dimension_basis).lower() or "unknown_basis"
        if basis not in _VALID_BASES:
            rejected_ids.append(wid)
            reasons.append("invalid_dimension_basis")
            continue

        w_val = _finite_pos(witness.width_mm)
        h_val = _finite_pos(witness.height_mm)
        if w_val is None and h_val is None and _clean(witness.raw_callout_text):
            parsed_w, parsed_h, ambig = parse_garage_door_callout_dimensions(
                witness.raw_callout_text,
                bare_pair_order=witness.bare_pair_order,
            )
            if ambig:
                rejected_ids.append(wid)
                reasons.append(ambig)
                continue
            w_val = _finite_pos(parsed_w)
            h_val = _finite_pos(parsed_h)

        if w_val is None and h_val is None:
            rejected_ids.append(wid)
            reasons.append("empty_dimension_witness")
            continue

        supporting_ids.append(wid)
        bases.add(basis)
        if w_val is not None:
            widths.append((wid, round(w_val, 2), basis))
        if h_val is not None:
            heights.append((wid, round(h_val, 2), basis))

    resolved_width: float | None = None
    resolved_height: float | None = None
    resolved_basis: str | None = None

    if widths:
        w_vals = [v for _, v, _ in widths]
        if max(w_vals) - min(w_vals) > _DIM_CONFLICT_TOLERANCE_MM:
            reasons.append("conflicting_garage_door_width_witnesses")
        else:
            resolved_width = round(sum(w_vals) / len(w_vals), 2)
    else:
        reasons.append("garage_door_width_missing")

    if heights:
        h_vals = [v for _, v, _ in heights]
        if max(h_vals) - min(h_vals) > _DIM_CONFLICT_TOLERANCE_MM:
            reasons.append("conflicting_garage_door_height_witnesses")
        else:
            resolved_height = round(sum(h_vals) / len(h_vals), 2)
    else:
        # Explicit policy guard: never substitute 2040 mm standard external door height
        reasons.append("garage_door_height_missing_2040_fallback_forbidden")

    if len(bases) == 1:
        resolved_basis = next(iter(bases))
    elif len(bases) > 1:
        concrete_bases = bases - {"unknown_basis"}
        if len(concrete_bases) == 1:
            resolved_basis = next(iter(concrete_bases))
        elif len(concrete_bases) > 1:
            reasons.append("conflicting_garage_door_dimension_basis")

    # Cross-check authenticated width against calibrated aperture span geometry
    if resolved_width is not None and geom_width_mm is not None:
        diff_mm = abs(resolved_width - geom_width_mm)
        rel_diff = diff_mm / max(resolved_width, geom_width_mm, 1.0)
        if diff_mm > _GEOMETRY_WIDTH_ABS_TOL_MM and rel_diff > _GEOMETRY_WIDTH_REL_TOL:
            reasons.append("garage_aperture_width_geometry_mismatch")

    dedup_reasons = tuple(dict.fromkeys(reasons))
    dim_ok = (
        host_ok
        and garage_kind is not None
        and resolved_width is not None
        and resolved_height is not None
        and not dedup_reasons
    )
    abstained = not dim_ok

    payload_for_hash = {
        "opening_id": opening_id,
        "garage_door_kind": garage_kind,
        "host_authenticated": host_ok,
        "dimension_authenticated": dim_ok,
        "abstained": abstained,
        "width_mm": resolved_width if dim_ok else None,
        "height_mm": resolved_height if dim_ok else None,
        "dimension_basis": resolved_basis if dim_ok else None,
        "aperture_geometry_width_mm": geom_width_mm,
        "supporting_witness_ids": sorted(supporting_ids),
        "rejected_witness_ids": sorted(rejected_ids),
        "blocking_reasons": list(dedup_reasons),
        "standard_door_2040_fallback_blocked": True,
    }
    digest = _canonical_sha(payload_for_hash)
    evidence_id = f"garage_door_dim_shadow_{digest[:16]}"

    return GaragePanelDoorDimensionEvidence(
        evidence_id=evidence_id,
        opening_id=opening_id,
        garage_door_kind=garage_kind,
        host_authenticated=host_ok,
        dimension_authenticated=dim_ok,
        abstained=abstained,
        width_mm=resolved_width if dim_ok else None,
        height_mm=resolved_height if dim_ok else None,
        dimension_basis=resolved_basis if dim_ok else None,
        aperture_geometry_width_mm=geom_width_mm,
        supporting_witness_ids=tuple(sorted(supporting_ids)),
        rejected_witness_ids=tuple(sorted(rejected_ids)),
        blocking_reasons=dedup_reasons,
        standard_door_2040_fallback_blocked=True,
        commercial_authority_granted=False,
        measurement_authorized=False,
        shadow_only=True,
        digest_sha256=digest,
    )
