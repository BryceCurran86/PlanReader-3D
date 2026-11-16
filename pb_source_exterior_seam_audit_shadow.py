"""Shadow-only, source-owned exterior seam audit for a bounded path-ID set.

This is a consumer of the canonical outside-face walker, not a second walker.
It never closes a gap or promotes a candidate to measurement authority.
"""
from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from shapely.ops import unary_union

from pb_source_unbounded_building_face_walk_shadow import (
    _owner,
    _topology_host_pairs,
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
    owned_bars = []
    for bar in wall_bars:
        owned = _owner(bar)
        if owned is not None:
            owners.update(owned[1])
            owned_bars.append((owned[0], owned[1], bar))
    missing = tuple(i for i in ids if i not in owners)
    # The canonical walk may be expensive on original pages. Do not rerun it
    # for each audited native path, and do not repeatedly union every wall bar.
    union = source_wall_union
    if union is None and owned_bars:
        union = unary_union([geom for geom, _ids, _bar in owned_bars])
    walk = walk_source_unbounded_building_face(
        wall_bars, source_words,
        shared_dividers=shared_dividers, source_wall_union=union,
    )
    topology = _topology_host_pairs(drawings, source_words)
    neutral_seams = ()
    if drawings:
        from pb_source_neutral_wall_seam_continuity import (
            detect_source_neutral_wall_seams,
        )
        neutral_seams = detect_source_neutral_wall_seams(drawings, page_index=-1)
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
            shared_dividers=shared_dividers, source_wall_union=union,
            canonical_walk=walk, topology_host_pairs=topology,
            neutral_seams=neutral_seams, owned_bars=owned_bars,
        )
        receipts.append({
            "native_path_id": path_id,
            "status": "CANDIDATE",
            "reason": receipt["canonical_walk_reason"],
            "neighbors": receipt["neighbors"],
            "grey_seam_pairs": receipt["grey_seam_pairs"],
            "party_interior": path_id in walk.internal_party_wall_native_path_ids,
        })
    # Audit identity is a source-input receipt, not a commercial footprint ID.
    # The same page/path IDs can produce different diagnostics if their native
    # wall geometry or authenticated opening evidence changes. Hash the exact
    # normalized geometry bytes; never publish original coordinates.
    input_hash = hashlib.sha256()
    for path_ids, geom_wkb in sorted(
        (tuple(path_ids), geom.normalize().wkb)
        for geom, path_ids, _bar in owned_bars
    ):
        input_hash.update(json.dumps(path_ids, separators=(",", ":")).encode("ascii"))
        input_hash.update(geom_wkb)
        input_hash.update(b"\\0")
    if union is not None:
        input_hash.update(union.normalize().wkb)
    for pair in sorted(tuple(sorted(pair)) for pair in topology):
        input_hash.update(json.dumps(pair, separators=(",", ":")).encode("ascii"))
    for seam in sorted(
        (int(row.first_host_path_id), int(row.second_host_path_id),
         tuple(sorted(int(i) for i in row.neutral_fill_path_ids)))
        for row in neutral_seams
    ):
        input_hash.update(json.dumps(seam, separators=(",", ":")).encode("ascii"))
    scope = json.dumps(
        [source_sha256, page_index, ids, input_hash.hexdigest(),
         walk.status, walk.reason, walk.unclosed_dwelling_sides],
        separators=(",", ":"),
    )
    return {
        "schema_version": "shadow_exterior_seam_audit_v2",
        "audit_id": hashlib.sha256(scope.encode("ascii")).hexdigest(),
        "source_sha256": source_sha256,
        "source_hash_authenticated": False,
        "source_hash_validation": "caller_supplied_format_only",
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
