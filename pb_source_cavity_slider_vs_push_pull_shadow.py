"""Source-neutral geometric discriminator: cavity slider vs push-pull paired doors.

Implements Work Order Item 19 as a pure, read-only, default-off shadow module:
- Evaluates door symbol primitives strictly in wall-local (u, n) coordinates
  derived from authenticated jamb endpoints, ensuring full translation and
  rotation invariance.
- Separates wall-embedded cavity slider pocket/leaf cues (recessed parallel
  track/leaf inside the host wall band, zero swing arcs) from push-pull /
  paired double-swing doors (opposing swing arcs or twin hinged leaves swinging
  out of the wall band, zero wall-embedded pocket).
- Fails closed (CONFLICT / ABSTAINED) on hybrid slider+swing cues, text-only
  claims without geometric cues, text-vs-geometry contradictions, or degenerate
  aperture spans. Never grants commercial or opening-kind authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

CLASS_CAVITY_SLIDER = "cavity_slider_pocket_leaf"
CLASS_PUSH_PULL_PAIRED = "push_pull_paired_door"
CLASS_SINGLE_SWING = "single_swing_door"
CLASS_CONFLICT = "door_operation_cue_conflict"
CLASS_ABSTAINED = "door_operation_unresolved"

SUBTYPE_SINGLE_CAVITY_SLIDER = "single_cavity_slider"
SUBTYPE_BIPARTING_CAVITY_SLIDER = "bi_parting_cavity_slider"
SUBTYPE_PAIRED_DOUBLE_SWING = "paired_double_swing"
SUBTYPE_DOUBLE_ACTION_PUSH_PULL = "double_action_push_pull"
SUBTYPE_SINGLE_HINGED = "single_hinged_swing"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_SLIDER_TEXT_RE = re.compile(r"\b(?:csd|c\.?s\.?d\.?|cavity\s+slid\w*|pocket\s+door)\b", re.IGNORECASE)
_PUSH_PULL_TEXT_RE = re.compile(r"\b(?:push\s*/?\s*pull|double\s+action|double\s+swing|paired\s+swing)\b", re.IGNORECASE)

_PARALLEL_ANGLE_MAX_DEG = 8.0
_HINGED_ANGLE_MIN_DEG = 35.0
_MIN_SWING_SWEEP_DEG = 60.0
_MAX_SWING_SWEEP_DEG = 120.0
_JAMB_ANCHOR_TOL_FRAC = 0.20

Point = tuple[float, float]
Segment = tuple[Point, Point]


def _req_str(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _req_sha256(value: object, name: str) -> str:
    clean = _req_str(value, name).lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{name} must be a 64-char hex sha256")
    return clean


def _req_pt(value: object, name: str) -> Point:
    if type(value) is not tuple or len(value) != 2:
        raise ValueError(f"{name} must be a finite 2-tuple")
    x, y = value
    if isinstance(x, bool) or isinstance(y, bool):
        raise ValueError(f"{name} must be numeric")
    fx, fy = float(x), float(y)
    if not (math.isfinite(fx) and math.isfinite(fy)):
        raise ValueError(f"{name} must be finite")
    return (fx, fy)


def _req_seg(value: object, name: str) -> Segment:
    if type(value) is not tuple or len(value) != 2:
        raise ValueError(f"{name} must be a 2-tuple of points")
    return (_req_pt(value[0], f"{name}[0]"), _req_pt(value[1], f"{name}[1]"))


@dataclass(frozen=True)
class SwingArcCue:
    arc_id: str
    center_pt: Point
    midpoint_pt: Point
    radius_pt: float
    sweep_deg: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "arc_id", _req_str(self.arc_id, "arc_id"))
        object.__setattr__(self, "center_pt", _req_pt(self.center_pt, "center_pt"))
        object.__setattr__(self, "midpoint_pt", _req_pt(self.midpoint_pt, "midpoint_pt"))
        if isinstance(self.radius_pt, bool) or not math.isfinite(float(self.radius_pt)) or float(self.radius_pt) <= 0.0:
            raise ValueError("radius_pt must be a positive finite float")
        if isinstance(self.sweep_deg, bool) or not math.isfinite(float(self.sweep_deg)) or float(self.sweep_deg) <= 0.0:
            raise ValueError("sweep_deg must be a positive finite float")
        object.__setattr__(self, "radius_pt", float(self.radius_pt))
        object.__setattr__(self, "sweep_deg", float(self.sweep_deg))


@dataclass(frozen=True)
class DoorApertureSymbolObservation:
    opening_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    host_wall_id: str
    jamb_a: Point
    jamb_b: Point
    wall_thickness_pt: float
    leaf_segments: tuple[Segment, ...] = ()
    pocket_recess_segments: tuple[Segment, ...] = ()
    swing_arcs: tuple[SwingArcCue, ...] = ()
    text_cues: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for field in ("opening_id", "document_id", "revision_id", "page_id", "viewport_id", "host_wall_id"):
            object.__setattr__(self, field, _req_str(getattr(self, field), field))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "jamb_a", _req_pt(self.jamb_a, "jamb_a"))
        object.__setattr__(self, "jamb_b", _req_pt(self.jamb_b, "jamb_b"))
        if isinstance(self.wall_thickness_pt, bool) or not math.isfinite(float(self.wall_thickness_pt)) or float(self.wall_thickness_pt) <= 0.0:
            raise ValueError("wall_thickness_pt must be a positive finite float")
        object.__setattr__(self, "wall_thickness_pt", float(self.wall_thickness_pt))
        object.__setattr__(
            self, "leaf_segments", tuple(_req_seg(s, "leaf_segments") for s in self.leaf_segments)
        )
        object.__setattr__(
            self,
            "pocket_recess_segments",
            tuple(_req_seg(s, "pocket_recess_segments") for s in self.pocket_recess_segments),
        )
        object.__setattr__(
            self,
            "text_cues",
            tuple(" ".join(str(t or "").strip().split()) for t in self.text_cues if str(t or "").strip()),
        )


@dataclass(frozen=True)
class DoorOperationDiscriminationShadow:
    record_id: str
    opening_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    host_wall_id: str
    classification: str
    subtype: str | None
    status: EvidenceResolutionStatus
    pocket_side_count: int
    parallel_inband_leaf_count: int
    hinged_leaf_count: int
    valid_swing_arc_count: int
    swing_sides_occupied: int
    retains_wall_continuity_over_pocket: bool
    wall_cut_excludes_pocket: bool
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False
    opening_kind_authority_granted: bool = False


def _to_local(pt: Point, origin: Point, u: Point, n: Point) -> Point:
    dx, dy = pt[0] - origin[0], pt[1] - origin[1]
    return (dx * u[0] + dy * u[1], dx * n[0] + dy * n[1])


def _seg_angle_to_u_deg(p0: Point, p1: Point) -> float | None:
    du, dn = p1[0] - p0[0], p1[1] - p0[1]
    length = math.hypot(du, dn)
    if length <= 1e-6:
        return None
    cos_a = max(-1.0, min(1.0, abs(du) / length))
    return math.degrees(math.acos(cos_a))


def classify_door_operation_cues(
    obs: DoorApertureSymbolObservation,
) -> DoorOperationDiscriminationShadow:
    """Classify cavity slider pocket/leaf cues separately from push-pull paired doors."""
    dx = obs.jamb_b[0] - obs.jamb_a[0]
    dy = obs.jamb_b[1] - obs.jamb_a[1]
    span = math.hypot(dx, dy)
    if span < 4.0:
        return _make_result(
            obs, CLASS_ABSTAINED, None, EvidenceResolutionStatus.ABSTAINED,
            0, 0, 0, 0, 0, False, False, ("degenerate_aperture_span",),
        )
    u = (dx / span, dy / span)
    n = (-u[1], u[0])
    half_t = obs.wall_thickness_pt / 2.0

    # Inspect pocket recess cues in wall-local (u, n) coordinates.
    pocket_left = False
    pocket_right = False
    for seg in obs.pocket_recess_segments:
        a = _to_local(seg[0], obs.jamb_a, u, n)
        b = _to_local(seg[1], obs.jamb_a, u, n)
        ang = _seg_angle_to_u_deg(a, b)
        if ang is None or ang > _PARALLEL_ANGLE_MAX_DEG:
            continue
        if max(abs(a[1]), abs(b[1])) > half_t * 1.30:
            continue
        u_lo, u_hi = min(a[0], b[0]), max(a[0], b[0])
        if u_lo < -0.20 * span and u_hi <= 0.15 * span:
            pocket_left = True
        if u_hi > span + 0.20 * span and u_lo >= 0.85 * span:
            pocket_right = True
    pocket_sides = int(pocket_left) + int(pocket_right)

    # Inspect leaf strokes: separate parallel wall-band sliding leaves from hinged swinging leaves.
    parallel_inband_leaves = 0
    hinged_at_a = 0
    hinged_at_b = 0
    hinged_leaves = 0
    hinged_sides: set[int] = set()
    jamb_tol = max(2.5, _JAMB_ANCHOR_TOL_FRAC * span)

    for seg in obs.leaf_segments:
        a = _to_local(seg[0], obs.jamb_a, u, n)
        b = _to_local(seg[1], obs.jamb_a, u, n)
        seg_len = math.hypot(b[0] - a[0], b[1] - a[1])
        ang = _seg_angle_to_u_deg(a, b)
        if ang is None or seg_len < 0.20 * span:
            continue
        u_lo, u_hi = min(a[0], b[0]), max(a[0], b[0])
        max_abs_n = max(abs(a[1]), abs(b[1]))
        if ang <= _PARALLEL_ANGLE_MAX_DEG and max_abs_n <= half_t * 1.70:
            # Sliding leaf lies parallel to wall axis spanning across/adjacent to the aperture.
            if u_hi > 0.0 and u_lo < span:
                parallel_inband_leaves += 1
        elif ang >= _HINGED_ANGLE_MIN_DEG and max_abs_n > half_t * 1.50:
            # Hinged leaf projects well outside wall thickness and anchors near a jamb.
            near_a = min(math.hypot(a[0], a[1]), math.hypot(b[0], b[1])) <= jamb_tol + half_t
            near_b = min(math.hypot(a[0] - span, a[1]), math.hypot(b[0] - span, b[1])) <= jamb_tol + half_t
            if near_a or near_b:
                hinged_leaves += 1
                if near_a:
                    hinged_at_a += 1
                if near_b:
                    hinged_at_b += 1
                tip_n = a[1] if abs(a[1]) >= abs(b[1]) else b[1]
                hinged_sides.add(1 if tip_n > 0.0 else -1)

    # Inspect swing arc cues in wall-local (u, n) coordinates.
    valid_arcs = 0
    arc_sides: set[int] = set()
    arcs_at_a = 0
    arcs_at_b = 0
    for arc in obs.swing_arcs:
        if not (_MIN_SWING_SWEEP_DEG <= arc.sweep_deg <= _MAX_SWING_SWEEP_DEG):
            continue
        if not (0.25 * span <= arc.radius_pt <= 1.15 * span):
            continue
        c_loc = _to_local(arc.center_pt, obs.jamb_a, u, n)
        m_loc = _to_local(arc.midpoint_pt, obs.jamb_a, u, n)
        near_a = math.hypot(c_loc[0], c_loc[1]) <= jamb_tol + half_t
        near_b = math.hypot(c_loc[0] - span, c_loc[1]) <= jamb_tol + half_t
        if not (near_a or near_b):
            continue
        if abs(m_loc[1]) <= half_t:
            continue
        valid_arcs += 1
        arc_sides.add(1 if m_loc[1] > 0.0 else -1)
        if near_a:
            arcs_at_a += 1
        if near_b:
            arcs_at_b += 1

    all_swing_sides = hinged_sides | arc_sides
    has_slider_geom = pocket_sides >= 1 and parallel_inband_leaves >= 1
    has_any_pocket = pocket_sides >= 1
    has_any_swing = hinged_leaves >= 1 or valid_arcs >= 1

    text_joined = " ".join(obs.text_cues)
    has_slider_text = bool(_SLIDER_TEXT_RE.search(text_joined))
    has_push_pull_text = bool(_PUSH_PULL_TEXT_RE.search(text_joined))

    if has_slider_text and has_push_pull_text:
        return _make_result(
            obs, CLASS_CONFLICT, None, EvidenceResolutionStatus.CONFLICT,
            pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
            False, False, ("conflicting_slider_and_push_pull_text_cues",),
        )

    # Hybrid geometry (both wall pocket recess and swinging leaf/arc) fails closed.
    if has_any_pocket and has_any_swing:
        return _make_result(
            obs, CLASS_CONFLICT, None, EvidenceResolutionStatus.CONFLICT,
            pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
            False, False, ("hybrid_slider_and_swing_cues_conflict",),
        )

    # 1. Cavity slider branch.
    if has_slider_geom:
        if has_push_pull_text:
            return _make_result(
                obs, CLASS_CONFLICT, None, EvidenceResolutionStatus.CONFLICT,
                pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
                False, False, ("text_vs_geometry_operation_conflict",),
            )
        subtype = (
            SUBTYPE_BIPARTING_CAVITY_SLIDER if pocket_sides == 2 else SUBTYPE_SINGLE_CAVITY_SLIDER
        )
        reasons = ["cavity_slider_pocket_and_parallel_leaf_corroborated"]
        if has_slider_text:
            reasons.append("slider_text_cue_corroborated")
        return _make_result(
            obs, CLASS_CAVITY_SLIDER, subtype, EvidenceResolutionStatus.CORROBORATED,
            pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
            True, True, tuple(reasons),
        )

    # 2. Push-pull / paired double-swing branch (zero wall pocket).
    is_paired_both_jambs = (hinged_at_a >= 1 and hinged_at_b >= 1) or (arcs_at_a >= 1 and arcs_at_b >= 1)
    is_double_action_both_sides = len(all_swing_sides) == 2 and (valid_arcs >= 2 or hinged_leaves >= 2)
    if (is_paired_both_jambs or is_double_action_both_sides) and parallel_inband_leaves == 0:
        if has_slider_text:
            return _make_result(
                obs, CLASS_CONFLICT, None, EvidenceResolutionStatus.CONFLICT,
                pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
                False, False, ("text_vs_geometry_operation_conflict",),
            )
        subtype = (
            SUBTYPE_DOUBLE_ACTION_PUSH_PULL if is_double_action_both_sides else SUBTYPE_PAIRED_DOUBLE_SWING
        )
        reasons = ["push_pull_or_paired_swing_cues_corroborated"]
        if has_push_pull_text:
            reasons.append("push_pull_text_cue_corroborated")
        return _make_result(
            obs, CLASS_PUSH_PULL_PAIRED, subtype, EvidenceResolutionStatus.CORROBORATED,
            pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
            False, False, tuple(reasons),
        )

    # 3. Single hinged swing door branch.
    if hinged_leaves == 1 and valid_arcs == 1 and len(all_swing_sides) == 1 and parallel_inband_leaves == 0:
        if has_slider_text or has_push_pull_text:
            return _make_result(
                obs, CLASS_CONFLICT, None, EvidenceResolutionStatus.CONFLICT,
                pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
                False, False, ("text_vs_geometry_operation_conflict",),
            )
        return _make_result(
            obs, CLASS_SINGLE_SWING, SUBTYPE_SINGLE_HINGED, EvidenceResolutionStatus.CORROBORATED,
            pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
            False, False, ("single_swing_door_cues_corroborated",),
        )

    # Text cues alone or incomplete geometry abstain cleanly.
    return _make_result(
        obs, CLASS_ABSTAINED, None, EvidenceResolutionStatus.ABSTAINED,
        pocket_sides, parallel_inband_leaves, hinged_leaves, valid_arcs, len(all_swing_sides),
        False, False, ("insufficient_door_operation_cues",),
    )


def _make_result(
    obs: DoorApertureSymbolObservation,
    classification: str,
    subtype: str | None,
    status: EvidenceResolutionStatus,
    pocket_sides: int,
    parallel_leaves: int,
    hinged_leaves: int,
    valid_arcs: int,
    swing_sides: int,
    retains_cont: bool,
    excludes_pocket: bool,
    reasons: tuple[str, ...],
) -> DoorOperationDiscriminationShadow:
    record_id = stable_contract_id(
        "door_operation_discrimination_shadow",
        {
            "opening_id": obs.opening_id,
            "document_id": obs.document_id,
            "revision_id": obs.revision_id,
            "source_sha256": obs.source_sha256,
            "page_id": obs.page_id,
            "viewport_id": obs.viewport_id,
            "host_wall_id": obs.host_wall_id,
            "classification": classification,
            "subtype": subtype,
            "status": status.value,
            "reason_codes": reasons,
        },
    )
    return DoorOperationDiscriminationShadow(
        record_id=record_id,
        opening_id=obs.opening_id,
        document_id=obs.document_id,
        revision_id=obs.revision_id,
        source_sha256=obs.source_sha256,
        page_id=obs.page_id,
        viewport_id=obs.viewport_id,
        host_wall_id=obs.host_wall_id,
        classification=classification,
        subtype=subtype,
        status=status,
        pocket_side_count=pocket_sides,
        parallel_inband_leaf_count=parallel_leaves,
        hinged_leaf_count=hinged_leaves,
        valid_swing_arc_count=valid_arcs,
        swing_sides_occupied=swing_sides,
        retains_wall_continuity_over_pocket=retains_cont,
        wall_cut_excludes_pocket=excludes_pocket,
        reason_codes=reasons,
        commercial_authority_granted=False,
        opening_kind_authority_granted=False,
    )


__all__ = [
    "CLASS_ABSTAINED",
    "CLASS_CAVITY_SLIDER",
    "CLASS_CONFLICT",
    "CLASS_PUSH_PULL_PAIRED",
    "CLASS_SINGLE_SWING",
    "DoorApertureSymbolObservation",
    "DoorOperationDiscriminationShadow",
    "SCHEMA_VERSION",
    "SUBTYPE_BIPARTING_CAVITY_SLIDER",
    "SUBTYPE_DOUBLE_ACTION_PUSH_PULL",
    "SUBTYPE_PAIRED_DOUBLE_SWING",
    "SUBTYPE_SINGLE_CAVITY_SLIDER",
    "SUBTYPE_SINGLE_HINGED",
    "SwingArcCue",
    "classify_door_operation_cues",
]
