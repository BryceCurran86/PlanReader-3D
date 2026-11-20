"""Evidence-only correspondence between source-hosted sliding spans and native openings.

A single source aperture may generate several different physical-opening
candidate observation IDs (left jamb, centre mark, right jamb). A new issuer
must not assume these are three installed doors. This reviewer NEVER assigns
one canonical opening to a wall, proves a metric or publishes a quantity.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import math
import re

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_migration_contracts import QuantityEvidence
from pb_source_sliding_door_footprint_continuity import ExteriorSlidingDoorFootprintBridge

_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


def _inside_one_source_span(
    geometry: tuple[float, ...], bounds: tuple[float, float, float, float],
    *, tolerance_pt: float = 1.25,
) -> bool:
    if (
        type(geometry) is not tuple or len(geometry) != 4
        or type(bounds) is not tuple or len(bounds) != 4
        or any(type(x) not in (int, float) or not math.isfinite(x)
               for x in (*geometry, *bounds))
        or bounds[2] <= bounds[0] or bounds[3] <= bounds[1]
    ):
        return False
    x0, y0, x1, y1 = geometry
    return (
        bounds[0]-tolerance_pt <= min(x0, x1) <= bounds[2]+tolerance_pt
        and bounds[0]-tolerance_pt <= max(x0, x1) <= bounds[2]+tolerance_pt
        and bounds[1]-tolerance_pt <= min(y0, y1) <= bounds[3]+tolerance_pt
        and bounds[1]-tolerance_pt <= max(y0, y1) <= bounds[3]+tolerance_pt
    )


def review_sliding_aperture_representative_owners(
    bridges: Iterable[ExteriorSlidingDoorFootprintBridge],
    canonical_openings: Iterable[LiveCanonicalOpeningObject],
    *,
    expected_source_sha256: str,
    published_quantities: Iterable[QuantityEvidence] = (),
) -> dict[str, object]:
    """Count native candidate representations for each *one* original span.

    Geometry helps to flag possible duplicate source representatives; it never
    proves they share one commercial opening identity. Conflicted overlaps,
    wrong source/page and duplicate identity all fail closed in review.
    """
    if type(expected_source_sha256) is not str or _SHA_RE.fullmatch(expected_source_sha256) is None:
        raise ValueError("full_original_source_sha256_required")
    source_bridges=tuple(bridges)
    candidates=tuple(canonical_openings)
    issued=tuple(published_quantities)
    seen_bridges=set()
    for b in source_bridges:
        if (
            type(b) is not ExteriorSlidingDoorFootprintBridge
            or type(b.page_index) is not int or b.page_index < 0
            or b.measurement_authorized is not False
            or b.physical_wall_authenticated is not False
            or type(b.first_host_path_id) is not int
            or type(b.second_host_path_id) is not int
            or b.first_host_path_id == b.second_host_path_id
            or not _inside_one_source_span(
                (b.bounds_pdf_pts[0], b.bounds_pdf_pts[1],
                 b.bounds_pdf_pts[2], b.bounds_pdf_pts[3]), b.bounds_pdf_pts,
            )
        ):
            raise ValueError("untrusted_sliding_footprint_bridge")
        key=(b.page_index, tuple(sorted((b.first_host_path_id, b.second_host_path_id))),
             b.axis, b.bounds_pdf_pts)
        if key in seen_bridges:
            raise ValueError("duplicate_native_source_aperture_bridge")
        seen_bridges.add(key)
    seen_openings=set()
    match_counts=Counter()
    matching_by_id={}
    reviewed=0
    conflicted=0
    for opening in candidates:
        if type(opening) is not LiveCanonicalOpeningObject:
            raise ValueError("typed_producer_owned_openings_required")
        if (
            not isinstance(opening.canonical_opening_id, str)
            or not opening.canonical_opening_id
            or opening.canonical_opening_id in seen_openings
        ):
            raise ValueError("duplicate_or_missing_canonical_opening")
        seen_openings.add(opening.canonical_opening_id)
        if (
            opening.source_sha256 != expected_source_sha256
            or opening.opening_kind != "door"
            or type(opening.page_id) is not str
            or not opening.page_id.isdecimal()
        ):
            continue
        reviewed+=1
        matched=[]
        for index, b in enumerate(source_bridges):
            if int(opening.page_id) != b.page_index+1:
                continue
            if any(_inside_one_source_span(g,b.bounds_pdf_pts)
                   for g in opening.source_geometries):
                matched.append(index)
        if len(matched)>1:
            conflicted+=1
        elif len(matched)==1:
            match_counts[matched[0]]+=1
            matching_by_id[opening.canonical_opening_id]=matched[0]
    public_ids=set()
    for q in issued:
        if (
            type(q) is not QuantityEvidence or q.family != "opening_area"
            or len(q.input_entity_ids)!=1 or not q.input_entity_ids[0]
        ):
            raise ValueError("source_area_published_identity_invalid")
        ident=q.input_entity_ids[0]
        if ident in public_ids or ident not in seen_openings:
            raise ValueError("source_area_published_identity_duplicate_or_unowned")
        public_ids.add(ident)
    publication_by_bridge=Counter(
        matching_by_id[ident] for ident in public_ids if ident in matching_by_id
    )
    return {
        "status":"SOURCE_SLIDING_APERTURE_REPRESENTATIVE_REVIEW_ONLY",
        "source_original_sha256":expected_source_sha256,
        "source_bridge_count":len(source_bridges),
        "source_typed_door_candidates_reviewed":reviewed,
        "source_door_candidates_with_unique_bridge":sum(match_counts.values()),
        "source_door_candidates_overlapping_multiple_bridges":conflicted,
        "bridges_with_multiple_native_representatives":sum(n>1 for n in match_counts.values()),
        "native_representatives_on_multi_candidate_bridges":sum(n for n in match_counts.values() if n>1),
        "bridges_with_multiple_published_areas":sum(n>1 for n in publication_by_bridge.values()),
        "physical_opening_authenticated":False,
        "measurement_authorized":False,
        "commercial_publication_allowed":False,
        "benchmark_score_granted":False,
    }
