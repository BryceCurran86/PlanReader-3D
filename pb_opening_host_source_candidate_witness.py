"""Stable W4 candidate-membership witness for an authenticated opening host.

This is NOT a physical wall identity, host-binding receipt, equivalence proof,
QuantityEvidence or opening-count authority. It only gives a deterministic
source-scoped address to an unchanged set of producer-authenticated hybrid W4
candidate identities when the surrounding SourceVisibility snapshot changes.
A changed path/provenance identity produces a different witness; an ambiguous
host must never receive one.

The candidate identity IDs must themselves come from corroborated sealed W4
host records. Callers may not manufacture them from labels or proximity.
"""
from __future__ import annotations

import re
from typing import Optional, Sequence

from pb_migration_contracts import stable_contract_id


_SOURCE_SHA_RE = re.compile(r"[0-9a-f]{64}", re.ASCII)


def source_candidate_membership_witness_id(
    *,
    document_id: str,
    source_sha256: str,
    page_id: str,
    opening_identity_id: str,
    member_candidate_identity_ids: Sequence[str],
) -> Optional[str]:
    """Return snapshot-independent, membership-sensitive evidence *hint*.

    Even matching witness IDs do not certify same physical wall when the
    source's W4 equivalence groups or owner roles have changed. Such changes
    require separate positive source proof before a host receipt may be
    treated as retained.
    """
    if (not isinstance(document_id, str) or not document_id
            or not isinstance(source_sha256, str)
            or _SOURCE_SHA_RE.fullmatch(source_sha256) is None
            or not isinstance(page_id, str) or not page_id.isdecimal()
            or not isinstance(opening_identity_id, str)
            or not opening_identity_id.startswith("physical_opening_existence_")
            or not isinstance(member_candidate_identity_ids, (tuple, list))
            or not member_candidate_identity_ids):
        return None
    identities=tuple(member_candidate_identity_ids)
    if (any(not isinstance(v, str) or not v.startswith("wall2_") or len(v)<=6
            for v in identities)
            or len(set(identities)) != len(identities)):
        return None
    return stable_contract_id(
        "opening_source_candidate_membership_witness_v1",
        {
            "document_id": document_id,
            "source_sha256": source_sha256,
            "page_id": page_id,
            "opening_identity_id": opening_identity_id,
            "member_candidate_identity_ids": tuple(sorted(identities)),
        },
        digest_chars=32,
    )
