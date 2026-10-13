"""Source-only G17 flank primitive/W4 ancestor audit for unresolved raster openings.

This is deliberately NOT an opening host resolver. It publishes exact original
source observation receipts and primitive ancestry for the FIRST unmapped G17
flank stage only. It must never choose a nearest wall, relax tolerances, infer
geometry or count/height, or publish an opening-area customer quantity.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector


UNMAPPED_G17_FLANK_REASONS = frozenset({
    "raster_source_band_left_source_primitive_unmapped",
    "raster_source_band_right_source_primitive_unmapped",
    "raster_source_band_left_local_wall_owner_unmapped",
    "raster_source_band_right_local_wall_owner_unmapped",
})


def _clean(value: object) -> str:
    return str(value or "").strip()


def audit_g17_unhosted_flank_original_ancestry(
    source_visibility_producer: object,
    published: object,
    composition: object,
) -> list[dict[str, Any]]:
    """List exact authenticated opening observations and only EXACT W4 source refs.

    The function is a passive source-authority observer. No source observation
    is reclassified and no physical candidate/host is created, even if its
    exact source line belongs to a W4 physical wall. An absent/unauthenticated
    source record is an explicit failure, not a silent inferred substitute.
    """
    revision=published.revision
    snapshot=published.snapshot
    visibility=source_visibility_producer.authority()
    opening_authority=composition.physical_opening_authority
    wall_authority=composition.physical_wall_candidate_authority
    wall_by_source: dict[tuple[str,str],list[dict[str,Any]]] = defaultdict(list)
    for scope in wall_authority._scopes.values():
        if scope.status is not EvidenceResolutionStatus.CORROBORATED:
            continue
        if (scope.source_sha256 != revision.source_sha256
                or scope.revision_id != revision.revision_id
                or scope.snapshot_id != snapshot.snapshot_id
                or not _clean(scope.page_id)):
            raise RuntimeError("foreign W4 scope in exact raster source lineage audit")
        for wall in scope.records:
            identity=wall.physical_identity
            if not identity.usable:
                continue
            wall_id=_clean(wall.wall_candidate_id)
            if not wall_id:
                raise RuntimeError("original W4 source candidate identity absent")
            for source_ref in identity.source_primitive_ids:
                if not _clean(source_ref):
                    continue
                wall_by_source[(str(scope.page_id),_clean(source_ref))].append({
                    "wall_candidate_id":wall_id,
                    "candidate_identity_id":identity.candidate_identity_id,
                    "decision_scope_id":scope.decision_scope_id,
                    "scope_complete":bool(scope.scope_complete),
                })
    result=[]
    source_inventory=frozenset(published.raster_opening_primitive_observation_ids)
    for trace in composition.opening_bindings:
        if trace.status is not EvidenceResolutionStatus.ABSTAINED:
            continue
        reasons=set(trace.reason_codes)
        if not reasons & UNMAPPED_G17_FLANK_REASONS:
            continue
        observed=_clean(trace.representative_observation_id)
        opening_id=_clean(trace.opening_identity_id)
        if not observed or not opening_id or trace.host_wall_id or trace.record_id:
            raise RuntimeError("unhosted source flank audit changed authentic opening ownership")
        selector=ObservationSelector(
            document_id=revision.document_id,
            revision_id=revision.revision_id,
            source_sha256=revision.source_sha256,
            snapshot_id=snapshot.snapshot_id,
            observation_id=observed,
        )
        existence=opening_authority.prove_existence(selector)
        source_opening=existence.existence_record
        if (existence.status is not EvidenceResolutionStatus.CORROBORATED
                or source_opening is None
                or source_opening.record_id != opening_id
                or source_opening.snapshot_id != snapshot.snapshot_id
                or source_opening.source_sha256 != revision.source_sha256):
            raise RuntimeError("unhosted flank no longer has original authenticated opening")
        if len(source_opening.source_observation_ids) != len(set(source_opening.source_observation_ids)):
            raise RuntimeError("duplicate source G17 observation addresses")
        source_rows=[]
        for oid in sorted(source_opening.source_observation_ids):
            if oid not in source_inventory:
                raise RuntimeError("G17 source observation outside authentic raster source inventory")
            child=ObservationSelector(
                document_id=revision.document_id,
                revision_id=revision.revision_id,
                source_sha256=revision.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                observation_id=oid,
            )
            receipt=visibility.resolve_raster_opening_primitive(child)
            observation=receipt.observation
            if (receipt.status is not EvidenceResolutionStatus.CORROBORATED
                    or observation is None
                    or observation.observation_id != oid
                    or observation.source_sha256 != revision.source_sha256
                    or observation.snapshot_id != snapshot.snapshot_id
                    or observation.page_id != source_opening.page_id):
                raise RuntimeError("G17 raster flank source observation unverified")
            source_ref=_clean(observation.source_primitive_ref)
            owners=wall_by_source.get((str(observation.page_id),source_ref),[])
            parents=[]
            for parent_id in sorted(observation.derivation_parent_ids):
                parent_selector=ObservationSelector(
                    document_id=revision.document_id,
                    revision_id=revision.revision_id,
                    source_sha256=revision.source_sha256,
                    snapshot_id=snapshot.snapshot_id,
                    observation_id=parent_id,
                )
                # The sealed source authority authenticates the original G17 parent;
                # the visibility facade has no generic resolve() method.
                parent_resolution=visibility._source_authority.resolve(parent_selector)
                parent=parent_resolution.observation
                if (parent_resolution.status is not EvidenceResolutionStatus.CORROBORATED
                        or parent is None or parent.observation_id != parent_id
                        or parent.source_sha256 != revision.source_sha256
                        or parent.snapshot_id != snapshot.snapshot_id
                        or parent.page_id != observation.page_id):
                    raise RuntimeError("G17 original producer derivation parent unverified")
                parent_source_ref=_clean(parent.source_primitive_ref)
                parents.append({
                    "observation_id":parent_id,
                    "observation_kind":parent.observation_kind,
                    "source_primitive_ref":parent_source_ref,
                    "geometry_pdf_pts":list(parent.geometry),
                    "exact_source_ref_w4_candidates":sorted(
                        wall_by_source.get((str(parent.page_id),parent_source_ref),[]),
                        key=lambda row:(row["decision_scope_id"],row["wall_candidate_id"])
                    ),
                })
            # No first/nearest selection: preserve all exact-source W4 owners,
            # including conflicting candidates or incomplete side-scope W4.
            source_rows.append({
                "observation_id":oid,
                "observation_kind":observation.observation_kind,
                "source_primitive_ref":source_ref,
                "geometry_pdf_pts":list(observation.geometry),
                "source_lineage_parent_ids":list(observation.derivation_parent_ids),
                "authenticated_source_parents":parents,
                "exact_source_ref_w4_candidates":sorted(
                    owners,key=lambda row:(row["decision_scope_id"],row["wall_candidate_id"])
                ),
            })
        result.append({
            "physical_opening_id":opening_id,
            "page_id":source_opening.page_id,
            "source_sha256":revision.source_sha256,
            "snapshot_id":snapshot.snapshot_id,
            "representative_observation_id":observed,
            "host_status":"abstained",
            "host_reason_codes":sorted(reasons),
            "source_g17_observations":source_rows,
            "host_granted":False,
            "aperture_geometry_complete_granted":False,
            "opening_height_or_count_granted":False,
            "metric_quantity_granted":False,
        })
    return sorted(result,key=lambda row:row["physical_opening_id"])
