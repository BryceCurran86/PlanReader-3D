"""Read-only native source receipts excluded before physical wall W2 topology.

No retained candidate becomes a physical wall, a canonical room or a FIRM
quantity. Ambiguous source identity fails closed.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class FilteredNativePrimitiveReceipt:
    source_id: str
    path_index: int
    geometry: tuple[float, float, float, float]
    status: str = "FILTERED_NATIVE_CANDIDATE_ONLY"


def filtered_native_primitive_receipts(
    original: Sequence[Mapping[str, object]],
    retained: Sequence[Mapping[str, object]],
) -> tuple[FilteredNativePrimitiveReceipt, ...]:
    """Inventory excluded unambiguous source lines, never mint W2 ancestry."""
    def sid(row):
        value = row.get("id")
        return value if isinstance(value, str) and value and value == value.strip() else None

    orig_counts = Counter(sid(row) for row in original)
    keep_counts = Counter(sid(row) for row in retained)
    if orig_counts[None] or keep_counts[None]:
        return ()
    unique_orig = {sid(row): row for row in original if orig_counts[sid(row)] == 1}
    unique_keep = {sid(row): row for row in retained if keep_counts[sid(row)] == 1}
    if any(count != 1 for count in keep_counts.values()):
        return ()
    if any(key not in unique_orig or dict(row) != dict(unique_orig[key])
           for key, row in unique_keep.items()):
        return ()
    receipts = []
    for key, row in unique_orig.items():
        if key in keep_counts or str(row.get("kind") or "") != "line":
            continue
        try:
            path = row["path_index"]
            if not isinstance(path, int) or isinstance(path, bool) or path < 0:
                continue
            coords = tuple(float(row[k]) for k in ("x1", "y1", "x2", "y2"))
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not all(map(math.isfinite, coords)) or coords[:2] == coords[2:]:
            continue
        receipts.append(FilteredNativePrimitiveReceipt(key, path, coords))
    return tuple(sorted(receipts, key=lambda r: (r.path_index, r.source_id)))
