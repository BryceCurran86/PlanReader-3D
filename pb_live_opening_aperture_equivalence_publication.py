"""Safety gate for optional physical-aperture opening-area consolidation.

An aperture-equivalence *diagnostic* is not authority to suppress an existing
source-sealed opening quantity.  The former enabled branch could discard
uncompared / ambiguous records, choose the first lexicographic member as owner,
and create an unsealable multi-opening quantity from caller-supplied verdicts.

Default OFF is byte-for-byte compatible with the original publication output.
ON is not a supported commercial capability until a producer-owned physical
identity and source-receipt reproof is wired at composition level, preserving
one canonical opening id per sealed quantity and all ambiguous quantities.
Fail explicitly rather than silently deleting measurements or manufacturing
a source proof.  This module never changes frozen benchmark truth.
"""
from __future__ import annotations

from typing import Sequence

from pb_migration_contracts import QuantityEvidence
from pb_opening_aperture_equivalence_shadow import ApertureRecord, PairVerdict
from pb_source_closed_run_export import SourceClosedRunConflictError


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
    """Keep existing outputs unchanged, or reject an unproven collapse.

    The optional records and pair verdicts are *caller provided*, not issued
    by the physical aperture authority.  No combination of these fields alone
    is sufficient to prove a unique physical customer-quantity owner.
    """
    if type(enabled) is not bool:
        raise TypeError("aperture equivalence publication must be an explicit boolean")
    published = tuple(quantities)
    if not enabled:
        return published
    if any(type(item) is not QuantityEvidence for item in published):
        raise TypeError("quantities must contain QuantityEvidence")
    # A physical opening's partition_receipt must be re-issued and verified
    # against original source observations before a source-owned composition
    # may remove another canonical member.  This API has no such authority.
    # Raise even for 'distinct' or empty supplied verdict sets: an enabled
    # publication flag must never silently imply an actual consolidation.
    raise SourceClosedRunConflictError(
        "aperture equivalence publication requires original-source physical "
        "partition reproof and a one-opening-id sealed customer composition"
    )


__all__ = ["apply_aperture_equivalence_publication"]
