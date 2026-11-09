"""Shadow-only diagnostic: an elevation label proposed as the KIND of the SAME registered physical opening.

A label such as "ALUMINIUM ENTRY DOOR" says what an object is only if it is *attached* to that object. This core
attaches a label to a drawn outline ONLY through a stroked leader chain and refuses every other association. It
neither mints a kind nor writes to the opening kind authority: the result is a PROPOSAL (``CANDIDATE``) with receipts,
to be handed to that authority only after the plan-to-elevation instance match it depends on.

Rules (MAX 6733403455 and 6733647877; AGENTS.md)
------------------------------------------------
* The label's kind comes from an explicit token in its own words (``DOOR`` or ``WINDOW``). Never from the height,
  the 2,100 datum, the leaf, the outline shape or the width. This module has no height or width input at all.
* The leader is a chain of axis-aligned stroked segments that starts within ``START_TOL_PT`` of the label's words,
  leads away from them, and whose consecutive segments share an exact end point (``CONTACT_TOL_PT``). Every route
  from the label is followed (a fork explores both branches); only a route END that lies inside an outline attaches
  anything, so a branch that ends in blank space changes nothing, while a route longer than ``MAX_CHAIN_SEGMENTS`` or
  more than ``MAX_ROUTES`` routes abstains. Nothing is closed by proximity beyond the start tolerance.
* The tip must lie STRICTLY inside the witnessed outline. The outlines that contain the tip must form one nested
  chain (a leaf inside its frame inside its surround is one physical door); two overlapping outlines that do not
  nest are different objects, so the association abstains.
* Every route end that lies inside an outline must lie inside ONE nested chain that contains the witnessed outline:
  a label (or several labels) whose routes land in different, non-nested instances abstains. Two labels that reach
  the same instance with different kinds conflict. A label that reaches nothing is ignored.
* The words must be text-integrity CORROBORATED for the proposal to be authenticated text; raw words stay
  ``raw_unverified_diagnostic_only``. The proposal is never ``CORROBORATED`` and is never an authority.
* Pure, deterministic, order-invariant, no input mutation. Nothing in production imports this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"
START_TOL_PT = 6.0
CONTACT_TOL_PT = 1e-3
NEST_TOL_PT = 0.05      # drawn rectangle edges that coincide within 0.05 pt are the same edge
INSIDE_MARGIN_PT = 0.2
MIN_LEADER_SEGMENT_PT = 1.0
MAX_CHAIN_SEGMENTS = 6
MAX_ROUTES = 16
AXIS_TOL_PT = 0.05     # leaders are drawn orthogonally; a diagonal stroke (hatching, a brick course) is not a leader

KIND_PROPOSAL = "elevation_label_kind_proposal_candidate_shadow"
NO_KIND_TOKEN = "label_has_no_explicit_kind_token"
MIXED_KIND_TOKENS = "label_has_both_door_and_window_tokens"
NO_LEADER = "no_label_leader_chain_reaches_this_instance"
LEADER_BRANCHES = "leader_routes_overflow_or_are_unfinished"
NOT_NESTED = "leader_tip_inside_non_nested_outlines"
COMPETING_LABELS = "competing_label_kinds_for_one_physical_instance"
AMBIGUOUS_LEADERS = "label_leaders_reach_different_instances"
WITNESSED_MISSING = "witnessed_outline_not_in_outline_set"
INVALID_INPUT = "label_kind_input_invalid"
GATE_PROMOTION = "authority_promotion_review_required_kind_authority_untouched"

_DOOR = re.compile(r"\bDOORS?\b", re.IGNORECASE)
_WINDOW = re.compile(r"\bWINDOWS?\b", re.IGNORECASE)

TEXT_CORROBORATED = "corroborated"
TEXT_RAW = "raw_unverified"
TEXT_TRUST_RAW_DIAGNOSTIC = "raw_unverified_diagnostic_only"


@dataclass(frozen=True)
class LabelBlock:
    """The words of ONE printed label, in reading order."""

    block_id: str
    text: str
    bbox: tuple[float, float, float, float]
    receipt_ids: tuple[str, ...] = ()
    text_trust: str = ""


@dataclass(frozen=True)
class StrokeSegment:
    x0: float
    y0: float
    x1: float
    y1: float
    receipt_id: str = ""


@dataclass(frozen=True)
class OutlineBox:
    outline_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    receipt_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class KindProposal:
    record_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    kind: Optional[str] = None
    label_text: Optional[str] = None
    label_block_id: Optional[str] = None
    outline_id: Optional[str] = None
    nested_outline_ids: tuple[str, ...] = ()
    text_trust: str = ""
    source_observation_ids: tuple[str, ...] = ()
    result_id: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    @property
    def is_candidate(self) -> bool:
        return self.status is EvidenceResolutionStatus.CANDIDATE


def _finite(*values) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def _result(record_id, status, reasons, **kw) -> KindProposal:
    payload = {
        "schema_version": SCHEMA_VERSION, "record": record_id, "status": status.value, "reasons": tuple(reasons),
        "kind": kw.get("kind"), "label": kw.get("label_block_id"), "outline": kw.get("outline_id"),
        "nested": tuple(kw.get("nested_outline_ids", ())), "trust": kw.get("text_trust", ""),
        "receipts": tuple(kw.get("source_observation_ids", ())),
    }
    return KindProposal(record_id=record_id, status=status, reason_codes=tuple(reasons),
                        result_id=stable_contract_id("elevation_label_kind_proposal_shadow", payload, digest_chars=32), **kw)


def label_kind(text: str) -> tuple[Optional[str], Optional[str]]:
    """(kind, problem). ``door`` or ``window`` only from an explicit token; both tokens together is a problem."""
    has_door, has_window = bool(_DOOR.search(text or "")), bool(_WINDOW.search(text or ""))
    if has_door and has_window:
        return None, MIXED_KIND_TOKENS
    if has_door:
        return "door", None
    if has_window:
        return "window", None
    return None, NO_KIND_TOKEN


def _same(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= CONTACT_TOL_PT


def _dist_to_bbox(point, bbox) -> float:
    dx = max(bbox[0] - point[0], 0.0, point[0] - bbox[2])
    dy = max(bbox[1] - point[1], 0.0, point[1] - bbox[3])
    return math.hypot(dx, dy)


def _valid(blocks, strokes, outlines) -> bool:
    for b in blocks:
        if not isinstance(b.text, str) or len(b.bbox) != 4 or not _finite(*b.bbox):
            return False
    for s in strokes:
        if not _finite(s.x0, s.y0, s.x1, s.y1):
            return False
    for o in outlines:
        if not o.outline_id or not _finite(o.x0, o.y0, o.x1, o.y1) or not (o.x1 > o.x0 and o.y1 > o.y0):
            return False
    return (len({b.block_id for b in blocks}) == len(blocks) and len({o.outline_id for o in outlines}) == len(outlines))


def _continuations(usable, used, here):
    out = []
    for i, s in enumerate(usable):
        if i in used:
            continue
        if _same((s.x0, s.y0), here):
            out.append((i, s, (s.x1, s.y1)))
        elif _same((s.x1, s.y1), here):
            out.append((i, s, (s.x0, s.y0)))
    return out


def _chains(block: LabelBlock, strokes: Sequence[StrokeSegment]):
    """Every route from the label: ``([(end, segments)], overflow)``.

    A route starts with an axis-aligned stroke that begins near the words and leads away from them, then follows
    exact end-to-end contacts. A fork explores every branch. ``overflow`` is set when a route is longer than
    ``MAX_CHAIN_SEGMENTS`` or the label has more than ``MAX_ROUTES`` routes: such a label is not a clean leader.
    """
    usable = [s for s in strokes if math.hypot(s.x1 - s.x0, s.y1 - s.y0) >= MIN_LEADER_SEGMENT_PT
              and (abs(s.x1 - s.x0) <= AXIS_TOL_PT or abs(s.y1 - s.y0) <= AXIS_TOL_PT)]
    routes, overflow = [], False
    for fi, first in enumerate(usable):
        for start, far in (((first.x0, first.y0), (first.x1, first.y1)), ((first.x1, first.y1), (first.x0, first.y0))):
            if _dist_to_bbox(start, block.bbox) > START_TOL_PT or _dist_to_bbox(far, block.bbox) <= _dist_to_bbox(start, block.bbox):
                continue                        # must start near the words and lead away from them
            stack = [(far, (first,), frozenset({fi}))]
            while stack:
                here, chain, used = stack.pop()
                nxt = _continuations(usable, used, here)
                if not nxt:
                    routes.append((here, chain))
                    if len(routes) > MAX_ROUTES:
                        return routes, True
                    continue
                if len(chain) >= MAX_CHAIN_SEGMENTS:
                    overflow = True              # unfinished: too long to be a single leader
                    continue
                for i, s, far2 in nxt:
                    stack.append((far2, chain + (s,), used | {i}))
    return routes, overflow


def _inside(point, o: OutlineBox) -> bool:
    return (o.x0 + INSIDE_MARGIN_PT < point[0] < o.x1 - INSIDE_MARGIN_PT
            and o.y0 + INSIDE_MARGIN_PT < point[1] < o.y1 - INSIDE_MARGIN_PT)


def _nested(boxes: Sequence[OutlineBox]) -> bool:
    ordered = sorted(boxes, key=lambda o: ((o.x1 - o.x0) * (o.y1 - o.y0), o.outline_id))
    return all(a.x0 >= b.x0 - NEST_TOL_PT and a.x1 <= b.x1 + NEST_TOL_PT and a.y0 >= b.y0 - NEST_TOL_PT
               and a.y1 <= b.y1 + NEST_TOL_PT for a, b in zip(ordered, ordered[1:]))


def _text_trust(values: Sequence[str]) -> str:
    if values and all(v == TEXT_CORROBORATED for v in values):
        return TEXT_CORROBORATED
    if values and all(v in (TEXT_CORROBORATED, TEXT_RAW, TEXT_TRUST_RAW_DIAGNOSTIC) for v in values):
        return TEXT_TRUST_RAW_DIAGNOSTIC
    return ""


def propose_kind_from_leader(
    record_id: str,
    witnessed_outline_id: Optional[str],
    outlines: Sequence[OutlineBox],
    blocks: Sequence[LabelBlock],
    strokes: Sequence[StrokeSegment],
) -> KindProposal:
    """Kind proposal for the physical opening whose witnessed outline is ``witnessed_outline_id``."""
    if not _valid(blocks, strokes, outlines):
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (INVALID_INPUT,))
    witnessed = next((o for o in outlines if o.outline_id == witnessed_outline_id), None)
    if witnessed is None:
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (WITNESSED_MISSING,))
    by_id = {o.outline_id: o for o in outlines}
    reached = []          # (block, kind, problem, holder ids, receipts)
    seen = set()
    for block in sorted(blocks, key=lambda b: b.block_id):
        routes, overflow = _chains(block, strokes)
        if overflow:                            # too many or too long routes: not a clean leader, whatever they reach
            seen.add(LEADER_BRANCHES)
            continue
        tips = []
        for end, segs in routes:
            holders = sorted((o for o in outlines if _inside(end, o)), key=lambda o: o.outline_id)
            tips.append((segs, holders))
        if not any(witnessed.outline_id in {o.outline_id for o in holders} for _, holders in tips):
            continue                            # this label does not reach the witnessed instance
        if any(not _nested(holders) for _, holders in tips):
            seen.add(NOT_NESTED)
            continue
        union = sorted({o.outline_id for _, holders in tips for o in holders})
        kind, problem = label_kind(block.text)
        receipts = set(block.receipt_ids) | {s.receipt_id for segs, holders in tips if holders for s in segs if s.receipt_id}
        receipts |= {i for u in union for i in by_id[u].receipt_ids}
        reached.append((block, kind, problem, tuple(union), tuple(sorted(receipts))))
    usable = [r for r in reached if r[2] is None]
    if not usable:
        problems = {r[2] for r in reached}
        for reason in (NOT_NESTED, LEADER_BRANCHES, MIXED_KIND_TOKENS, NO_KIND_TOKEN):
            if reason in seen or reason in problems:
                return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (reason,))
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (NO_LEADER,))
    kinds = {r[1] for r in usable}
    union_ids = tuple(sorted({i for r in usable for i in r[3]}))
    if len(kinds) > 1:
        return _result(record_id, EvidenceResolutionStatus.CONFLICT, (COMPETING_LABELS,), nested_outline_ids=union_ids,
                       outline_id=witnessed.outline_id)
    if not _nested([by_id[i] for i in union_ids]):
        return _result(record_id, EvidenceResolutionStatus.ABSTAINED, (AMBIGUOUS_LEADERS,), outline_id=witnessed.outline_id)
    blocks_used = [r[0] for r in usable]
    receipts = tuple(sorted({i for r in usable for i in r[4]}))
    return _result(
        record_id, EvidenceResolutionStatus.CANDIDATE, (KIND_PROPOSAL,), kind=next(iter(kinds)),
        label_text=" / ".join(b.text for b in blocks_used), label_block_id="+".join(b.block_id for b in blocks_used),
        outline_id=witnessed.outline_id, nested_outline_ids=union_ids,
        text_trust=_text_trust([b.text_trust for b in blocks_used]), source_observation_ids=receipts)


__all__ = [
    "KIND_PROPOSAL", "KindProposal", "LabelBlock", "OutlineBox", "StrokeSegment", "label_kind", "propose_kind_from_leader",
    "COMPETING_LABELS", "AMBIGUOUS_LEADERS", "INVALID_INPUT", "LEADER_BRANCHES", "MIXED_KIND_TOKENS", "NOT_NESTED",
    "NO_KIND_TOKEN", "NO_LEADER", "WITNESSED_MISSING", "GATE_PROMOTION",
]
