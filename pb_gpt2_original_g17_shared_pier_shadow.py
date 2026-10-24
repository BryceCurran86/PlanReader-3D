"""Original G17 dual-ended common-pier candidate, strictly SOURCE ONLY.

This is a narrow adapter to the existing reviewed GPT MAX two-ended-pier
geometric auditor. An authenticated *physical* opening + source-visible
parent receipts must independently pass the GPT2 original reproof before
they enter this helper. The auditor does NOT prove a complete page-wide
physical owner universe: an unselected third opening might share a face.
All existing physical-identity collision quarantine remains mandatory.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pb_gpt2_g17_opening_source_band_ownership_shadow import (
    OriginalG17OpeningFlankOwnership,
)
from pb_gpt2_raster_opening_parent_source_shadow import (
    RasterOpeningParentSourceHandoff,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tools.diag_gptmax_g17_shared_dual_end_piers import (
    audit_shared_original_g17_dual_end_piers,
)


@dataclass(frozen=True)
class OriginalG17SharedPierCandidateResult:
    status: str
    source_sha256: str
    source_sharing_pairs: tuple[dict, ...]
    submitted_physical_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    entire_original_opening_universe_authenticated: bool = False
    third_original_owner_excluded: bool = False
    physical_instance_conflict_exempted: bool = False
    w4_structural_wall_granted: bool = False
    opening_host_granted: bool = False
    opening_count_granted: bool = False
    metric_area_granted: bool = False
    customer_release_granted: bool = False


def audit_gpt2_original_g17_shared_piers_shadow(
    original_sources: Mapping[
        str, tuple[OriginalG17OpeningFlankOwnership,
                   RasterOpeningParentSourceHandoff]
    ],
) -> OriginalG17SharedPierCandidateResult:
    """Retain shared-face / distinct-end alternatives, NEVER release a host.

    A source-only candidate can be reported for two physical IDs even while
    BOTH remain quarantined in the independent physical ownership ledger.
    The provided subset cannot prove that no unselected third owner exists.
    """
    if not isinstance(original_sources, Mapping) or not original_sources:
        return OriginalG17SharedPierCandidateResult(
            "ABSTAIN", "", (), (), ("original_g17_source_roster_missing",),
        )
    digests: set[str] = set()
    # A uniform page *per owner* is insufficient: unrelated PDF pages may
    # contain identical geometry. Preserve one original canonical page across
    # ALL submitted owners before the source-only geometric delegate runs.
    original_pages: set[str] = set()
    indexed: dict[str, dict[str, dict]] = {}
    for physical_id, entry in original_sources.items():
        if (type(physical_id) is not str or not physical_id
                or type(entry) is not tuple or len(entry) != 2):
            return OriginalG17SharedPierCandidateResult(
                "ABSTAIN", "", (), (), ("original_g17_ownership_input_invalid",),
            )
        owner, parents = entry
        if (type(owner) is not OriginalG17OpeningFlankOwnership
                or type(parents) is not RasterOpeningParentSourceHandoff
                or owner.status is not EvidenceResolutionStatus.CORROBORATED
                or owner.physical_opening_id != physical_id
                or not owner.shadow_only
                or owner.host_binding_granted or owner.w4_wall_membership_granted
                or owner.firm_area_granted or owner.opening_count_granted
                or owner.whole_wall_frame_granted
                or owner.customer_publication_granted
                or parents.status != "SOURCE_ONLY_CANDIDATE"
                or not parents.shadow_only or parents.unresolved_parent_ids
                or parents.structural_host_granted
                or parents.whole_wall_frame_granted
                or parents.metric_quantity_granted
                or parents.customer_publication_granted
                or owner.source_sha256 != parents.source_sha256
                or not parents.lines):
            return OriginalG17SharedPierCandidateResult(
                "ABSTAIN", "", (), (), ("original_g17_source_owner_not_reproved",),
            )
        digests.add(owner.source_sha256)
        receipt_ids = [line.visible_observation_id for line in parents.lines]
        root_ids = [line.parent_observation_id for line in parents.lines]
        band_source_obs = tuple(sorted(
            line.visible_observation_id for line in parents.lines
            if line.observation_kind in ("raster_wall_band_face",
                                         "raster_wall_band_end")
        ))
        end_source_parents = tuple(sorted(
            line.parent_observation_id for line in parents.lines
            if line.observation_kind == "raster_wall_band_end"
        ))
        scoped_pages = {line.page_id for line in parents.lines}
        if (len(set(receipt_ids)) != len(receipt_ids)
                or len(set(root_ids)) != len(root_ids)
                or tuple(sorted(receipt_ids)) != owner.physical_source_observation_ids
                or tuple(sorted(root_ids)) != owner.authenticated_source_parent_ids
                or owner.authenticated_flank_source_visible_ids != band_source_obs
                or owner.authenticated_flank_end_parent_ids != end_source_parents
                or len(end_source_parents) != 2
                or set(root_ids) != set(parents.requested_parent_ids)
                or len(scoped_pages) != 1
                or any(type(page) is not str or not page.isdecimal()
                       or int(page) < 1 or str(int(page)) != page
                       for page in scoped_pages)
                or not receipt_ids):
            return OriginalG17SharedPierCandidateResult(
                "ABSTAIN", "", (), (),
                ("original_g17_source_parent_or_cap_ownership_conflict",),
            )
        original_pages.update(scoped_pages)
        inventory = {}
        for line in parents.lines:
            if (type(line.page_id) is not str or not line.page_id
                    or line.w4_wall_identity_granted
                    or line.host_binding_granted or line.opening_count_granted):
                return OriginalG17SharedPierCandidateResult(
                    "ABSTAIN", "", (), (), ("original_g17_parent_source_is_not_shadow",),
                )
            inventory[line.visible_observation_id] = {
                "id": line.visible_observation_id,
                "kind": line.observation_kind,
                "geometry_pdf_pts": list(line.geometry_pdf_points),
                "parents": [line.parent_observation_id],
            }
        indexed[physical_id] = inventory
    if len(digests) != 1:
        return OriginalG17SharedPierCandidateResult(
            "ABSTAIN", "", (), (),
            ("original_g17_pier_source_sha_scope_conflict",),
        )
    if len(original_pages) != 1:
        return OriginalG17SharedPierCandidateResult(
            "ABSTAIN", "", (), (),
            ("original_g17_cross_owner_page_scope_conflict",),
        )
    digest = next(iter(digests))
    try:
        report = audit_shared_original_g17_dual_end_piers(indexed)
    except (KeyError, TypeError, ValueError, OverflowError):
        return OriginalG17SharedPierCandidateResult(
            "ABSTAIN", digest, (), tuple(sorted(indexed)),
            ("original_g17_two_end_source_geometry_invalid",),
        )
    source_pairs = tuple(report["source_sharing_pairs"])
    positive = any(row.get("source_closed_pier_candidate") is True
                   for row in source_pairs)
    return OriginalG17SharedPierCandidateResult(
        "SOURCE_ONLY_SHARED_PIER_CANDIDATE" if positive
        else "SOURCE_ONLY_SHARED_FACE_CONFLICT",
        digest, source_pairs, tuple(sorted(indexed)),
        ("original_source_two_end_pier_candidate_unconfirmed_global_owner",)
        if positive else ("original_shared_faces_missing_distinct_owned_caps",),
    )
