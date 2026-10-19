"""Producer-owned original adjacent G17 shared-pier W2/W3/W4 reproof.

Consumes only a LIVE source-backed wall/opening composition and its identical
published source snapshot. Shared face/dual-end source identities are necessary,
not sufficient, for one structural wall or an opening host. This report grants
no host, frame, metric, count or customer quantity.
"""
from __future__ import annotations

from pb_live_wall_opening_authority_composition import LiveWallOpeningAuthorityComposition
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import PublishedVisibleSourceSnapshot
from tools.diag_gptmax_g17_shared_dual_end_piers import (
    audit_shared_original_g17_dual_end_piers,
)
from tools.diag_gptmax_g17_shared_pier_w2_shadow import (
    isolated_original_dual_end_w2_w4,
)


def original_shared_pier_candidate_w4_reproof(published, comp) -> dict:
    """Reissue every source parent; do not import caller-supplied opening rows."""
    if (type(published) is not PublishedVisibleSourceSnapshot
            or type(comp) is not LiveWallOpeningAuthorityComposition
            or tuple(comp.page_ids) != ("3",)
            or comp.revision_id != published.revision.revision_id):
        raise TypeError("exact original page-3 published source composition required")
    physical = comp.physical_opening_authority
    source = physical.source_visibility_authority()
    revision = published.revision
    snapshot = published.snapshot
    inventories = {}
    skipped_unresolved = []
    for trace in comp.opening_bindings:
        if trace.opening_identity_id is None:
            skipped_unresolved.append(trace.representative_observation_id)
            continue
        selector = ObservationSelector(
            document_id=revision.document_id,
            revision_id=revision.revision_id,
            source_sha256=revision.source_sha256,
            snapshot_id=snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        existence = physical.prove_existence(selector)
        opening = existence.existence_record
        if (existence.status is not EvidenceResolutionStatus.CORROBORATED
                or existence.proposition != PHYSICAL_OPENING_EXISTS
                or opening is None or opening.record_id != trace.opening_identity_id
                or opening.page_id != "3"
                or opening.document_id != selector.document_id
                or opening.revision_id != selector.revision_id
                or opening.source_sha256 != selector.source_sha256
                or opening.snapshot_id != selector.snapshot_id):
            raise ValueError("current original physical opening source issuer unavailable")
        owned = {}
        for observation_id in sorted(opening.source_observation_ids):
            result = source.resolve_raster_opening_primitive(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            o = result.observation
            if (result.status is not EvidenceResolutionStatus.CORROBORATED
                    or o is None or o.page_id != "3"
                    or not o.derivation_parent_ids):
                raise ValueError("original shared-pier source observation missing")
            owned[observation_id] = {
                "id": observation_id,
                "kind": o.observation_kind,
                "geometry_pdf_pts": list(o.geometry),
                "parents": sorted(o.derivation_parent_ids),
                "source_primitive_ref": o.source_primitive_ref,
            }
        previous = inventories.get(opening.record_id)
        if previous is not None and previous != owned:
            raise ValueError("one physical opening claims conflicting source rosters")
        inventories[opening.record_id] = owned

    source_result = audit_shared_original_g17_dual_end_piers(inventories)
    for pair in source_result["source_sharing_pairs"]:
        pair["isolated_original_W2_W3_W4_source_graph"] = (
            isolated_original_dual_end_w2_w4(
                pair, inventories, source_sha=revision.source_sha256,
                page_id="3",
            ) if pair["source_closed_pier_candidate"] else None
        )
    source_result.update({
        "source_sha256": revision.source_sha256,
        "source_snapshot_id": snapshot.snapshot_id,
        "source_revision_id": revision.revision_id,
        "selected_source_page_ids": ["3"],
        "producer_reproven_physical_opening_count": len(inventories),
        "unresolved_original_source_selectors": sorted(set(skipped_unresolved)),
        "all_g17_face_and_parent_ids_reproven_from_current_source": True,
        "shared_pier_structural_wall_role_proven": False,
        "shared_pier_host_equivalence_proven": False,
        "opening_host_or_frame_publication_granted": False,
        "metric_or_count_publication_granted": False,
        "customer_or_frozen_score_granted": False,
    })
    return source_result
