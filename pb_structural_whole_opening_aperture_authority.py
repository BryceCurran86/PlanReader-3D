"""Source-authenticated whole-opening aperture structural authority.

Resolves the structural whole-opening interpretation blocker:
1. Distinguishes physical wall apertures from internal glazing subdivisions
   and glazing post gaps (e.g. 2.64-2.88 pt gaps between glass panes).
2. Establishes source-authenticated terminal jamb roles at outer aperture
   boundaries across multi-layer wall faces (heavy 0.96 pt structural strokes,
   masonry pier caps, and lining returns).
3. Verifies host wall continuity beyond terminal jambs.
4. Preserves paint and graphic-state uncertainty (unstroked fill boundaries,
   white masks, clipped strokes, and unproven terminal paint abstain; stepped
   returns with multi-layer offsets preserve AMBIGUOUS_MULTI_LAYER_OFFSET).
5. Emits producer-owned WholeOpeningApertureRecord and provides candidate
   filtering that existing authorities (PhysicalOpeningAuthority,
   OpeningHostBindingAuthority) can consume in shadow mode.

Operates strictly in shadow mode: status=CANDIDATE,
commercial_projection_allowed=False, takeoff_eligible=False.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_opening_authority import (
    CandidateSemanticOpening,
    SourceObservationRecord,
)

WHOLE_OPENING_APERTURE_SCHEMA_VERSION = "1.0.0"
WHOLE_OPENING_APERTURE_METHOD = "structural_whole_opening_aperture_authority"

# Public Reason Codes
WHOLE_OPENING_APERTURE_CORROBORATED = "whole_opening_aperture_corroborated"
INTERNAL_GLAZING_SUBDIVISION_GAP = "internal_glazing_subdivision_gap"
GLAZING_SUBDIVISION_DISCRIMINATED = "glazing_subdivision_discriminated"
STRUCTURAL_TERMINAL_JAMB_PROVEN = "structural_terminal_jamb_proven"
HOST_WALL_CONTINUITY_PROVEN = "host_wall_continuity_proven"
AMBIGUOUS_MULTI_LAYER_OFFSET = "ambiguous_multi_layer_offset"
AMBIGUOUS_STRUCTURAL_BOUNDARY = "ambiguous_structural_boundary"
TERMINAL_ROLE_UNPROVEN = "original_terminal_paint_structural_role_unproven"
FILL_MASK_BOUNDARY_UNPROVEN = "fill_mask_boundary_unproven"
APERTURE_EXTENT_INCOMPLETE = "aperture_extent_incomplete"
WALL_CONTINUITY_MISSING = "wall_continuity_missing"
APERTURE_BUDGET_EXCEEDED = "aperture_budget_exceeded"
APERTURE_OBSERVATION_INTEGRITY_FAILURE = "aperture_observation_integrity_failure"

# Structural quality indicators
STRUCTURAL_JAMB_HEAVY = "structural_jamb_heavy"
STRUCTURAL_JAMB_PIER_RETURN = "structural_jamb_pier_return"
STRUCTURAL_JAMB_LINING_RETURN = "structural_jamb_lining_return"
STRUCTURAL_JAMB_COMPOSITE = "structural_jamb_composite"

# Tolerances & Thresholds (paper points)
_SNAP_TOL_PT = 2.5
_COORD_EQ_TOL = 1e-4
_ORTHO_TOL = 0.05
_PARALLEL_TOL = 1e-4
_MAX_INTERNAL_POST_SPAN_PT = 6.0
_MAX_GLASS_PAIR_DEPTH_PT = 2.0
_HEAVY_STROKE_WIDTH_PT = 0.8
_MAX_ITEMS_PER_PAGE = 120_000

_SOLID_DASH_RE = re.compile(r"^\s*\[\s*\]\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)?\s*$")

# Internal Seals
_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


def _is_black(stroke_rgb: tuple[float, ...] | None) -> bool:
    if not stroke_rgb:
        return True
    return max(stroke_rgb) <= 0.1


def _is_solid(dashes: Any) -> bool:
    if not dashes:
        return True
    return bool(_SOLID_DASH_RE.fullmatch(str(dashes)))


@dataclass(frozen=True)
class ApertureSourceStroke:
    """Rich visual stroke representation with graphic state for aperture analysis."""

    observation_id: str
    geometry: tuple[float, float, float, float]
    stroke_width: float = 0.48
    stroke_rgb: tuple[float, ...] | None = (0.0, 0.0, 0.0)
    stroke_opacity: float = 1.0
    dashes: str = "[] 0"
    is_fill_mask: bool = False
    is_clipped: bool = False


@dataclass(frozen=True)
class GlazingSubdivisionDiscriminationRecord:
    """Record proving an ink gap is an internal glazing post/mullion, NOT a wall opening."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str | None
    axis: str
    is_internal_subdivision: bool
    subdivision_span_along: tuple[float, float]
    subdivision_depth_across: float
    member_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed or self.takeoff_eligible:
            raise ValueError("subdivision record must remain in shadow mode")


