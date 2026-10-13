"""Explicitly declared approval of snapshot-scoped receipt rekeys.

Adding genuine source observations to a page changes the SourceVisibility
``snapshot_id``.  Host and frame receipts are hashes of that snapshot, so every
previously authenticated receipt is rekeyed even when the physical proposition
behind it is unchanged.  The strict retention gates reject that, by design
(``gptmax_source_host_rekey_parity_ledger`` classifies it as an *unapproved*
rekey).  This module is the separate, explicit approval step.

An approval exists only for one declared event: the exact source SHA, the exact
baseline snapshot and the exact candidate snapshot.  It never publishes a host,
frame, count or quantity, and it never edits a report.  The existing strict
comparators keep their default behaviour when no declaration matches.

What an approval proves, on top of ``compare_source_host_rekeys``:

* the physical opening identity universe is identical;
* every previously hosted opening keeps the same W4 member candidates, the same
  positive candidate identity / source primitive ancestry / source-edge
  geometry / centerline and (stage shape) the same source-space frame geometry
  -- only snapshot-scoped receipt addresses and generated split ordinals move;
* the only newly hosted openings are the declared ones, each an existing,
  corroborated physical opening with a host receipt; every other unhosted
  opening is unchanged except exact declared reason transitions;
* **all original W4 source geometry is conserved**: retained walls cover exactly
  their original line, a vanished wall has one successor covering every original
  fragment (terminal endpoints included), and the W4 scope-level claims are equal
  modulo snapshot ids;
* every declared report key is verified (canonical openings, summary, semantic
  inventory, id-churn keys) or listed in ``unverified_changed_report_keys``;
  every undeclared key is equal;
* the declaration may rekey snapshot-scoped receipts only when it says so
  (``allow_snapshot_receipt_rekey``; default is exact retention).

It does not replace the physical-source gates: it can only pass an event that
leaves the canonical W4 scope untouched apart from snapshot ids.
"""
from __future__ import annotations

import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Sequence

from tools.gptmax_source_host_rekey_parity_ledger import compare_source_host_rekeys
from tools.source_report_scoped_equality import (
    additive_observation_inventory_equal,
    equal_modulo_snapshot_scoped_ids,
    evidence_swap_matches,
)

DECLARATION_SCHEMA = "declared_additive_source_retention.v1"
DEFAULT_DECLARATIONS_PATH = Path(__file__).with_name(
    "declared_additive_source_retention.json"
)

