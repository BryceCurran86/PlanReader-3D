"""Producer-verified G17/W4 source registration in original native image pixels.

Unlike a caller-shaped image/edge comparison, this handoff obtains BOTH the
G17 physical opening and ordinary W4 edge inventory from exact producer-owned
authorities. It grants NO physical equivalence, structural wall, host, frame,
measurement, count, customer output or benchmark authority.
"""
from __future__ import annotations

from collections.abc import Sequence
from hashlib import sha256

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_native_image_xref_scope import (
    native_g17_w4_pixel_registration_shadow,
    _line as _axis_line_for_native_xref,
)


def _blocked(reason, *, source_sha, page_id, opening_ids=()):
    return {
        "status": EvidenceResolutionStatus.ABSTAINED.value,
        "reason_codes": [reason],
        "source_sha256": source_sha,
        "page_id": page_id,
        "physical_opening_ids": sorted(opening_ids),
        "original_producer_scope_verified": False,
        "opening_roster_complete_proven": False,
        "complete_structural_wall_equivalence_proven": False,
        "source_parent_equivalence_granted": False,
        "host_binding_granted": False,
        "firm_area_granted": False,
        "opening_count_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
    }


def producer_bound_g17_w4_native_xref_shadow(
    source: SourceVisibilityProducer,
    *,
    wall_authority: PhysicalWallCandidateAuthority,
    wall_selector: PhysicalWallCandidateSelector,
    opening_selectors: Sequence[ObservationSelector],
):
    """Re-prove exact source roots and consume producer-owned wall/opening facts.

    The supplied opening selectors address records; they supply no geometry.
    This is an addressed SUBSET: an omitted opening cannot imply a negative or
    physical-universe completeness. The complete W4 candidate universe is
    derived by the existing page-scope wall authority.
    """
    if (type(source) is not SourceVisibilityProducer
            or type(wall_authority) is not PhysicalWallCandidateAuthority
            or type(wall_selector) is not PhysicalWallCandidateSelector):
        raise TypeError("existing sealed source/W4 authority and selector required")
    if not isinstance(opening_selectors, (tuple, list)) or not opening_selectors:
        raise ValueError("original physical opening selectors required")
    if any(type(x) is not ObservationSelector for x in opening_selectors):
        raise TypeError("opening source selectors must be typed and producer address-only")

    published = source.published_snapshot_for_revision(wall_selector.revision_id)
    if published is None:
        raise ValueError("original source revision was not published")
    root = ("document_id", "revision_id", "source_sha256", "snapshot_id")
    if (any(getattr(wall_selector, x) != (
            getattr(published.snapshot, x)
            if x == "snapshot_id" else getattr(published.revision, x))
            for x in root)
            or any(getattr(opening, x) != getattr(wall_selector, x)
                   for opening in opening_selectors for x in root)):
        raise ValueError("original W4/opening/source roots differ")
    if (not wall_selector.page_id.isdecimal()
            or wall_selector.decision_scope_id !=
            f"wall-source:page-{wall_selector.page_id}"):
        raise ValueError("complete original W4 page selector required")

    original = source._producer._store.source_bytes_by_revision.get(
        wall_selector.revision_id
    )
    if (type(original) is not bytes
            or sha256(original).hexdigest() != wall_selector.source_sha256):
        raise ValueError("immutable original source PDF bytes unavailable")

    scope = wall_authority.resolve_scope(wall_selector)
    if (scope.status is not EvidenceResolutionStatus.CORROBORATED
            or not scope.scope_complete
            or scope.proposition != PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
            or scope.equivalence is None
            or any(getattr(scope, x) != getattr(wall_selector, x)
                   for x in root + ("page_id", "decision_scope_id"))):
        return _blocked(
            "original_complete_w4_wall_source_scope_unavailable",
            source_sha=wall_selector.source_sha256,
            page_id=wall_selector.page_id,
        )

    opening_authority = source.physical_opening_authority()
    g17 = []
    physical_ids = []
    seen_selectors = set()
    seen_edge_ids = set()
    for selector in opening_selectors:
        if selector.observation_id in seen_selectors:
            return _blocked(
                "duplicate_original_opening_selector",
                source_sha=wall_selector.source_sha256,
                page_id=wall_selector.page_id,
                opening_ids=physical_ids,
            )
        seen_selectors.add(selector.observation_id)
        existing = opening_authority.prove_existence(selector)
        physical = existing.existence_record
        if (existing.status is not EvidenceResolutionStatus.CORROBORATED
                or existing.proposition != PHYSICAL_OPENING_EXISTS
                or physical is None
                or physical.page_id != wall_selector.page_id
                or any(getattr(physical, x) != getattr(wall_selector, x)
                       for x in root)):
            return _blocked(
                "original_g17_physical_opening_existence_unproven",
                source_sha=wall_selector.source_sha256,
                page_id=wall_selector.page_id,
                opening_ids=physical_ids,
            )
        if physical.record_id in physical_ids:
            return _blocked(
                "duplicate_original_g17_physical_identity",
                source_sha=wall_selector.source_sha256,
                page_id=wall_selector.page_id,
                opening_ids=physical_ids,
            )
        physical_ids.append(physical.record_id)
        local = build_opening_local_g17_wall_shadow(source, selector)
        if (local.physical_opening_id != physical.record_id
                or local.opening_host_granted
                or local.metric_quantity_granted
                or len(local.flanks) != 2
                or any(not f.source_ink_supported for f in local.flanks)):
            return _blocked(
                "original_g17_source_flanks_incomplete",
                source_sha=wall_selector.source_sha256,
                page_id=wall_selector.page_id,
                opening_ids=physical_ids,
            )
        for flank_index, flank in enumerate(local.flanks):
            for wall in flank.exact_coordinate_records:
                for f in wall.source_edge_fragments:
                    edge_id = f"{physical.record_id}:{flank_index}:{f.edge_id}"
                    if edge_id in seen_edge_ids:
                        return _blocked(
                            "original_g17_local_edge_address_collision",
                            source_sha=wall_selector.source_sha256,
                            page_id=wall_selector.page_id,
                            opening_ids=physical_ids,
                        )
                    seen_edge_ids.add(edge_id)
                    g17.append({"edge_id": edge_id,
                                "geometry_pdf_pts": tuple(f.geometry)})

    ordinary = []
    non_axis_w4_edges = []
    seen_w4 = set()
    for w in scope.records:
        if not w.wall_candidate_id or not w.physical_identity.usable:
            continue
        for f in w.source_edge_fragments:
            edge_id = f"{w.wall_candidate_id}:{f.edge_id}"
            if edge_id in seen_w4:
                return _blocked(
                    "original_w4_source_edge_address_collision",
                    source_sha=wall_selector.source_sha256,
                    page_id=wall_selector.page_id,
                    opening_ids=physical_ids,
                )
            seen_w4.add(edge_id)
            # The native-pixel lattice comparator is deliberately axis-only.
            # An authenticated diagonal W4 fragment is not evidence against
            # source existence, and MUST remain a typed excluded alternative,
            # rather than silently disappearing or crashing the whole page.
            if _axis_line_for_native_xref(tuple(f.geometry)) is None:
                non_axis_w4_edges.append(edge_id)
                continue
            ordinary.append({"edge_id": edge_id,
                             "geometry_pdf_pts": tuple(f.geometry)})
    if not g17 or not ordinary:
        return _blocked(
            "original_g17_or_w4_primitive_edges_unavailable",
            source_sha=wall_selector.source_sha256,
            page_id=wall_selector.page_id,
            opening_ids=physical_ids,
        )

    pixel = native_g17_w4_pixel_registration_shadow(
        original, expected_sha256=wall_selector.source_sha256,
        page_id=wall_selector.page_id, g17_edges=tuple(g17),
        w4_edges=tuple(ordinary),
    )
    if (source.published_snapshot_for_revision(wall_selector.revision_id) != published
            or wall_authority.resolve_scope(wall_selector) != scope
            or sha256(source._producer._store.source_bytes_by_revision[
                wall_selector.revision_id
            ]).hexdigest() != wall_selector.source_sha256):
        raise RuntimeError("original producer source/W4 snapshot changed during audit")
    return {
        **pixel,
        "status": "producer_owned_native_xref_registration_shadow",
        "physical_opening_ids": sorted(physical_ids),
        "original_producer_scope_verified": True,
        "g17_source_edges_reissued": len(g17),
        "ordinary_w4_edges_reissued": len(ordinary),
        "ordinary_w4_non_axis_source_edges_excluded": sorted(non_axis_w4_edges),
        "opening_roster_complete_proven": False,
        "complete_structural_wall_equivalence_proven": False,
        "source_parent_equivalence_granted": False,
        "host_binding_granted": False,
        "firm_area_granted": False,
        "opening_count_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
    }
