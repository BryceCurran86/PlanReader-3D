"""Fail-closed retention for producer-proved G17 source representative selectors.

A producer support member is NOT automatically a positive physical-existence
selector. This read-only comparison can never grant a W4 host or signed area.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import re

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_OBS = re.compile(r"source_observation_[0-9a-f]{32}\Z")
_OPEN = re.compile(r"physical_opening_existence_[0-9a-f]{32}\Z")
RETAINED = "SOURCE_REPRESENTATIVE_RETAINED_SHADOW"
ABSTAIN = "ABSTAIN_SOURCE_REPRESENTATIVE_RETENTION"


@dataclass(frozen=True)
class SourceSelectorWitness:
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    physical_opening_id: str
    observation_id: str
    geometry_pt: tuple[float, float, float, float]
    existence_corroborated: bool


def _check(row: SourceSelectorWitness):
    if type(row) is not SourceSelectorWitness:
        raise TypeError("source selector witness required")
    if (not isinstance(row.document_id, str) or not row.document_id
        or not isinstance(row.revision_id, str) or not row.revision_id
        or not isinstance(row.source_sha256, str) or not _SHA.fullmatch(row.source_sha256)
        or not isinstance(row.page_id, str) or not row.page_id.isdecimal()
        or str(int(row.page_id)) != row.page_id or int(row.page_id) < 1
        or not isinstance(row.physical_opening_id, str) or not _OPEN.fullmatch(row.physical_opening_id)
        or not isinstance(row.observation_id, str) or not _OBS.fullmatch(row.observation_id)
        or not isinstance(row.geometry_pt, tuple) or len(row.geometry_pt) != 4
        or any(type(v) not in (int, float) or not math.isfinite(float(v)) for v in row.geometry_pt)
        or type(row.existence_corroborated) is not bool):
        raise ValueError("malformed source selector witness")


def compare_original_source_selector(
    original: SourceSelectorWitness,
    changed: tuple[SourceSelectorWitness, ...],
) -> dict:
    """Retain old representative ONLY when the same source ID, geometry and
    physical existence are independently proved under the changed policy.

    Positive input receipts must originate from source-authority calls.
    If that contract is unprovable, the caller must abstain, not inject rows.
    No first/nearest source support member may rekey the opening.
    """
    _check(original)
    if not original.existence_corroborated:
        raise ValueError("original representative must have positive physical existence")
    if type(changed) is not tuple:
        raise TypeError("immutable changed-policy selector receipts required")
    observed = {}
    old_scope = (original.document_id, original.revision_id, original.source_sha256,
                 original.page_id, original.physical_opening_id)
    for row in changed:
        _check(row)
        if (row.document_id, row.revision_id, row.source_sha256,
            row.page_id, row.physical_opening_id) != old_scope:
            raise ValueError("foreign source, revision, page or physical opening")
        previous = observed.get(row.observation_id)
        if previous is not None and previous != row:
            raise ValueError("contradictory repeated source selector receipt")
        observed[row.observation_id] = row
    positives = sorted(oid for oid, row in observed.items() if row.existence_corroborated)
    old = observed.get(original.observation_id)
    if old is None or not old.existence_corroborated:
        reason = "original_representative_no_longer_positive"
    elif old.geometry_pt != original.geometry_pt:
        reason = "original_representative_source_geometry_changed"
    else:
        reason = None
    return {
        "status": RETAINED if reason is None else ABSTAIN,
        "physical_opening_id": original.physical_opening_id,
        "original_representative_observation_id": original.observation_id,
        "retained_representative_observation_id": original.observation_id if reason is None else None,
        "positive_changed_selector_ids": positives,
        "competing_positive_selector_ids": [x for x in positives if x != original.observation_id],
        "reason_codes": [] if reason is None else [reason],
        "source_only": True,
        "host_granted": False, "frame_granted": False,
        "quantity_granted": False, "count_granted": False,
    }
