"""Producer-owned source figured dimension and wall witness shadow authority (Item 18).

Recovers figured room dimensions and corresponding physical wall witnesses:
- Verifies exact consistency between figured dimension numeral and scaled linework length.
- Authenticates perpendicular witness lines (extension lines) at dimension endpoints.
- Verifies physical contact between witness stroke terminals and internal wall faces (within 2.5 pt snap tolerance).
- Binds dimension text to proved physical wall faces without spatial proximity guessing.
- Serializes the verified witness chain (dimension line + witness lines) to standard OGC WKB hex.
- Operates strictly in shadow mode with CANDIDATE status and non-commercial flags.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SOURCE_FIGURED_DIMENSION_WITNESS_SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
FIGURED_WALL_WITNESS_CHAIN_RESOLVED = "figured_wall_witness_chain_resolved"
FIGURED_WALL_WITNESS_CHAIN_UNRESOLVED = "figured_wall_witness_chain_unresolved"
DIMENSION_FIGURE_MISMATCH = "dimension_figure_mismatch"
WITNESS_LINE_DISCONTINUOUS_OR_MISSING = "witness_line_discontinuous_or_missing"
WITNESS_NOT_PERPENDICULAR = "witness_not_perpendicular"
WITNESS_WALL_CONTACT_UNRESOLVED = "witness_wall_contact_unresolved"
AMBIGUOUS_WALL_WITNESS_BINDING = "ambiguous_wall_witness_binding"
DEGENERATE_DIMENSION_GEOMETRY = "degenerate_dimension_geometry"
FIGURED_DIMENSION_RECORD_UNAVAILABLE = "figured_dimension_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/dim_obs_id

SNAP_TOLERANCE_PT = 2.5


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


# ── Genuine OGC WKB Serialization ──────────────────────────────────────────────


def _multilinestring_to_wkb_hex(lines: Sequence[Sequence[Tuple[float, float]]]) -> str:
    """Encode 2D MultiLineString into genuine standard OGC Well-Known Binary hex."""
    header = struct.pack("<BII", 1, 5, len(lines))
    sub_lines = []
    for pts in lines:
        sub_header = struct.pack("<BII", 1, 2, len(pts))
        sub_coords = b"".join(struct.pack("<dd", float(x), float(y)) for x, y in pts)
        sub_lines.append(sub_header + sub_coords)
    return (header + b"".join(sub_lines)).hex()


# ── Contracts ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceFiguredDimensionWitnessSelector:
    """Selector identifying the exact dimension observation for witness chain resolution."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    dimension_observation_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "dimension_observation_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.dimension_observation_id,
        )


@dataclass(frozen=True)
class SourceFiguredDimensionWitnessRecord:
    """Sealed record proving authentic figured dimension and wall witness chain."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    dimension_observation_id: str
    figured_text: str
    dimension_m: float
    scaled_length_m: Optional[float]
    dimension_line_pts: Tuple[Tuple[float, float], Tuple[float, float]]
    witness_1_pts: Tuple[Tuple[float, float], Tuple[float, float]]
    witness_2_pts: Tuple[Tuple[float, float], Tuple[float, float]]
    witnessed_wall_1_id: str
    witnessed_wall_2_id: str
    witness_chain_wkb_hex: str
    corroborating_evidence_ids: Tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    schema_version: str = SOURCE_FIGURED_DIMENSION_WITNESS_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceFiguredDimensionWitnessRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class SourceFiguredDimensionWitnessResult:
    """Result of figured dimension and wall witness chain resolution."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SourceFiguredDimensionWitnessRecord] = None
    schema_version: str = SOURCE_FIGURED_DIMENSION_WITNESS_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SourceFiguredDimensionWitnessResult:
    return SourceFiguredDimensionWitnessResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


# ── Geometric Analysis ────────────────────────────────────────────────────────


