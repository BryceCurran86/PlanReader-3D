"""Autonomous structural opening accuracy recovery — Milestone 3.

Source-neutral through-wall aperture hosting hypotheses; not original-source authority.
Reconciles whole-opening apertures (e.g. Maryborough W05, W03/W01, W02) with continuous
loadbearing through-walls and narrow inter-aperture structural dividing piers.

Enforces:
1. Through-wall continuity: Openings are hosted in continuous structural walls without
   destroying through-wall continuity or fragmenting the parent wall into severed stubs.
2. Narrow inter-aperture pier hypotheses: a geometric gap cannot authenticate a solid
   structural pier without independent original-source wall evidence.
3. Strict fail-closed geometric validation: Fails closed on transverse wall crossings,
   angular misalignment (> 1°), or transverse displacements exceeding wall half-thickness.
4. Strict shadow isolation: commercial_projection_allowed=False, takeoff_eligible=False.
"""

from __future__ import annotations

import math
from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

DEFAULT_SNAP_TOLERANCE_PT = 2.5
_ALIGNMENT_COS_TOL = 0.9995  # ~1.8 degrees tolerance
_COORD_TOL = 1e-4


def _finite_real(value: object) -> bool:
    """Reject non-numeric, Boolean, nonfinite and unrepresentably large coordinates."""
    if type(value) not in (int, float):
        return False
    if type(value) is int and abs(value) > 2**53:
        return False  # distinct source integers would alias on float conversion
    try:
        return math.isfinite(float(value))
    except (OverflowError, ValueError):
        return False


def _finite_point(point: object) -> bool:
    """A source-coordinate pair must contain two real, finite, non-Boolean values."""
    return (
        type(point) in (tuple, list)
        and len(point) == 2
        and all(_finite_real(value) for value in point)
    )


@dataclass(frozen=True)
class ContinuousThroughWallCandidate:
    """A continuous structural through-wall running through an architectural plan."""

    wall_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    thickness_pt: float

    def __post_init__(self) -> None:
        if not self.wall_id.strip():
            raise ValueError("wall_id required")
        if (not _finite_real(self.thickness_pt) or self.thickness_pt <= 0.0):
            raise ValueError("thickness_pt must be positive and finite")
        if not _finite_point(self.start_pt) or not _finite_point(self.end_pt):
            raise ValueError("Through-wall endpoints must have finite coordinates")
        dx = self.end_pt[0] - self.start_pt[0]
        dy = self.end_pt[1] - self.start_pt[1]
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance) or distance <= _COORD_TOL:
            raise ValueError("Through-wall start and end points must be distinct and finite")
        # A frozen record cannot retain mutable caller-owned endpoint lists.
        object.__setattr__(self, "start_pt", tuple(float(v) for v in self.start_pt))
        object.__setattr__(self, "end_pt", tuple(float(v) for v in self.end_pt))

    @property
    def length_pt(self) -> float:
        dx = self.end_pt[0] - self.start_pt[0]
        dy = self.end_pt[1] - self.start_pt[1]
        return math.hypot(dx, dy)

    @property
    def axis_unit(self) -> tuple[float, float]:
        dx = self.end_pt[0] - self.start_pt[0]
        dy = self.end_pt[1] - self.start_pt[1]
        length = self.length_pt
        return (dx / length, dy / length)

    @property
    def normal_unit(self) -> tuple[float, float]:
        ax, ay = self.axis_unit
        return (-ay, ax)

    @property
    def origin_pt(self) -> tuple[float, float]:
        return self.start_pt


@dataclass(frozen=True)
class InterAperturePierRecord:
    """A structural wall pier bridging consecutive openings along a through-wall."""

    pier_id: str
    pier_start_station: float
    pier_end_station: float
    pier_width_pt: float
    left_opening_id: str
    right_opening_id: str
    is_structural_masonry_pier: bool | None = None
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    first_remaining_gate: str = "original_source_structural_pier_unverified"


