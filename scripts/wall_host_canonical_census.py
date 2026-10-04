#!/usr/bin/env python3
"""Read-only census of the wall -> opening host -> canonical wall chain on one PDF page.

Runs the live producer-owned chain exactly as the customer path does (no caller geometry,
no bypass) and reports where legitimate wall fragments stop short of a usable canonical
host: wall candidates and their physical equivalence (how many are ambiguous, which
geometric family the ambiguous pairs belong to), opening host bindings and whole-wall
frames by reason code, and the canonical walls that result.

It uses public authority APIs and the candidates' own geometry only. It reads no expected
quantity, project name or file name, and it never alters an authority result.

    python scripts/wall_host_canonical_census.py --pdf plan.pdf --page 3 --json census.json
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pb_live_canonical_wall_composition import compose_live_canonical_walls  # noqa: E402
from pb_live_wall_opening_authority_composition import (  # noqa: E402
    compose_live_wall_opening_authority,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector  # noqa: E402
from pb_source_visibility_authority import SourceVisibilityProducer  # noqa: E402

# Descriptive histogram bins only (points). They never decide anything.
_LATERAL_BINS = ((0.01, "<0.01"), (0.5, "<0.5"), (2.5, "<2.5"), (8.0, "<8"), (24.0, "<24"))
_GAP_BINS = ((1e-6, "touch"), (2.5, "gap<=2.5"), (7.5, "gap<=7.5"))
_PARALLEL_DEG = 3.0


def _bin(value: float, bins, overflow: str) -> str:
    for limit, label in bins:
        if value < limit if label.startswith("<") else value <= limit:
            return label
    return overflow


def pair_family(left: tuple[float, float, float, float], right: tuple[float, float, float, float]) -> str:
    """Geometric family of two straight wall candidates (diagnostic labels only)."""
    ax, ay, bx, by = left
    cx, cy, dx, dy = right
    la, lb = math.hypot(bx - ax, by - ay), math.hypot(dx - cx, dy - cy)
    if la < 1e-9 or lb < 1e-9:
        return "degenerate"
    ua = ((bx - ax) / la, (by - ay) / la)
    ub = ((dx - cx) / lb, (dy - cy) / lb)
    angle = math.degrees(math.asin(min(1.0, abs(ua[0] * ub[1] - ua[1] * ub[0]))))
    if angle > _PARALLEL_DEG:
        return "nonparallel"
    normal = (-ua[1], ua[0])
    lateral = abs(((cx - ax) * normal[0] + (cy - ay) * normal[1] + (dx - ax) * normal[0] + (dy - ay) * normal[1]) / 2.0)
    ia = sorted((ax * ua[0] + ay * ua[1], bx * ua[0] + by * ua[1]))
    ib = sorted((cx * ua[0] + cy * ua[1], dx * ua[0] + dy * ua[1]))
    overlap = min(ia[1], ib[1]) - max(ia[0], ib[0])
    along = "overlap" if overlap > 1e-6 else _bin(-overlap, _GAP_BINS, "gap>7.5")
    return f"parallel lateral{_bin(lateral, _LATERAL_BINS, '>=24')} {along}"


def _line(record: Any) -> tuple[float, float, float, float]:
    points = record.wall_candidate.centerline_pts
    return (float(points[0][0]), float(points[0][1]), float(points[-1][0]), float(points[-1][1]))


def census(pdf: Path, page: str) -> dict[str, Any]:
    started = time.perf_counter()
    source = SourceVisibilityProducer(producer_method="wall-host-canonical-census", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="census", source_bytes=pdf.read_bytes(), source_locator="memory://census.pdf"
    )
    ingested = time.perf_counter()
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=(page,)
    )
    composed = time.perf_counter()
    canonical = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=composition)

    current = source.published_snapshot_for_revision(published.revision.revision_id)
    scope = composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=page,
            decision_scope_id=f"wall-source:page-{page}",
        )
    )
    records = {record.wall_candidate_id: record for record in scope.records}
    equivalence = scope.equivalence
    families: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    equivalence_report: Optional[dict[str, Any]] = None
    if equivalence is not None:
        for left, right, classification in equivalence.pair_classifications:
            families[classification][pair_family(_line(records[left]), _line(records[right]))] += 1
        audit = equivalence.candidate_pair_audit
        equivalence_report = {
            "walls": len(records),
            "representatives": len(equivalence.representative_wall_ids),
            "same_groups": len(equivalence.equivalence_groups),
            "multi_member_groups": sum(1 for group in equivalence.equivalence_groups if len(group) > 1),
            "ambiguous_walls": len(equivalence.ambiguous_wall_ids),
            "abstained_walls": len(equivalence.abstained_wall_ids),
            "verified_points_per_mm": audit.verified_points_per_mm,
            "pairs_total": audit.total_pairs,
            "pairs_considered": audit.considered_pairs,
            "pairs_excluded": audit.excluded_pairs,
            "exclusion_reasons": dict(audit.exclusion_reason_counts),
            "pair_classes": {cls: dict(counter.most_common(12)) for cls, counter in families.items()},
        }

    bindings = collections.Counter(
        (trace.status.value, tuple(trace.reason_codes)) for trace in composition.opening_bindings
    )
    frames = collections.Counter(
        (trace.status.value, tuple(trace.reason_codes)) for trace in composition.host_frames
    )
    return {
        "seconds": {"ingest": round(ingested - started, 1), "compose": round(composed - ingested, 1)},
        "composition": {"status": composition.status.value, "reasons": list(dict.fromkeys(composition.reason_codes))[:12]},
        "wall_scope": [
            {
                "page": trace.page_id,
                "status": trace.status.value,
                "scope_complete": trace.scope_complete,
                "walls": len(trace.wall_candidate_ids),
                "reasons": list(trace.reason_codes),
            }
            for trace in composition.wall_scopes
        ],
        "equivalence": equivalence_report,
        "opening_bindings": [
            {"count": count, "status": status, "reasons": list(reasons)} for (status, reasons), count in bindings.most_common()
        ],
        "host_frames": [
            {"count": count, "status": status, "reasons": list(reasons)} for (status, reasons), count in frames.most_common()
        ],
        "canonical_walls": {
            "status": canonical.status.value,
            "walls": len(canonical.walls),
            "physical_identity_resolved": sum(1 for wall in canonical.walls if wall.physical_identity_resolved),
            "multi_member": sum(1 for wall in canonical.walls if len(wall.member_wall_candidate_ids) > 1),
            "with_openings": sum(1 for wall in canonical.walls if wall.opening_identity_ids),
            "unresolved_candidates": len(canonical.unresolved_wall_candidate_ids),
            "identity_statuses": dict(collections.Counter(wall.identity_status for wall in canonical.walls)),
        },
    }


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page", required=True, help="1-based source page number")
    parser.add_argument("--json", type=Path, help="write the full report here")
    args = parser.parse_args(argv)
    report = census(args.pdf, str(args.page).strip())
    print(json.dumps(report, indent=1, sort_keys=True))
    if args.json:
        args.json.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
