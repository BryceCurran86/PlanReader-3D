"""Reissue live, typed canonical producer objects into the existing registry.

This adapter never discovers an object, resolves identity, calculates a quantity,
or creates a customer row. Missing physical identity or source lineage is an
explicit gap. Only original QuantityEvidence and explicitly supplied output rows
can supply dependencies.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_canonical_roof_projection import LiveCanonicalRoofObject
from pb_live_canonical_room_composition import LiveCanonicalRoomObject
from pb_live_canonical_slab_projection import LiveCanonicalSlabObject
from pb_live_canonical_structural_member_projection import LiveCanonicalStructuralMemberObject
from pb_live_canonical_wall_finish_surface import LiveCanonicalWallFinishSurfaceObject
from pb_live_ceiling_lining_integration import LiveCanonicalCeilingSurfaceObject
from pb_live_external_physical_net_wall_publication import LiveCanonicalWallObject
from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_takeoff_coverage_registry import (
    ENUMERATION_COMPLETE,
    ENUMERATION_INCOMPLETE,
    ENUMERATION_UNAVAILABLE,
    CoverageRegistryRunManifestV1,
    CoverageRegistrySummaryV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    TakeoffOutputRowUniverseSnapshotV1,
    build_coverage_registry_v1,
)
from pb_takeoff_output_authority import TakeoffOutputRow


# Explicit types only: a dictionary, W10 display object or look-alike cannot
# become an admitted object by presenting similarly named fields.
_PRODUCERS = {
    LiveCanonicalWallObject: ("wall", "canonical_wall_id", "physical_wall_id", "pb_live_canonical_wall_composition"),
    LiveCanonicalOpeningObject: ("opening", "canonical_opening_id", "physical_opening_id", "pb_live_physical_opening_void_composition"),
    LiveCanonicalRoomObject: ("room", "canonical_room_id", "physical_room_id", "pb_live_canonical_room_composition"),
    LiveCanonicalFloorSurfaceObject: ("floor", "canonical_floor_id", "canonical_floor_id", "pb_live_canonical_floor_surface"),
    LiveCanonicalSlabObject: ("slab", "canonical_slab_id", "slab_id", "pb_live_canonical_slab_projection"),
    LiveCanonicalCeilingSurfaceObject: ("ceiling", "canonical_ceiling_id", "canonical_ceiling_id", "pb_live_ceiling_lining_integration"),
    LiveCanonicalRoofObject: ("roof", "canonical_roof_id", "canonical_roof_id", "pb_live_canonical_roof_projection"),
    LiveCanonicalWallFinishSurfaceObject: ("finish_surface", "canonical_surface_id", "canonical_surface_id", "pb_live_canonical_wall_finish_surface"),
    LiveCanonicalStructuralMemberObject: ("structural_member", "canonical_structural_member_id", "physical_member_id", "pb_live_canonical_structural_member_projection"),
}


def _lineage(obj: object) -> tuple[str, str, str, str]:
    if type(obj) is LiveCanonicalStructuralMemberObject:
        provenance = obj.provenance
        return tuple(str(provenance.get(f"selector_{field}") or "").strip() for field in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
        ))
    return tuple(str(getattr(obj, field, "") or "").strip() for field in (
        "document_id", "revision_id", "source_sha256", "snapshot_id",
    ))


def _physical_identity_resolved(obj: object) -> bool:
    if type(obj) is LiveCanonicalWallObject:
        return obj.physical_identity_resolved is True and bool(obj.physical_wall_id)
    if type(obj) is LiveCanonicalFloorSurfaceObject:
        return obj.physical_floor_surface_identity_resolved is True
    return True


def _metadata(obj: object, category: str, canonical_id: str, quantities: Sequence[QuantityEvidence]) -> dict:
    evidence_ids = getattr(obj, "evidence_ids", getattr(obj, "source_evidence_ids", ()))
    pages = getattr(obj, "page_ids", ()) or (
        getattr(obj, "page_id", getattr(obj, "source_page", None)),
    )
    return {
        "object_type": category,
        "source_pages": pages,
        # This is the producer's exact canonical identity. CANONICALIZED does
        # not claim that every metric dimension or 3D coordinate is complete.
        "geometry_ids": (canonical_id,),
        "evidence_ids": tuple(evidence_ids),
        "host_wall_id": getattr(obj, "host_wall_id", getattr(obj, "canonical_wall_id", None)) if category != "wall" else None,
        "provenance": {
            "canonical_object_id": canonical_id,
            "geometry_complete": getattr(obj, "geometry_complete", False),
            "metric_geometry_complete": getattr(obj, "metric_geometry_complete", False),
            # Original aggregate values stay aggregate: never divide them among
            # member objects. These fields verify the customer row, not geometry.
            "quantity_evidence_values": {q.quantity_id: q.value for q in quantities},
            "quantity_evidence_units": {q.quantity_id: q.unit for q in quantities},
            "quantity_evidence_statuses": {q.quantity_id: q.status for q in quantities},
        },
    }


def collect_live_canonical_coverage(
    *,
    objects: Sequence[object],
    quantities: Sequence[QuantityEvidence] = (),
    output_rows: Sequence[TakeoffOutputRow] | None = None,
    registry_run_scope: str,
) -> tuple[tuple[CoverageRegistrySummaryV1, ...], dict[str, list[str]]]:
    """Enumerate only source-proven typed producer identities, without promotion.

    None output_rows means the customer/output collection was not enumerated;
    an explicit empty collection means it was enumerated and produced no rows.
    Separate source snapshots are never combined. Quantities join ONLY through
    their original input_entity_ids. Equal values, labels, marks or evidence IDs
    do not create links.
    """
    if not str(registry_run_scope or "").strip():
        raise ValueError("registry_run_scope is required")
    if any(type(q) is not QuantityEvidence for q in quantities):
        raise TypeError("quantities must contain original QuantityEvidence")
    if output_rows is not None and any(type(row) is not TakeoffOutputRow for row in output_rows):
        raise TypeError("output_rows must contain TakeoffOutputRow")

    groups: dict[tuple, list] = defaultdict(list)
    gaps: dict[str, set[str]] = defaultdict(set)
    for obj in objects:
        descriptor = _PRODUCERS.get(type(obj))
        if descriptor is None:
            raise TypeError("objects must contain supported live canonical producer types")
        category, canonical_field, physical_field, producer = descriptor
        if type(obj) is LiveCanonicalOpeningObject and obj.opening_kind in {"door", "window"}:
            gaps["door_window"].add("door_window_reuses_opening_identity_without_filling_identity")
        lineage = _lineage(obj)
        if not all(lineage):
            gaps[category].add("producer_source_lineage_unavailable")
            continue
        groups[(lineage, category, producer, canonical_field, physical_field)].append(obj)

    summaries: list[CoverageRegistrySummaryV1] = []
    for key, group in sorted(groups.items()):
        lineage, category, producer, canonical_field, physical_field = key
        document_id, revision_id, sha256, snapshot_id = lineage
        run_id = stable_contract_id("live_coverage", {
            "scope": registry_run_scope, "lineage": lineage, "producer": producer,
            "category": category,
        })
        common = dict(source_document_id=document_id, revision_id=revision_id,
                      source_sha256=sha256, snapshot_id=snapshot_id, registry_run_id=run_id)
        admitted: dict[str, object] = {}
        reasons: set[str] = set()
        for obj in group:
            physical_id = str(getattr(obj, physical_field) or "").strip()
            canonical_id = str(getattr(obj, canonical_field) or "").strip()
            if not physical_id or not canonical_id or not _physical_identity_resolved(obj):
                reasons.add("producer_physical_identity_unresolved")
                continue
            if physical_id in admitted:
                # Do not choose one of two competing canonical representations.
                raise ValueError(f"duplicate producer physical identity: {physical_id}")
            admitted[physical_id] = obj
        status = ENUMERATION_COMPLETE
        if reasons:
            gaps[category].update(reasons)
            status = ENUMERATION_INCOMPLETE if admitted else ENUMERATION_UNAVAILABLE

        object_key = (producer, category)
        quantity_key = (producer, "live_quantity_evidence")
        row_key = (producer, "customer_output_rows")
        manifest = CoverageRegistryRunManifestV1(
            **common, expected_object_universe_keys=(object_key,),
            expected_quantity_evidence_universe_keys=(quantity_key,),
            expected_takeoff_row_universe_keys=(row_key,),
        )
        snapshot = ProducerObjectUniverseSnapshotV1(
            **common, producer=producer, owning_authority=producer, category=category,
            admitted_object_ids=tuple(sorted(admitted)), enumeration_status=status,
            reason_codes=tuple(sorted(reasons)),
        )
        # A dependency is retained even if another input entity was not admitted:
        # the registry reports that defect, rather than inventing the other ID.
        linked = tuple(q for q in quantities if set(q.input_entity_ids).intersection(admitted))
        quantity_ids = {q.quantity_id for q in linked}
        rows = tuple(row for row in (output_rows or ()) if row.quantity_id in quantity_ids)
        quantity_snapshot = QuantityEvidenceUniverseSnapshotV1(
            **common, producer=quantity_key[0], source=quantity_key[1],
            quantity_ids=tuple(sorted(quantity_ids)), enumeration_status=ENUMERATION_COMPLETE,
        )
        row_snapshots = () if output_rows is None else (TakeoffOutputRowUniverseSnapshotV1(
            **common, source=row_key[0], collection=row_key[1],
            quantity_ids=tuple(row.quantity_id for row in rows), enumeration_status=ENUMERATION_COMPLETE,
        ),)
        summaries.append(build_coverage_registry_v1(
            manifest=manifest, object_universe_snapshots=(snapshot,),
            quantity_evidence_universe_snapshots=(quantity_snapshot,),
            takeoff_output_row_universe_snapshots=row_snapshots,
            quantity_evidence_by_universe={quantity_key: linked},
            takeoff_rows_by_universe={row_key: rows} if output_rows is not None else None,
            object_metadata_by_id={physical_id: _metadata(
                obj, category, str(getattr(obj, canonical_field)),
                tuple(q for q in linked if physical_id in q.input_entity_ids),
            )
                                   for physical_id, obj in admitted.items()},
        ))
    return tuple(summaries), {category: sorted(reasons) for category, reasons in sorted(gaps.items())}


__all__ = ["collect_live_canonical_coverage"]
