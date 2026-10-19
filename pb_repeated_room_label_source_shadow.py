"""Shadow-only exact source observation ownership for repeated room labels.

No spatial proximity, text similarity, or caller-chosen first match can grant
room identity. Original trusted lines and producer-issued room label receipts
are mandatory. This module never creates a room, dimension or quantity.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence


def uniquely_owned_repeated_label_lines(
    room_receipts: Mapping[str, Sequence[str]],
    trusted_lines: Sequence[object],
) -> dict[str, object]:
    """One-to-one original native observation binding, else return no owners."""
    if not isinstance(room_receipts, Mapping) or len(room_receipts) < 2:
        return {}
    if type(trusted_lines) not in (tuple, list):
        return {}
    if len(trusted_lines) != len(room_receipts):
        return {}
    original_owners: dict[str, set[str]] = {}
    for room_id, raw in room_receipts.items():
        if type(room_id) is not str or not room_id or room_id != room_id.strip():
            return {}
        if type(raw) not in (tuple, list) or not raw:
            return {}
        if any(type(x) is not str or not x or x != x.strip() for x in raw):
            return {}
        if len(set(raw)) != len(raw):
            return {}
        original_owners[room_id] = set(raw)
    # A label observation ID cannot be reassigned to two distinct rooms.
    cross_owners = Counter(e for ids in original_owners.values() for e in ids)
    if any(count != 1 for count in cross_owners.values()):
        return {}
    result: dict[str, object] = {}
    all_line_obs: set[str] = set()
    for line in trusted_lines:
        raw_obs = getattr(line, "observation_ids", None)
        raw_receipts = getattr(line, "receipt_ids", None)
        if type(raw_obs) not in (list, tuple) or not raw_obs:
            return {}
        if type(raw_receipts) not in (list, tuple) or not raw_receipts:
            return {}
        if any(type(e) is not str or not e or e != e.strip()
               for e in (*raw_obs, *raw_receipts)):
            return {}
        if len(set(raw_obs)) != len(raw_obs) or len(set(raw_receipts)) != len(raw_receipts):
            return {}
        observations = set(raw_obs)
        if all_line_obs.intersection(observations):
            return {}
        all_line_obs.update(observations)
        owners = [rid for rid, ids in original_owners.items()
                  if observations.issubset(ids)]
        if len(owners) != 1 or owners[0] in result:
            return {}
        result[owners[0]] = line
    return result if len(result) == len(original_owners) else {}
