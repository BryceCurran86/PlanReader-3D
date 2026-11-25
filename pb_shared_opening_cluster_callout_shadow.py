"""Source-neutral shadow resolver for shared/adjacent opening clusters and callouts.

Implements Work Order Item 18 as a pure, read-only, default-off shadow evidence
module with zero commercial authority promotion:
- Resolves authenticated two-leg corner opening assemblies (75-105 deg, <= 15 pt
  corner post) and adjacent co-linear shared-pier pairs (<= 15 pt pier) without
  double-counting overlapping legs, shared corner posts, or shared callout text.
- Applies a uniquely owned shared corner/cluster callout to both authenticated
  legs of that assembly when neither leg carries a conflicting callout, while
  strictly refusing to transfer labels across pages, revisions, source hashes,
  viewports, or unrelated assemblies.
- Fails closed (CONFLICT / ABSTAINED) on overlapping/duplicate legs, 3-way
  ambiguous junctions, competing callouts, cross-cluster callout ambiguity, or
  shared-vs-leg callout disagreements.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_structural_corner_aperture_continuity_authority import (
    MAX_CORNER_ANGLE_DEG,
    MAX_CORNER_POST_DIM_PT,
    MAX_LEG_SPAN_PT,
    MIN_CORNER_ANGLE_DEG,
    MIN_LEG_SPAN_PT,
)

SCHEMA_VERSION = "1.0.0"

CLUSTER_CORNER_ASSEMBLY = "corner_two_leg_assembly"
CLUSTER_ADJACENT_SHARED_PIER = "adjacent_shared_pier_cluster"

_COLINEAR_ANGLE_TOL_DEG = 5.0
_COLINEAR_LATERAL_TOL_PT = 2.5
_OVERLAP_TOL_PT = 0.5
_DEFAULT_MAX_CALLOUT_DIST_PT = 90.0
_AMBIGUITY_MARGIN_PT = 12.0
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

Point = tuple[float, float]


def _req_str(value: object, name: str) -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def _req_sha256(value: object, name: str) -> str:
    clean = _req_str(value, name).lower()
    if not _SHA256_RE.fullmatch(clean):
        raise ValueError(f"{name} must be a 64-char hex sha256")
    return clean


def _req_point(value: object, name: str) -> Point:
    if type(value) is not tuple or len(value) != 2:
        raise ValueError(f"{name} must be a 2-tuple of finite floats")
    x, y = value
    if isinstance(x, bool) or isinstance(y, bool):
        raise ValueError(f"{name} must be numeric")
    fx, fy = float(x), float(y)
    if not (math.isfinite(fx) and math.isfinite(fy)):
        raise ValueError(f"{name} must be finite")
    return (fx, fy)


def _opt_pos_mm(value: object, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive int or None")
    return value


@dataclass(frozen=True)
class ClusterOpeningLegCandidate:
    leg_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    host_wall_id: str
    start_pt: Point
    end_pt: Point
    evidence_ids: tuple[str, ...]
    opening_kind: str = "opening"

    def __post_init__(self) -> None:
        object.__setattr__(self, "leg_id", _req_str(self.leg_id, "leg_id"))
        object.__setattr__(self, "document_id", _req_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _req_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "page_id", _req_str(self.page_id, "page_id"))
        object.__setattr__(self, "viewport_id", _req_str(self.viewport_id, "viewport_id"))
        object.__setattr__(self, "host_wall_id", _req_str(self.host_wall_id, "host_wall_id"))
        p0 = _req_point(self.start_pt, "start_pt")
        p1 = _req_point(self.end_pt, "end_pt")
        object.__setattr__(self, "start_pt", p0)
        object.__setattr__(self, "end_pt", p1)
        ev = tuple(sorted({_req_str(v, "evidence_ids") for v in self.evidence_ids}))
        if not ev:
            raise ValueError("evidence_ids must be non-empty")
        object.__setattr__(self, "evidence_ids", ev)
        object.__setattr__(self, "opening_kind", _req_str(self.opening_kind, "opening_kind").lower())

    @property
    def span_pt(self) -> float:
        return math.hypot(self.end_pt[0] - self.start_pt[0], self.end_pt[1] - self.start_pt[1])

    @property
    def scope_key(self) -> tuple[str, str, str, str, str]:
        return (self.document_id, self.revision_id, self.source_sha256, self.page_id, self.viewport_id)


@dataclass(frozen=True)
class OpeningClusterCalloutWitness:
    callout_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    observation_id: str
    raw_text: str
    anchor_pt: Point
    declared_height_mm: int | None = None
    declared_width_mm: int | None = None
    explicit_leg_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "callout_id", _req_str(self.callout_id, "callout_id"))
        object.__setattr__(self, "document_id", _req_str(self.document_id, "document_id"))
        object.__setattr__(self, "revision_id", _req_str(self.revision_id, "revision_id"))
        object.__setattr__(self, "source_sha256", _req_sha256(self.source_sha256, "source_sha256"))
        object.__setattr__(self, "page_id", _req_str(self.page_id, "page_id"))
        object.__setattr__(self, "viewport_id", _req_str(self.viewport_id, "viewport_id"))
        object.__setattr__(self, "observation_id", _req_str(self.observation_id, "observation_id"))
        object.__setattr__(self, "raw_text", _req_str(self.raw_text, "raw_text"))
        object.__setattr__(self, "anchor_pt", _req_point(self.anchor_pt, "anchor_pt"))
        object.__setattr__(self, "declared_height_mm", _opt_pos_mm(self.declared_height_mm, "declared_height_mm"))
        object.__setattr__(self, "declared_width_mm", _opt_pos_mm(self.declared_width_mm, "declared_width_mm"))
        if self.explicit_leg_id is not None:
            clean_leg = str(self.explicit_leg_id).strip()
            object.__setattr__(self, "explicit_leg_id", clean_leg or None)

    @property
    def scope_key(self) -> tuple[str, str, str, str, str]:
        return (self.document_id, self.revision_id, self.source_sha256, self.page_id, self.viewport_id)


@dataclass(frozen=True)
class ClusterMemberCalloutBinding:
    leg_id: str
    host_wall_id: str
    member_count: int
    callout_id: str | None
    callout_observation_id: str | None
    callout_text: str | None
    declared_height_mm: int | None
    declared_width_mm: int | None
    shared_callout_inherited: bool
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class SharedOpeningClusterShadow:
    cluster_id: str
    cluster_kind: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    junction_pt: Point
    separation_pt: float
    angle_deg: float
    leg_ids: tuple[str, ...]
    resolved_leg_count: int
    shared_callout_applied_to_both_legs: bool
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    members: tuple[ClusterMemberCalloutBinding, ...]
    commercial_authority_granted: bool = False


@dataclass(frozen=True)
class SharedOpeningClusterReport:
    schema_version: str
    clusters: tuple[SharedOpeningClusterShadow, ...]
    unclustered_leg_ids: tuple[str, ...]
    conflict_leg_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _unit_vec(a: Point, b: Point) -> Point | None:
    d = _dist(a, b)
    if d <= 1e-9:
        return None
    return ((b[0] - a[0]) / d, (b[1] - a[1]) / d)


def _angle_between_deg(u: Point, v: Point) -> float:
    dot = max(-1.0, min(1.0, abs(u[0] * v[0] + u[1] * v[1])))
    return math.degrees(math.acos(dot))


def _closest_endpoints(leg_a: ClusterOpeningLegCandidate, leg_b: ClusterOpeningLegCandidate) -> tuple[Point, Point, float]:
    pairs = (
        (leg_a.start_pt, leg_b.start_pt),
        (leg_a.start_pt, leg_b.end_pt),
        (leg_a.end_pt, leg_b.start_pt),
        (leg_a.end_pt, leg_b.end_pt),
    )
    best = min(pairs, key=lambda pair: _dist(pair[0], pair[1]))
    return best[0], best[1], _dist(best[0], best[1])


def _segments_overlap_collinear(a: ClusterOpeningLegCandidate, b: ClusterOpeningLegCandidate) -> bool:
    ua = _unit_vec(a.start_pt, a.end_pt)
    ub = _unit_vec(b.start_pt, b.end_pt)
    if ua is None or ub is None:
        return False
    if _angle_between_deg(ua, ub) > _COLINEAR_ANGLE_TOL_DEG:
        return False
    # Lateral distance of b.start_pt from line of a
    dx = b.start_pt[0] - a.start_pt[0]
    dy = b.start_pt[1] - a.start_pt[1]
    lateral = abs(dx * (-ua[1]) + dy * ua[0])
    if lateral > _COLINEAR_LATERAL_TOL_PT:
        return False
    pa = sorted((a.start_pt[0] * ua[0] + a.start_pt[1] * ua[1], a.end_pt[0] * ua[0] + a.end_pt[1] * ua[1]))
    pb = sorted((b.start_pt[0] * ua[0] + b.start_pt[1] * ua[1], b.end_pt[0] * ua[0] + b.end_pt[1] * ua[1]))
    overlap = min(pa[1], pb[1]) - max(pa[0], pb[0])
    return overlap > _OVERLAP_TOL_PT


def _classify_leg_pair(
    a: ClusterOpeningLegCandidate, b: ClusterOpeningLegCandidate,
) -> tuple[str, Point, float, float] | None:
    """Return (cluster_kind, junction_pt, separation_pt, angle_deg) or None."""
    if a.scope_key != b.scope_key:
        return None
    if not (MIN_LEG_SPAN_PT <= a.span_pt <= MAX_LEG_SPAN_PT and MIN_LEG_SPAN_PT <= b.span_pt <= MAX_LEG_SPAN_PT):
        return None
    ua = _unit_vec(a.start_pt, a.end_pt)
    ub = _unit_vec(b.start_pt, b.end_pt)
    if ua is None or ub is None:
        return None
    pa, pb, sep = _closest_endpoints(a, b)
    if sep > MAX_CORNER_POST_DIM_PT:
        return None
    angle = _angle_between_deg(ua, ub)
    junction = ((pa[0] + pb[0]) / 2.0, (pa[1] + pb[1]) / 2.0)

    if MIN_CORNER_ANGLE_DEG <= angle <= MAX_CORNER_ANGLE_DEG and a.host_wall_id != b.host_wall_id:
        return (CLUSTER_CORNER_ASSEMBLY, junction, sep, angle)

    if angle <= _COLINEAR_ANGLE_TOL_DEG and a.host_wall_id == b.host_wall_id:
        dx = b.start_pt[0] - a.start_pt[0]
        dy = b.start_pt[1] - a.start_pt[1]
        lateral = abs(dx * (-ua[1]) + dy * ua[0])
        if lateral <= _COLINEAR_LATERAL_TOL_PT and not _segments_overlap_collinear(a, b):
            return (CLUSTER_ADJACENT_SHARED_PIER, junction, sep, angle)

    return None


def _callouts_conflict(left: OpeningClusterCalloutWitness, right: OpeningClusterCalloutWitness) -> bool:
    if (
        left.declared_height_mm is not None
        and right.declared_height_mm is not None
        and left.declared_height_mm != right.declared_height_mm
    ):
        return True
    if (
        left.declared_width_mm is not None
        and right.declared_width_mm is not None
        and left.declared_width_mm != right.declared_width_mm
    ):
        return True
    if (
        left.declared_height_mm is None
        and left.declared_width_mm is None
        and right.declared_height_mm is None
        and right.declared_width_mm is None
        and left.raw_text.strip().upper() != right.raw_text.strip().upper()
    ):
        return True
    return False


def resolve_shared_opening_clusters(
    *,
    legs: Sequence[ClusterOpeningLegCandidate],
    callouts: Sequence[OpeningClusterCalloutWitness],
    max_shared_callout_distance_pt: float = _DEFAULT_MAX_CALLOUT_DIST_PT,
) -> SharedOpeningClusterReport:
    """Resolve two-leg corner/adjacent clusters and shared callouts without double-counting."""
    if isinstance(max_shared_callout_distance_pt, bool) or not math.isfinite(max_shared_callout_distance_pt) or max_shared_callout_distance_pt <= 0.0:
        raise ValueError("max_shared_callout_distance_pt must be a positive finite float")

    seen_leg_ids: set[str] = set()
    for leg in legs:
        if leg.leg_id in seen_leg_ids:
            raise ValueError(f"duplicate_cluster_leg_id:{leg.leg_id}")
        seen_leg_ids.add(leg.leg_id)

    seen_callout_ids: set[str] = set()
    for callout in callouts:
        if callout.callout_id in seen_callout_ids:
            raise ValueError(f"duplicate_cluster_callout_id:{callout.callout_id}")
        seen_callout_ids.add(callout.callout_id)

    ordered_legs = sorted(legs, key=lambda item: (item.scope_key, item.leg_id))
    conflict_legs: set[str] = set()
    report_reasons: set[str] = set()

    # 1. Reject overlapping/duplicate co-linear legs within the same scope so one
    # physical opening can never be double-counted as two cluster members.
    for i in range(len(ordered_legs)):
        for j in range(i + 1, len(ordered_legs)):
            a, b = ordered_legs[i], ordered_legs[j]
            if a.scope_key == b.scope_key and _segments_overlap_collinear(a, b):
                conflict_legs.add(a.leg_id)
                conflict_legs.add(b.leg_id)
                report_reasons.add("duplicate_or_overlapping_cluster_leg")

    # 2. Discover candidate pairwise cluster edges among non-conflicting legs.
    adj: dict[str, list[tuple[str, str, Point, float, float]]] = {}
    leg_by_id = {leg.leg_id: leg for leg in ordered_legs}
    for i in range(len(ordered_legs)):
        a = ordered_legs[i]
        if a.leg_id in conflict_legs:
            continue
        for j in range(i + 1, len(ordered_legs)):
            b = ordered_legs[j]
            if b.leg_id in conflict_legs:
                continue
            pair = _classify_leg_pair(a, b)
            if pair is not None:
                kind, jpt, sep, angle = pair
                adj.setdefault(a.leg_id, []).append((b.leg_id, kind, jpt, sep, angle))
                adj.setdefault(b.leg_id, []).append((a.leg_id, kind, jpt, sep, angle))

    # 3. Partition connected components: ONLY clean 2-leg components form clusters;
    # 3+-leg components fail closed as ambiguous_multi_leg_cluster.
    visited: set[str] = set()
    raw_clusters: list[tuple[ClusterOpeningLegCandidate, ClusterOpeningLegCandidate, str, Point, float, float]] = []
    for leg in ordered_legs:
        if leg.leg_id in visited or leg.leg_id not in adj:
            continue
        comp: list[str] = []
        stack = [leg.leg_id]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            comp.append(cur)
            for nb, *_ in adj.get(cur, ()):
                if nb not in visited:
                    stack.append(nb)
        if len(comp) != 2:
            conflict_legs.update(comp)
            report_reasons.add("ambiguous_multi_leg_cluster")
            continue
        id_a, id_b = sorted(comp)
        _nb, kind, jpt, sep, angle = adj[id_a][0]
        raw_clusters.append((leg_by_id[id_a], leg_by_id[id_b], kind, jpt, sep, angle))

    # 4. Evaluate shared-callout ownership globally across all clusters in the same
    # scope so one shared callout cannot be claimed by two distinct clusters.
    shared_candidates_by_cluster: dict[int, list[OpeningClusterCalloutWitness]] = {
        idx: [] for idx in range(len(raw_clusters))
    }
    ambiguous_shared_clusters: set[int] = set()
    explicit_by_leg: dict[str, list[OpeningClusterCalloutWitness]] = {}

    for callout in sorted(callouts, key=lambda c: c.callout_id):
        if callout.explicit_leg_id is not None:
            target_leg = leg_by_id.get(callout.explicit_leg_id)
            if target_leg is not None and target_leg.scope_key == callout.scope_key:
                explicit_by_leg.setdefault(target_leg.leg_id, []).append(callout)
            continue
        # Unowned (potentially shared) callout: find all clusters in the EXACT same
        # (document_id, revision_id, source_sha256, page_id, viewport_id) within radius.
        in_range: list[tuple[float, int]] = []
        for idx, (leg_a, _leg_b, _kind, jpt, _sep, _angle) in enumerate(raw_clusters):
            if leg_a.scope_key != callout.scope_key:
                continue
            d = _dist(callout.anchor_pt, jpt)
            if d <= max_shared_callout_distance_pt:
                in_range.append((d, idx))
        if not in_range:
            continue
        in_range.sort(key=lambda pair: (pair[0], pair[1]))
        if len(in_range) >= 2 and (in_range[1][0] - in_range[0][0]) <= _AMBIGUITY_MARGIN_PT:
            # Ambiguous across multiple clusters -> block all tied clusters fail-closed.
            best_dist = in_range[0][0]
            for dist_val, c_idx in in_range:
                if dist_val - best_dist <= _AMBIGUITY_MARGIN_PT:
                    ambiguous_shared_clusters.add(c_idx)
            report_reasons.add("callout_ambiguous_across_clusters")
            continue
        # Also reject if two distinct clusters are BOTH within range and the callout
        # does not clearly belong exclusively to one (within half the distance of the 2nd).
        if len(in_range) >= 2 and in_range[1][0] < in_range[0][0] * 1.5:
            ambiguous_shared_clusters.add(in_range[0][1])
            ambiguous_shared_clusters.add(in_range[1][1])
            report_reasons.add("callout_ambiguous_across_clusters")
            continue
        shared_candidates_by_cluster[in_range[0][1]].append(callout)

    # 5. Build deterministic SharedOpeningClusterShadow records.
    clusters_out: list[SharedOpeningClusterShadow] = []
    clustered_leg_ids: set[str] = set()

    for idx, (leg_a, leg_b, kind, jpt, sep, angle) in enumerate(raw_clusters):
        clustered_leg_ids.add(leg_a.leg_id)
        clustered_leg_ids.add(leg_b.leg_id)
        shared_list = shared_candidates_by_cluster[idx]
        exp_a = explicit_by_leg.get(leg_a.leg_id, [])
        exp_b = explicit_by_leg.get(leg_b.leg_id, [])

        c_reasons: list[str] = []
        shared_applied = False
        members: list[ClusterMemberCalloutBinding] = []

        if idx in ambiguous_shared_clusters:
            c_status = EvidenceResolutionStatus.CONFLICT
            c_reasons.append("callout_ambiguous_across_clusters")
        elif len(shared_list) > 1 or len(exp_a) > 1 or len(exp_b) > 1:
            c_status = EvidenceResolutionStatus.CONFLICT
            c_reasons.append("ambiguous_competing_cluster_callouts")
        elif len(shared_list) == 1:
            shared = shared_list[0]
            # Check for conflict against any explicit per-leg callout.
            conflict_with_explicit = any(_callouts_conflict(shared, ex) for ex in (*exp_a, *exp_b))
            if conflict_with_explicit:
                c_status = EvidenceResolutionStatus.CONFLICT
                c_reasons.append("shared_vs_leg_callout_conflict")
            else:
                c_status = EvidenceResolutionStatus.CORROBORATED
                shared_applied = True
                c_reasons.append("shared_cluster_callout_resolved_to_both_legs")
                for leg, ex_list in ((leg_a, exp_a), (leg_b, exp_b)):
                    chosen = ex_list[0] if ex_list else shared
                    inherited = not bool(ex_list)
                    members.append(
                        ClusterMemberCalloutBinding(
                            leg_id=leg.leg_id,
                            host_wall_id=leg.host_wall_id,
                            member_count=1,
                            callout_id=chosen.callout_id,
                            callout_observation_id=chosen.observation_id,
                            callout_text=chosen.raw_text,
                            declared_height_mm=chosen.declared_height_mm,
                            declared_width_mm=chosen.declared_width_mm,
                            shared_callout_inherited=inherited,
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=(
                                ("shared_callout_inherited_from_authenticated_cluster",)
                                if inherited
                                else ("explicit_leg_callout_corroborated_with_shared_cluster",)
                            ),
                        )
                    )
        elif exp_a or exp_b:
            # Explicit leg-owned callout(s) ONLY — never silently copy leg A's
            # leg-specific callout onto unlabelled leg B.
            c_status = (
                EvidenceResolutionStatus.CORROBORATED
                if (exp_a and exp_b)
                else EvidenceResolutionStatus.ABSTAINED
            )
            c_reasons.append(
                "independent_per_leg_callouts_preserved"
                if (exp_a and exp_b)
                else "partial_explicit_leg_callout_no_cross_transfer"
            )
            for leg, ex_list in ((leg_a, exp_a), (leg_b, exp_b)):
                if ex_list:
                    chosen = ex_list[0]
                    members.append(
                        ClusterMemberCalloutBinding(
                            leg_id=leg.leg_id,
                            host_wall_id=leg.host_wall_id,
                            member_count=1,
                            callout_id=chosen.callout_id,
                            callout_observation_id=chosen.observation_id,
                            callout_text=chosen.raw_text,
                            declared_height_mm=chosen.declared_height_mm,
                            declared_width_mm=chosen.declared_width_mm,
                            shared_callout_inherited=False,
                            status=EvidenceResolutionStatus.CORROBORATED,
                            reason_codes=("explicit_leg_callout_only",),
                        )
                    )
                else:
                    members.append(
                        ClusterMemberCalloutBinding(
                            leg_id=leg.leg_id,
                            host_wall_id=leg.host_wall_id,
                            member_count=1,
                            callout_id=None,
                            callout_observation_id=None,
                            callout_text=None,
                            declared_height_mm=None,
                            declared_width_mm=None,
                            shared_callout_inherited=False,
                            status=EvidenceResolutionStatus.ABSTAINED,
                            reason_codes=("unlabelled_cluster_leg_no_shared_callout",),
                        )
                    )
        else:
            c_status = EvidenceResolutionStatus.ABSTAINED
            c_reasons.append("cluster_geometry_resolved_without_callout")

        if not members:
            for leg in (leg_a, leg_b):
                members.append(
                    ClusterMemberCalloutBinding(
                        leg_id=leg.leg_id,
                        host_wall_id=leg.host_wall_id,
                        member_count=1,
                        callout_id=None,
                        callout_observation_id=None,
                        callout_text=None,
                        declared_height_mm=None,
                        declared_width_mm=None,
                        shared_callout_inherited=False,
                        status=c_status,
                        reason_codes=tuple(c_reasons),
                    )
                )

        cluster_id = stable_contract_id(
            "shared_opening_cluster_shadow",
            {
                "cluster_kind": kind,
                "document_id": leg_a.document_id,
                "revision_id": leg_a.revision_id,
                "source_sha256": leg_a.source_sha256,
                "page_id": leg_a.page_id,
                "viewport_id": leg_a.viewport_id,
                "leg_ids": (leg_a.leg_id, leg_b.leg_id),
                "status": c_status.value,
                "reason_codes": tuple(c_reasons),
            },
        )
        clusters_out.append(
            SharedOpeningClusterShadow(
                cluster_id=cluster_id,
                cluster_kind=kind,
                document_id=leg_a.document_id,
                revision_id=leg_a.revision_id,
                source_sha256=leg_a.source_sha256,
                page_id=leg_a.page_id,
                viewport_id=leg_a.viewport_id,
                junction_pt=(round(jpt[0], 4), round(jpt[1], 4)),
                separation_pt=round(sep, 4),
                angle_deg=round(angle, 4),
                leg_ids=(leg_a.leg_id, leg_b.leg_id),
                resolved_leg_count=2,
                shared_callout_applied_to_both_legs=shared_applied,
                status=c_status,
                reason_codes=tuple(c_reasons),
                members=tuple(members),
                commercial_authority_granted=False,
            )
        )

    unclustered = tuple(
        sorted(
            leg.leg_id
            for leg in ordered_legs
            if leg.leg_id not in clustered_leg_ids and leg.leg_id not in conflict_legs
        )
    )
    return SharedOpeningClusterReport(
        schema_version=SCHEMA_VERSION,
        clusters=tuple(sorted(clusters_out, key=lambda c: c.cluster_id)),
        unclustered_leg_ids=unclustered,
        conflict_leg_ids=tuple(sorted(conflict_legs)),
        reason_codes=tuple(sorted(report_reasons)),
        commercial_authority_granted=False,
    )


__all__ = [
    "CLUSTER_ADJACENT_SHARED_PIER",
    "CLUSTER_CORNER_ASSEMBLY",
    "ClusterMemberCalloutBinding",
    "ClusterOpeningLegCandidate",
    "OpeningClusterCalloutWitness",
    "SCHEMA_VERSION",
    "SharedOpeningClusterReport",
    "SharedOpeningClusterShadow",
    "resolve_shared_opening_clusters",
]