@dataclass(frozen=True)
class ApertureHostCandidateInput:
    """Input whole-opening aperture to be bound to a host through-wall."""

    physical_opening_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    terminal_jamb_observation_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.physical_opening_id.strip():
            raise ValueError("physical_opening_id required")
        if not _finite_point(self.start_pt) or not _finite_point(self.end_pt):
            raise ValueError("Aperture endpoints must have finite coordinates")
        dx = self.end_pt[0] - self.start_pt[0]
        dy = self.end_pt[1] - self.start_pt[1]
        distance = math.hypot(dx, dy)
        if not math.isfinite(distance) or distance <= _COORD_TOL:
            raise ValueError("Aperture start and end points must be distinct and finite")
        observations = self.terminal_jamb_observation_ids
        if (type(observations) not in (tuple, list)
                or any(not isinstance(v, str) or not v.strip() for v in observations)
                or len(set(observations)) != len(observations)):
            raise ValueError("terminal_jamb_observation_ids must be distinct nonblank strings")
        object.__setattr__(self, "start_pt", tuple(float(v) for v in self.start_pt))
        object.__setattr__(self, "end_pt", tuple(float(v) for v in self.end_pt))
        object.__setattr__(self, "terminal_jamb_observation_ids", tuple(sorted(observations)))


@dataclass(frozen=True)
class ThroughWallHostedOpeningRecord:
    """Immutable record binding a whole-opening aperture to a continuous host wall."""

    hosting_record_id: str
    physical_opening_id: str
    host_wall_id: str
    u0_pt: float
    u1_pt: float
    whole_wall_length_pt: float
    wall_thickness_pt: float
    axis_unit: tuple[float, float]
    normal_unit: tuple[float, float]
    origin_pt: tuple[float, float]
    opening_start_pt: tuple[float, float]
    opening_end_pt: tuple[float, float]
    terminal_jamb_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    first_remaining_gate: str
    adjacent_pier_ids: tuple[str, ...] = ()
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    shadow_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "hosting_record_id": self.hosting_record_id,
            "physical_opening_id": self.physical_opening_id,
            "host_wall_id": self.host_wall_id,
            "opening_start_pt": list(self.opening_start_pt),
            "opening_end_pt": list(self.opening_end_pt),
            "terminal_jamb_observation_ids": list(self.terminal_jamb_observation_ids),
            "u0_pt": self.u0_pt,
            "u1_pt": self.u1_pt,
            "whole_wall_length_pt": self.whole_wall_length_pt,
            "wall_thickness_pt": self.wall_thickness_pt,
            "axis_unit": list(self.axis_unit),
            "normal_unit": list(self.normal_unit),
            "origin_pt": list(self.origin_pt),
            "status": self.status.value,
            "first_remaining_gate": self.first_remaining_gate,
            "adjacent_pier_ids": list(self.adjacent_pier_ids),
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
            "shadow_only": self.shadow_only,
        }


class StructuralThroughWallApertureHostProducer:
    """Producer responsible for structuring through-wall hosting evidence."""

    def __init__(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
    ) -> None:
        if not document_id.strip():
            raise ValueError("document_id required")
        if not revision_id.strip():
            raise ValueError("revision_id required")
        if not source_sha256.strip():
            raise ValueError("source_sha256 required")
        self._document_id = document_id
        self._revision_id = revision_id
        self._source_sha256 = source_sha256

    @property
    def document_id(self) -> str:
        return self._document_id

    @property
    def revision_id(self) -> str:
        return self._revision_id

    @property
    def source_sha256(self) -> str:
        return self._source_sha256


