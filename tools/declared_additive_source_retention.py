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
  geometry / centerline and (when framed) the same source-space frame geometry
  -- only snapshot-scoped receipt addresses and generated split ordinals move;
* no previously hosted opening is lost and no previously framed opening gains a
  different frame;
* the only newly hosted openings are the declared ones, and each is an
  existing, corroborated physical opening with a host receipt;
* every other unhosted opening keeps its status, representative observation,
  members and receipts; its reason codes change only through an exact declared
  ``before -> after`` transition.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from tools.gptmax_source_host_rekey_parity_ledger import compare_source_host_rekeys

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
_DECLARATION_KEYS = frozenset(
    {
        "source_sha256",
        "baseline_snapshot_id",
        "candidate_snapshot_id",
        "expected_new_host_ids",
        "expected_new_frame_host_ids",
        "expected_unhosted_reason_changes",
        "tracking_issue",
    }
)
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
    baseline_snapshot_id: str
    candidate_snapshot_id: str
    expected_new_host_ids: tuple[str, ...]
    expected_new_frame_host_ids: tuple[str, ...]
    expected_unhosted_reason_changes: tuple[ReasonChange, ...]
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
    issue = raw["tracking_issue"]
    if type(issue) is not int or issue <= 0:
        raise ValueError("declaration tracking_issue must be a positive integer")
    return Declaration(
        source_sha256=sha,
        baseline_snapshot_id=_text(raw["baseline_snapshot_id"], "baseline_snapshot_id"),
        candidate_snapshot_id=_text(raw["candidate_snapshot_id"], "candidate_snapshot_id"),
        expected_new_host_ids=hosts,
        expected_new_frame_host_ids=frames,
        expected_unhosted_reason_changes=tuple(changes),
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


def approve_declared_additive_rekeys(
    baseline: Mapping[str, Any],
    candidate: Mapping[str, Any],
    declarations: Sequence[Declaration] | None = None,
) -> dict[str, Any] | None:
    """Return an approval for a declared event, ``None`` when none is declared.

    When a declaration matches this exact (SHA, baseline snapshot, candidate
    snapshot) event but the reports violate it, a ``ValueError`` is raised: a
    declared event is never silently downgraded to the strict path.
    """
    if not isinstance(baseline, Mapping) or not isinstance(candidate, Mapping):
        raise ValueError("source reports must be objects")
    base = as_ledger_report(baseline)
    cand = as_ledger_report(candidate)
    active = load_declarations() if declarations is None else tuple(declarations)
    declaration = _matching(active, base, cand)
    if declaration is None:
        return None

    ledger = compare_source_host_rekeys(base, cand)
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
        "source_sha256": declaration.source_sha256,
        "baseline_snapshot_id": declaration.baseline_snapshot_id,
        "candidate_snapshot_id": declaration.candidate_snapshot_id,
        "exact_retained_host_ids": exact,
        "rekeyed_host_ids": rekeyed,
        "declared_new_host_ids": sorted(declared_hosts),
        "declared_new_frame_host_ids": sorted(declared_frames),
        "accepted_unhosted_reason_change_ids": sorted(consumed),
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
    approval = approve_declared_additive_rekeys(baseline, candidate, declarations)
    if approval is None and explain:
        import sys

        print(
            "UNDECLARED additive-source event (no matching declaration): "
            + json.dumps(event_key(baseline, candidate), sort_keys=True),
            file=sys.stderr,
        )
    return approval is not None


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    candidate = json.loads(args.candidate.read_text(encoding="utf-8"))
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
    print(json.dumps({k: v for k, v in approval.items() if not isinstance(v, list)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
