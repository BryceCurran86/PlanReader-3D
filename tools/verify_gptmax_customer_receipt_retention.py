"""Strict commercial/customer receipt retention for ONE source-proven additive host.

This complements, never replaces, original physical W4/host source gates,
sealed quantity parity, verify_sealed_customer_output, and frozen scoring.
No expected quantities, benchmark truth, or geometry are read or inferred.
"""
from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

RECEIPT_FIELDS = frozenset({
    "host_binding_record_id", "host_frame_record_id",
    "host_wall_id", "snapshot_id",
})
HOST_RECEIPT_PREFIXES = ("opening_host_binding_v3_", "opening_host_frame_v2_")
FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError("customer original-source retention refused: " + message)


def _by(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, Mapping), "non-mapping source/customer record")
        key = row.get(field)
        _require(isinstance(key, str) and bool(key) and key not in result,
                 f"duplicate or invalid {field}")
        result[key] = row
    return result


def _same_except(old: Mapping[str, Any], new: Mapping[str, Any],
                 allowed: frozenset[str], label: str) -> None:
    _require(set(old) == set(new), f"{label}: schema/fields changed")
    for field in old:
        if field not in allowed:
            _require(old[field] == new[field], f"{label}: unsupported {field} change")


def _rewrite_approved_receipts(value: Any, substitutions: Mapping[str, str],
                               *, field: str = "") -> Any:
    """Change only authenticated, specifically recognized receipt fields.

    Unknown nested metadata/content and non-host evidence remain EXACT.
    A string that merely resembles a receipt never authorizes a substitution.
    """
    if isinstance(value, Mapping):
        return {key: _rewrite_approved_receipts(item, substitutions, field=key)
                for key, item in value.items()}
    if isinstance(value, list):
        return [_rewrite_approved_receipts(item, substitutions, field=field)
                for item in value]
    if isinstance(value, str) and (
        field in RECEIPT_FIELDS
        or (field == "evidence_ids" and value.startswith(HOST_RECEIPT_PREFIXES))
    ):
        return substitutions.get(value, value)
    return value


def _notes_provenance(row: Mapping[str, Any]) -> Mapping[str, Any]:
    value = row.get("commercial_projection_provenance")
    _require(isinstance(value, Mapping), "commercial provenance missing")
    notes = row.get("notes")
    _require(isinstance(notes, str), "customer notes missing")
    try:
        parsed = json.loads(notes)
    except (ValueError, TypeError) as exc:
        raise ValueError("customer original-source retention refused: notes not JSON") from exc
    _require(parsed == value, "customer notes disagree with provenance")
    fingerprint = row.get("commercial_projection_fingerprint")
    _require(isinstance(fingerprint, str) and bool(FINGERPRINT.fullmatch(fingerprint)),
             "unsigned or malformed commercial fingerprint")
    return value


