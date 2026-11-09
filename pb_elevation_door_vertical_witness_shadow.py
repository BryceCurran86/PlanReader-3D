"""Shadow-only diagnostic: elevation vertical witness for one plan opening (default off, authority-free).

Question answered, as DIAGNOSTIC EVIDENCE only
----------------------------------------------
Does ONE plan opening have exactly one drawn elevation outline whose head sits on a figured elevation datum
and whose base sits on FFL, reached by a UNIQUE plan-to-elevation registration that uses no type mark, no name
and no benchmark value?

Chain
-----
1. Datum calibration. The elevation view carries FFL and head level lines joined by figured vertical dimensions.
   The drawn spacing times one common scale must reproduce EVERY printed value within ``DATUM_SCALE_TOL``. A chain
   that does not self-calibrate abstains. The title-block scale is never used.
2. Registration. An elevation's horizontal axis equals one plan axis. Spans are matched by width and position;
   one (sign, offset) hypothesis must explain at least two elevation outlines of DIFFERENT widths and strictly
   more of them than every other hypothesis. Equal widths in points across two distinct widths also prove that
   plan and elevation share one scale. Symmetric or single-anchor scenes abstain.
3. Witness. The outline at the registered interval (width and both edges within tolerance) must have its head on
   exactly one datum level and its base on FFL (leaf base, or an enclosing frame base).

Contract (AGENTS.md; MAX 6731795141)
------------------------------------
* A positive is ``EvidenceResolutionStatus.CANDIDATE``, never ``CORROBORATED``. No quantity, no kind, no host,
  no frame, no customer row. The kind, host and frame gates stay closed elsewhere.
* ``opening_height_mm`` is the PRINTED datum value (FFL to head), the architectural opening height. The drawn leaf
  height is reported separately as ``leaf_height_mm`` with distinct provenance and is never substituted.
* Two plan records that match the same outline are held (CONFLICT); there is no nearest, first or smallest winner.
* Foreign or stale scope, off-datum head, off-FFL base, competing heights, an interior opening with no outline,
  and ambiguous registration all abstain or conflict.
* Pure and deterministic; inputs are frozen and never mutated. Nothing imports this module from production.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"
WIDTH_TOL_PT = 0.15
POSITION_TOL_PT = 0.15
HEAD_TOL_PT = 0.15
BASE_TOL_PT = 0.15
DATUM_SCALE_TOL = 0.005
DISTINCT_WIDTH_PT = 1.0

CANDIDATE_REASON = "elevation_door_vertical_witness_candidate_shadow"
DATUM_UNAVAILABLE = "elevation_datum_chain_unavailable"
DATUM_SCALE_INCONSISTENT = "elevation_datum_scale_inconsistent"
FOREIGN_SCOPE = "elevation_scope_ownership_mismatch"
REGISTRATION_INSUFFICIENT = "plan_elevation_registration_insufficient_anchors"
REGISTRATION_AMBIGUOUS = "plan_elevation_registration_ambiguous"
NO_OUTLINE = "no_elevation_outline_at_registered_interval"
COMPETING_OUTLINES = "competing_elevation_outlines_at_registered_interval"
MULTIPLE_PLAN_RECORDS = "elevation_outline_matches_multiple_plan_records"
HEAD_NOT_ON_DATUM = "elevation_head_not_on_datum"
COMPETING_HEIGHTS = "elevation_competing_heights"
BASE_NOT_ON_FFL = "elevation_base_not_on_ffl"
PROMOTION_GATE = "authority_promotion_review_required_kind_host_frame_untouched"


@dataclass(frozen=True)
class PlanSpan:
    """One plan opening interval along a facade axis, in plan points."""

    record_id: str
    a0: float
    a1: float


@dataclass(frozen=True)
class ElevOutline:
    """One drawn elevation outline. ``y`` grows downward on the page; head is the smaller y."""

    outline_id: str
    x0: float
    x1: float
    y_head: float
    y_base_leaf: float
    y_base_frame: Optional[float] = None
    explicit_height_mm: Optional[float] = None   # a height stated on this very outline, if any


@dataclass(frozen=True)
class DatumLevel:
    name: str
    y: float
    figured_mm: float


@dataclass(frozen=True)
class ElevationDatum:
    """FFL line plus figured head levels, all on one view."""

    ffl_y: float
    levels: tuple[DatumLevel, ...]


@dataclass(frozen=True)
class Scope:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str


@dataclass(frozen=True)
class Registration:
    sign: int
    offset: float
    matched_outline_ids: tuple[str, ...]
    anchor_widths_pt: tuple[float, ...]


@dataclass(frozen=True)
class VerticalWitnessResult:
    record_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    outline_id: Optional[str] = None
    opening_height_mm: Optional[float] = None
    head_level_name: Optional[str] = None
    leaf_height_mm: Optional[float] = None
    mm_per_pt: Optional[float] = None
    competing_plan_record_ids: tuple[str, ...] = ()
    overlapping_plan_record_ids: tuple[str, ...] = ()
    registration_anchor_widths_pt: tuple[float, ...] = ()
    result_id: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    @property
    def is_candidate(self) -> bool:
        return self.status is EvidenceResolutionStatus.CANDIDATE


def _result(record_id, status, reasons, **kw) -> VerticalWitnessResult:
    payload = {
        "schema_version": SCHEMA_VERSION, "record": record_id, "status": status.value, "reasons": tuple(reasons),
        "outline": kw.get("outline_id"), "height": kw.get("opening_height_mm"), "head": kw.get("head_level_name"),
        "competing": tuple(kw.get("competing_plan_record_ids", ())),
    }
    return VerticalWitnessResult(
        record_id=record_id, status=status, reason_codes=tuple(reasons),
        result_id=stable_contract_id("elevation_vertical_witness_shadow", payload, digest_chars=32), **kw,
    )


# ----------------------------------------------------------------------------------- datum

def calibrate_datum(datum: ElevationDatum) -> Optional[float]:
    """mm per page point from the printed values, or ``None`` if the chain does not self-calibrate."""
    if not datum.levels:
        return None
    ratios = []
    for level in datum.levels:
        spacing = datum.ffl_y - level.y
        if spacing <= 0.0 or level.figured_mm <= 0.0:
            return None
        ratios.append(level.figured_mm / spacing)
    mean = sum(ratios) / len(ratios)
    if mean <= 0.0 or any(abs(r - mean) / mean > DATUM_SCALE_TOL for r in ratios):
        return None
    return mean


# ------------------------------------------------------------------------------ registration

def _near(a: float, b: float, tol: float) -> bool:
    return abs(a - b) <= tol


def _project(span: PlanSpan, sign: int, offset: float) -> tuple[float, float]:
    if sign > 0:
        return (span.a0 + offset, span.a1 + offset)
    return (-span.a1 + offset, -span.a0 + offset)


def register_plan_to_elevation(
    plan: Sequence[PlanSpan], outlines: Sequence[ElevOutline],
) -> tuple[Optional[Registration], Optional[str]]:
    """Unique (sign, offset) or a reason. Deterministic and order-invariant."""
    plan = tuple(sorted(plan, key=lambda p: (p.record_id, p.a0, p.a1)))
    outlines = tuple(sorted(outlines, key=lambda o: (o.outline_id, o.x0, o.x1)))
    candidates: dict[tuple[int, int], float] = {}
    for p in plan:
        pw = p.a1 - p.a0
        for o in outlines:
            if not _near(pw, o.x1 - o.x0, WIDTH_TOL_PT):
                continue
            for sign in (1, -1):
                offset = (o.x0 - p.a0) if sign > 0 else (o.x0 + p.a1)
                candidates[(sign, round(offset / POSITION_TOL_PT))] = offset
    scored = []
    for (sign, _), offset in sorted(candidates.items()):
        matched = []
        for o in outlines:
            for p in plan:
                x0, x1 = _project(p, sign, offset)
                if _near(x0, o.x0, POSITION_TOL_PT) and _near(x1, o.x1, POSITION_TOL_PT):
                    matched.append(o)
                    break
        widths = sorted({round(o.x1 - o.x0, 2) for o in matched})
        distinct = []
        for w in widths:
            if not distinct or w - distinct[-1] > DISTINCT_WIDTH_PT:
                distinct.append(w)
        scored.append((len(matched), len(distinct), sign, offset, tuple(sorted(o.outline_id for o in matched)), tuple(distinct)))
    if not scored:
        return None, REGISTRATION_INSUFFICIENT
    scored.sort(key=lambda s: (-s[0], -s[1], s[2], s[3]))
    best = scored[0]
    if best[0] < 2 or best[1] < 2:
        return None, REGISTRATION_INSUFFICIENT
    for other in scored[1:]:
        different = other[2] != best[2] or abs(other[3] - best[3]) > 2.0 * POSITION_TOL_PT
        if different and other[0] >= best[0]:
            return None, REGISTRATION_AMBIGUOUS
    return Registration(best[2], best[3], best[4], best[5]), None


# --------------------------------------------------------------------------------- witness

def resolve_vertical_witness(
    record_id: str,
    plan: Sequence[PlanSpan],
    outlines: Sequence[ElevOutline],
    datum: ElevationDatum,
    *,
    plan_scope: Scope,
    elevation_scope: Scope,
) -> VerticalWitnessResult:
    """Witness for ONE plan record, against all facade spans and one elevation view."""
    if plan_scope != elevation_scope:
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (FOREIGN_SCOPE,))
    scale = calibrate_datum(datum)
    if scale is None:
        reason = DATUM_UNAVAILABLE if not datum.levels else DATUM_SCALE_INCONSISTENT
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (reason,))
    target = next((p for p in plan if p.record_id == record_id), None)
    if target is None:
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (NO_OUTLINE,), mm_per_pt=scale)
    registration, why = register_plan_to_elevation(plan, outlines)
    if registration is None:
        status = EvidenceResolutionStatus.CONFLICT if why == REGISTRATION_AMBIGUOUS else EvidenceResolutionStatus.ABSTAINED
        return _result(record_id, status, (why,), mm_per_pt=scale)
    x0, x1 = _project(target, registration.sign, registration.offset)
    at_interval = [
        o for o in sorted(outlines, key=lambda o: (o.outline_id, o.x0))
        if _near(o.x0, x0, POSITION_TOL_PT) and _near(o.x1, x1, POSITION_TOL_PT)
    ]
    if not at_interval:
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (NO_OUTLINE,), mm_per_pt=scale,
                       registration_anchor_widths_pt=registration.anchor_widths_pt)
    if len(at_interval) > 1:
        return _result(record_id, EvidenceResolutionStatus.CONFLICT, (COMPETING_OUTLINES,), mm_per_pt=scale,
                       registration_anchor_widths_pt=registration.anchor_widths_pt)
    outline = at_interval[0]
    sharing = tuple(sorted(
        p.record_id for p in plan
        if p.record_id != record_id
        and all(_near(a, b, POSITION_TOL_PT) for a, b in zip(_project(p, registration.sign, registration.offset), (outline.x0, outline.x1)))
    ))
    if sharing:
        return _result(record_id, EvidenceResolutionStatus.CONFLICT, (MULTIPLE_PLAN_RECORDS,), outline_id=outline.outline_id,
                       competing_plan_record_ids=sharing, mm_per_pt=scale,
                       registration_anchor_widths_pt=registration.anchor_widths_pt)
    on_head = [lv for lv in datum.levels if _near(lv.y, outline.y_head, HEAD_TOL_PT)]
    if not on_head:
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (HEAD_NOT_ON_DATUM,), outline_id=outline.outline_id,
                       mm_per_pt=scale, registration_anchor_widths_pt=registration.anchor_widths_pt)
    if len({lv.figured_mm for lv in on_head}) > 1:
        return _result(record_id, EvidenceResolutionStatus.CONFLICT, (COMPETING_HEIGHTS,), outline_id=outline.outline_id,
                       mm_per_pt=scale, registration_anchor_widths_pt=registration.anchor_widths_pt)
    head = on_head[0]
    if outline.explicit_height_mm is not None and abs(outline.explicit_height_mm - head.figured_mm) > 0.5:
        return _result(record_id, EvidenceResolutionStatus.CONFLICT, (COMPETING_HEIGHTS,), outline_id=outline.outline_id,
                       mm_per_pt=scale, registration_anchor_widths_pt=registration.anchor_widths_pt)
    bases = [b for b in (outline.y_base_leaf, outline.y_base_frame) if b is not None]
    if not any(_near(b, datum.ffl_y, BASE_TOL_PT) for b in bases):
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (BASE_NOT_ON_FFL,), outline_id=outline.outline_id,
                       mm_per_pt=scale, registration_anchor_widths_pt=registration.anchor_widths_pt)
    return _result(
        record_id, EvidenceResolutionStatus.CANDIDATE, (CANDIDATE_REASON,), outline_id=outline.outline_id,
        opening_height_mm=float(head.figured_mm), head_level_name=head.name,
        leaf_height_mm=round((outline.y_base_leaf - outline.y_head) * scale, 1), mm_per_pt=round(scale, 4),
        registration_anchor_widths_pt=registration.anchor_widths_pt,
    )


def assess_elevation_vertical_witness_shadow(
    views: Sequence[Mapping[str, object]], *, enabled: bool = False,
) -> tuple[VerticalWitnessResult, ...]:
    """Default off. ``views``: mappings with ``plan``, ``outlines``, ``datum``, ``plan_scope``, ``elevation_scope``.

    Returns one result per plan record per view. Every record is assessed against every view; a record is only a
    candidate where exactly one view gives a candidate (two views disagreeing is reported by the caller).
    """
    if type(enabled) is not bool:
        raise TypeError("enabled must be a bool")
    if not enabled:
        return ()
    rows: list[VerticalWitnessResult] = []
    for view in views:
        for span in sorted(view["plan"], key=lambda p: p.record_id):
            rows.append(resolve_vertical_witness(
                span.record_id, view["plan"], view["outlines"], view["datum"],
                plan_scope=view["plan_scope"], elevation_scope=view["elevation_scope"],
            ))
    return tuple(rows)


__all__ = [
    "CANDIDATE_REASON", "DatumLevel", "ElevOutline", "ElevationDatum", "PlanSpan", "Registration", "Scope",
    "VerticalWitnessResult", "assess_elevation_vertical_witness_shadow", "calibrate_datum",
    "register_plan_to_elevation", "resolve_vertical_witness",
]
