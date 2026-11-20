"""Review-only source window bridge ↔ canonical opening representative identity.

Several native observation fragments can yield different canonical opening
candidates for ONE original printed two-axis window. Never rank the nearest
candidate, combine source figures with the wrong PDF, or duplicate its area.
"""
from __future__ import annotations
from collections import Counter, defaultdict
from collections.abc import Iterable
import math
import re

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_source_native_figured_window_bridge_review import (
    NativeFiguredWindowBridgeReviewResult,
)
from pb_source_window_footprint_continuity import WindowFootprintBridge

_HEX64=re.compile(r"^[0-9a-f]{64}$")


def _geometry_in_original_aperture(
    source_geometries: tuple[tuple[float,...],...],
    bounds: tuple[float,float,float,float],
) -> bool:
    if not isinstance(source_geometries,tuple):
        return False
    if (
        type(bounds) is not tuple or len(bounds)!=4
        or any(type(n) not in (int,float) or not math.isfinite(n) for n in bounds)
        or bounds[2]<=bounds[0] or bounds[3]<=bounds[1]
    ):
        return False
    for geom in source_geometries:
        if (
            type(geom) is not tuple or len(geom)!=4
            or any(type(n) not in (int,float) or not math.isfinite(n) for n in geom)
        ):
            continue
        x0,y0,x1,y1=geom
        if (
            bounds[0]-1.25<=min(x0,x1)<=max(x0,x1)<=bounds[2]+1.25
            and bounds[1]-1.25<=min(y0,y1)<=max(y0,y1)<=bounds[3]+1.25
        ):
            return True
    return False


def compare_figured_window_source_to_canonical_representatives(
    figured: NativeFiguredWindowBridgeReviewResult,
    bridges: Iterable[WindowFootprintBridge],
    canonical_openings: Iterable[LiveCanonicalOpeningObject],
    *, expected_source_sha256: str,
) -> dict[str,object]:
    """Compare EXISTING original-source evidence with EXISTING canonical objects.

    Output never contains original physical object IDs, numeric quantities,
    private source text or a chosen billable opening.
    """
    if type(expected_source_sha256) is not str or _HEX64.fullmatch(expected_source_sha256) is None:
        raise ValueError("full_original_source_sha256_required")
    if (
        type(figured) is not NativeFiguredWindowBridgeReviewResult
        or figured.source_sha256!=expected_source_sha256
        or type(figured.page_index) is not int or figured.page_index<0
        or figured.physical_wall_authenticated is not False
        or figured.customer_quantity_authorized is not False
        or figured.frozen_benchmark_scored is not False
    ):
        raise ValueError("source_window_figure_review_untrusted")
    original_bridges=tuple(bridges)
    by_source_paths={}
    for b in original_bridges:
        if type(b) is not WindowFootprintBridge or b.page_index!=figured.page_index:
            continue
        if b.physical_wall_authenticated is not False or b.measurement_authorized is not False:
            raise ValueError("source_window_bridge_claimed_unsupported_authority")
        key=(b.left_host_path_id,b.right_host_path_id,tuple(b.marker_path_ids))
        if key in by_source_paths:
            raise ValueError("duplicate_native_source_window_bridge")
        by_source_paths[key]=b
    source_witnesses=tuple(figured.unique_source_figured_window_bridges)
    seen_receipts=set()
    figure_to_bridge={}
    for w in source_witnesses:
        if (
            w.source_sha256!=expected_source_sha256
            or w.page_index!=figured.page_index
            or w.physical_wall_authenticated is not False
            or w.customer_quantity_authorized is not False
            or w.metric_authorized is not False
            or w.frozen_benchmark_scored is not False
            or type(w.receipt_id) is not str or not w.receipt_id
            or w.receipt_id in seen_receipts
        ):
            raise ValueError("source_figured_window_witness_untrusted")
        seen_receipts.add(w.receipt_id)
        key=(w.native_host_path_ids[0],w.native_host_path_ids[1],
             tuple(w.native_window_marker_path_ids))
        b=by_source_paths.get(key)
        if b is None:
            raise ValueError("source_figured_window_has_no_exact_original_bridge")
        figure_to_bridge[w.receipt_id]=b
    source_candidates=tuple(canonical_openings)
    seen_canonical=set()
    memberships=defaultdict(list)
    source_kind_ambiguity=Counter()
    for opening in source_candidates:
        if (
            type(opening) is not LiveCanonicalOpeningObject
            or type(opening.canonical_opening_id) is not str
            or not opening.canonical_opening_id
            or opening.canonical_opening_id in seen_canonical
        ):
            raise ValueError("duplicate_or_untrusted_canonical_opening")
        seen_canonical.add(opening.canonical_opening_id)
        if (
            opening.source_sha256!=expected_source_sha256
            or opening.page_id!=str(figured.page_index+1)
        ):
            continue
        spans=[
            w.receipt_id for w in source_witnesses
            if _geometry_in_original_aperture(
                opening.source_geometries,
                figure_to_bridge[w.receipt_id].bounds_pdf_pts,
            )
        ]
        if len(spans)!=1:
            if len(spans)>1:
                source_kind_ambiguity["candidate_on_multiple_original_window_spans"]+=1
            continue
        if opening.opening_kind not in (None,"window"):
            source_kind_ambiguity["conflicting_existing_opening_type"]+=1
            continue
        memberships[spans[0]].append(opening)
    candidates_count=0
    hosted_count=0
    unique_host_witnesses=0
    multi_host_witnesses=0
    absent_canonical=0
    source_only_rows=[]
    for w in source_witnesses:
        rows=memberships[w.receipt_id]
        host_count=sum(bool(o.host_wall_id) for o in rows)
        candidates_count+=len(rows)
        hosted_count+=host_count
        unique_host_witnesses+=host_count==1
        multi_host_witnesses+=host_count>1
        absent_canonical+=not rows
        state=(
            "NO_CANONICAL_ORIGINAL_OPENING_SOURCE_WITNESS" if not rows
            else "UNIQUE_HOSTED_REPRESENTATIVE_REVIEW_ONLY" if host_count==1
            else "MULTIPLE_HOSTED_REPRESENTATIVES_REQUIRE_PHYSICAL_OWNER_PROOF"
                 if host_count>1 else "CANONICAL_CANDIDATES_WITHOUT_HOST_PROOF"
        )
        source_only_rows.append({
            "source_window_receipt_id":w.receipt_id,
            "canonical_representative_count":len(rows),
            "canonical_representatives_with_wall_id":host_count,
            "status":state,
            "physical_wall_authenticated":False,
            "opening_metric_authorized":False,
            "source_customer_row_authorized":False,
        })
    return {
        "status":"SOURCE_NATIVE_WINDOW_CANONICAL_OWNER_REVIEW_ONLY",
        "original_source_sha256":expected_source_sha256,
        "source_figured_window_witness_count":len(source_witnesses),
        "source_canonical_window_representative_count":candidates_count,
        "source_canonical_representatives_with_wall_id":hosted_count,
        "windows_with_one_wall_id_representative":unique_host_witnesses,
        "windows_with_competing_wall_id_representatives":multi_host_witnesses,
        "windows_without_any_canonical_opening_representation":absent_canonical,
        "ambiguous_canonical_multispan_count":source_kind_ambiguity["candidate_on_multiple_original_window_spans"],
        "conflicting_existing_door_type_count":source_kind_ambiguity["conflicting_existing_opening_type"],
        "window_source_review_rows":source_only_rows,
        "physical_wall_authenticated":False,
        "opening_metric_authorized":False,
        "customer_quantity_authorized":False,
        "official_benchmark_scored":False,
    }