class StructuralThroughWallApertureHostAuthority:
    """Authority evaluating through-wall continuity, inter-aperture piers, and host frame geometry."""

    def __init__(self, producer: StructuralThroughWallApertureHostProducer) -> None:
        self._producer = producer

    def bind_openings_to_through_wall(
        self,
        *,
        through_wall: ContinuousThroughWallCandidate,
        openings: Sequence[ApertureHostCandidateInput],
        transverse_wall_segments: Sequence[
            tuple[tuple[float, float], tuple[float, float]]
        ] = (),
        snap_tolerance_pt: float = DEFAULT_SNAP_TOLERANCE_PT,
    ) -> tuple[
        tuple[ThroughWallHostedOpeningRecord, ...], tuple[InterAperturePierRecord, ...]
    ]:
        """Bind whole-opening apertures to a continuous through-wall, resolving inter-aperture piers."""
        if (not _finite_real(snap_tolerance_pt)
                or not 0.0 <= snap_tolerance_pt <= DEFAULT_SNAP_TOLERANCE_PT):
            raise ValueError("snap_tolerance_pt must be finite and within the 2.5pt cap")
        # Every supplied transverse obstruction belongs to the candidate universe.
        # A malformed/NaN crossing cannot be silently treated as "no obstruction".
        # Validate even when there are no openings, so bad evidence never disappears.
        for segment in transverse_wall_segments:
            if (type(segment) not in (tuple, list) or len(segment) != 2
                    or not _finite_point(segment[0]) or not _finite_point(segment[1])):
                raise ValueError("transverse_wall_segments require finite endpoint pairs")
            dx = segment[1][0] - segment[0][0]
            dy = segment[1][1] - segment[0][1]
            distance = math.hypot(dx, dy)
            if not math.isfinite(distance) or distance <= _COORD_TOL:
                raise ValueError("transverse_wall_segments require distinct finite endpoints")
        if not openings:
            return ((), ())

        wall_len = through_wall.length_pt
        ax, ay = through_wall.axis_unit
        nx, ny = through_wall.normal_unit
        ox, oy = through_wall.origin_pt
        half_thick = through_wall.thickness_pt / 2.0

        def project_pt(p: tuple[float, float]) -> tuple[float, float]:
            rel_x = p[0] - ox
            rel_y = p[1] - oy
            # Individually finite endpoints can still overflow when projected
            # against a distant wall origin. NaN comparisons would bypass the
            # wall-band and extent veto and could fabricate a full-wall host.
            if not math.isfinite(rel_x) or not math.isfinite(rel_y):
                raise ValueError("aperture projection must remain finite")
            along = rel_x * ax + rel_y * ay
            perp = rel_x * nx + rel_y * ny
            if not math.isfinite(along) or not math.isfinite(perp):
                raise ValueError("aperture projection must remain finite")
            return along, perp

        intermediate_openings: list[dict[str, Any]] = []

        for op in openings:
            p1_along, p1_perp = project_pt(op.start_pt)
            p2_along, p2_perp = project_pt(op.end_pt)

            u_min = min(p1_along, p2_along)
            u_max = max(p1_along, p2_along)
            # 1. Check angular alignment with wall axis
            op_dx = op.end_pt[0] - op.start_pt[0]
            op_dy = op.end_pt[1] - op.start_pt[1]
            op_len = math.hypot(op_dx, op_dy)
            cos_theta = abs((op_dx * ax + op_dy * ay) / op_len)
            if not math.isfinite(cos_theta):
                raise ValueError("aperture alignment must remain finite")
            if cos_theta < _ALIGNMENT_COS_TOL:
                status = EvidenceResolutionStatus.ABSTAINED
                gate = "aperture_wall_axis_misaligned"
                rec = self._make_record(
                    op, through_wall, u_min, u_max, status, gate
                )
                intermediate_openings.append(
                    {"rec": rec, "u_min": u_min, "u_max": u_max, "valid": False}
                )
                continue

            # Both physical jamb endpoints must lie in the proved wall band.
            # Their *average* can be zero even when each is outside it (a long,
            # slightly oblique opening may still pass the angular threshold).
            # Do not elect a host from a centroid-only coincidence.
            # 2. Check transverse displacement from wall centerline
            if max(abs(p1_perp), abs(p2_perp)) > half_thick + snap_tolerance_pt:
                status = EvidenceResolutionStatus.ABSTAINED
                gate = "aperture_outside_host_wall_band"
                rec = self._make_record(
                    op, through_wall, u_min, u_max, status, gate
                )
                intermediate_openings.append(
                    {"rec": rec, "u_min": u_min, "u_max": u_max, "valid": False}
                )
                continue

            # 3. Check bounds along wall length
            if u_min < -snap_tolerance_pt or u_max > wall_len + snap_tolerance_pt:
                status = EvidenceResolutionStatus.ABSTAINED
                gate = "aperture_extends_beyond_wall_extent"
                rec = self._make_record(
                    op, through_wall, u_min, u_max, status, gate
                )
                intermediate_openings.append(
                    {"rec": rec, "u_min": u_min, "u_max": u_max, "valid": False}
                )
                continue

            # A snap allowance cannot manufacture a physical host interval.
            # Both endpoints may lie just outside a wall end and still pass
            # the ±2.5pt extent check; clipping must leave real wall overlap.
            clipped_u_min = max(0.0, u_min)
            clipped_u_max = min(wall_len, u_max)
            if clipped_u_max - clipped_u_min <= _COORD_TOL:
                rec = self._make_record(
                    op, through_wall, u_min, u_max,
                    EvidenceResolutionStatus.ABSTAINED,
                    "aperture_no_host_wall_overlap",
                )
                intermediate_openings.append(
                    {"rec": rec, "u_min": u_min, "u_max": u_max, "valid": False}
                )
                continue

            # 4. Check transverse wall crossings obstructing the opening
            obstructed = False
            for t_start, t_end in transverse_wall_segments:
                t1_along, t1_perp = project_pt(t_start)
                t2_along, t2_perp = project_pt(t_end)
                # Clip the WHOLE finite segment against the open interior of
                # the opening's wall band. Both obstacle endpoints may lie
                # outside the opening while the segment crosses its centre.
                # An endpoint-only station test would miss that obstruction.
                if not all(math.isfinite(value) for value in (
                    t1_along, t1_perp, t2_along, t2_perp,
                )):
                    raise ValueError("transverse_wall_segments projection must be finite")
                # A fixed snap trim can swallow a narrow opening entirely,
                # skipping a real transverse structural obstruction. Reduce
                # the trim conservatively to retain a physical test interior.
                interior_margin = min(snap_tolerance_pt, (u_max - u_min) / 4.0)
                u_low = u_min + interior_margin
                u_high = u_max - interior_margin
                if u_low >= u_high:
                    obstructed = True  # numerically unresolved: fail closed
                    break
                t_low, t_high = 0.0, 1.0
                for v0, v1, low, high in (
                    (t1_along, t2_along, u_low, u_high),
                    (t1_perp, t2_perp, -half_thick, half_thick),
                ):
                    delta = v1 - v0
                    if delta == 0.0:
                        if not low < v0 < high:
                            break
                        continue
                    enter = (low - v0) / delta
                    leave = (high - v0) / delta
                    t_low = max(t_low, min(enter, leave))
                    t_high = min(t_high, max(enter, leave))
                    if t_low >= t_high:
                        break
                else:
                    obstructed = True
                    break

            if obstructed:
                status = EvidenceResolutionStatus.ABSTAINED
                gate = "host_through_wall_obstructed"
                rec = self._make_record(
                    op, through_wall, u_min, u_max, status, gate
                )
                intermediate_openings.append(
                    {"rec": rec, "u_min": u_min, "u_max": u_max, "valid": False}
                )
                continue

            # Passed all structural gating
            intermediate_openings.append(
                {
                    "op": op,
                    "u_min": max(0.0, u_min),
                    "u_max": min(wall_len, u_max),
                    "valid": True,
                }
            )

        # 5. Evaluate consecutive openings to discover inter-aperture piers
        valid_items = [item for item in intermediate_openings if item["valid"]]
        valid_items.sort(
            key=lambda x: (x["u_min"], x["u_max"], x["op"].physical_opening_id)
        )

        # Independently named apertures cannot both corroborate overlapping
        # physical wall intervals. Keep EVERY candidate and abstain on the
        # entire overlap-connected component, including nested intervals.
        # Also reject repeated physical identities even at disjoint stations:
        # a single physical opening cannot occupy two distinct wall spans.
        conflicting_positions: set[int] = set()
        if valid_items:
            component = [0]
            component_end = valid_items[0]["u_max"]
            for index in range(1, len(valid_items)):
                item = valid_items[index]
                if item["u_min"] < component_end:
                    component.append(index)
                    component_end = max(component_end, item["u_max"])
                else:
                    if len(component) > 1:
                        conflicting_positions.update(component)
                    component = [index]
                    component_end = item["u_max"]
            if len(component) > 1:
                conflicting_positions.update(component)

        # Identity conflicts belong to the COMPLETE observation universe, not
        # just the candidates which passed geometry. Otherwise a separately
        # ABSTAINED observation of the same physical opening silently disappears
        # and its valid sibling can be incorrectly corroborated.
        identity_occurrences: dict[str, int] = {}
        for opening in openings:
            identity_occurrences[opening.physical_opening_id] = (
                identity_occurrences.get(opening.physical_opening_id, 0) + 1
            )
        for index, item in enumerate(valid_items):
            if identity_occurrences[item["op"].physical_opening_id] > 1:
                conflicting_positions.add(index)

        # One native terminal jamb observation cannot prove two different
        # physical apertures, even when their station intervals are disjoint.
        # Consult the COMPLETE observation universe: an already-rejected
        # sibling must not disappear and silently validate the other claim.
        observation_owners: dict[str, set[str]] = {}
        for opening in openings:
            for observation_id in opening.terminal_jamb_observation_ids:
                observation_owners.setdefault(observation_id, set()).add(
                    opening.physical_opening_id
                )
        reused_observations = {
            observation_id for observation_id, owners in observation_owners.items()
            if len(owners) > 1
        }
        observation_conflicts = {
            index for index, item in enumerate(valid_items)
            if reused_observations.intersection(
                item["op"].terminal_jamb_observation_ids
            )
        }

        for index in sorted(conflicting_positions | observation_conflicts):
            item = valid_items[index]
            item["valid"] = False
            item["rec"] = self._make_record(
                item["op"],
                through_wall,
                item["u_min"],
                item["u_max"],
                EvidenceResolutionStatus.ABSTAINED,
                (
                    "aperture_terminal_jamb_observation_conflict"
                    if index in observation_conflicts
                    else "aperture_physical_interval_conflict"
                ),
            )

        # A rejected geometric opening can still occupy a plausible host-wall
        # station interval. Excluding it from valid_items must not silently
        # make its two surviving neighbors consecutive physical apertures.
        # Far-off-band observations cannot veto an unrelated pier candidate.
        unresolved_wall_band_intervals: list[tuple[float, float]] = []
        for item in intermediate_openings:
            if item["valid"]:
                continue
            low = max(0.0, item["u_min"])
            high = min(wall_len, item["u_max"])
            if high <= low:
                continue
            rejected = item["rec"]
            _, p0_perp = project_pt(rejected.opening_start_pt)
            _, p1_perp = project_pt(rejected.opening_end_pt)
            if max(abs(p0_perp), abs(p1_perp)) <= half_thick + snap_tolerance_pt:
                unresolved_wall_band_intervals.append((low, high))

        # An in-band rejected aperture blocks a gap iff its low station is
        # strictly below the next opening start AND its high station is
        # strictly above the previous opening end.  Prefix maximum highs
        # over sorted lows answer that exact predicate in logarithmic time,
        # rather than scanning every rejected interval for every candidate.
        unresolved_wall_band_intervals.sort()
        rejected_lows: list[float] = []
        rejected_prefix_highs: list[float] = []
        greatest_high = -math.inf
        for low, high in unresolved_wall_band_intervals:
            rejected_lows.append(low)
            greatest_high = max(greatest_high, high)
            rejected_prefix_highs.append(greatest_high)

        piers: list[InterAperturePierRecord] = []
        pier_ids_by_opening: dict[str, list[str]] = {}

        for i in range(len(valid_items) - 1):
            curr = valid_items[i]
            nxt = valid_items[i + 1]
            # Never bridge an ambiguous physical aperture to manufacture a
            # structural pier between otherwise disjoint candidates.
            if not curr["valid"] or not nxt["valid"]:
                continue
            # An abstained same-band candidate inside the proposed gap leaves
            # physical consecutiveness unresolved, so no pier is inferred.
            # bisect_left excludes low == next start; the strict prefix
            # comparison excludes high == previous end (edge touch only).
            cutoff = bisect_left(rejected_lows, nxt["u_min"])
            if cutoff and rejected_prefix_highs[cutoff - 1] > curr["u_max"]:
                continue
            gap = nxt["u_min"] - curr["u_max"]
            if (
                0.5 <= gap <= 60.0
            ):  # Narrow structural pier (e.g. 7.44 pt in Maryborough)
                pier_payload = {
                    "document_id": self._producer.document_id,
                    "revision_id": self._producer.revision_id,
                    "source_sha256": self._producer.source_sha256,
                    "host_wall_id": through_wall.wall_id,
                    "host_start_pt": tuple(float(v).hex() for v in through_wall.start_pt),
                    "host_end_pt": tuple(float(v).hex() for v in through_wall.end_pt),
                    "host_thickness_pt": float(through_wall.thickness_pt).hex(),
                    "left_opening_id": curr["op"].physical_opening_id,
                    "right_opening_id": nxt["op"].physical_opening_id,
                    "left_jamb_endpoints": tuple(sorted(
                        tuple(float(v).hex() for v in p)
                        for p in (curr["op"].start_pt, curr["op"].end_pt)
                    )),
                    "right_jamb_endpoints": tuple(sorted(
                        tuple(float(v).hex() for v in p)
                        for p in (nxt["op"].start_pt, nxt["op"].end_pt)
                    )),
                    "left_jamb_observations": curr["op"].terminal_jamb_observation_ids,
                    "right_jamb_observations": nxt["op"].terminal_jamb_observation_ids,
                    "start_station": float(curr["u_max"]).hex(),
                    "end_station": float(nxt["u_min"]).hex(),
                    "width_pt": float(gap).hex(),
                }
                pier_id = stable_contract_id(
                    "inter_aperture_pier", pier_payload, digest_chars=32
                )
                pier_rec = InterAperturePierRecord(
                    pier_id=pier_id,
                    pier_start_station=curr["u_max"],
                    pier_end_station=nxt["u_min"],
                    pier_width_pt=gap,
                    left_opening_id=curr["op"].physical_opening_id,
                    right_opening_id=nxt["op"].physical_opening_id,
                    is_structural_masonry_pier=None,
                )
                piers.append(pier_rec)
                pier_ids_by_opening.setdefault(
                    curr["op"].physical_opening_id, []
                ).append(pier_id)
                pier_ids_by_opening.setdefault(
                    nxt["op"].physical_opening_id, []
                ).append(pier_id)

        # Assemble final records
        final_records: list[ThroughWallHostedOpeningRecord] = []
        for item in intermediate_openings:
            if not item["valid"]:
                final_records.append(item["rec"])
            else:
                op = item["op"]
                op_id = op.physical_opening_id
                adjacent_piers = tuple(pier_ids_by_opening.get(op_id, ()))
                rec = self._make_record(
                    op,
                    through_wall,
                    item["u_min"],
                    item["u_max"],
                    EvidenceResolutionStatus.CANDIDATE,
                    "original_source_host_unverified",
                    adjacent_piers=adjacent_piers,
                )
                final_records.append(rec)

        return tuple(final_records), tuple(piers)

    def _make_record(
        self,
        opening: ApertureHostCandidateInput,
        through_wall: ContinuousThroughWallCandidate,
        u0: float,
        u1: float,
        status: EvidenceResolutionStatus,
        gate: str,
        adjacent_piers: tuple[str, ...] = (),
    ) -> ThroughWallHostedOpeningRecord:
        # Projected stations alone alias transversely shifted or clipped jambs.
        opening_start, opening_end = sorted((opening.start_pt, opening.end_pt))
        payload = {
            "document_id": self._producer.document_id,
            "revision_id": self._producer.revision_id,
            "source_sha256": self._producer.source_sha256,
            "physical_opening_id": opening.physical_opening_id,
            "host_wall_id": through_wall.wall_id,
            "opening_start_pt": tuple(float(v).hex() for v in opening_start),
            "opening_end_pt": tuple(float(v).hex() for v in opening_end),
            "terminal_jamb_observation_ids": opening.terminal_jamb_observation_ids,
            "host_start_pt": tuple(float(v).hex() for v in through_wall.start_pt),
            "host_end_pt": tuple(float(v).hex() for v in through_wall.end_pt),
            "host_thickness_pt": float(through_wall.thickness_pt).hex(),
            "u0_pt": float(u0).hex(),
            "u1_pt": float(u1).hex(),
            "status": status.value,
            "first_remaining_gate": gate,
            # The record's lineage includes its geometric neighbor relationships.
            # Otherwise one isolated host and the same host with a candidate
            # pier share an ID despite different adjacent_pier_ids in to_dict().
            "adjacent_pier_ids": tuple(sorted(adjacent_piers)),
        }
        rec_id = stable_contract_id(
            "through_wall_hosted_opening", payload, digest_chars=32
        )
        return ThroughWallHostedOpeningRecord(
            hosting_record_id=rec_id,
            physical_opening_id=opening.physical_opening_id,
            host_wall_id=through_wall.wall_id,
            opening_start_pt=opening_start,
            opening_end_pt=opening_end,
            terminal_jamb_observation_ids=opening.terminal_jamb_observation_ids,
            u0_pt=u0,
            u1_pt=u1,
            whole_wall_length_pt=through_wall.length_pt,
            wall_thickness_pt=through_wall.thickness_pt,
            axis_unit=through_wall.axis_unit,
            normal_unit=through_wall.normal_unit,
            origin_pt=through_wall.origin_pt,
            status=status,
            first_remaining_gate=gate,
            adjacent_pier_ids=adjacent_piers,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            shadow_only=True,
        )
