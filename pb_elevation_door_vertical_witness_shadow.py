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
import math
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
INVALID_INPUT = "elevation_witness_input_invalid"
DUPLICATE_IDENTITY = "elevation_witness_duplicate_identity"
COMPETING_VIEWS = "competing_elevation_views"
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
    receipt_ids: tuple[str, ...] = ()            # source observation ids that drew this outline (when source-owned)


@dataclass(frozen=True)
class DatumLevel:
    name: str
    y: float
    figured_mm: float
    receipt_ids: tuple[str, ...] = ()   # dimension line, tick and figured-word observation ids


@dataclass(frozen=True)
class ElevationDatum:
    """FFL line plus figured head levels, all on one view."""

    ffl_y: float
    levels: tuple[DatumLevel, ...]
    receipt_ids: tuple[str, ...] = ()


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
    source_observation_ids: tuple[str, ...] = ()
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
        "receipts": tuple(kw.get("source_observation_ids", ())),
    }
    return VerticalWitnessResult(
        record_id=record_id, status=status, reason_codes=tuple(reasons),
        result_id=stable_contract_id("elevation_vertical_witness_shadow", payload, digest_chars=32), **kw,
    )


# --------------------------------------------------------------------------- validation

def _finite(*values) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def _validate(plan: Sequence[PlanSpan], outlines: Sequence[ElevOutline]) -> Optional[str]:
    """``INVALID_INPUT`` for non-finite or inverted geometry, ``DUPLICATE_IDENTITY`` for a repeated id, else ``None``."""
    for p in plan:
        if not isinstance(p.record_id, str) or not p.record_id or not _finite(p.a0, p.a1) or not p.a1 > p.a0:
            return INVALID_INPUT
    for o in outlines:
        if (not isinstance(o.outline_id, str) or not o.outline_id
                or not _finite(o.x0, o.x1, o.y_head, o.y_base_leaf) or not o.x1 > o.x0 or not o.y_base_leaf > o.y_head):
            return INVALID_INPUT
        if o.y_base_frame is not None and (not _finite(o.y_base_frame) or not o.y_base_frame >= o.y_head):
            return INVALID_INPUT
        if o.explicit_height_mm is not None and (not _finite(o.explicit_height_mm) or not o.explicit_height_mm > 0.0):
            return INVALID_INPUT
    if len({p.record_id for p in plan}) != len(plan) or len({o.outline_id for o in outlines}) != len(outlines):
        return DUPLICATE_IDENTITY
    return None


# ----------------------------------------------------------------------------------- datum

def calibrate_datum(datum: ElevationDatum) -> Optional[float]:
    """mm per page point from the printed values, or ``None`` if the chain does not self-calibrate."""
    if not datum.levels or not _finite(datum.ffl_y):
        return None
    ratios = []
    for level in datum.levels:
        if not _finite(level.y, level.figured_mm):
            return None
        spacing = datum.ffl_y - level.y
        if spacing <= 0.0 or level.figured_mm <= 0.0 or not math.isfinite(spacing):
            return None
        ratios.append(level.figured_mm / spacing)
    mean = sum(ratios) / len(ratios)
    if not math.isfinite(mean) or mean <= 0.0 or any(abs(r - mean) / mean > DATUM_SCALE_TOL for r in ratios):
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
    invalid = _validate(plan, outlines)
    if invalid is not None:
        return None, invalid
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
    invalid = _validate(plan, outlines)
    if invalid == DUPLICATE_IDENTITY:
        return _result(record_id, EvidenceResolutionStatus.CONFLICT, (DUPLICATE_IDENTITY,))
    if invalid is not None:
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (invalid,))
    scale = calibrate_datum(datum)
    if scale is None:
        reason = DATUM_UNAVAILABLE if not datum.levels else DATUM_SCALE_INCONSISTENT
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (reason,))
    matches = [p for p in plan if p.record_id == record_id]    # unique after validation
    target = matches[0] if matches else None
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
    anchors = [o for o in outlines if o.outline_id in registration.matched_outline_ids]
    receipts = tuple(sorted(set(
        outline.receipt_ids + head.receipt_ids + datum.receipt_ids + tuple(r for a in anchors for r in a.receipt_ids)
    )))
    return _result(
        record_id, EvidenceResolutionStatus.CANDIDATE, (CANDIDATE_REASON,), outline_id=outline.outline_id,
        source_observation_ids=receipts,
        opening_height_mm=float(head.figured_mm), head_level_name=head.name,
        leaf_height_mm=round((outline.y_base_leaf - outline.y_head) * scale, 1), mm_per_pt=round(scale, 4),
        registration_anchor_widths_pt=registration.anchor_widths_pt,
    )


