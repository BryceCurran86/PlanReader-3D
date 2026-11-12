"""Default-off publication consumer for one-aperture opening-area classes.

Claude's #4267 shadow groups sealed opening records. This consumer may collapse
already-issued area quantities to one row per authenticated equivalent class
while retaining every member identity. It never invents area, host, frame or
FIRM authority. Ambiguous, unproven, distinct-but-uncompared shared-figure, and
non-clique classes publish nothing for their members.

Default ``enabled=False`` returns the caller quantities unchanged.
"""
from __future__ import annotations

from dataclasses import replace
from typing import Sequence

from pb_migration_contracts import QuantityEvidence
from pb_opening_aperture_equivalence_shadow import (
    ApertureRecord,
    PairVerdict,
    classes_by_record,
    resolve_aperture_equivalence,
)


def _quantity_opening_id(quantity: QuantityEvidence) -> str:
    refs = tuple(quantity.input_entity_ids)
    if refs:
        return str(refs[0])
    meta = quantity.metadata or {}
    return str(meta.get("canonical_opening_id") or meta.get("physical_opening_id") or "")


def apply_aperture_equivalence_publication(
    quantities: Sequence[QuantityEvidence],
    records: Sequence[ApertureRecord],
    verdicts: Sequence[PairVerdict],
    *,
    enabled: bool = False,
) -> tuple[QuantityEvidence, ...]:
    """Filter already-built opening-area quantities through aperture classes."""
    if type(enabled) is not bool:
        raise TypeError("aperture equivalence publication must be an explicit boolean")
    published = tuple(quantities)
    if not enabled:
        return published
    if any(type(item) is not QuantityEvidence for item in published):
        raise TypeError("quantities must contain QuantityEvidence")

    classes = resolve_aperture_equivalence(records, verdicts, enabled=True)
    by_id = classes_by_record(classes)
    by_opening = {_quantity_opening_id(item): item for item in published}
    if len(by_opening) != len(published):
        raise ValueError("opening-area quantities must have unique opening identities")

    out: list[QuantityEvidence] = []
    seen_classes: set[str] = set()
    for quantity in published:
        opening_id = _quantity_opening_id(quantity)
        aperture = by_id.get(opening_id)
        if aperture is None or aperture.is_ambiguous:
            continue
        if aperture.class_id in seen_classes:
            continue
        seen_classes.add(aperture.class_id)
        members = aperture.member_ids
        if not aperture.is_consolidated:
            out.append(quantity)
            continue
        member_quantities = tuple(
            by_opening[member_id] for member_id in members if member_id in by_opening
        )
        if len(member_quantities) != len(members):
            continue
        values = {item.value for item in member_quantities}
        if len(values) != 1:
            continue
        representative = by_opening[members[0]]
        evidence_ids = tuple(
            sorted(
                {eid for item in member_quantities for eid in item.evidence_ids}
                | set(aperture.receipt_ids)
            )
        )
        metadata = dict(representative.metadata)
        metadata["aperture_class_id"] = aperture.class_id
        metadata["aperture_member_ids"] = members
        metadata["aperture_equivalence_status"] = aperture.status.value
        metadata["can_issue_firm_quantity"] = False
        out.append(
            replace(
                representative,
                input_entity_ids=members,
                evidence_ids=evidence_ids,
                metadata=metadata,
            )
        )
    return tuple(out)


__all__ = ["apply_aperture_equivalence_publication"]