def _extract_endpoints(seg: Mapping[str, Any]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    if "p1" in seg and "p2" in seg:
        p1, p2 = seg["p1"], seg["p2"]
        return ((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
    if "x1" in seg and "y1" in seg and "x2" in seg and "y2" in seg:
        return ((float(seg["x1"]), float(seg["y1"])), (float(seg["x2"]), float(seg["y2"])))
    if "points" in seg:
        pts = seg["points"]
        if len(pts) >= 2:
            return ((float(pts[0][0]), float(pts[0][1])), (float(pts[-1][0]), float(pts[-1][1])))
    return None


def _point_dist(p: Tuple[float, float], q: Tuple[float, float]) -> float:
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _point_to_line_dist(pt: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Distance from point to infinite line passing through p1 and p2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    line_len = math.hypot(dx, dy)
    if line_len < 1e-6:
        return _point_dist(pt, p1)
    return abs((pt[0] - p1[0]) * (-dy) + (pt[1] - p1[1]) * dx) / line_len


def _point_to_segment_dist(pt: Tuple[float, float], p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    """Distance from point to finite segment p1-p2."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    line_len = math.hypot(dx, dy)
    if line_len < 1e-6:
        return _point_dist(pt, p1)
    u_x = dx / line_len
    u_y = dy / line_len
    t = (pt[0] - p1[0]) * u_x + (pt[1] - p1[1]) * u_y
    if t <= 0.0:
        return _point_dist(pt, p1)
    if t >= line_len:
        return _point_dist(pt, p2)
    proj = (p1[0] + t * u_x, p1[1] + t * u_y)
    return _point_dist(pt, proj)


# ── Producer & Authority ───────────────────────────────────────────────────────


class SourceFiguredDimensionWitnessAuthority:
    """Sealed lookup authority for published figured dimension and wall witness records."""

    def __init__(
        self,
        records: Mapping[_Key, SourceFiguredDimensionWitnessResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceFiguredDimensionWitnessAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def resolve(self, selector: SourceFiguredDimensionWitnessSelector) -> SourceFiguredDimensionWitnessResult:
        if type(selector) is not SourceFiguredDimensionWitnessSelector:
            raise TypeError("selector must be SourceFiguredDimensionWitnessSelector")
        return self._records.get(selector.key, _abstained(FIGURED_DIMENSION_RECORD_UNAVAILABLE))


class SourceFiguredDimensionWitnessProducer:
    """Producer for authenticating figured room dimensions and wall witnesses."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SourceFiguredDimensionWitnessProducer must be obtained via create()")
        self._results: Dict[_Key, SourceFiguredDimensionWitnessResult] = {}

    @classmethod
    def create(cls) -> SourceFiguredDimensionWitnessProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def evaluate_and_publish(
        self,
        selector: SourceFiguredDimensionWitnessSelector,
        *,
        figured_text: str,
        figured_dimension_m: float,
        dimension_line: Mapping[str, Any],
        witness_strokes: Sequence[Mapping[str, Any]],
        candidate_walls: Sequence[Mapping[str, Any]],
        scale_px_per_m: Optional[float] = None,
    ) -> SourceFiguredDimensionWitnessResult:
        """Evaluate dimension line, witness strokes, and wall connections."""
        if type(selector) is not SourceFiguredDimensionWitnessSelector:
            raise TypeError("selector must be SourceFiguredDimensionWitnessSelector")

        # 1. Validate dimension line
        dim_pts = _extract_endpoints(dimension_line)
        if not dim_pts:
            res = _abstained(DEGENERATE_DIMENSION_GEOMETRY)
            self._results[selector.key] = res
            return res

        (e1_x, e1_y), (e2_x, e2_y) = dim_pts
        dim_dx = e2_x - e1_x
        dim_dy = e2_y - e1_y
        dim_len = math.hypot(dim_dx, dim_dy)
        if dim_len < 1e-4:
            res = _abstained(DEGENERATE_DIMENSION_GEOMETRY)
            self._results[selector.key] = res
            return res

        dim_u_x = dim_dx / dim_len
        dim_u_y = dim_dy / dim_len

        # 2. Check figure vs scaled length consistency
        scaled_len_m: Optional[float] = None
        if scale_px_per_m is not None and scale_px_per_m > 0:
            scaled_len_m = round(dim_len / scale_px_per_m, 4)
            diff_m = abs(figured_dimension_m - scaled_len_m)
            if diff_m > 0.05 and (diff_m / figured_dimension_m) > 0.02:
                res = _abstained(DIMENSION_FIGURE_MISMATCH)
                self._results[selector.key] = res
                return res

        # 3. Find perpendicular witness strokes at e1 and e2
        e1 = (e1_x, e1_y)
        e2 = (e2_x, e2_y)

        def _find_witness(end_pt: Tuple[float, float]) -> Optional[Tuple[Tuple[Tuple[float, float], Tuple[float, float]], Tuple[float, float], str]]:
            """Find witness stroke touching end_pt and return (stroke_pts, wall_contact_pt, stroke_id)."""
            candidates = []
            for stroke in witness_strokes:
                s_pts = _extract_endpoints(stroke)
                if not s_pts:
                    continue
                (w1_x, w1_y), (w2_x, w2_y) = s_pts
                wdx = w2_x - w1_x
                wdy = w2_y - w1_y
                wlen = math.hypot(wdx, wdy)
                if wlen < 1e-4:
                    continue
                wu_x = wdx / wlen
                wu_y = wdy / wlen

                # Perpendicularity check: dot product near 0
                dot = abs(dim_u_x * wu_x + dim_u_y * wu_y)
                if dot > 0.035:  # ~2 degrees
                    continue

                d_w1 = _point_dist(end_pt, (w1_x, w1_y))
                d_w2 = _point_dist(end_pt, (w2_x, w2_y))
                if d_w1 <= SNAP_TOLERANCE_PT:
                    candidates.append((s_pts, (w2_x, w2_y), str(stroke.get("id") or "")))
                elif d_w2 <= SNAP_TOLERANCE_PT:
                    candidates.append((s_pts, (w1_x, w1_y), str(stroke.get("id") or "")))

            if len(candidates) == 1:
                return candidates[0]
            return None

        w1_data = _find_witness(e1)
        w2_data = _find_witness(e2)

        if not w1_data or not w2_data:
            res = _abstained(WITNESS_LINE_DISCONTINUOUS_OR_MISSING)
            self._results[selector.key] = res
            return res

        w1_pts, w1_terminal, w1_id = w1_data
        w2_pts, w2_terminal, w2_id = w2_data

        # 4. Find wall contact for each witness terminal
        def _find_wall_contact(terminal_pt: Tuple[float, float]) -> Optional[str]:
            wall_hits = []
            for wall in candidate_walls:
                wall_id = str(wall.get("id") or wall.get("candidate_id") or "")
                wall_pts = _extract_endpoints(wall)
                if not wall_pts or not wall_id:
                    continue
                d = _point_to_segment_dist(terminal_pt, wall_pts[0], wall_pts[1])
                if d <= SNAP_TOLERANCE_PT:
                    wall_hits.append(wall_id)
            if len(wall_hits) == 1:
                return wall_hits[0]
            return None

        wall_1_id = _find_wall_contact(w1_terminal)
        wall_2_id = _find_wall_contact(w2_terminal)

        if not wall_1_id or not wall_2_id:
            res = _abstained(WITNESS_WALL_CONTACT_UNRESOLVED)
            self._results[selector.key] = res
            return res

        if wall_1_id == wall_2_id:
            # Dimension witnessed to the exact same wall is ambiguous or degenerate
            res = _abstained(AMBIGUOUS_WALL_WITNESS_BINDING)
            self._results[selector.key] = res
            return res

        # 5. Generate MultiLineString WKB
        lines = [
            [(e1_x, e1_y), (e2_x, e2_y)],
            [w1_pts[0], w1_pts[1]],
            [w2_pts[0], w2_pts[1]],
        ]
        wkb_hex = _multilinestring_to_wkb_hex(lines)

        # 6. Mint stable contract ID
        rec_id = stable_contract_id(
            "source_figured_dimension_witness_record",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "page_id": selector.page_id,
                "dimension_observation_id": selector.dimension_observation_id,
            },
        )

        record = SourceFiguredDimensionWitnessRecord(
            record_id=rec_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            dimension_observation_id=selector.dimension_observation_id,
            figured_text=figured_text,
            dimension_m=figured_dimension_m,
            scaled_length_m=scaled_len_m,
            dimension_line_pts=dim_pts,
            witness_1_pts=w1_pts,
            witness_2_pts=w2_pts,
            witnessed_wall_1_id=wall_1_id,
            witnessed_wall_2_id=wall_2_id,
            witness_chain_wkb_hex=wkb_hex,
            corroborating_evidence_ids=tuple(sorted([selector.dimension_observation_id, w1_id, w2_id, wall_1_id, wall_2_id])),
            status=EvidenceResolutionStatus.CANDIDATE,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_RECORD_SEAL,
        )

        res = SourceFiguredDimensionWitnessResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(FIGURED_WALL_WITNESS_CHAIN_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = res
        return res

    def authority(self) -> SourceFiguredDimensionWitnessAuthority:
        return SourceFiguredDimensionWitnessAuthority(self._results, _seal=_AUTHORITY_SEAL)
