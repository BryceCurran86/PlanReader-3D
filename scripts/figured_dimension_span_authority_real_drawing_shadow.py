"""Real-drawing shadow diagnostic for pb_figured_dimension_span_authority.

Research/diagnostic only. Does not compare against BOQ quantities, does not
publish anything, does not touch benchmark gold, does not tune any threshold
to raise a count. Reuses the exact same real floor-plan page/region specs
already established and verified by
``scripts/canonical_wall_room_real_drawing_census.py`` so this diagnostic is
scoped to real floor-plan viewports, not whatever happens to be biggest on
the page.

This operates one layer BELOW pb_figured_dimension_span_authority itself:
that module consumes already-classified ``DimensionSpanCandidate`` records
(target entity + semantic span kind already known), and producing those from
raw PDF evidence is explicitly out of scope for this PR (see that module's
docstring). This script instead runs the existing, lower-layer
``pb_figured_dimension_evidence`` extractor directly against real drawings to
honestly report how far the CURRENT pipeline gets: how many dimension
systems it finds, how many reach a complete witness-bound chain (both
endpoints resolved), and -- necessarily -- zero with an exact semantic span
binding, since no endpoint-to-physical-entity classifier exists yet at this
layer. That gap is the real, honest finding, not a bug in this script.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Sequence

import fitz

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pb_figured_dimension_evidence import (
    BindingStatus,
    apply_anchor_binding,
    bind_observation_to_vector_geometry,
    calibrate_dimension_layout,
    extract_native_dimension_observations,
    extract_vector_segments,
)

# Same sources dir the rest of the shadow-model diagnostics use. Gitignored,
# so it only exists on a machine that already has the real BOQ/drawing PDFs;
# fall back to the primary working copy when this worktree's own copy (also
# gitignored, so absent by construction) is missing.
_CANDIDATE_SOURCES_DIRS = [
    REPO_ROOT / "benchmarks" / "sources",
    Path(r"C:\Users\bryce\Documents\PB-PlanReader-3D\benchmarks\sources"),
]
SOURCES_DIR = next((d for d in _CANDIDATE_SOURCES_DIRS if d.is_dir()), _CANDIDATE_SOURCES_DIRS[0])

# Identical page/region specs to scripts/canonical_wall_room_real_drawing_census.py
# -- these are the already-verified real floor-plan viewport regions for the
# four projects used throughout this engineering effort. Not re-derived, not
# re-tuned.
PROJECTS = [
    {"name": "Baghau", "pdf": SOURCES_DIR / "bq_and_drawing_1747803602496.pdf", "page_0based": 35, "region": (350.0, 350.0, 950.0, 850.0)},
    {"name": "Lamu", "pdf": SOURCES_DIR / "lamu-ishakani-ecd-classrooms-boq.pdf", "page_0based": 40, "region": (100.0, 20.0, 750.0, 380.0)},
    {"name": "Dungicha", "pdf": SOURCES_DIR / "dungicha_3classrooms.pdf", "page_0based": 133, "region": (0.0, 550.0, 900.0, 950.0)},
    {"name": "KSTVET", "pdf": SOURCES_DIR / "1727358888238-bq-nd-drawing.pdf", "page_0based": 53, "region": (150.0, 300.0, 750.0, 800.0)},
]


def _bbox_fully_inside(inner: Sequence[float], outer: Sequence[float]) -> bool:
    return (
        float(inner[0]) >= float(outer[0])
        and float(inner[1]) >= float(outer[1])
        and float(inner[2]) <= float(outer[2])
        and float(inner[3]) <= float(outer[3])
    )


def _point_inside(point, bbox: Sequence[float]) -> bool:
    return float(bbox[0]) <= point[0] <= float(bbox[2]) and float(bbox[1]) <= point[1] <= float(bbox[3])


def _census_one(spec: Dict[str, Any]) -> Dict[str, Any]:
    doc = fitz.open(str(spec["pdf"]))
    try:
        page = doc[spec["page_0based"]]
        region = spec["region"]
        layout = calibrate_dimension_layout(page)

        segments = [
            s for s in extract_vector_segments(page, page_num=spec["page_0based"] + 1)
            if _point_inside(s.start, region) and _point_inside(s.end, region)
        ]
        native = [
            o for o in extract_native_dimension_observations(page, page_num=spec["page_0based"] + 1)
            if o.bbox is not None and _bbox_fully_inside(o.bbox, region)
        ]

        status_counts: Dict[str, int] = {status.value: 0 for status in BindingStatus}
        for observation in native:
            binding = bind_observation_to_vector_geometry(observation, segments, layout)
            status_counts[binding.status] += 1

        discovered = len(native)
        witness_bound = status_counts[BindingStatus.WITNESS_BOUND.value]
        both_endpoints_resolved = witness_bound  # identical in the current binder
        exact_semantic_span_binding = 0  # always -- see module docstring

        blocked_breakdown = {
            k: v for k, v in status_counts.items()
            if k != BindingStatus.WITNESS_BOUND.value and v > 0
        }

        return {
            "project": spec["name"],
            "dimension_systems_discovered": discovered,
            "complete_witness_bound_chain": witness_bound,
            "both_endpoints_resolved": both_endpoints_resolved,
            "exact_semantic_span_binding": exact_semantic_span_binding,
            "blocked_breakdown": blocked_breakdown,
            "blocked_reason": (
                "no endpoint-to-physical-entity classifier exists yet at this layer "
                "(target_entity_id + semantic_span_kind are not derivable from raw "
                "PDF evidence alone) -- explicitly future work, see module docstring"
            ),
        }
    finally:
        doc.close()


def main() -> None:
    results = [_census_one(spec) for spec in PROJECTS]
    print(json.dumps(results, indent=2))
    out_path = REPO_ROOT / "scripts" / "figured_dimension_span_authority_real_drawing_shadow_output.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nwritten to {out_path}")


if __name__ == "__main__":
    main()