_VIEW_LEVEL = frozenset({
    DATUM_UNAVAILABLE, DATUM_SCALE_INCONSISTENT, FOREIGN_SCOPE, REGISTRATION_INSUFFICIENT, REGISTRATION_AMBIGUOUS,
    INVALID_INPUT, DUPLICATE_IDENTITY,
})
_ABSTAIN_PRIORITY = (
    HEAD_NOT_ON_DATUM, BASE_NOT_ON_FFL, COMPETING_HEIGHTS, COMPETING_OUTLINES, MULTIPLE_PLAN_RECORDS, NO_OUTLINE,
    DATUM_SCALE_INCONSISTENT, DATUM_UNAVAILABLE, REGISTRATION_AMBIGUOUS, REGISTRATION_INSUFFICIENT, FOREIGN_SCOPE,
    INVALID_INPUT, DUPLICATE_IDENTITY,
)


def aggregate_across_views(results: Sequence[VerticalWitnessResult]) -> tuple[VerticalWitnessResult, ...]:
    """One result per plan record from per-view results, so no view can be cherry-picked.

    A view that could not register or calibrate says nothing about a record and is ignored for conflicts. Among the
    views that did assess the record: two candidates, or a candidate plus a record-level conflict elsewhere, is a
    CONFLICT (``competing_elevation_views``). Exactly one candidate and no record-level conflict stays a CANDIDATE;
    otherwise the most specific abstention is reported. Deterministic and input-order invariant.
    """
    by_record: dict[str, list[VerticalWitnessResult]] = {}
    for r in results:
        by_record.setdefault(r.record_id, []).append(r)
    out = []
    for record_id in sorted(by_record):
        rows = sorted(by_record[record_id], key=lambda r: (r.status.value, r.reason_codes, r.outline_id or "", r.result_id or ""))
        assessed = [r for r in rows if r.reason_codes[0] not in _VIEW_LEVEL]
        candidates = [r for r in assessed if r.is_candidate]
        conflicts = [r for r in assessed if r.status is EvidenceResolutionStatus.CONFLICT]
        if len(candidates) >= 2 or (candidates and conflicts):
            out.append(_result(record_id, EvidenceResolutionStatus.CONFLICT, (COMPETING_VIEWS,)))
        elif len(candidates) == 1:
            out.append(candidates[0])
        elif conflicts:
            out.append(sorted(conflicts, key=lambda r: (r.reason_codes, r.outline_id or ""))[0])
        else:
            def rank(r):
                code = r.reason_codes[0]
                return _ABSTAIN_PRIORITY.index(code) if code in _ABSTAIN_PRIORITY else len(_ABSTAIN_PRIORITY)
            out.append(sorted(rows, key=lambda r: (rank(r), r.reason_codes, r.outline_id or ""))[0])
    return tuple(out)


def assess_elevation_vertical_witness_shadow(
    views: Sequence[Mapping[str, object]], *, enabled: bool = False,
) -> tuple[VerticalWitnessResult, ...]:
    """Default off. ``views``: mappings with ``plan``, ``outlines``, ``datum``, ``plan_scope``, ``elevation_scope``.

    Returns ONE result per plan record: every record is assessed against every view and the per-view results go
    through ``aggregate_across_views``, so competing views or values can never be turned into a candidate by
    picking one of them.
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
    return aggregate_across_views(rows)


__all__ = [
    "CANDIDATE_REASON", "COMPETING_VIEWS", "DUPLICATE_IDENTITY", "INVALID_INPUT", "aggregate_across_views", "DatumLevel", "ElevOutline", "ElevationDatum", "PlanSpan", "Registration", "Scope",
    "VerticalWitnessResult", "assess_elevation_vertical_witness_shadow", "calibrate_datum",
    "register_plan_to_elevation", "resolve_vertical_witness",
]