@dataclass(frozen=True)
class WholeOpeningApertureRecord:
    """Source-authenticated whole-opening aperture boundary with terminal jambs."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str | None
    axis: str
    aperture_span_along: tuple[float, float]
    wall_band_across: tuple[float, float]
    terminal_jamb_lo_ids: tuple[str, ...]
    terminal_jamb_hi_ids: tuple[str, ...]
    host_face_ids: tuple[str, ...]
    glazing_strip_ids: tuple[str, ...]
    discriminated_subdivision_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    structural_role: str
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def __post_init__(self) -> None:
        if self.commercial_projection_allowed or self.takeoff_eligible:
            raise ValueError("whole-opening record must remain in shadow mode")


@dataclass(frozen=True)
class WholeOpeningApertureSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    aperture_id: str


@dataclass(frozen=True)
class WholeOpeningApertureResult:
    status: EvidenceResolutionStatus
    record: WholeOpeningApertureRecord | None
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class _InternalStroke:
    observation_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    is_h: bool
    is_v: bool
    black: bool
    solid: bool
    opaque: bool
    has_fill_mask: bool
    clipped: bool

    def along_span(self, is_h: bool) -> tuple[float, float]:
        return (self.x0, self.x1) if is_h else (self.y0, self.y1)

    def across_span(self, is_h: bool) -> tuple[float, float]:
        return (self.y0, self.y1) if is_h else (self.x0, self.x1)

    def along_station(self, is_h: bool) -> float:
        return self.x0 if is_h else self.y0

    def across_pos(self, is_h: bool) -> float:
        return self.y0 if is_h else self.x0


class StructuralWholeOpeningApertureProducer:
    """Sealed producer discovering whole-aperture boundaries and discriminating posts."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden. Use create().")
        self._aperture_records: dict[str, WholeOpeningApertureRecord] = {}
        self._subdivision_records: dict[
            str, GlazingSubdivisionDiscriminationRecord
        ] = {}
        self._discriminated_obs_ids: set[str] = set()
        self._page_processed: set[tuple[str, str, str, str, str]] = set()

    @classmethod
    def create(cls) -> StructuralWholeOpeningApertureProducer:
        return cls(_PRODUCER_SEAL)

    def analyze_page(
        self,
        seed: SourceObservationRecord,
        records: Sequence[Any],
        *,
        stroke_properties: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> tuple[WholeOpeningApertureRecord, ...]:
        """Analyze a page to discover whole openings and discriminate glazing posts."""
        page_key = (
            seed.document_id,
            seed.revision_id,
            seed.source_sha256,
            seed.snapshot_id,
            str(seed.page_id),
        )
        if page_key in self._page_processed:
            return tuple(
                r
                for r in self._aperture_records.values()
                if (
                    r.document_id,
                    r.revision_id,
                    r.source_sha256,
                    r.snapshot_id,
                    r.page_id,
                )
                == page_key
            )

        if len(records) > _MAX_ITEMS_PER_PAGE:
            self._page_processed.add(page_key)
            return ()

        # 1. Collect valid visible strokes on this page
        strokes: list[_InternalStroke] = []
        for rec in records:
            if isinstance(rec, ApertureSourceStroke):
                geom = rec.geometry
                x0, y0, x1, y1 = (
                    float(geom[0]),
                    float(geom[1]),
                    float(geom[2]),
                    float(geom[3]),
                )
                dx = abs(x1 - x0)
                dy = abs(y1 - y0)
                is_h = dy <= _ORTHO_TOL and dx > _ORTHO_TOL
                is_v = dx <= _ORTHO_TOL and dy > _ORTHO_TOL
                if not is_h and not is_v:
                    continue
                if is_h and x0 > x1:
                    x0, x1 = x1, x0
                elif is_v and y0 > y1:
                    y0, y1 = y1, y0
                strokes.append(
                    _InternalStroke(
                        observation_id=rec.observation_id,
                        x0=x0,
                        y0=y0,
                        x1=x1,
                        y1=y1,
                        width=rec.stroke_width,
                        is_h=is_h,
                        is_v=is_v,
                        black=_is_black(rec.stroke_rgb),
                        solid=_is_solid(rec.dashes),
                        opaque=(rec.stroke_opacity == 1.0),
                        has_fill_mask=rec.is_fill_mask,
                        clipped=rec.is_clipped,
                    )
                )
                continue

            if (
                rec.document_id != seed.document_id
                or rec.revision_id != seed.revision_id
            ):
                continue
            if (
                rec.source_sha256 != seed.source_sha256
                or rec.snapshot_id != seed.snapshot_id
            ):
                continue
            if str(rec.page_id) != str(seed.page_id):
                continue
            geom = rec.geometry
            if not geom or len(geom) != 4:
                continue
            x0, y0, x1, y1 = (
                float(geom[0]),
                float(geom[1]),
                float(geom[2]),
                float(geom[3]),
            )
            dx = abs(x1 - x0)
            dy = abs(y1 - y0)
            is_h = dy <= _ORTHO_TOL and dx > _ORTHO_TOL
            is_v = dx <= _ORTHO_TOL and dy > _ORTHO_TOL
            if not is_h and not is_v:
                continue
            # Canonicalize line order
            if is_h and x0 > x1:
                x0, x1 = x1, x0
            elif is_v and y0 > y1:
                y0, y1 = y1, y0

            props = (
                stroke_properties.get(rec.observation_id, {})
                if stroke_properties
                else {}
            )
            raw_w = props.get("stroke_width", getattr(rec, "stroke_width", None))
            width = float(raw_w) if raw_w is not None else 0.48
            rgb = props.get("stroke_rgb", getattr(rec, "stroke_rgb", None))
            black = _is_black(rgb)
            dashes = props.get("dashes", getattr(rec, "dashes", None))
            solid = _is_solid(dashes)
            opacity = props.get("stroke_opacity", getattr(rec, "stroke_opacity", 1.0))
            opaque = (opacity == 1.0) if opacity is not None else True
            has_fill_mask = props.get(
                "is_fill_mask", getattr(rec, "is_fill_mask", False)
            )
            clipped = props.get("is_clipped", getattr(rec, "is_clipped", False))

            strokes.append(
                _InternalStroke(
                    observation_id=rec.observation_id,
                    x0=x0,
                    y0=y0,
                    x1=x1,
                    y1=y1,
                    width=width,
                    is_h=is_h,
                    is_v=is_v,
                    black=black,
                    solid=solid,
                    opaque=opaque,
                    has_fill_mask=has_fill_mask,
                    clipped=clipped,
                )
            )

        # 2. Find glazing cell pairs and multi-panel strips
        # We search both H and V axes
        discovered_apertures: list[WholeOpeningApertureRecord] = []
        for axis in ("H", "V"):
            apertures = self._process_axis(seed, strokes, axis)
            discovered_apertures.extend(apertures)

        self._page_processed.add(page_key)
        return tuple(discovered_apertures)

    def _process_axis(
        self,
        seed: SourceObservationRecord,
        strokes: Sequence[_InternalStroke],
        axis: str,
    ) -> list[WholeOpeningApertureRecord]:
        is_h = axis == "H"
        along_strokes = [
            s for s in strokes if (s.is_h if is_h else s.is_v) and s.black and s.solid
        ]
        cross_strokes = [s for s in strokes if (s.is_v if is_h else s.is_h)]

        # Group along strokes by across coordinate (within snap tol)
        by_across: dict[float, list[_InternalStroke]] = defaultdict(list)
        for s in along_strokes:
            pos = round((s.y0 if is_h else s.x0) / 0.12) * 0.12
            by_across[pos].append(s)

        # Find parallel pairs separated by glass depth <= 2.0 pt
        across_positions = sorted(by_across.keys())
        glass_pairs: list[
            tuple[float, float, list[_InternalStroke], list[_InternalStroke]]
        ] = []
        for i, a0 in enumerate(across_positions):
            for a1 in across_positions[i + 1 :]:
                depth = a1 - a0
                if depth > _MAX_GLASS_PAIR_DEPTH_PT:
                    break
                if depth >= 0.40:
                    glass_pairs.append((a0, a1, by_across[a0], by_across[a1]))

        apertures: list[WholeOpeningApertureRecord] = []
        consumed_panels: set[tuple[str, str]] = set()

        for p_lo, p_hi, list_lo, list_hi in glass_pairs:
            # Sort by along coordinate so chains start from the earliest panel
            sorted_lo = sorted(list_lo, key=lambda s: s.x0 if is_h else s.y0)
            sorted_hi = sorted(list_hi, key=lambda s: s.x0 if is_h else s.y0)

            for s_lo in sorted_lo:
                lo_a0 = s_lo.x0 if is_h else s_lo.y0
                lo_a1 = s_lo.x1 if is_h else s_lo.y1
                for s_hi in sorted_hi:
                    if (s_lo.observation_id, s_hi.observation_id) in consumed_panels:
                        continue
                    hi_a0 = s_hi.x0 if is_h else s_hi.y0
                    hi_a1 = s_hi.x1 if is_h else s_hi.y1
                    overlap_0 = max(lo_a0, hi_a0)
                    overlap_1 = min(lo_a1, hi_a1)
                    if (
                        overlap_1 - overlap_0 < 10.0
                    ):  # panel must be at least 10 pt long
                        continue

                    # Check for end ticks closing this glass panel across depth
                    ticks_lo = [
                        t
                        for t in cross_strokes
                        if abs(t.along_station(is_h) - overlap_0) <= _SNAP_TOL_PT
                        and t.across_span(is_h)[0] <= p_lo + _SNAP_TOL_PT
                        and t.across_span(is_h)[1] >= p_hi - _SNAP_TOL_PT
                    ]
                    ticks_hi = [
                        t
                        for t in cross_strokes
                        if abs(t.along_station(is_h) - overlap_1) <= _SNAP_TOL_PT
                        and t.across_span(is_h)[0] <= p_lo + _SNAP_TOL_PT
                        and t.across_span(is_h)[1] >= p_hi - _SNAP_TOL_PT
                    ]

                    # Panel found! Now check for chained panels (adjacent panels with small post gap)
                    # Look for neighboring panels separated by post gap <= 5.0 pt
                    chain_panels = [
                        (overlap_0, overlap_1, s_lo, s_hi, ticks_lo, ticks_hi)
                    ]

                    # Extend chain forward
                    curr_hi = overlap_1
                    while True:
                        next_panel = None
                        for s_next_lo in list_lo:
                            n_lo_a0 = s_next_lo.x0 if is_h else s_next_lo.y0
                            n_lo_a1 = s_next_lo.x1 if is_h else s_next_lo.y1
                            gap = n_lo_a0 - curr_hi
                            if 0.5 <= gap <= _MAX_INTERNAL_POST_SPAN_PT:
                                for s_next_hi in list_hi:
                                    n_hi_a0 = s_next_hi.x0 if is_h else s_next_hi.y0
                                    n_hi_a1 = s_next_hi.x1 if is_h else s_next_hi.y1
                                    if (
                                        abs(n_hi_a0 - n_lo_a0) <= _SNAP_TOL_PT
                                        and n_hi_a1 > n_hi_a0 + 10.0
                                    ):
                                        next_panel = (
                                            n_lo_a0,
                                            min(n_lo_a1, n_hi_a1),
                                            s_next_lo,
                                            s_next_hi,
                                        )
                                        break
                            if next_panel:
                                break
                        if next_panel:
                            # Verify ticks at start and end of next panel
                            nxt_ticks_lo = [
                                t
                                for t in cross_strokes
                                if abs(t.along_station(is_h) - next_panel[0])
                                <= _SNAP_TOL_PT
                                and t.across_span(is_h)[0] <= p_lo + _SNAP_TOL_PT
                                and t.across_span(is_h)[1] >= p_hi - _SNAP_TOL_PT
                            ]
                            nxt_ticks_hi = [
                                t
                                for t in cross_strokes
                                if abs(t.along_station(is_h) - next_panel[1])
                                <= _SNAP_TOL_PT
                                and t.across_span(is_h)[0] <= p_lo + _SNAP_TOL_PT
                                and t.across_span(is_h)[1] >= p_hi - _SNAP_TOL_PT
                            ]
                            chain_panels.append(
                                (
                                    next_panel[0],
                                    next_panel[1],
                                    next_panel[2],
                                    next_panel[3],
                                    nxt_ticks_lo,
                                    nxt_ticks_hi,
                                )
                            )
                            curr_hi = next_panel[1]
                        else:
                            break

                    if len(chain_panels) >= 1:
                        for cp in chain_panels:
                            consumed_panels.add(
                                (cp[2].observation_id, cp[3].observation_id)
                            )

                        # Full extent of whole glazing assembly
                        total_lo = chain_panels[0][0]
                        total_hi = chain_panels[-1][1]

                        # 3. Discriminate internal post gaps between adjacent panels
                        discriminated_subdivision_ids: list[str] = []
                        for k in range(len(chain_panels) - 1):
                            post_start = chain_panels[k][1]
                            post_end = chain_panels[k + 1][0]
                            post_span = post_end - post_start
                            if post_span <= _MAX_INTERNAL_POST_SPAN_PT:
                                # Collect member observation IDs for this post gap
                                post_obs = set()
                                post_obs.add(chain_panels[k][2].observation_id)
                                post_obs.add(chain_panels[k][3].observation_id)
                                post_obs.add(chain_panels[k + 1][2].observation_id)
                                post_obs.add(chain_panels[k + 1][3].observation_id)
                                for t in chain_panels[k][5]:
                                    post_obs.add(t.observation_id)
                                for t in chain_panels[k + 1][4]:
                                    post_obs.add(t.observation_id)

                                sub_id = stable_contract_id(
                                    "glazing_subdivision",
                                    {
                                        "doc": seed.document_id,
                                        "page": seed.page_id,
                                        "along": (
                                            round(post_start, 3),
                                            round(post_end, 3),
                                        ),
                                        "across": (round(p_lo, 3), round(p_hi, 3)),
                                    },
                                    digest_chars=24,
                                )
                                sub_rec = GlazingSubdivisionDiscriminationRecord(
                                    record_id=sub_id,
                                    document_id=seed.document_id,
                                    revision_id=seed.revision_id,
                                    source_sha256=seed.source_sha256,
                                    snapshot_id=seed.snapshot_id,
                                    page_id=str(seed.page_id),
                                    viewport_id=seed.viewport_id,
                                    axis=axis,
                                    is_internal_subdivision=True,
                                    subdivision_span_along=(
                                        round(post_start, 3),
                                        round(post_end, 3),
                                    ),
                                    subdivision_depth_across=round(p_hi - p_lo, 3),
                                    member_observation_ids=tuple(sorted(post_obs)),
                                    status=EvidenceResolutionStatus.CORROBORATED,
                                    reason_codes=(
                                        INTERNAL_GLAZING_SUBDIVISION_GAP,
                                        GLAZING_SUBDIVISION_DISCRIMINATED,
                                    ),
                                )
                                self._subdivision_records[sub_id] = sub_rec
                                self._discriminated_obs_ids.update(post_obs)
                                discriminated_subdivision_ids.append(sub_id)

                        # 4. Detect outer terminal jambs at total_lo and total_hi
                        wall_band_pad = 15.0
                        wall_band = (p_lo - wall_band_pad, p_hi + wall_band_pad)

                        outer_lo, jambs_lo = self._find_terminal_jamb_station(
                            cross_strokes,
                            total_lo,
                            -1,
                            wall_band,
                            is_h=is_h,
                            glass_depth_band=(p_lo, p_hi),
                        )
                        outer_hi, jambs_hi = self._find_terminal_jamb_station(
                            cross_strokes,
                            total_hi,
                            +1,
                            wall_band,
                            is_h=is_h,
                            glass_depth_band=(p_lo, p_hi),
                        )

                        # Check for end post gap between glass panels and outer terminal jambs
                        if jambs_lo and outer_lo < total_lo:
                            sub_id_lo = stable_contract_id(
                                "glazing_subdivision",
                                {
                                    "doc": seed.document_id,
                                    "page": seed.page_id,
                                    "along": (round(outer_lo, 3), round(total_lo, 3)),
                                    "across": (round(p_lo, 3), round(p_hi, 3)),
                                },
                                digest_chars=24,
                            )
                            sub_rec_lo = GlazingSubdivisionDiscriminationRecord(
                                record_id=sub_id_lo,
                                document_id=seed.document_id,
                                revision_id=seed.revision_id,
                                source_sha256=seed.source_sha256,
                                snapshot_id=seed.snapshot_id,
                                page_id=str(seed.page_id),
                                viewport_id=seed.viewport_id,
                                axis=axis,
                                is_internal_subdivision=True,
                                subdivision_span_along=(
                                    round(outer_lo, 3),
                                    round(total_lo, 3),
                                ),
                                subdivision_depth_across=round(p_hi - p_lo, 3),
                                member_observation_ids=tuple(
                                    sorted(s.observation_id for s in jambs_lo)
                                ),
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(
                                    INTERNAL_GLAZING_SUBDIVISION_GAP,
                                    GLAZING_SUBDIVISION_DISCRIMINATED,
                                ),
                            )
                            self._subdivision_records[sub_id_lo] = sub_rec_lo
                            self._discriminated_obs_ids.update(
                                sub_rec_lo.member_observation_ids
                            )
                            discriminated_subdivision_ids.append(sub_id_lo)
                            total_lo = outer_lo

                        if jambs_hi and outer_hi > total_hi:
                            sub_id_hi = stable_contract_id(
                                "glazing_subdivision",
                                {
                                    "doc": seed.document_id,
                                    "page": seed.page_id,
                                    "along": (round(total_hi, 3), round(outer_hi, 3)),
                                    "across": (round(p_lo, 3), round(p_hi, 3)),
                                },
                                digest_chars=24,
                            )
                            sub_rec_hi = GlazingSubdivisionDiscriminationRecord(
                                record_id=sub_id_hi,
                                document_id=seed.document_id,
                                revision_id=seed.revision_id,
                                source_sha256=seed.source_sha256,
                                snapshot_id=seed.snapshot_id,
                                page_id=str(seed.page_id),
                                viewport_id=seed.viewport_id,
                                axis=axis,
                                is_internal_subdivision=True,
                                subdivision_span_along=(
                                    round(total_hi, 3),
                                    round(outer_hi, 3),
                                ),
                                subdivision_depth_across=round(p_hi - p_lo, 3),
                                member_observation_ids=tuple(
                                    sorted(s.observation_id for s in jambs_hi)
                                ),
                                status=EvidenceResolutionStatus.CORROBORATED,
                                reason_codes=(
                                    INTERNAL_GLAZING_SUBDIVISION_GAP,
                                    GLAZING_SUBDIVISION_DISCRIMINATED,
                                ),
                            )
                            self._subdivision_records[sub_id_hi] = sub_rec_hi
                            self._discriminated_obs_ids.update(
                                sub_rec_hi.member_observation_ids
                            )
                            discriminated_subdivision_ids.append(sub_id_hi)
                            total_hi = outer_hi

                        # Evaluate paint & graphic-state uncertainty
                        has_uncertain_lo = any(
                            s.has_fill_mask or s.clipped or not s.opaque
                            for s in jambs_lo
                        )
                        has_uncertain_hi = any(
                            s.has_fill_mask or s.clipped or not s.opaque
                            for s in jambs_hi
                        )

                        # Check for stepped pier offset (e.g. 0.72 pt lining offset in Maryborough W03)
                        stepped_offset = False
                        if jambs_hi:
                            stations = [s.along_station(is_h) for s in jambs_hi]
                            spread = max(stations) - min(stations)
                            if _ORTHO_TOL < spread <= 2.0:
                                stepped_offset = True

                        # 5. Check Host Wall Continuity beyond terminal jambs
                        wall_cont_lo = self._check_wall_continuity(
                            along_strokes, total_lo, -1, wall_band, is_h=is_h
                        )
                        wall_cont_hi = self._check_wall_continuity(
                            along_strokes, total_hi, +1, wall_band, is_h=is_h
                        )
                        wall_cont_proven = wall_cont_lo and wall_cont_hi

                        reasons: list[str] = []
                        if has_uncertain_lo or has_uncertain_hi:
                            status = EvidenceResolutionStatus.ABSTAINED
                            reasons.append(TERMINAL_ROLE_UNPROVEN)
                        elif not jambs_lo or not jambs_hi:
                            status = EvidenceResolutionStatus.ABSTAINED
                            reasons.append(APERTURE_EXTENT_INCOMPLETE)
                        elif not wall_cont_proven:
                            status = EvidenceResolutionStatus.ABSTAINED
                            reasons.append(WALL_CONTINUITY_MISSING)
                        else:
                            status = EvidenceResolutionStatus.CANDIDATE
                            reasons.append(WHOLE_OPENING_APERTURE_CORROBORATED)
                            reasons.append(STRUCTURAL_TERMINAL_JAMB_PROVEN)
                            reasons.append(HOST_WALL_CONTINUITY_PROVEN)
                            if stepped_offset:
                                reasons.append(AMBIGUOUS_MULTI_LAYER_OFFSET)

                        role = (
                            STRUCTURAL_JAMB_HEAVY
                            if any(
                                s.width >= _HEAVY_STROKE_WIDTH_PT
                                for s in (*jambs_lo, *jambs_hi)
                            )
                            else (
                                STRUCTURAL_JAMB_COMPOSITE
                                if stepped_offset
                                else STRUCTURAL_JAMB_PIER_RETURN
                            )
                        )

                        # Collect all host face IDs (lines running outside the opening)
                        host_face_ids = tuple(
                            sorted(
                                s.observation_id
                                for s in along_strokes
                                if (
                                    s.along_span(is_h)[1] <= total_lo + _SNAP_TOL_PT
                                    or s.along_span(is_h)[0] >= total_hi - _SNAP_TOL_PT
                                )
                                and (
                                    p_lo - wall_band_pad
                                    <= s.across_pos(is_h)
                                    <= p_hi + wall_band_pad
                                )
                            )
                        )

                        aperture_id = stable_contract_id(
                            "whole_opening_aperture",
                            {
                                "doc": seed.document_id,
                                "page": seed.page_id,
                                "span": (round(total_lo, 3), round(total_hi, 3)),
                                "axis": axis,
                            },
                            digest_chars=24,
                        )

                        record = WholeOpeningApertureRecord(
                            record_id=aperture_id,
                            document_id=seed.document_id,
                            revision_id=seed.revision_id,
                            source_sha256=seed.source_sha256,
                            snapshot_id=seed.snapshot_id,
                            page_id=str(seed.page_id),
                            viewport_id=seed.viewport_id,
                            axis=axis,
                            aperture_span_along=(
                                round(total_lo, 3),
                                round(total_hi, 3),
                            ),
                            wall_band_across=(round(p_lo, 3), round(p_hi, 3)),
                            terminal_jamb_lo_ids=tuple(
                                sorted(s.observation_id for s in jambs_lo)
                            ),
                            terminal_jamb_hi_ids=tuple(
                                sorted(s.observation_id for s in jambs_hi)
                            ),
                            host_face_ids=host_face_ids,
                            glazing_strip_ids=(),
                            discriminated_subdivision_ids=tuple(
                                discriminated_subdivision_ids
                            ),
                            status=status,
                            structural_role=role,
                            reason_codes=tuple(reasons),
                        )
                        self._aperture_records[aperture_id] = record
                        apertures.append(record)

        return apertures

    def _detect_terminal_jambs(
        self,
        cross_strokes: Sequence[_InternalStroke],
        target_station: float,
        wall_band: tuple[float, float],
        *,
        is_h: bool,
        glass_depth_band: tuple[float, float] | None = None,
    ) -> list[_InternalStroke]:
        """Detect perpendicular jamb strokes crossing the wall band at target station."""
        b0, b1 = wall_band
        matching: list[_InternalStroke] = []
        for s in cross_strokes:
            pos = s.along_station(is_h)
            if abs(pos - target_station) <= _SNAP_TOL_PT:
                s_b0, s_b1 = s.across_span(is_h)
                span_len = s_b1 - s_b0
                # A structural jamb cannot be merely an internal glass pane end tick
                if glass_depth_band is not None:
                    g0, g1 = glass_depth_band
                    if (
                        span_len <= 1.5
                        and s_b0 >= g0 - _SNAP_TOL_PT
                        and s_b1 <= g1 + _SNAP_TOL_PT
                    ):
                        continue
                # Must overlap with wall band
                if s_b1 >= b0 and s_b0 <= b1:
                    matching.append(s)
        return matching

    def _find_terminal_jamb_station(
        self,
        cross_strokes: Sequence[_InternalStroke],
        glass_station: float,
        direction: int,  # -1 for lo, +1 for hi
        wall_band: tuple[float, float],
        *,
        is_h: bool,
        glass_depth_band: tuple[float, float],
    ) -> tuple[float, list[_InternalStroke]]:
        """Find terminal jamb station at glass_station or slightly outward across an end post."""
        relevant_cross = [
            s
            for s in cross_strokes
            if s.across_span(is_h)[1] >= wall_band[0]
            and s.across_span(is_h)[0] <= wall_band[1]
        ]
        candidates: list[tuple[bool, float, float, list[_InternalStroke]]] = []
        for s in relevant_cross:
            pos = s.along_station(is_h)
            dist = (glass_station - pos) if direction < 0 else (pos - glass_station)
            if 0.0 <= dist <= _MAX_INTERNAL_POST_SPAN_PT:
                j = self._detect_terminal_jambs(
                    relevant_cross,
                    pos,
                    wall_band,
                    is_h=is_h,
                    glass_depth_band=glass_depth_band,
                )
                if j:
                    g0, g1 = glass_depth_band
                    has_wall_return = any(
                        (
                            st.across_span(is_h)[0] < g0 - 2.0
                            or st.across_span(is_h)[1] > g1 + 2.0
                        )
                        for st in j
                    )
                    candidates.append((has_wall_return, dist, pos, j))

        if not candidates:
            return glass_station, []

        end_post_candidates = [c for c in candidates if c[1] >= 1.5 and c[0]]
        if end_post_candidates:
            # For end post candidates, pick the primary jamb station closest to end post boundary
            end_post_candidates.sort(key=lambda c: c[1])
            best = end_post_candidates[0]
        else:
            # Pick immediate jamb closest to glass (smallest dist) with wall returns preferred
            immediate_candidates = [c for c in candidates if c[1] <= 1.5]
            if immediate_candidates:
                immediate_candidates.sort(key=lambda c: (c[0], -c[1]), reverse=True)
                best = immediate_candidates[0]
            else:
                best = candidates[0]

        all_jambs = list(best[3])
        for s in relevant_cross:
            pos = s.along_station(is_h)
            if 0.0 < abs(pos - best[2]) <= 2.0:
                all_jambs.extend(
                    self._detect_terminal_jambs(
                        [s],
                        pos,
                        wall_band,
                        is_h=is_h,
                        glass_depth_band=glass_depth_band,
                    )
                )
        return best[2], all_jambs

    def _check_wall_continuity(
        self,
        along_strokes: Sequence[_InternalStroke],
        terminal_station: float,
        direction: int,  # -1 for lo (along < station), +1 for hi (along > station)
        wall_band: tuple[float, float],
        *,
        is_h: bool,
    ) -> bool:
        """Verify that wall face strokes continue beyond the terminal station."""
        b0, b1 = wall_band
        for s in along_strokes:
            across = s.across_pos(is_h)
            if b0 <= across <= b1:
                a0, a1 = s.along_span(is_h)
                if direction < 0:
                    # Looking for wall continuing backwards from terminal_station
                    if (
                        a0 < terminal_station - _SNAP_TOL_PT
                        and a1 >= terminal_station - 10.0
                    ):
                        return True
                else:
                    # Looking for wall continuing forwards from terminal_station
                    if (
                        a1 > terminal_station + _SNAP_TOL_PT
                        and a0 <= terminal_station + 10.0
                    ):
                        return True
        return False

    def filter_opening_candidates(
        self,
        candidates: Sequence[CandidateSemanticOpening],
    ) -> tuple[CandidateSemanticOpening, ...]:
        """Filter out candidates that correspond to discriminated internal glazing posts."""
        retained: list[CandidateSemanticOpening] = []
        for cand in candidates:
            cand_obs = set(cand.source_observation_ids)
            # If all observations or key member observations are inside a discriminated post gap
            is_post = False
            for sub_rec in self._subdivision_records.values():
                sub_obs = set(sub_rec.member_observation_ids)
                if cand_obs and cand_obs <= sub_obs:
                    is_post = True
                    break
            if not is_post:
                retained.append(cand)
        return tuple(retained)

    def authority(self) -> StructuralWholeOpeningApertureAuthority:
        """Produce frozen read-only authority."""
        return StructuralWholeOpeningApertureAuthority(
            self._aperture_records,
            self._subdivision_records,
            _seal=_AUTHORITY_SEAL,
        )


class StructuralWholeOpeningApertureAuthority:
    """Frozen read-only authority for querying whole apertures and subdivisions."""

    def __init__(
        self,
        apertures: Mapping[str, WholeOpeningApertureRecord],
        subdivisions: Mapping[str, GlazingSubdivisionDiscriminationRecord],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError(
                "Direct instantiation forbidden. Obtain from producer.authority()."
            )
        self._apertures = dict(apertures)
        self._subdivisions = dict(subdivisions)

    def resolve_aperture(self, aperture_id: str) -> WholeOpeningApertureRecord | None:
        return self._apertures.get(aperture_id)

    def all_apertures(self) -> tuple[WholeOpeningApertureRecord, ...]:
        return tuple(
            sorted(
                self._apertures.values(),
                key=lambda r: (r.page_id, r.axis, r.aperture_span_along),
            )
        )

    def all_discriminated_subdivisions(
        self,
    ) -> tuple[GlazingSubdivisionDiscriminationRecord, ...]:
        return tuple(
            sorted(
                self._subdivisions.values(),
                key=lambda r: (r.page_id, r.subdivision_span_along),
            )
        )

    def is_internal_glazing_subdivision(self, observation_id: str) -> bool:
        """Check if an observation belongs to a discriminated internal glazing post."""
        for sub in self._subdivisions.values():
            if observation_id in sub.member_observation_ids:
                return True
        return False

    def whole_aperture_for_station(
        self,
        page_id: str,
        along_pos: float,
        across_pos: float,
        *,
        axis: str,
    ) -> WholeOpeningApertureRecord | None:
        """Find the whole opening aperture containing the given point."""
        for ap in self._apertures.values():
            if (
                ap.page_id == str(page_id)
                and ap.axis == axis
                and ap.aperture_span_along[0] - _SNAP_TOL_PT
                <= along_pos
                <= ap.aperture_span_along[1] + _SNAP_TOL_PT
                and ap.wall_band_across[0] - _SNAP_TOL_PT
                <= across_pos
                <= ap.wall_band_across[1] + _SNAP_TOL_PT
            ):
                return ap
        return None
