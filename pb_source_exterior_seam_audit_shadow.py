"""Shadow-only, source-owned exterior seam audit for a bounded path-ID set.

This is a consumer of the canonical outside-face walker, not a second walker.
It never closes a gap or promotes a candidate to measurement authority.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from pb_source_unbounded_building_face_walk_shadow import (
    _owner,
    diagnose_source_outside_face_neighbors,
    walk_source_unbounded_building_face,
)

MAX_AUDIT_PATHS = 64


def audit_exterior_seams(
    wall_bars: Sequence[Any],
    native_path_ids: Sequence[int],
    *,
    source_words: Sequence[Any] = (),
    drawings: Sequence[Mapping[str, Any] | object] = (),
    shared_dividers: Sequence[Any] = (),
    source_wall_union: Any | None = None,
    source_sha256: str,
    page_index: int,
) -> dict[str, Any]:
    """Return stable path-owned seam receipts, with zero inferred joins.

    A caller must supply the authenticated source hash and zero-based page.
    Source coordinates and PDF content are deliberately not serialized.
    """
    if not isinstance(source_sha256, str) or len(source_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in source_sha256
    ):
        raise ValueError("source_sha256 must be lowercase SHA-256")
    if isinstance(page_index, bool) or not isinstance(page_index, int) or page_index < 0:
        raise ValueError("page_index must be a nonnegative integer")
    if not native_path_ids or len(native_path_ids) > MAX_AUDIT_PATHS:
        raise ValueError("bounded nonempty path list required")
    if any(isinstance(i, bool) or not isinstance(i, int) or i < 0 for i in native_path_ids):
        raise ValueError("native path IDs must be nonnegative integers")
    ids = tuple(sorted(set(native_path_ids)))
    owners: set[int] = set()
    for bar in wall_bars:
        owned = _owner(bar)
        if owned is not None:
            owners.update(owned[1])
    missing = tuple(i for i in ids if i not in owners)
    walk = walk_source_unbounded_building_face(
        wall_bars, source_words,
        shared_dividers=shared_dividers, source_wall_union=source_wall_union,
    )
    receipts = []
    for path_id in ids:
        if path_id in missing:
            receipts.append({
                "native_path_id": path_id,
                "reason": "requested_path_not_source_owned",
                "neighbors": [],
                "status": "ABSTAINED",
            })
            continue
        receipt = diagnose_source_outside_face_neighbors(
            wall_bars, path_id, drawings=drawings, source_words=source_words,
            shared_dividers=shared_dividers, source_wall_union=source_wall_union,
        )
        receipts.append({
            "native_path_id": path_id,
            "status": "CANDIDATE",
            "reason": receipt["canonical_walk_reason"],
            "neighbors": receipt["neighbors"],
            "grey_seam_pairs": receipt["grey_seam_pairs"],
            "party_interior": path_id in walk.internal_party_wall_native_path_ids,
        })
    scope = json.dumps([source_sha256, page_index, ids], separators=(",", ":"))
    return {
        "schema_version": "shadow_exterior_seam_audit_v1",
        "audit_id": hashlib.sha256(scope.encode("ascii")).hexdigest(),
        "source_sha256": source_sha256,
        "page_index": page_index,
        "canonical_walk_status": walk.status,
        "canonical_walk_reason": walk.reason,
        "unclosed_dwelling_sides": list(walk.unclosed_dwelling_sides),
        "source_missing_path_ids": list(missing),
        "receipts": receipts,
        "building_footprint_authenticated": False,
        "measurement_authorized": False,
        "snap_join_applied": False,
        "official_frozen120_score_change": 0,
    }
