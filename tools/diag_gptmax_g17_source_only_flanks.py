"""Shadow-only closed G17 flank inventory from *already authenticated* receipts.

Input is the original source-verified G17-to-parent audit sidecar. It does not
render, mutate source snapshots, select walls, publish hosts, assume dimensions,
or infer construction quantities.
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping


def _line(value: object) -> tuple[float, float, float, float]:
    if not isinstance(value, (tuple, list)) or len(value) != 4:
        raise ValueError("source G17 geometry must have four coordinates")
    if any(type(x) not in (int, float) or not math.isfinite(float(x)) for x in value):
        raise ValueError("nonfinite/invalid source G17 geometry")
    return tuple(float(x) for x in value)


def source_only_closed_flanks(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Nominate geometry only when the full G17 source face/end graph closes."""
    source_sha = receipt.get("source_sha256")
    physical_id = receipt.get("physical_opening_id")
    if (not isinstance(source_sha, str) or len(source_sha) != 64
            or not isinstance(physical_id, str) or not physical_id
            or receipt.get("host_status") != "abstained"
            or receipt.get("host_granted") is not False
            or receipt.get("metric_quantity_granted") is not False):
        raise ValueError("unauthenticated or promoted G17 input")
    rows = receipt.get("source_g17_observations")
    if not isinstance(rows, list) or not rows:
        raise ValueError("original G17 observations unavailable")
    groups: dict[tuple[str, float, float], list[tuple[float, str]]] = defaultdict(list)
    ends: dict[tuple[str, float, float, float], list[str]] = defaultdict(list)
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValueError("malformed G17 source observation")
        oid = row.get("observation_id")
        if not isinstance(oid, str) or not oid or oid in seen:
            raise ValueError("duplicate/unbound G17 observation")
        seen.add(oid)
        parents = row.get("authenticated_source_parents")
        if not isinstance(parents, list) or not parents:
            raise ValueError("source G17 parent not authenticated")
        for parent in parents:
            if not isinstance(parent, Mapping) or not parent.get("observation_id"):
                raise ValueError("missing original G17 source parent")
        x0, y0, x1, y1 = _line(row.get("geometry_pdf_pts"))
        kind = row.get("observation_kind")
        if kind == "raster_wall_band_face":
            if y0 == y1 and x0 < x1:
                groups[("horizontal", x0, x1)].append((y0, oid))
            elif x0 == x1 and y0 < y1:
                groups[("vertical", y0, y1)].append((x0, oid))
            else:
                raise ValueError("malformed G17 physical band face")
        elif kind == "raster_wall_band_end":
            if x0 == x1 and y0 < y1:
                ends[("horizontal", x0, y0, y1)].append(oid)
            elif y0 == y1 and x0 < x1:
                ends[("vertical", y0, x0, x1)].append(oid)
            else:
                raise ValueError("malformed G17 end cap")
        elif kind in ("raster_thin_ink_run", "raster_line_run"):
            # Additional physical ink does not supply wall/host authority.
            continue
        else:
            raise ValueError("unexpected original G17 source observation kind")
    flank_rows = []
    if len(groups) == 2 and sum(len(v) for v in groups.values()) == 4 and sum(map(len, ends.values())) == 2:
        candidates = []
        for (axis, lo, hi), faces in groups.items():
            offsets = sorted(faces)
            if len(faces) != 2 or offsets[0][0] >= offsets[1][0]:
                break
            a, b = offsets[0][0], offsets[1][0]
            bbox = [lo, a, hi, b] if axis == "horizontal" else [a, lo, b, hi]
            candidates.append((axis, lo, hi, a, b, bbox, [offsets[0][1], offsets[1][1]]))
        if len(candidates) == 2:
            candidates.sort(key=lambda v: (v[0], v[1]))
            left, right = candidates
            if (left[0] == right[0] and left[2] < right[1]
                    and not (left[3] > right[4] or right[3] > left[4])):
                for side, row, edge in (("first", left, left[2]), ("second", right, right[1])):
                    axis, lo, hi, a, b, bbox, face_ids = row
                    end_ids = ends.get((axis, edge, a, b), [])
                    if len(end_ids) != 1:
                        break
                    flank_rows.append({
                        "side_in_original_source_order": side,
                        "orientation": axis,
                        "source_bbox_pdf_pts": bbox,
                        "source_observation_ids": sorted(face_ids + end_ids),
                    })
    if len(flank_rows) != 2:
        flank_rows = []
    return {
        "physical_opening_id": physical_id,
        "source_sha256": source_sha,
        "host_status": "abstained",
        "closed_source_flank_nomination": bool(flank_rows),
        "source_flank_boxes": flank_rows,
        "unresolved_reason": None if flank_rows else "exact_original_g17_face_end_closure_unavailable",
        "physical_host_granted": False,
        "opening_height_or_count_granted": False,
        "metric_quantity_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-report", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    original = json.loads(args.source_report.read_text(encoding="utf-8"))
    receipts = original.get("unhosted_raster_flank_source_receipts")
    if not isinstance(receipts, list):
        raise ValueError("authenticated source flank sidecar missing")
    result = [source_only_closed_flanks(r) for r in receipts]
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