def verify_customer_receipt_rekeys(
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    baseline_source: Mapping[str, Any],
    candidate_source: Mapping[str, Any],
    *,
    expected_new_physical_id: str,
    expected_new_quantity_id: str,
) -> dict[str, Any]:
    """Reject any non-receipt change to the seven old customer rows.

    The inputs MUST be fresh sealed/customer runs and matched source reports
    from the SAME original pre-change execution and its proposed revision.
    A historic archived customer run cannot be compared to a different modern
    baseline source snapshot: its old receipt IDs won't match, so it fails.
    """
    sha = baseline_source.get("source_sha256")
    _require(isinstance(sha, str) and len(sha) == 64
             and sha == candidate_source.get("source_sha256"),
             "original source SHA changed")
    _require(baseline_source.get("primitive_safety_cap") ==
             candidate_source.get("primitive_safety_cap") == 20_000,
             "raster safety cap changed")
    old_wall_scopes = baseline_source.get("source_owned_wall_scopes")
    new_wall_scopes = candidate_source.get("source_owned_wall_scopes")
    _require(isinstance(old_wall_scopes, list) and isinstance(new_wall_scopes, list)
             and len(old_wall_scopes) == len(new_wall_scopes),
             "canonical W4 source scopes changed")
    for old_scope, new_scope in zip(old_wall_scopes, new_wall_scopes):
        _require(old_scope.get("records") == new_scope.get("records"),
                 "an original W4 physical wall/path/source edge changed")
        _same_except(old_scope, new_scope, frozenset({"snapshot_id"}), "W4 scope")

    old_snapshot = baseline_source.get("snapshot_id")
    new_snapshot = candidate_source.get("snapshot_id")
    _require(isinstance(old_snapshot, str) and isinstance(new_snapshot, str)
             and old_snapshot != new_snapshot,
             "not a distinct authenticated additive snapshot")

    old_bindings = _by(baseline_source["opening_bindings"], "opening_identity_id")
    new_bindings = _by(candidate_source["opening_bindings"], "opening_identity_id")
    old_frames = _by(baseline_source["host_frame_traces"], "opening_identity_id")
    new_frames = _by(candidate_source["host_frame_traces"], "opening_identity_id")
    _require(set(old_bindings) == set(new_bindings) == set(old_frames) == set(new_frames),
             "original opening/frame universe changed")

    target = expected_new_physical_id
    _require(target in old_bindings and old_bindings[target].get("status") == "abstained",
             "new host not an originally ABSTAINED source opening")
    _require(new_bindings[target].get("status") == "corroborated"
             and new_bindings[target].get("record_id")
             and len(new_bindings[target].get("member_wall_candidate_ids") or ()) == 2,
             "exactly one source-proven new two-flank host required")
    _require(not old_frames[target].get("record_id")
             and not new_frames[target].get("record_id"),
             "supplemental event invented a complete host frame")

    substitutions: dict[str, str] = {old_snapshot: new_snapshot}
    old_host_count = 0
    frame_count = 0
    for opening_id, old in old_bindings.items():
        new = new_bindings[opening_id]
        old_frame, new_frame = old_frames[opening_id], new_frames[opening_id]
        if opening_id == target:
            continue
        if old.get("status") == "corroborated":
            _require(new.get("status") == "corroborated",
                     f"{opening_id} lost an original host")
            _same_except(old, new, frozenset({"record_id", "host_wall_id"}),
                         f"{opening_id} source host")
            for field in ("record_id", "host_wall_id"):
                before, after = old.get(field), new.get(field)
                _require(isinstance(before, str) and bool(before)
                         and isinstance(after, str) and bool(after),
                         f"{opening_id}: host receipt absent")
                substitutions[before] = after
            old_host_count += 1
        else:
            _require(old == new, f"{opening_id}: unhosted source proposition changed")

        if old_frame.get("record_id"):
            _require(new_frame.get("record_id") and
                     old_frame.get("status") == new_frame.get("status") == "corroborated",
                     f"{opening_id}: original positive frame lost")
            _same_except(old_frame, new_frame,
                         frozenset({"record_id", "host_wall_id"}),
                         f"{opening_id} original frame")
            substitutions[old_frame["record_id"]] = new_frame["record_id"]
            frame_count += 1
        else:
            _require(old_frame == new_frame,
                     f"{opening_id}: original unframed source disposition changed")

    _require(old_host_count > 0 and frame_count > 0, "no original host/frame controls")
    before_rows = _by(baseline_rows, "quantity_id")
    after_rows = _by(candidate_rows, "quantity_id")
    _require(bool(before_rows) and set(after_rows) - set(before_rows) ==
             {expected_new_quantity_id} and set(before_rows) <= set(after_rows),
             "not exactly one additional customer quantity row")
    new_row = after_rows[expected_new_quantity_id]
    _require(new_row.get("canonical_entity_ids") == [target]
             and new_row.get("source_sha256") == sha,
             "additional row lacks the expected authenticated physical source")
    _notes_provenance(new_row)

    signed_receipts = 0
    for quantity_id, old in before_rows.items():
        new = after_rows[quantity_id]
        physical = old.get("canonical_entity_ids")
        _require(isinstance(physical, list) and len(physical) == 1
                 and physical == new.get("canonical_entity_ids")
                 and physical[0] in old_bindings
                 and old_bindings[physical[0]].get("status") == "corroborated",
                 f"{quantity_id}: old customer source identity changed")
        _require(old.get("source_sha256") == new.get("source_sha256") == sha,
                 f"{quantity_id}: customer original SHA changed")
        excluded = {"commercial_projection_fingerprint", "commercial_projection_provenance",
                    "notes", "evidence_ids"}
        _same_except(old, new, frozenset(excluded), f"{quantity_id} commercial row")
        old_prov, new_prov = _notes_provenance(old), _notes_provenance(new)
        _require(_rewrite_approved_receipts(old_prov, substitutions) == new_prov,
                 f"{quantity_id}: nested commercial provenance altered")
        old_ids, new_ids = old.get("evidence_ids"), new.get("evidence_ids")
        _require(isinstance(old_ids, list) and isinstance(new_ids, list)
                 and _rewrite_approved_receipts(old_ids, substitutions,
                                                field="evidence_ids") == new_ids,
                 f"{quantity_id}: non-host evidence changed")
        signed_receipts += 1

    # This is a *retention* checker, not customer-signature authentication.
    # Production must additionally call verify_sealed_customer_output against
    # the new signed run and independently reconcile the frozen evaluator.
    return {
        "source_sha256": sha,
        "previous_customers_preserved_except_authenticated_receipts": signed_receipts,
        "original_host_propositions_preserved": old_host_count,
        "original_positive_frames_preserved": frame_count,
        "additional_source_owned_customer_id": expected_new_quantity_id,
        "new_host_frame_still_abstained": True,
        "frozen_benchmark_matches_claimed": 0,
    }