ACCEPTED_LEDGER_STATES = frozenset(
    {
        "EXACT_PRIOR_RECEIPTS_RETAINED",
        "UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY",
    }
)
# Receipt fields that legitimately follow a snapshot change on a retained host.
REKEY_FLAGS = frozenset(
    {"host_owner_changed", "host_receipt_changed", "source_frame_changed"}
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
REPORT_SHAPES = ("stage_report", "face_report")
_DECLARATION_KEYS = frozenset(
    {
        "source_sha256",
        "report_shape",
        "baseline_snapshot_id",
        "candidate_snapshot_id",
        "expected_new_host_ids",
        "expected_new_frame_host_ids",
        "expected_unhosted_reason_changes",
        "expected_changed_report_keys",
        "expected_id_churn_report_keys",
        "allow_snapshot_receipt_rekey",
        "tracking_issue",
    }
)
# Report keys whose change is verified by dedicated code in the approval itself.
_VERIFIED_ELSEWHERE_KEYS = frozenset(
    {
        "snapshot_id",  # bound exactly by the declaration's baseline/candidate snapshot ids
        "opening_bindings",
        "host_frames",
        "host_frame_traces",
        "resolved_host_frame_evidence",
        "source_owned_wall_scopes",
        "source_owned_wall_scope_results",
        "canonical_openings",
        "summary",
        "semantic_inventory",
        "composition_reason_codes",
    }
)
_HOST_COUNT_SUMMARY_KEYS = frozenset({"authenticated_hosts", "host_bindings"})
_FRAME_COUNT_SUMMARY_KEYS = frozenset({"resolved_source_frames", "host_frames"})
_REASON_CHANGE_KEYS = frozenset({"opening_identity_id", "before", "after"})
# The only binding / frame fields that follow a snapshot change on a retained
# host.  Everything else on those rows must be identical.
_SNAPSHOT_SCOPED_FIELDS = frozenset({"host_wall_id", "record_id"})
# Fields of an unrelated unhosted opening that must never move.
_UNHOSTED_FROZEN_FIELDS = (
    "status",
    "page_id",
    "representative_observation_id",
    "member_wall_candidate_ids",
    "host_wall_id",
    "record_id",
)


@dataclass(frozen=True)
class ReasonChange:
    opening_identity_id: str
    before: tuple[str, ...]
    after: tuple[str, ...]


@dataclass(frozen=True)
class Declaration:
    source_sha256: str
    report_shape: str
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    expected_new_host_ids: tuple[str, ...]
    expected_new_frame_host_ids: tuple[str, ...]
    expected_unhosted_reason_changes: tuple[ReasonChange, ...]
    expected_changed_report_keys: tuple[str, ...]
    expected_id_churn_report_keys: tuple[str, ...]
    allow_snapshot_receipt_rekey: bool
    tracking_issue: int


def _text(value: object, name: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"declaration {name} must be a non-empty trimmed string")
    return value


def _unique_texts(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise ValueError(f"declaration {name} must be a list")
    result = tuple(_text(item, name) for item in value)
    if len(set(result)) != len(result):
        raise ValueError(f"declaration {name} has repeated entries")
    return result


def parse_declaration(raw: Mapping[str, Any]) -> Declaration:
    if not isinstance(raw, Mapping) or set(raw) != _DECLARATION_KEYS:
        raise ValueError("declaration must carry exactly the documented fields")
    sha = _text(raw["source_sha256"], "source_sha256")
    if _SHA256.fullmatch(sha) is None:
        raise ValueError("declaration source_sha256 must be lowercase sha256")
    shape = _text(raw["report_shape"], "report_shape")
    if shape not in REPORT_SHAPES:
        raise ValueError("declaration report_shape must be one of " + ", ".join(REPORT_SHAPES))
    hosts = _unique_texts(raw["expected_new_host_ids"], "expected_new_host_ids")
    if not hosts:
        raise ValueError("declaration must name at least one expected new host")
    frames = _unique_texts(raw["expected_new_frame_host_ids"], "expected_new_frame_host_ids")
    if not set(frames) <= set(hosts):
        raise ValueError("a newly framed opening must itself be a declared new host")
    changes_raw = raw["expected_unhosted_reason_changes"]
    if not isinstance(changes_raw, list):
        raise ValueError("declaration expected_unhosted_reason_changes must be a list")
    changes = []
    for item in changes_raw:
        if not isinstance(item, Mapping) or set(item) != _REASON_CHANGE_KEYS:
            raise ValueError("declared reason change must carry exactly the documented fields")
        before = _unique_texts(item["before"], "reason change before")
        after = _unique_texts(item["after"], "reason change after")
        if before == after:
            raise ValueError("declared reason change must change something")
        changes.append(
            ReasonChange(_text(item["opening_identity_id"], "opening_identity_id"), before, after)
        )
    if len({change.opening_identity_id for change in changes}) != len(changes):
        raise ValueError("an opening may declare at most one reason change")
    if set(hosts) & {change.opening_identity_id for change in changes}:
        raise ValueError("a newly hosted opening cannot also declare a reason change")
    keys = _unique_texts(raw["expected_changed_report_keys"], "expected_changed_report_keys")
    if "snapshot_id" not in keys:
        raise ValueError("a snapshot-changing event must declare snapshot_id among its changed report keys")
    churn = _unique_texts(raw["expected_id_churn_report_keys"], "expected_id_churn_report_keys")
    if not set(churn) <= set(keys):
        raise ValueError("id-churn report keys must also be declared changed report keys")
    if set(churn) & _VERIFIED_ELSEWHERE_KEYS:
        raise ValueError("keys verified by dedicated rules cannot be declared as id-churn keys")
    rekey = raw["allow_snapshot_receipt_rekey"]
    if type(rekey) is not bool:
        raise ValueError("declaration allow_snapshot_receipt_rekey must be a boolean")
    issue = raw["tracking_issue"]
    if type(issue) is not int or issue <= 0:
        raise ValueError("declaration tracking_issue must be a positive integer")
    return Declaration(
        source_sha256=sha,
        report_shape=shape,
        baseline_snapshot_id=_text(raw["baseline_snapshot_id"], "baseline_snapshot_id"),
        candidate_snapshot_id=_text(raw["candidate_snapshot_id"], "candidate_snapshot_id"),
        expected_new_host_ids=hosts,
        expected_new_frame_host_ids=frames,
        expected_unhosted_reason_changes=tuple(changes),
        expected_changed_report_keys=keys,
        expected_id_churn_report_keys=churn,
        allow_snapshot_receipt_rekey=rekey,
        tracking_issue=issue,
    )


def parse_declarations(raw: object) -> tuple[Declaration, ...]:
    if not isinstance(raw, Mapping) or set(raw) != {"schema", "declarations"}:
        raise ValueError("declaration file must carry exactly schema and declarations")
    if raw["schema"] != DECLARATION_SCHEMA:
        raise ValueError("unsupported declaration schema")
    if not isinstance(raw["declarations"], list):
        raise ValueError("declarations must be a list")
    result = tuple(parse_declaration(item) for item in raw["declarations"])
    events = [
        (d.source_sha256, d.baseline_snapshot_id, d.candidate_snapshot_id) for d in result
    ]
    if len(set(events)) != len(events):
        raise ValueError("declared source events must be unique")
    return result


def load_declarations(path: Path | None = None) -> tuple[Declaration, ...]:
    """Load committed declarations.  A missing file means strict-only."""
    target = DEFAULT_DECLARATIONS_PATH if path is None else Path(path)
    if not target.exists():
        return ()
    return parse_declarations(json.loads(target.read_text(encoding="utf-8")))


def as_ledger_report(report: Mapping[str, Any]) -> Mapping[str, Any]:
    """View a stage-tool report in the ledger's shape without altering it.

    ``diag_gptmax_source_authority_stages`` and
    ``diag_opening_wall_face_preservation`` serialize the same authority views
    under different keys.  Only keys that are absent are filled in, and only
    from the identically-named authority view.
    """
    if not isinstance(report, Mapping):
        raise ValueError("source report must be an object")
    view = dict(report)
    if "host_frames" not in view and "host_frame_traces" in view:
        view["host_frames"] = report["host_frame_traces"]
    if "source_owned_wall_scope_results" not in view and "source_owned_wall_scopes" in view:
        view["source_owned_wall_scope_results"] = report["source_owned_wall_scopes"]
    return view


def _index(rows: object, name: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError(f"{name} must be a list")
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        identity = row.get("opening_identity_id") if isinstance(row, Mapping) else None
        if type(identity) is not str or not identity or identity in result:
            raise ValueError(f"{name} has missing or repeated physical identities")
        result[identity] = row
    return result


def _matching(
    declarations: Sequence[Declaration],
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
) -> Declaration | None:
    sha = baseline.get("source_sha256")
    matches = [
        d
        for d in declarations
        if d.source_sha256 == sha
        and candidate.get("source_sha256") == sha
        and d.baseline_snapshot_id == baseline.get("snapshot_id")
        and d.candidate_snapshot_id == candidate.get("snapshot_id")
    ]
    if len(matches) > 1:
        raise ValueError("ambiguous declared additive source events")
    return matches[0] if matches else None


def _wall_records(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    walls: dict[str, Mapping[str, Any]] = {}
    for scope in report.get("source_owned_wall_scope_results") or ():
        for record in scope.get("records") or ():
            walls[record["wall_candidate_id"]] = record
    return walls


def _wall_physical_key(record: Mapping[str, Any]) -> tuple[str, frozenset[str], str]:
    try:
        identity = record["physical_identity"]
        return (
            str(identity["candidate_identity_id"]),
            frozenset(identity["source_primitive_ids"]),
            json.dumps(identity["path_fingerprint"], sort_keys=True),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("declared additive retention refused: malformed W4 wall record") from exc


# Source geometry is compared in PDF points.  Tolerance is far below the shortest
# real terminal fragment that additive source has been seen to destroy (0.12 pt).
COVERAGE_TOLERANCE_PT = 1e-3


def _fragment_segments(record: Mapping[str, Any]) -> list[tuple[float, float, float, float]]:
    try:
        segments = [
            tuple(float(v) for v in fragment["geometry"])
            for fragment in record["source_edge_fragments"]
        ]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("declared additive retention refused: malformed W4 source fragments") from exc
    if not segments or any(len(segment) != 4 for segment in segments):
        raise ValueError("declared additive retention refused: malformed W4 source fragments")
    return segments


def _segment_covered(
    segment: tuple[float, float, float, float],
    others: Sequence[tuple[float, float, float, float]],
) -> bool:
    """True when ``segment`` lies entirely on the union of collinear ``others``."""
    import math

    x1, y1, x2, y2 = segment
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= COVERAGE_TOLERANCE_PT:
        return False  # a degenerate source fragment proves nothing
    ux, uy = (x2 - x1) / length, (y2 - y1) / length
    intervals: list[tuple[float, float]] = []
    for a1, b1, a2, b2 in others:
        off1 = abs((a1 - x1) * uy - (b1 - y1) * ux)
        off2 = abs((a2 - x1) * uy - (b2 - y1) * ux)
        if off1 > COVERAGE_TOLERANCE_PT or off2 > COVERAGE_TOLERANCE_PT:
            continue  # not on the same physical line
        t1 = (a1 - x1) * ux + (b1 - y1) * uy
        t2 = (a2 - x1) * ux + (b2 - y1) * uy
        low, high = min(t1, t2), max(t1, t2)
        if high < -COVERAGE_TOLERANCE_PT or low > length + COVERAGE_TOLERANCE_PT:
            continue
        intervals.append((max(low, 0.0), min(high, length)))
    reached = 0.0
    for low, high in sorted(intervals):
        if low > reached + COVERAGE_TOLERANCE_PT:
            return False
        reached = max(reached, high)
    return reached >= length - COVERAGE_TOLERANCE_PT


def _covers(
    successor: Mapping[str, Any], original: Mapping[str, Any]
) -> bool:
    """Every original source fragment lies on the successor's source fragments."""
    successor_segments = _fragment_segments(successor)
    return all(_segment_covered(seg, successor_segments) for seg in _fragment_segments(original))


def _verify_wall_scope_metadata(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> None:
    """Scope-level W4 fields (status, completeness, equivalence, boundary, ...) stay equal.

    Only snapshot-scoped ids may move and source observation lists may only grow;
    anything else (an equivalence group, a boundary evaluation, a completeness
    flag) is a change to what the W4 scope *claims* and is refused.
    """
    def scopes(report: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
        result: dict[str, Mapping[str, Any]] = {}
        for scope in report.get("source_owned_wall_scope_results") or ():
            scope_id = scope.get("decision_scope_id") if isinstance(scope, Mapping) else None
            if type(scope_id) is not str or not scope_id or scope_id in result:
                raise ValueError("declared additive retention refused: malformed W4 scope identity")
            result[scope_id] = scope
        return result

    old, new = scopes(baseline), scopes(candidate)
    if set(old) != set(new):
        raise ValueError("declared additive retention refused: W4 scope universe changed")
    for scope_id in sorted(old):
        before = {k: v for k, v in old[scope_id].items() if k != "records"}
        after = {k: v for k, v in new[scope_id].items() if k != "records"}
        if not additive_observation_inventory_equal(before, after):
            differing = sorted(
                k
                for k in set(before) | set(after)
                if not additive_observation_inventory_equal({k: before.get(k)}, {k: after.get(k)})
            )
            raise ValueError(
                "declared additive retention refused: W4 scope metadata changed beyond snapshot ids and added "
                f"source observations: {scope_id}: " + ", ".join(differing)
            )


def w4_delta_explained_by_source_delta(
    baseline: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, int]:
    """Refuse W4 changes that conserve less than all original source geometry.

    * a wall id present in both keeps its candidate identity, source primitive
      ancestry and physical path, and its source fragments cover exactly the same
      physical line (it may only gain an interior split node);
    * every wall id that disappears has exactly one successor on the same source
      primitives, and that successor's source fragments cover **every** original
      source fragment, terminal endpoints included -- a successor that merely
      shares primitive ids but lost a terminal tail (e.g. snap-collapsed at a new
      crossing) is refused, as is any shifted endpoint or diagonal;
    * every other new wall is built from at least one source primitive no baseline
      wall used.
    Ambiguity (several walls on the same primitives) is refused, never elected.
    """
    old, new = _wall_records(baseline), _wall_records(candidate)
    retained_changed = sorted(
        wall_id
        for wall_id in set(old) & set(new)
        if _wall_physical_key(old[wall_id]) != _wall_physical_key(new[wall_id])
    )
    if retained_changed:
        raise ValueError(
            "declared additive retention refused: retained W4 wall changed identity, ancestry or path: "
            + ", ".join(retained_changed[:5])
        )
    not_conserved = sorted(
        wall_id
        for wall_id in set(old) & set(new)
        if not (_covers(new[wall_id], old[wall_id]) and _covers(old[wall_id], new[wall_id]))
    )
    if not_conserved:
        raise ValueError(
            "declared additive retention refused: retained W4 wall no longer covers exactly its original source geometry: "
            + ", ".join(not_conserved[:5])
        )
    lost = sorted(set(old) - set(new))
    gained = sorted(set(new) - set(old))
    by_ancestry_lost: dict[frozenset[str], list[str]] = {}
    by_ancestry_gained: dict[frozenset[str], list[str]] = {}
    for wall_id in lost:
        by_ancestry_lost.setdefault(_wall_physical_key(old[wall_id])[1], []).append(wall_id)
    for wall_id in gained:
        by_ancestry_gained.setdefault(_wall_physical_key(new[wall_id])[1], []).append(wall_id)
    for ancestry, lost_ids in by_ancestry_lost.items():
        successors = by_ancestry_gained.get(ancestry, [])
        if not successors:
            raise ValueError(
                "declared additive retention refused: W4 wall disappeared without a successor on its source primitives: "
                + lost_ids[0]
            )
        if len(lost_ids) != 1 or len(successors) != 1:
            raise ValueError(
                "declared additive retention refused: ambiguous W4 successors on the same source primitives: "
                + ", ".join(sorted(lost_ids + successors)[:4])
            )
        if not _covers(new[successors[0]], old[lost_ids[0]]):
            raise ValueError(
                "declared additive retention refused: W4 successor does not cover the original source geometry "
                f"(terminal or path lost): {lost_ids[0]} -> {successors[0]}"
            )
    baseline_primitives = set().union(*(_wall_physical_key(r)[1] for r in old.values())) if old else set()
    unexplained = sorted(
        wall_id
        for ancestry, rows in by_ancestry_gained.items()
        if ancestry not in by_ancestry_lost
        for wall_id in rows
        if not (ancestry - baseline_primitives)
    )
    if unexplained:
        raise ValueError(
            "declared additive retention refused: new W4 wall is not built from any new source primitive: "
            + ", ".join(unexplained[:5])
        )
    # Record-level conservation (above) names the exact wall that lost geometry;
    # scope-level claims (equivalence groups, boundary evaluation, completeness)
    # are checked after it and must be equal modulo snapshot ids / added observations.
    _verify_wall_scope_metadata(baseline, candidate)
    return {
        "retained": len(set(old) & set(new)),
        "lost_with_covering_successor": len(lost),
        "gained_from_new_source": len(gained) - len(lost),
    }


def _verify_canonical_openings(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    old_hosted: set[str],
    gained: set[str],
    declared_frames: set[str],
    allow_rekey: bool,
    bindings: Mapping[str, Mapping[str, Any]],
    frames: Mapping[str, Mapping[str, Any]],
) -> None:
    """Canonical opening records change only where the verified host rows change."""
    try:
        old = {row["physical_opening_id"]: row for row in baseline["canonical_openings"]}
        new = {row["physical_opening_id"]: row for row in candidate["canonical_openings"]}
    except (KeyError, TypeError) as exc:
        raise ValueError("declared additive retention refused: malformed canonical_openings") from exc
    if set(old) != set(new):
        raise ValueError("declared additive retention refused: canonical opening universe changed")
    host_fields = {"host_wall_id", "host_binding_record_id", "host_frame_record_id"}
    always = {"snapshot_id", "evidence_ids"} | host_fields
    for opening_id in sorted(old):
        before, after = old[opening_id], new[opening_id]
        changed = {key for key in set(before) | set(after) if before.get(key) != after.get(key)}
        if changed - always:
            raise ValueError(
                f"declared additive retention refused: canonical opening changed beyond host receipts: "
                f"{opening_id}: " + ", ".join(sorted(changed - always))
            )
        binding = bindings.get(opening_id, {})
        frame = frames.get(opening_id, {})
        # The canonical record must agree with the (verified) host and frame rows.
        if (
            (after.get("host_wall_id") or None) != (binding.get("host_wall_id") or None)
            or (after.get("host_binding_record_id") or None) != (binding.get("record_id") or None)
            or (after.get("host_frame_record_id") or None) != (frame.get("record_id") or None)
        ):
            raise ValueError(
                f"declared additive retention refused: canonical opening disagrees with host/frame rows: {opening_id}"
            )
        if opening_id in gained:
            net = {"opening_host_binding_v3": 1, "opening_host_frame_v2": int(opening_id in declared_frames)}
            allowed_changes = {"snapshot_id", "evidence_ids", "host_wall_id", "host_binding_record_id"}
            if opening_id in declared_frames:
                allowed_changes.add("host_frame_record_id")
        elif opening_id in old_hosted:
            net = {}
            allowed_changes = {"snapshot_id", "evidence_ids"} | (host_fields if allow_rekey else set())
        else:
            net = {}
            allowed_changes = {"snapshot_id"}
        if changed - allowed_changes:
            raise ValueError(
                f"declared additive retention refused: canonical opening field changed without a verified cause: "
                f"{opening_id}: " + ", ".join(sorted(changed - allowed_changes))
            )
        if "evidence_ids" in changed and not evidence_swap_matches(
            before.get("evidence_ids"), after.get("evidence_ids"), net_additions=net
        ):
            raise ValueError(
                f"declared additive retention refused: canonical opening evidence changed beyond receipts: {opening_id}"
            )


def _reason_codes(
    value: object,
    name: str,
    *,
    require_unique: bool = False,
) -> set[str]:
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"declared additive retention refused: {name} must be a list")
    if any(type(code) is not str or not code or code != code.strip() for code in value):
        raise ValueError(f"declared additive retention refused: {name} contains malformed reasons")
    if require_unique and len(set(value)) != len(value):
        raise ValueError(f"declared additive retention refused: {name} contains duplicate reasons")
    # Individual producer rows may repeat a typed reason while aggregating
    # several sub-authorities.  Aggregate composition reasons are required to
    # be unique; row multiplicity carries no extra semantic authority here.
    return set(value)


def _verify_composition_reason_codes(
    baseline: object,
    candidate: object,
    *,
    affected_opening_ids: set[str],
    old_bindings: Mapping[str, Mapping[str, Any]],
    new_bindings: Mapping[str, Mapping[str, Any]],
    old_frames: Mapping[str, Mapping[str, Any]],
    new_frames: Mapping[str, Mapping[str, Any]],
) -> None:
    """Aggregate reasons may move only with independently verified opening rows.

    This closes the final blind top-level key in a declared source-addition
    event.  The declaration cannot invent a semantic reason or silently remove
    an unrelated reason: every aggregate addition/removal must be witnessed by
    the before/after binding or frame rows of an opening whose physical change
    was already verified by this approval.
    """
    before = _reason_codes(
        baseline, "baseline composition_reason_codes", require_unique=True
    )
    after = _reason_codes(
        candidate, "candidate composition_reason_codes", require_unique=True
    )
    added = after - before
    removed = before - after
    if not added and not removed:
        return
    if not affected_opening_ids:
        raise ValueError(
            "declared additive retention refused: composition reasons changed without "
            "a verified opening authority change"
        )

    before_affected: set[str] = set()
    after_affected: set[str] = set()
    after_all_rows: set[str] = set()
    for opening_id in affected_opening_ids:
        if opening_id not in old_bindings or opening_id not in new_bindings:
            raise ValueError(
                "declared additive retention refused: composition reason owner is absent "
                f"from opening bindings: {opening_id}"
            )
        if opening_id not in old_frames or opening_id not in new_frames:
            raise ValueError(
                "declared additive retention refused: composition reason owner is absent "
                f"from frame rows: {opening_id}"
            )
        before_affected |= _reason_codes(
            old_bindings[opening_id].get("reason_codes") or (),
            f"baseline binding reasons for {opening_id}",
        )
        before_affected |= _reason_codes(
            old_frames[opening_id].get("reason_codes") or (),
            f"baseline frame reasons for {opening_id}",
        )
        after_affected |= _reason_codes(
            new_bindings[opening_id].get("reason_codes") or (),
            f"candidate binding reasons for {opening_id}",
        )
        after_affected |= _reason_codes(
            new_frames[opening_id].get("reason_codes") or (),
            f"candidate frame reasons for {opening_id}",
        )
    for rows, label in ((new_bindings, "candidate binding"), (new_frames, "candidate frame")):
        for opening_id, row in rows.items():
            after_all_rows |= _reason_codes(
                row.get("reason_codes") or (),
                f"{label} reasons for {opening_id}",
            )

    unsupported_added = sorted(added - after_affected)
    if unsupported_added:
        raise ValueError(
            "declared additive retention refused: composition reasons added without "
            "verified opening-row authority: " + ", ".join(unsupported_added)
        )
    unsupported_removed = sorted(removed - before_affected)
    if unsupported_removed:
        raise ValueError(
            "declared additive retention refused: composition reasons removed without "
            "verified opening-row authority: " + ", ".join(unsupported_removed)
        )
    still_live = sorted(removed & after_all_rows)
    if still_live:
        raise ValueError(
            "declared additive retention refused: aggregate composition reason was "
            "removed while still present on a candidate opening row: "
            + ", ".join(still_live)
        )


def _verify_summary(
    baseline: Any,
    candidate: Any,
    *,
    new_hosts: int,
    new_frames: int,
) -> None:
    """Counts move only by the declared new hosts / frames; every other entry is equal."""
    if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping) or set(baseline) != set(candidate):
        raise ValueError("declared additive retention refused: summary shape changed")
    for key in sorted(baseline):
        before, after = baseline[key], candidate[key]
        if key in _HOST_COUNT_SUMMARY_KEYS or key in _FRAME_COUNT_SUMMARY_KEYS:
            expected = new_hosts if key in _HOST_COUNT_SUMMARY_KEYS else new_frames
            if type(before) is not int or type(after) is not int or after != before + expected:
                raise ValueError(
                    f"declared additive retention refused: summary {key} is not {expected} above the baseline"
                )
        elif before != after:
            raise ValueError(f"declared additive retention refused: summary {key} changed")



def approve_declared_additive_rekeys(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    declarations: Sequence[Declaration] | None = None,
    *,
    normalize: Callable[[Any], Any] | None = None,
) -> dict[str, Any] | None:
    """Return an approval for a declared event, ``None`` when none is declared.

    When a declaration matches this exact (SHA, baseline snapshot, candidate
    snapshot) event but the reports violate it, a ``ValueError`` is raised: a
    declared event is never silently downgraded to the strict path.

    Every top-level report key that the declaration does not list as expected to
    change must be equal between the two reports (after the caller's optional
    ``normalize``, e.g. an order-insensitive form of reason-code lists), so a
    declared event can never hide a change to an unrelated part of the report.
    """
    if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
        raise ValueError("source reports must be objects")
    base = as_ledger_report(baseline)
    cand = as_ledger_report(candidate)
    active = load_declarations() if declarations is None else tuple(declarations)
    declaration = _matching(active, base, cand)
    if declaration is None:
        return None

    # ``stage_report`` carries the frame geometry array and every frame is
    # geometry-verified.  ``face_report`` (diag_opening_wall_face_preservation)
    # never carries it: frame membership, receipts and reasons are verified but
    # frame *geometry* is explicitly not (``frame_geometry_verified: False``).
    # The declared shape must match the reports, so a tool that silently drops
    # the evidence cannot downgrade a stage_report verification.
    ledger = compare_source_host_rekeys(
        base, cand, frame_evidence=declaration.report_shape == "stage_report"
    )
    rows = ledger["source_comparison_rows"]
    refused = sorted(
        row["physical_opening_id"]
        for row in rows
        if row["source_comparison_status"] not in ACCEPTED_LEDGER_STATES
    )
    if refused:
        raise ValueError(
            "declared additive retention refused: original source proof changed or lost: "
            + ", ".join(refused)
        )

    rekeyed_rows = [
        row["physical_opening_id"]
        for row in rows
        if row["source_comparison_status"] == "UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY"
    ]
    if rekeyed_rows and not declaration.allow_snapshot_receipt_rekey:
        # Default stance: previously authenticated receipts must be retained
        # exactly.  Accepting a rekey of snapshot-scoped receipts is a separate,
        # explicit decision that the declaration has to make.
        raise ValueError(
            "declared additive retention refused: prior receipts were rekeyed but the declaration does not "
            "allow_snapshot_receipt_rekey: " + ", ".join(sorted(rekeyed_rows)[:5])
        )

    old = _index(base.get("opening_bindings"), "baseline opening_bindings")
    new = _index(cand.get("opening_bindings"), "candidate opening_bindings")
    if set(old) != set(new):
        raise ValueError("declared additive retention refused: physical opening universe changed")
    old_frames = _index(base.get("host_frames"), "baseline host_frames")
    new_frames = _index(cand.get("host_frames"), "candidate host_frames")

    old_hosted = {key for key, row in old.items() if row.get("host_wall_id")}
    new_hosted = {key for key, row in new.items() if row.get("host_wall_id")}
    if old_hosted - new_hosted:
        raise ValueError("declared additive retention refused: a prior host was lost")
    for key in sorted(old_hosted):
        for name, before_row, after_row in (
            ("binding", old[key], new[key]),
            ("frame", old_frames[key], new_frames[key]),
        ):
            stable_before = {k: v for k, v in before_row.items() if k not in _SNAPSHOT_SCOPED_FIELDS}
            stable_after = {k: v for k, v in after_row.items() if k not in _SNAPSHOT_SCOPED_FIELDS}
            if stable_before != stable_after:
                raise ValueError(
                    f"declared additive retention refused: retained host {name} changed beyond receipt addresses: {key}"
                )
    declared_hosts = set(declaration.expected_new_host_ids)
    gained = new_hosted - old_hosted
    if gained - declared_hosts:
        raise ValueError(
            "declared additive retention refused: undeclared new hosts: "
            + ", ".join(sorted(gained - declared_hosts))
        )
    if not declared_hosts <= set(old):
        raise ValueError("declared additive retention refused: declared host is not an existing physical opening")
    if not declared_hosts <= new_hosted:
        raise ValueError("declared additive retention refused: declared host is not hosted")
    for key in sorted(declared_hosts & gained):
        row = new[key]
        members = row.get("member_wall_candidate_ids")
        if (
            row.get("status") != "corroborated"
            or not row.get("record_id")
            or not isinstance(members, list)
            or not members
        ):
            raise ValueError(
                f"declared additive retention refused: declared host lacks a corroborated receipt: {key}"
            )
        # The opening itself must be the same source object; only its host is new.
        for field in ("page_id", "representative_observation_id"):
            if old[key].get(field) != row.get(field):
                raise ValueError(
                    f"declared additive retention refused: declared host {field} changed: {key}"
                )
    framed_before = {key for key, row in old_frames.items() if row.get("record_id")}
    framed_after = {key for key, row in new_frames.items() if row.get("record_id")}
    declared_frames = set(declaration.expected_new_frame_host_ids)
    if (framed_after - framed_before) - declared_frames:
        raise ValueError(
            "declared additive retention refused: undeclared new frames: "
            + ", ".join(sorted((framed_after - framed_before) - declared_frames))
        )
    if declared_frames - framed_after or declared_frames & framed_before:
        raise ValueError("declared additive retention refused: declared new frame did not occur")

    declared_reasons = {c.opening_identity_id: c for c in declaration.expected_unhosted_reason_changes}
    consumed: set[str] = set()
    for key in sorted(set(old) - old_hosted - gained):
        before_row, after_row = old[key], new[key]
        for field in _UNHOSTED_FROZEN_FIELDS:
            if before_row.get(field) != after_row.get(field):
                raise ValueError(
                    f"declared additive retention refused: unrelated opening {field} changed: {key}"
                )
        before_frame, after_frame = old_frames[key], new_frames[key]
        for field in ("record_id", "host_wall_id", "reason_codes"):
            if before_frame.get(field) != after_frame.get(field):
                raise ValueError(
                    f"declared additive retention refused: unrelated opening frame {field} changed: {key}"
                )
        before_reasons = tuple(before_row.get("reason_codes") or ())
        after_reasons = tuple(after_row.get("reason_codes") or ())
        if before_reasons != after_reasons:
            change = declared_reasons.get(key)
            if change is None or change.before != before_reasons or change.after != after_reasons:
                raise ValueError(
                    f"declared additive retention refused: undeclared reason change: {key}"
                )
            consumed.add(key)
    unused = sorted(set(declared_reasons) - consumed)
    if unused:
        raise ValueError(
            "declared additive retention refused: declared reason change did not occur: "
            + ", ".join(unused)
        )

    w4_delta = w4_delta_explained_by_source_delta(base, cand)

    norm = normalize if normalize is not None else (lambda value: value)
    changed_keys = set(declaration.expected_changed_report_keys)
    churn_keys = set(declaration.expected_id_churn_report_keys)

    def _differs(key: str) -> bool:
        if (key in baseline) != (key in candidate):
            return True
        if key not in baseline:
            return False
        # Normalize the keyed single-entry view, exactly as a gate's own
        # recursive normalizer sees it (it may act on the key, e.g. sort the
        # value of void_reason_codes or drop a sidecar key).
        return norm({key: baseline[key]}) != norm({key: candidate[key]})

    undeclared_keys = sorted(
        key for key in (set(baseline) | set(candidate)) - changed_keys if _differs(key)
    )
    if undeclared_keys:
        raise ValueError(
            "declared additive retention refused: undeclared report keys changed: "
            + ", ".join(undeclared_keys)
        )

    # Dedicated verification of the keys that carry quantities / host state: the
    # declaration acknowledges them, it never excuses them.
    if "canonical_openings" in baseline or "canonical_openings" in candidate:
        _verify_canonical_openings(
            baseline,
            candidate,
            old_hosted=old_hosted,
            gained=gained,
            declared_frames=declared_frames,
            allow_rekey=declaration.allow_snapshot_receipt_rekey,
            bindings=new,
            frames=new_frames,
        )
    if "summary" in baseline or "summary" in candidate:
        _verify_summary(
            baseline.get("summary"),
            candidate.get("summary"),
            new_hosts=len(gained),
            new_frames=len(framed_after - framed_before),
        )
    if "semantic_inventory" in baseline or "semantic_inventory" in candidate:
        if not additive_observation_inventory_equal(
            baseline.get("semantic_inventory"), candidate.get("semantic_inventory")
        ):
            raise ValueError(
                "declared additive retention refused: semantic inventory changed beyond added source observations"
            )
    if "composition_reason_codes" in baseline or "composition_reason_codes" in candidate:
        _verify_composition_reason_codes(
            baseline.get("composition_reason_codes"),
            candidate.get("composition_reason_codes"),
            affected_opening_ids=set(gained) | set(consumed),
            old_bindings=old,
            new_bindings=new,
            old_frames=old_frames,
            new_frames=new_frames,
        )
    for key in sorted(churn_keys):
        if (key in baseline) != (key in candidate) or not equal_modulo_snapshot_scoped_ids(
            norm({key: baseline.get(key)}), norm({key: candidate.get(key)})
        ):
            raise ValueError(
                f"declared additive retention refused: report key {key} changed beyond snapshot-scoped ids"
            )
    blind_keys = sorted(
        key
        for key in changed_keys
        if key not in churn_keys and key not in _VERIFIED_ELSEWHERE_KEYS and _differs(key)
    )
    unchanged_declared_keys = sorted(
        key
        for key in changed_keys
        if key in baseline and key in candidate and not _differs(key)
    )

    rekeyed = sorted(
        row["physical_opening_id"]
        for row in rows
        if row["source_comparison_status"] == "UNCHANGED_W4_AND_FRAME_SOURCE_WITH_RECEIPT_REKEY"
    )
    exact = sorted(
        row["physical_opening_id"]
        for row in rows
        if row["source_comparison_status"] == "EXACT_PRIOR_RECEIPTS_RETAINED"
    )
    return {
        "declaration_applied": True,
        "tracking_issue": declaration.tracking_issue,
        "report_shape": declaration.report_shape,
        "snapshot_receipt_rekey_allowed": declaration.allow_snapshot_receipt_rekey,
        "frame_geometry_verified": ledger["frame_geometry_verified"],
        "source_sha256": declaration.source_sha256,
        "baseline_snapshot_id": declaration.baseline_snapshot_id,
        "candidate_snapshot_id": declaration.candidate_snapshot_id,
        "exact_retained_host_ids": exact,
        "rekeyed_host_ids": rekeyed,
        "declared_new_host_ids": sorted(declared_hosts),
        "declared_new_frame_host_ids": sorted(declared_frames),
        "accepted_unhosted_reason_change_ids": sorted(consumed),
        "declared_report_keys_without_change": unchanged_declared_keys,
        # Acknowledged semantic changes that no code verified: reviewers read these.
        "unverified_changed_report_keys": blind_keys,
        "w4_wall_delta": w4_delta,
        # Every row whose serialized binding may differ without failing retention.
        "tolerated_binding_change_ids": sorted(set(rekeyed) | declared_hosts | consumed),
        "official_host_receipt_identity_acceptance": False,
        "host_publication_allowed": False,
        "opening_count_or_metric_publication_allowed": False,
        "benchmark_accuracy": None,
    }


def event_key(baseline: Mapping[str, Any], candidate: Mapping[str, Any]) -> dict[str, Any]:
    """The exact fields a declaration must bind, for error messages."""
    return {
        "source_sha256": baseline.get("source_sha256"),
        "baseline_snapshot_id": baseline.get("snapshot_id"),
        "candidate_snapshot_id": candidate.get("snapshot_id"),
    }


def declared_event_approved(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    declarations: Sequence[Declaration] | None = None,
    *,
    normalize: Callable[[Any], Any] | None = None,
    explain: bool = True,
) -> bool:
    """For inline gate assertions: ``strict_equal or declared_event_approved``.

    ``True`` only when this exact (SHA, baseline snapshot, candidate snapshot)
    event is declared and fully proven.  ``False`` when nothing is declared for
    it (the strict assertion then decides); the event key is printed to stderr
    so a reviewer can see exactly what a declaration would have to bind.  A
    declared but violated event raises, so it can never be mistaken for the
    undeclared case.
    """
    approval = approve_declared_additive_rekeys(
        baseline, candidate, declarations, normalize=normalize
    )
    if approval is None and explain:
        import sys

        print(
            "UNDECLARED additive-source event (no matching declaration): "
            + json.dumps(event_key(baseline, candidate), sort_keys=True),
            file=sys.stderr,
        )
    return approval is not None


def assert_unchanged_or_declared(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    normalize: Callable[[Any], Any] | None = None,
    message: str = "original source authority changed",
) -> None:
    """Strict equality, or exactly one declared and proven additive-source event."""
    norm = normalize if normalize is not None else (lambda value: value)
    if norm(baseline) == norm(candidate):
        return
    if declared_event_approved(baseline, candidate, normalize=normalize):
        return
    raise AssertionError(message)


# Evidence ids that are hashes of the SourceVisibility snapshot (one per quantity
# at most): they legitimately rekey when genuine source observations are added.
SNAPSHOT_SCOPED_EVIDENCE_PREFIXES = ("opening_host_binding_v3_", "opening_host_frame_v2_")
SEALED_QUANTITY_REKEYABLE_FIELDS = frozenset({"evidence_ids", "trace_evidence_ids", "fingerprint"})


def sealed_quantities_changed_only_by_snapshot_receipts(
    old_quantities: Sequence[Mapping[str, Any]],
    new_quantities: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Prove re-sealing changed prior rows only by snapshot-scoped receipts.

    Every previously sealed quantity must still exist (same ``quantity_id``) with
    every field equal except ``evidence_ids``, ``trace_evidence_ids`` and its
    own ``fingerprint``.  Within the evidence sets the symmetric difference may
    contain only snapshot-scoped host-binding / host-frame receipt ids, and at
    most one of each kind may be swapped per row.  Returns the row counts.
    """
    old = {row["quantity_id"]: row for row in old_quantities}
    new = {row["quantity_id"]: row for row in new_quantities}
    if len(old) != len(old_quantities) or len(new) != len(new_quantities):
        raise ValueError("sealed quantity ids must be unique")
    if not set(old) <= set(new):
        raise ValueError("a previously sealed quantity is missing: " + ", ".join(sorted(set(old) - set(new))))
    rekeyed = 0
    for quantity_id in sorted(old):
        before, after = old[quantity_id], new[quantity_id]
        changed_fields = {
            key for key in set(before) | set(after) if before.get(key) != after.get(key)
        }
        if changed_fields - SEALED_QUANTITY_REKEYABLE_FIELDS:
            raise ValueError(
                f"sealed quantity changed beyond snapshot receipts: {quantity_id}: "
                + ", ".join(sorted(changed_fields - SEALED_QUANTITY_REKEYABLE_FIELDS))
            )
        for field in ("evidence_ids", "trace_evidence_ids"):
            old_ids, new_ids = set(before.get(field) or ()), set(after.get(field) or ())
            removed, added = old_ids - new_ids, new_ids - old_ids
            for prefix in SNAPSHOT_SCOPED_EVIDENCE_PREFIXES:
                gone = [i for i in removed if i.startswith(prefix)]
                new_one = [i for i in added if i.startswith(prefix)]
                if len(gone) != len(new_one) or len(gone) > 1:
                    raise ValueError(
                        f"sealed quantity {field} swapped other than one {prefix}* receipt: {quantity_id}"
                    )
            other = [
                i
                for i in removed | added
                if not i.startswith(SNAPSHOT_SCOPED_EVIDENCE_PREFIXES)
            ]
            if other:
                raise ValueError(
                    f"sealed quantity {field} changed beyond snapshot receipts: {quantity_id}: "
                    + ", ".join(sorted(other)[:3])
                )
        if changed_fields:
            rekeyed += 1
    return {"prior_rows": len(old), "rekeyed_rows": rekeyed, "new_rows": len(set(new) - set(old))}


def suggest_declaration(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    report_shape: str,
    tracking_issue: int,
    allow_snapshot_receipt_rekey: bool,
    normalize: Callable[[Any], Any] | None = None,
) -> dict[str, Any]:
    """Derive the declaration that describes this exact report pair (a starting point).

    This only *describes* the differences it sees; it grants nothing.  The
    approval then verifies them, and a human decides whether the described event
    is acceptable.  Keys that differ only by snapshot-scoped ids and ordering are
    proposed as ``expected_id_churn_report_keys``; the rest are proposed as
    changed (and show up in ``unverified_changed_report_keys`` unless a dedicated
    rule verifies them).
    """
    base = as_ledger_report(baseline)
    cand = as_ledger_report(candidate)
    norm = normalize if normalize is not None else (lambda value: value)
    old = _index(base.get("opening_bindings"), "baseline opening_bindings")
    new = _index(cand.get("opening_bindings"), "candidate opening_bindings")
    gained = sorted(k for k, row in new.items() if row.get("host_wall_id") and not old.get(k, {}).get("host_wall_id"))
    old_frames = _index(base.get("host_frames"), "baseline host_frames")
    new_frames = _index(cand.get("host_frames"), "candidate host_frames")
    new_frame_hosts = sorted(
        k for k in gained if new_frames.get(k, {}).get("record_id") and not old_frames.get(k, {}).get("record_id")
    )
    reason_changes = [
        {
            "opening_identity_id": key,
            "before": list(old[key].get("reason_codes") or ()),
            "after": list(new[key].get("reason_codes") or ()),
        }
        for key in sorted(old)
        if key in new
        and key not in gained
        and not old[key].get("host_wall_id")
        and tuple(old[key].get("reason_codes") or ()) != tuple(new[key].get("reason_codes") or ())
    ]
    changed = sorted(
        key
        for key in set(baseline) | set(candidate)
        if (key in baseline) != (key in candidate)
        or norm({key: baseline[key]}) != norm({key: candidate[key]})
    )
    churn = sorted(
        key
        for key in changed
        if key not in _VERIFIED_ELSEWHERE_KEYS
        and key in baseline
        and key in candidate
        and equal_modulo_snapshot_scoped_ids(norm({key: baseline[key]}), norm({key: candidate[key]}))
    )
    return {
        "source_sha256": baseline.get("source_sha256"),
        "report_shape": report_shape,
        "baseline_snapshot_id": baseline.get("snapshot_id"),
        "candidate_snapshot_id": candidate.get("snapshot_id"),
        "expected_new_host_ids": gained,
        "expected_new_frame_host_ids": new_frame_hosts,
        "expected_unhosted_reason_changes": reason_changes,
        "expected_changed_report_keys": changed,
        "expected_id_churn_report_keys": churn,
        "allow_snapshot_receipt_rekey": bool(allow_snapshot_receipt_rekey),
        "tracking_issue": tracking_issue,
    }



@contextmanager
def strict_or_declared(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    *,
    normalize: Callable[[Any], Any] | None = None,
) -> Iterator[None]:
    """Wrap a gate's own strict assertions.

    The block runs unchanged.  If one of its ``assert`` statements fails, the
    failure is excused only when this exact event is declared and fully proven;
    otherwise the original ``AssertionError`` propagates.  A declared but
    violated event raises ``ValueError`` instead of being excused.
    """
    try:
        yield
    except AssertionError:
        if not declared_event_approved(baseline, candidate, normalize=normalize):
            raise


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--suggest",
        choices=REPORT_SHAPES,
        help="print a declaration describing this report pair (a starting point; grants nothing)",
    )
    parser.add_argument("--tracking-issue", type=int, default=0)
    parser.add_argument("--allow-snapshot-receipt-rekey", action="store_true")
    args = parser.parse_args(argv)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
    if args.suggest:
        suggestion = suggest_declaration(
            baseline,
            candidate,
            report_shape=args.suggest,
            tracking_issue=args.tracking_issue,
            allow_snapshot_receipt_rekey=args.allow_snapshot_receipt_rekey,
        )
        text = json.dumps(suggestion, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(text, encoding="utf-8")
        print(text, end="")
        return 0
    try:
        approval = approve_declared_additive_rekeys(baseline, candidate)
    except ValueError as exc:
        print(f"DECLARED EVENT REFUSED: {exc}")
        return 1
    if approval is None:
        print("NO DECLARATION for this event: " + json.dumps(event_key(baseline, candidate), sort_keys=True))
        return 1
    if args.output:
        args.output.write_text(json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in approval.items() if not isinstance(v, (list, dict))}, sort_keys=True))
    unverified = approval.get("unverified_changed_report_keys") or []
    if unverified:
        print("UNVERIFIED changed report keys (acknowledged, not checked): " + ", ".join(unverified))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
