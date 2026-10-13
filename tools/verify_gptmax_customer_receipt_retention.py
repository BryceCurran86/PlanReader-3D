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


def _host_receipt_substitutions_from_sealed_quantities(
    baseline_quantities: Sequence[Mapping[str, Any]],
    candidate_quantities: Sequence[Mapping[str, Any]],
    *,
    expected_new_quantity_id: str,
    sha: str,
) -> dict[str, dict[str, str]]:
    """Prove row-local receipt swaps in two separately sealed executions.

    This is intentionally narrower than a generic quantity comparison. Every
    prior quantity must retain every field except its signed fingerprint and
    snapshot-scoped host/frame evidence ids. Non-host evidence is exact.
    """
    old = _by(baseline_quantities, "quantity_id")
    new = _by(candidate_quantities, "quantity_id")
    _require(
        bool(old)
        and set(old) <= set(new)
        and set(new) - set(old) == {expected_new_quantity_id},
        "paired sealed runs are not exactly prior rows plus one new quantity",
    )
    result: dict[str, dict[str, str]] = {}
    allowed = frozenset({"fingerprint", "evidence_ids", "trace_evidence_ids"})
    for quantity_id, before in old.items():
        after = new[quantity_id]
        _same_except(before, after, allowed, f"{quantity_id} sealed quantity")
        _require(
            before.get("source_sha256") == after.get("source_sha256") == sha,
            f"{quantity_id}: sealed source SHA changed",
        )
        physical = before.get("object_identity_refs")
        _require(
            isinstance(physical, list)
            and len(physical) == 1
            and physical == after.get("object_identity_refs"),
            f"{quantity_id}: sealed physical identity changed",
        )
        substitutions: dict[str, str] = {}
        for field in ("evidence_ids", "trace_evidence_ids"):
            old_ids, new_ids = before.get(field), after.get(field)
            _require(
                isinstance(old_ids, list) and isinstance(new_ids, list),
                f"{quantity_id}: sealed evidence list malformed",
            )
            old_non_host = [
                value for value in old_ids
                if not (
                    isinstance(value, str)
                    and value.startswith(HOST_RECEIPT_PREFIXES)
                )
            ]
            new_non_host = [
                value for value in new_ids
                if not (
                    isinstance(value, str)
                    and value.startswith(HOST_RECEIPT_PREFIXES)
                )
            ]
            _require(
                old_non_host == new_non_host,
                f"{quantity_id}: sealed non-host evidence changed",
            )
            for prefix in HOST_RECEIPT_PREFIXES:
                gone = [
                    value for value in old_ids
                    if isinstance(value, str)
                    and value.startswith(prefix)
                    and value not in new_ids
                ]
                added = [
                    value for value in new_ids
                    if isinstance(value, str)
                    and value.startswith(prefix)
                    and value not in old_ids
                ]
                _require(
                    len(gone) == len(added) and len(gone) <= 1,
                    f"{quantity_id}: sealed {prefix} receipt swap malformed",
                )
                if gone:
                    prior = substitutions.get(gone[0])
                    _require(
                        prior in (None, added[0]),
                        f"{quantity_id}: inconsistent sealed receipt rekey",
                    )
                    substitutions[gone[0]] = added[0]
        before_fp, after_fp = before.get("fingerprint"), after.get("fingerprint")
        _require(
            isinstance(before_fp, str)
            and isinstance(after_fp, str)
            and bool(FINGERPRINT.fullmatch(before_fp))
            and bool(FINGERPRINT.fullmatch(after_fp)),
            f"{quantity_id}: malformed sealed fingerprint",
        )
        _require(
            bool(substitutions) == (before_fp != after_fp),
            f"{quantity_id}: sealed fingerprint/receipt rekey disagreement",
        )
        result[quantity_id] = substitutions
    return result


