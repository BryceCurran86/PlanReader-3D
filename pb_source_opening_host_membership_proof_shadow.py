"""Item 17: Opening host wall membership proof shadow.

Proves unique physical host-wall band membership for an authenticated opening
aperture and explicitly rejects:
- Parallel-neighbor walls (e.g., opposite corridor wall, twin acoustic leaf,
  adjacent parallel parapet/balustrade) that do not share the opening's
  coplanar wall-band centerline & thickness envelope;
- Cross-viewport, cross-page, cross-revision, and cross-document walls;
- Detached axial walls whose jamb gap does not span the opening's proven jambs;
- Competing overlapping host wall candidates unless upstream equivalence
  explicitly certifies SAME_PHYSICAL_WALL.

Pure Euclidean geometry -> invariant under rotation and translation.
Shadow-only; never grants commercial or measurement authority and contains zero
job-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
from typing import Any, Mapping, Sequence


_ANGLE_TOL_DEG = 5.0
_DEFAULT_CENTERLINE_OFFSET_RATIO = 0.25
_DEFAULT_JAMB_OVERLAP_TOL_PTS = 2.5


def _clean(value: object) -> str:
    return str(value or "").strip()


def _normalize(v: tuple[float, float]) -> tuple[float, float]:
    mag = math.hypot(v[0], v[1])
    if not math.isfinite(mag) or mag <= 1e-9:
        raise ValueError("vector must be non-zero and finite")
    return (v[0] / mag, v[1] / mag)


def _angle_deg(u: tuple[float, float], v: tuple[float, float]) -> float:
    dot = abs(max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1])))
    return math.degrees(math.acos(dot))


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class HostLineageRef:
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
class PhysicalOpeningApertureWitness:
    """Source-authenticated physical opening aperture with proven jamb endpoints."""

    opening_id: str
    lineage: HostLineageRef
    jamb_a_pt: tuple[float, float]
    jamb_b_pt: tuple[float, float]
    wall_thickness_pts: float
    source_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateHostWallBand:
    """Candidate host wall band described by centerline segment + thickness."""

    wall_id: str
    lineage: HostLineageRef
    p0: tuple[float, float]
    p1: tuple[float, float]
    thickness_pts: float
    wall_role: str = "structural_wall"
    physical_wall_equivalence_group: str | None = None


@dataclass(frozen=True)
class CandidateHostRejection:
    wall_id: str
    reason: str
    perpendicular_offset_pts: float | None = None
    angle_delta_deg: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "wall_id": self.wall_id,
            "reason": self.reason,
            "perpendicular_offset_pts": (
                round(self.perpendicular_offset_pts, 4)
                if self.perpendicular_offset_pts is not None
                else None
            ),
            "angle_delta_deg": (
                round(self.angle_delta_deg, 4)
                if self.angle_delta_deg is not None
                else None
            ),
        }


@dataclass(frozen=True)
class OpeningHostMembershipProof:
    proof_id: str
    opening_id: str
    proven: bool
    abstained: bool
    proven_host_wall_id: str | None
    equivalent_member_wall_ids: tuple[str, ...]
    rejections: tuple[CandidateHostRejection, ...]
    blocking_reasons: tuple[str, ...]
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_id": self.proof_id,
            "opening_id": self.opening_id,
            "proven": self.proven,
            "abstained": self.abstained,
            "proven_host_wall_id": self.proven_host_wall_id,
            "equivalent_member_wall_ids": list(self.equivalent_member_wall_ids),
            "rejections": [r.to_dict() for r in self.rejections],
            "blocking_reasons": list(self.blocking_reasons),
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def prove_opening_host_wall_membership_shadow(
    opening: PhysicalOpeningApertureWitness,
    candidate_walls: Sequence[CandidateHostWallBand],
    *,
    same_physical_wall_pairs: Sequence[tuple[str, str]] = (),
    ambiguous_equivalence_wall_ids: Sequence[str] = (),
) -> OpeningHostMembershipProof:
    """Prove unique host-wall membership and reject parallel-neighbor / cross-viewport hosts."""
    opening_id = _clean(opening.opening_id)
    if not opening_id:
        raise ValueError("opening_id is required")
    if not opening.lineage.is_valid():
        raise ValueError("opening lineage must be complete")

    dx = opening.jamb_b_pt[0] - opening.jamb_a_pt[0]
    dy = opening.jamb_b_pt[1] - opening.jamb_a_pt[1]
    span = math.hypot(dx, dy)
    if not math.isfinite(span) or span <= 1e-6:
        raise ValueError("opening jamb span must be positive and finite")
    if not math.isfinite(opening.wall_thickness_pts) or opening.wall_thickness_pts <= 0.0:
        raise ValueError("opening wall_thickness_pts must be positive and finite")

    axis = (dx / span, dy / span)
    normal = (-axis[1], axis[0])
    center = (
        (opening.jamb_a_pt[0] + opening.jamb_b_pt[0]) * 0.5,
        (opening.jamb_a_pt[1] + opening.jamb_b_pt[1]) * 0.5,
    )
    half_span = span * 0.5
    open_lin = opening.lineage.normalized()

    # Build equivalence adjacency from explicit upstream SAME_PHYSICAL_WALL pairs
    equiv_adj: dict[str, set[str]] = {}
    for a, b in same_physical_wall_pairs:
        ca, cb = _clean(a), _clean(b)
        if ca and cb:
            equiv_adj.setdefault(ca, set()).add(cb)
            equiv_adj.setdefault(cb, set()).add(ca)
    ambig_set = frozenset(_clean(w) for w in ambiguous_equivalence_wall_ids if _clean(w))

    rejections: list[CandidateHostRejection] = []
    matched_walls: list[CandidateHostWallBand] = []

    for wall in candidate_walls:
        wid = _clean(wall.wall_id) or "<unnamed>"
        if not wall.lineage.is_valid():
            rejections.append(CandidateHostRejection(wid, "invalid_candidate_wall_lineage"))
            continue

        w_lin = wall.lineage.normalized()
        if w_lin[:3] != open_lin[:3]:
            rejections.append(CandidateHostRejection(wid, "cross_lineage_host_rejected"))
            continue
        if w_lin[3] != open_lin[3]:
            rejections.append(CandidateHostRejection(wid, "cross_page_host_rejected"))
            continue
        if w_lin[4] != open_lin[4]:
            rejections.append(CandidateHostRejection(wid, "cross_viewport_host_rejected"))
            continue

        wdx = wall.p1[0] - wall.p0[0]
        wdy = wall.p1[1] - wall.p0[1]
        wlen = math.hypot(wdx, wdy)
        if not math.isfinite(wlen) or wlen <= 1e-6 or wall.thickness_pts <= 0.0:
            rejections.append(CandidateHostRejection(wid, "degenerate_wall_band_rejected"))
            continue

        w_unit = (wdx / wlen, wdy / wlen)
        ang = _angle_deg(axis, w_unit)
        if ang > _ANGLE_TOL_DEG:
            rejections.append(
                CandidateHostRejection(wid, "non_collinear_wall_angle_rejected", angle_delta_deg=ang)
            )
            continue

        # Project wall endpoints into opening's local (along, perp) frame
        rel0 = (wall.p0[0] - center[0], wall.p0[1] - center[1])
        rel1 = (wall.p1[0] - center[0], wall.p1[1] - center[1])
        perp0 = rel0[0] * normal[0] + rel0[1] * normal[1]
        perp1 = rel1[0] * normal[0] + rel1[1] * normal[1]
        perp_offset = max(abs(perp0), abs(perp1))

        # Tight coplanar band tolerance: strictly rejects parallel neighbor walls
        # offset by even half a wall thickness or across a corridor/cavity gap.
        max_centerline_offset = max(
            1.5, min(opening.wall_thickness_pts, wall.thickness_pts) * _DEFAULT_CENTERLINE_OFFSET_RATIO
        )
        if perp_offset > max_centerline_offset:
            rejections.append(
                CandidateHostRejection(
                    wid,
                    "parallel_neighbor_wall_rejected",
                    perpendicular_offset_pts=perp_offset,
                    angle_delta_deg=ang,
                )
            )
            continue

        # Thickness compatibility check (prevent thin trim/mullion or double-thick neighbor claiming host)
        thick_ratio = max(opening.wall_thickness_pts, wall.thickness_pts) / min(
            opening.wall_thickness_pts, wall.thickness_pts
        )
        if thick_ratio > 1.6:
            rejections.append(
                CandidateHostRejection(
                    wid,
                    "wall_thickness_mismatch_rejected",
                    perpendicular_offset_pts=perp_offset,
                    angle_delta_deg=ang,
                )
            )
            continue

        # Axial containment or jamb-abutment check along opening centerline:
        # Either the whole-wall band spans across the opening [-half_span, +half_span],
        # OR a split host wall segment abuts one of the jambs (within tolerance).
        a0 = rel0[0] * axis[0] + rel0[1] * axis[1]
        a1 = rel1[0] * axis[0] + rel1[1] * axis[1]
        w_min, w_max = min(a0, a1), max(a0, a1)
        spans_opening = (w_min <= -half_span + _DEFAULT_JAMB_OVERLAP_TOL_PTS) and (
            w_max >= half_span - _DEFAULT_JAMB_OVERLAP_TOL_PTS
        )
        abuts_left_jamb = abs(w_max - (-half_span)) <= _DEFAULT_JAMB_OVERLAP_TOL_PTS and w_min < -half_span
        abuts_right_jamb = abs(w_min - half_span) <= _DEFAULT_JAMB_OVERLAP_TOL_PTS and w_max > half_span

        if not (spans_opening or abuts_left_jamb or abuts_right_jamb):
            rejections.append(
                CandidateHostRejection(
                    wid,
                    "axially_detached_wall_rejected",
                    perpendicular_offset_pts=perp_offset,
                    angle_delta_deg=ang,
                )
            )
            continue

        matched_walls.append(wall)

    blocking_reasons: list[str] = []
    proven_host_id: str | None = None
    equiv_members: tuple[str, ...] = ()

    if not matched_walls:
        blocking_reasons.append("no_authenticated_host_wall_found")
    else:
        matched_ids = sorted(w.wall_id for w in matched_walls)
        if any(wid in ambig_set for wid in matched_ids):
            blocking_reasons.append("ambiguous_physical_wall_equivalence_for_host")
        elif len(matched_walls) == 1:
            proven_host_id = matched_walls[0].wall_id
            equiv_members = (proven_host_id,)
        else:
            # Multiple matched wall segments (e.g. left+right split host or dual representation)
            # may collapse ONLY if all matched walls belong to ONE proven physical equivalence class.
            groups = {w.physical_wall_equivalence_group for w in matched_walls if _clean(w.physical_wall_equivalence_group)}
            all_same_group = len(groups) == 1 and all(
                _clean(w.physical_wall_equivalence_group) in groups for w in matched_walls
            )
            # Or check connected component under explicit same_physical_wall_pairs
            visited: set[str] = set()
            stack = [matched_ids[0]]
            matched_set = set(matched_ids)
            while stack:
                cur = stack.pop()
                if cur in visited:
                    continue
                visited.add(cur)
                for nxt in equiv_adj.get(cur, ()):
                    if nxt in matched_set and nxt not in visited:
                        stack.append(nxt)
            all_connected = visited == matched_set

            if all_same_group or all_connected:
                proven_host_id = (
                    next(iter(groups)) if all_same_group else f"equiv_host_{_canonical_sha({'ids': matched_ids})[:12]}"
                )
                equiv_members = tuple(matched_ids)
            else:
                blocking_reasons.append("ambiguous_multiple_distinct_host_candidates")

    proven = proven_host_id is not None and not blocking_reasons
    payload = {
        "opening_id": opening_id,
        "proven": proven,
        "proven_host_wall_id": proven_host_id,
        "equivalent_member_wall_ids": list(equiv_members),
        "rejections": sorted((r.wall_id, r.reason) for r in rejections),
        "blocking_reasons": blocking_reasons,
    }
    digest = _canonical_sha(payload)
    return OpeningHostMembershipProof(
        proof_id=f"host_membership_proof_{digest[:16]}",
        opening_id=opening_id,
        proven=proven,
        abstained=not proven,
        proven_host_wall_id=proven_host_id,
        equivalent_member_wall_ids=equiv_members,
        rejections=tuple(rejections),
        blocking_reasons=tuple(blocking_reasons),
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
