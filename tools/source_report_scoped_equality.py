"""Equality of source-authority reports modulo snapshot-scoped identifiers.

A contract id such as ``opening_host_binding_v3_<hash>`` is
``stable_contract_id(prefix, payload)`` where the payload includes the
SourceVisibility ``snapshot_id`` (or another snapshot-scoped id).  Adding genuine
source observations to a page changes the snapshot, so every such id changes
while the physical proposition behind it does not.  This module defines the
*complete, code-derived* set of those prefixes and the comparisons that tolerate
exactly that churn and nothing else:

* ``equal_modulo_snapshot_scoped_ids`` -- structure, values and list contents are
  equal after masking only the snapshot-scoped ids and ignoring list order
  (several authorities emit lists sorted by those very ids);
* ``additive_observation_inventory_equal`` -- the same, except that lists named
  ``*observation_ids`` may only gain members;
* ``evidence_swap_matches`` -- an evidence-id set may differ only by swapping at
  most one host-binding and one host-frame receipt (plus declared net additions).

Physical ids (``physical_opening_existence_*``), source observation ids, wall /
candidate identities and every value stay compared exactly.
"""
from __future__ import annotations

import json
import re
from typing import Any, Mapping

# Each of these hashes a payload that contains ``snapshot_id`` (or, for
# ``opening_host_raster_whole_wall_frame_v1``, the host binding record id):
# pb_opening_host_binding_authority / pb_opening_host_frame_authority /
# pb_physical_opening_authority / pb_source_room_face_authority /
# pb_semantic_opening_enumeration_authority /
# pb_live_wall_opening_authority_composition, and ``source_snapshot_`` itself.
SNAPSHOT_SCOPED_ID_PREFIXES = (
    "source_snapshot",
    "live_wall_opening_scope",
    "semantic_opening_enumeration",
    "opening_host_binding_v3",
    "opening_host_binding_group",
    "opening_host_frame_v2",
    "opening_host_raster_whole_wall_frame_v1",
    "physical_opening_candidate",
    "physical_opening_raw_candidate",
    "source_room_face",
    "source_room_face_record",
)
RECEIPT_EVIDENCE_PREFIXES = ("opening_host_binding_v3", "opening_host_frame_v2")
MASK = "<SNAPSHOT_SCOPED_ID>"

_SNAPSHOT_ID = re.compile(
    r"\b(?:"
    + "|".join(sorted(SNAPSHOT_SCOPED_ID_PREFIXES, key=len, reverse=True))
    + r")_[0-9a-f]{16,}\b"
)


def mask_snapshot_scoped_ids(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {k: mask_snapshot_scoped_ids(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [mask_snapshot_scoped_ids(v) for v in value]
    if isinstance(value, str):
        return _SNAPSHOT_ID.sub(MASK, value)
    return value


def canonical_unordered(value: Any) -> Any:
    """Recursively sort lists so list order is ignored (dict key order never mattered)."""
    if isinstance(value, Mapping):
        return {k: canonical_unordered(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        items = [canonical_unordered(v) for v in value]
        return sorted(items, key=lambda item: json.dumps(item, sort_keys=True, default=str))
    return value


def equal_modulo_snapshot_scoped_ids(left: Any, right: Any) -> bool:
    return canonical_unordered(mask_snapshot_scoped_ids(left)) == canonical_unordered(
        mask_snapshot_scoped_ids(right)
    )


def _observation_lists_only_grow(left: Any, right: Any) -> Any:
    """Return ``(left', right')`` with ``*observation_ids`` lists reduced to a verdict.

    Raises ``ValueError`` when an observation list loses or duplicates a member.
    """
    if isinstance(left, Mapping) and isinstance(right, Mapping):
        if set(left) != set(right):
            raise ValueError("observation inventory keys changed")
        out_left, out_right = {}, {}
        for key in left:
            lv, rv = left[key], right[key]
            if (
                isinstance(key, str)
                and key.endswith("observation_ids")
                and isinstance(lv, list)
                and isinstance(rv, list)
                and all(isinstance(x, str) for x in (*lv, *rv))
            ):
                if len(set(lv)) != len(lv) or len(set(rv)) != len(rv):
                    raise ValueError(f"{key} has repeated observation ids")
                if not set(lv) <= set(rv):
                    raise ValueError(f"{key} lost source observations")
                out_left[key] = out_right[key] = None
            else:
                out_left[key], out_right[key] = _observation_lists_only_grow(lv, rv)
        return out_left, out_right
    return left, right


def additive_observation_inventory_equal(left: Any, right: Any) -> bool:
    """Equal modulo snapshot-scoped ids, except ``*observation_ids`` may only gain members."""
    try:
        reduced_left, reduced_right = _observation_lists_only_grow(left, right)
    except ValueError:
        return False
    return equal_modulo_snapshot_scoped_ids(reduced_left, reduced_right)


def evidence_swap_matches(
    old_ids: Any,
    new_ids: Any,
    *,
    net_additions: Mapping[str, int] | None = None,
) -> bool:
    """Evidence sets may differ only by receipt swaps (<=1 of each kind) and declared net additions."""
    if not isinstance(old_ids, (list, tuple)) or not isinstance(new_ids, (list, tuple)):
        return False
    if len(set(old_ids)) != len(old_ids) or len(set(new_ids)) != len(new_ids):
        return False
    removed = set(old_ids) - set(new_ids)
    added = set(new_ids) - set(old_ids)
    net = dict(net_additions or {})
    for prefix in RECEIPT_EVIDENCE_PREFIXES:
        gone = [i for i in removed if isinstance(i, str) and i.startswith(prefix + "_")]
        new_one = [i for i in added if isinstance(i, str) and i.startswith(prefix + "_")]
        if len(gone) > 1 or len(new_one) > 1 or len(new_one) - len(gone) != net.get(prefix, 0):
            return False
    leftovers = [
        i
        for i in removed | added
        if not (isinstance(i, str) and i.startswith(tuple(p + "_" for p in RECEIPT_EVIDENCE_PREFIXES)))
    ]
    return not leftovers