def _customer_execution_substitutions(
    old_row: Mapping[str, Any],
    new_row: Mapping[str, Any],
    *,
    physical_id: str,
    sealed_receipts: Mapping[str, str],
    old_binding: Mapping[str, Any],
    new_binding: Mapping[str, Any],
) -> dict[str, str]:
    """Authorize only signed execution-local ids for one unchanged host.

    The source reports already proved the physical host proposition unchanged.
    The paired sealed quantity proves exactly which host/frame receipt ids
    changed in the independently executed customer run. This helper then binds
    the customer-only wall-group/snapshot ids to that same physical row.
    """
    _require(
        old_binding.get("status") == new_binding.get("status") == "corroborated",
        f"{physical_id}: source host not retained",
    )
    _require(
        old_binding.get("member_wall_candidate_ids")
        == new_binding.get("member_wall_candidate_ids"),
        f"{physical_id}: customer host members changed",
    )
    old_prov, new_prov = _notes_provenance(old_row), _notes_provenance(new_row)
    oq = old_prov.get("quantity")
    nq = new_prov.get("quantity")
    ost = old_prov.get("source_trace")
    nst = new_prov.get("source_trace")
    _require(
        isinstance(oq, Mapping)
        and isinstance(nq, Mapping)
        and isinstance(ost, Mapping)
        and isinstance(nst, Mapping),
        f"{physical_id}: customer provenance structure malformed",
    )
    om, nm = oq.get("metadata"), nq.get("metadata")
    osm, nsm = ost.get("metadata"), nst.get("metadata")
    _require(
        isinstance(om, Mapping)
        and isinstance(nm, Mapping)
        and isinstance(osm, Mapping)
        and isinstance(nsm, Mapping),
        f"{physical_id}: customer provenance metadata malformed",
    )
    substitutions = dict(sealed_receipts)
    old_host = om.get("host_binding_record_id")
    new_host = nm.get("host_binding_record_id")
    _require(
        isinstance(old_host, str)
        and isinstance(new_host, str)
        and sealed_receipts.get(old_host) == new_host,
        f"{physical_id}: customer host receipt not proven by sealed run",
    )
    old_frame = om.get("host_frame_record_id")
    new_frame = nm.get("host_frame_record_id")
    if old_frame is not None or new_frame is not None:
        _require(
            isinstance(old_frame, str)
            and isinstance(new_frame, str)
            and sealed_receipts.get(old_frame) == new_frame,
            f"{physical_id}: customer frame receipt not proven by sealed run",
        )

    old_wall, new_wall = om.get("host_wall_id"), nm.get("host_wall_id")
    _require(
        isinstance(old_wall, str)
        and isinstance(new_wall, str)
        and bool(old_wall)
        and bool(new_wall)
        and osm.get("host_wall_id") == old_wall
        and nsm.get("host_wall_id") == new_wall,
        f"{physical_id}: customer host wall provenance inconsistent",
    )
    substitutions[old_wall] = new_wall

    old_snapshot, new_snapshot = om.get("snapshot_id"), nm.get("snapshot_id")
    _require(
        isinstance(old_snapshot, str)
        and isinstance(new_snapshot, str)
        and bool(old_snapshot)
        and bool(new_snapshot)
        and old_snapshot != new_snapshot,
        f"{physical_id}: customer execution snapshot did not rekey",
    )
    substitutions[old_snapshot] = new_snapshot
    return substitutions


def verify_customer_receipt_rekeys(
    baseline_rows: Sequence[Mapping[str, Any]],
    candidate_rows: Sequence[Mapping[str, Any]],
    baseline_source: Mapping[str, Any],
    candidate_source: Mapping[str, Any],
    *,
    expected_new_physical_id: str,
    expected_new_quantity_id: str,
    baseline_quantities: Sequence[Mapping[str, Any]] | None = None,
    candidate_quantities: Sequence[Mapping[str, Any]] | None = None,
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

    cross_execution_receipts: dict[str, dict[str, str]] | None = None
    if baseline_quantities is not None or candidate_quantities is not None:
        _require(
            baseline_quantities is not None and candidate_quantities is not None,
            "paired sealed quantities must be supplied together",
        )
        cross_execution_receipts = _host_receipt_substitutions_from_sealed_quantities(
            baseline_quantities,
            candidate_quantities,
            expected_new_quantity_id=expected_new_quantity_id,
            sha=sha,
        )

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
        row_substitutions = dict(substitutions)
        if cross_execution_receipts is not None:
            row_substitutions.update(
                _customer_execution_substitutions(
                    old,
                    new,
                    physical_id=physical[0],
                    sealed_receipts=cross_execution_receipts[quantity_id],
                    old_binding=old_bindings[physical[0]],
                    new_binding=new_bindings[physical[0]],
                )
            )
        _require(_rewrite_approved_receipts(old_prov, row_substitutions) == new_prov,
                 f"{quantity_id}: nested commercial provenance altered")
        old_ids, new_ids = old.get("evidence_ids"), new.get("evidence_ids")
        _require(isinstance(old_ids, list) and isinstance(new_ids, list)
                 and _rewrite_approved_receipts(old_ids, row_substitutions,
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
        "cross_execution_sealed_receipts_verified": (
            cross_execution_receipts is not None
        ),
        "frozen_benchmark_matches_claimed": 0,
    }
