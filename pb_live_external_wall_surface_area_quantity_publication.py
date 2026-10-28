"""Original-source per-wall external net surface quantities.

A complete physical external-wall producer already computes a union-subtracted
net wall surface, but the previous output had only the aggregate. This adapter
reissues one real metric area per ORIGINAL physical wall. It never guesses a
second painted face, material or missing opening. Commercial finish permission
remains false until an independent source material occurrence owns the face.
"""
from __future__ import annotations

import math

from shapely import wkb
from shapely.geometry import box

from pb_net_wall_boolean_union_authority import subtract_void_union_from_wall_polygon

from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
    LiveCanonicalWallObject,
)
from pb_migration_contracts import (
    EvidenceResolutionStatus, QuantityEvidence, stable_contract_id,
)
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import SealedSourceClosedRun, seal_source_closed_run


def _exact_ids(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, (tuple, list)):
        return None
    if any(type(x) is not str or not x or x != x.strip() for x in value):
        return None
    if len(set(value)) != len(value):
        return None
    return tuple(value)


def _positive(value: object) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) and number > 0.0 else None


def publish_live_per_wall_surface_area_quantities(
    publication: LiveExternalPhysicalNetWallPublication,
) -> tuple[QuantityEvidence, ...]:
    """Release only a complete original external wall universe, never a subset.

    An invalid single wall poisons the whole family. Choosing the valid subset
    would quietly overstate wall finish completeness and lose opening members.
    """
    if type(publication) is not LiveExternalPhysicalNetWallPublication:
        raise TypeError("publication must be an original external wall result")
    if publication.status is not EvidenceResolutionStatus.CORROBORATED:
        return ()
    aggregate = publication.quantity_evidence
    if (
        type(aggregate) is not QuantityEvidence
        or aggregate.abstained
        # A non-abstained numeric source object can still carry unresolved
        # original wall/opening conflicts. Never reissue its area as separate
        # per-wall source-closed facts by dropping these blockers.
        or bool(aggregate.blocking_reasons)
        or aggregate.status != "corroborated"
        or aggregate.family != "wall_net_area"
        or aggregate.semantic_key != "perimeter_walling"
        or aggregate.unit != "m2"
        or aggregate.reason_codes != (
            "live_external_physical_net_wall_publication_resolved",
        )
    ):
        return ()
    agg_m2 = _positive(aggregate.value)
    walls = publication.canonical_walls
    ids = _exact_ids(publication.external_wall_ids)
    if (
        agg_m2 is None or not walls or ids is None
        or len(walls) != len(ids)
        or _exact_ids(aggregate.input_entity_ids) != ids
        or not isinstance(aggregate.metadata, dict)
        or _exact_ids(aggregate.metadata.get("external_wall_ids")) != ids
        or _exact_ids(aggregate.metadata.get("canonical_wall_object_ids")) !=
            tuple(wall.canonical_wall_id for wall in walls)
        or aggregate.metadata.get("deduction_policy") !=
            "physical_geometry_not_trade_finish_policy"
        or publication.revision_id != aggregate.metadata.get("revision_id")
    ):
        return ()
    # The upstream producer binds every original gross/role/void/universe
    # receipt and the metric total into one stable aggregate contract. A
    # copied QuantityEvidence with a changed receipt roster must not be
    # reissued as source-closed per-wall quantities merely because its total
    # and physical-wall IDs still agree. Recompute the original producer seal
    # before selecting any individual wall. This grants no new authority.
    source_rosters = (
        ("gross_geometry_record_ids", publication.gross_geometry_record_ids),
        ("whole_wall_role_record_ids", publication.whole_wall_role_record_ids),
        ("physical_void_record_ids", publication.physical_void_record_ids),
        ("opening_universe_record_ids", publication.opening_universe_record_ids),
    )
    if any(
        _exact_ids(roster) is None
        or _exact_ids(aggregate.metadata.get(name)) != tuple(roster)
        for name, roster in source_rosters
    ):
        return ()
    # Every external wall requires an independently completed original
    # opening-universe census, including when no physical openings exist.
    # The producer's evidence roster is also exact and ordered; a copied
    # aggregate may not omit a void or universe receipt while retaining its ID.
    original_evidence_ids = tuple(dict.fromkeys(
        receipt
        for _, roster in source_rosters
        for receipt in roster
    ))
    if (
        not publication.opening_universe_record_ids
        or _exact_ids(aggregate.evidence_ids) != original_evidence_ids
    ):
        return ()
    if (
        len(publication.gross_geometry_record_ids) != len(ids)
        or len(publication.whole_wall_role_record_ids) != len(ids)
        or tuple(w.gross_geometry_record_id for w in walls)
            != tuple(publication.gross_geometry_record_ids)
        or tuple(w.whole_wall_role_record_id for w in walls)
            != tuple(publication.whole_wall_role_record_ids)
        or tuple(
            void.physical_void_record_id
            for wall in walls for void in wall.opening_voids
        ) != tuple(publication.physical_void_record_ids)
    ):
        return ()
    expected_aggregate_id = stable_contract_id(
        "external_physical_net_wall_area",
        {
            "revision_id": publication.revision_id,
            "physical_wall_ids": ids,
            "gross_geometry_record_ids": tuple(
                publication.gross_geometry_record_ids
            ),
            "whole_wall_role_record_ids": tuple(
                publication.whole_wall_role_record_ids
            ),
            "physical_void_record_ids": tuple(publication.physical_void_record_ids),
            "opening_universe_record_ids": tuple(
                publication.opening_universe_record_ids
            ),
            "value_m2": agg_m2,
        },
    )
    if aggregate.quantity_id != expected_aggregate_id:
        return ()

    source_scope = None
    output = []
    net_areas = []
    seen = set()
    for wall in walls:
        if type(wall) is not LiveCanonicalWallObject:
            return ()
        if (
            wall.physical_wall_id != wall.canonical_wall_id
            or wall.canonical_wall_id not in ids
            or wall.canonical_wall_id in seen
            or wall.role != "external"
            or not wall.physical_identity_resolved
            or not wall.metric_geometry_complete
            or not wall.quantity_complete
            or wall.revision_id != publication.revision_id
            or type(wall.source_sha256) is not str
            or len(wall.source_sha256) != 64
            or any(c not in "0123456789abcdefABCDEF" for c in wall.source_sha256)
            or set(wall.source_sha256) == {"0"}
            or _exact_ids(wall.evidence_ids) is None
            or not wall.gross_geometry_record_id
            or not wall.whole_wall_role_record_id
            or len(wall.plan_members) == 0
            or len({m.viewport_id for m in wall.plan_members}) != 1
        ):
            return ()
        scope = (
            wall.document_id, wall.source_sha256.lower(),
            wall.revision_id, wall.snapshot_id,
        )
        if source_scope is None:
            source_scope = scope
        elif scope != source_scope:
            return ()
        gross_m2, net_m2 = _positive(wall.gross_area_m2), _positive(wall.net_area_m2)
        if gross_m2 is None or net_m2 is None or net_m2 > gross_m2 + 0.000001:
            return ()
        # The original producer computes net = gross - union(ALL physical
        # opening voids). The aggregate ID binds the receipt roster and total
        # area, not the individual net polygon's physical position. Replay
        # that exact existing boolean operation before source-closed reissue:
        # a different same-area WKB must never inherit original wall evidence.
        try:
            gross_polygon = wkb.loads(bytes.fromhex(wall.gross_polygon_wkb_hex))
            polygon = wkb.loads(bytes.fromhex(wall.net_polygon_wkb_hex))
            if any(
                not all(math.isfinite(float(v)) for v in (
                    opening.u0, opening.u1, opening.z0, opening.z1,
                ))
                or not (opening.u0 < opening.u1 and opening.z0 < opening.z1)
                for opening in wall.opening_voids
            ):
                return ()
            replayed_net = subtract_void_union_from_wall_polygon(
                gross_polygon,
                tuple(
                    box(opening.u0, opening.z0, opening.u1, opening.z1)
                    for opening in wall.opening_voids
                ),
            )
            actual_area = float(polygon.area)
            gross_polygon_area = float(gross_polygon.area)
        except Exception:
            # Malformed WKB, invalid void geometry and GEOS failures cannot
            # inherit the original producer's physical wall seal.
            return ()
        if (
            not gross_polygon.is_valid or gross_polygon.is_empty
            or not math.isfinite(gross_polygon_area)
            or not math.isclose(
                gross_polygon_area, gross_m2, rel_tol=0.0, abs_tol=0.000002
            )
            or not polygon.is_valid or polygon.is_empty
            or not math.isfinite(actual_area)
            or not math.isclose(actual_area, net_m2, rel_tol=0.0, abs_tol=0.000002)
            or not polygon.equals(replayed_net)
        ):
            return ()
        seen.add(wall.canonical_wall_id)
        net_areas.append(net_m2)
        source_evidence = tuple(sorted(set((
            *aggregate.evidence_ids, *wall.evidence_ids,
        ))))
        quantity_id = stable_contract_id("wall_net_area", {
            "physical_wall_id":wall.physical_wall_id,
            "source_revision":wall.revision_id,
            "source_sha256":wall.source_sha256.lower(),
            "wall_net_polygon_hex":wall.net_polygon_wkb_hex,
            "aggregate_quantity_id":aggregate.quantity_id,
            "area_m2":net_m2,
        })
        output.append(QuantityEvidence(
            quantity_id=quantity_id,
            family="wall_net_area",
            semantic_key=f"wall_net_area:{wall.physical_wall_id}",
            value=net_m2,
            unit="m2",
            input_entity_ids=(wall.physical_wall_id,),
            formula="original_external_wall_gross_polygon_minus_union_of_physical_voids",
            formula_version="1.0.0",
            evidence_ids=source_evidence,
            authority=aggregate.authority,
            status="corroborated",
            confidence=aggregate.confidence,
            abstained=False,
            blocking_reasons=(),
            reason_codes=("source_closed_single_external_wall_net_area",),
            metadata={
                "document_id": wall.document_id,
                "source_sha256":wall.source_sha256.lower(),
                "revision_id":wall.revision_id,
                "snapshot_id":wall.snapshot_id,
                "page_no":wall.page_id,
                "viewport_id":wall.plan_members[0].viewport_id,
                "gross_area_m2":gross_m2,
                "aggregate_quantity_id":aggregate.quantity_id,
                "gross_geometry_record_id":wall.gross_geometry_record_id,
                "whole_wall_role_record_id":wall.whole_wall_role_record_id,
                "commercial_finish_permission":False,
                "face_multiplicity":1,
            },
        ))
    if (
        seen != set(ids)
        or not math.isclose(
            round(math.fsum(net_areas), 6), agg_m2,
            rel_tol=0.0, abs_tol=0.000001,
        )
    ):
        return ()
    return tuple(sorted(output, key=lambda q:q.quantity_id))


def seal_live_per_wall_surface_area_run(
    publication: LiveExternalPhysicalNetWallPublication,
    *,
    workspace_id: int,
    project_id: str,
) -> SealedSourceClosedRun:
    """Seal per-wall physical net m²; material/customer permission is separate."""
    quantities = publish_live_per_wall_surface_area_quantities(publication)
    if not quantities:
        raise ValueError("no source-complete original external wall surfaces")
    walls = {w.canonical_wall_id:w for w in publication.canonical_walls}
    traces = {}
    for quantity in quantities:
        wall = walls[quantity.input_entity_ids[0]]
        traces[quantity.quantity_id] = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=project_id,
            document_id=wall.document_id,
            source_sha256=wall.source_sha256,
            source_page=wall.page_id,
            viewport_id=wall.plan_members[0].viewport_id,
            revision_id=wall.revision_id,
            current_revision_id=wall.revision_id,
            evidence_ids=tuple(quantity.evidence_ids),
            canonical_entity_ids=tuple(quantity.input_entity_ids),
            metadata={
                "producer":"original_external_physical_net_wall_union",
                "one_physical_face_only":True,
                "commercial_finish_permission":False,
            },
        )
    run = seal_source_closed_run(
        quantities,project_id=project_id,traces_by_quantity_id=traces
    )
    if (
        len(run.quantities)!=len(quantities)
        or any(not q.lineage_ok or q.abstained for q in run.quantities)
    ):
        raise ValueError("original per-wall source lineage could not seal")
    return run


__all__ = [
    "publish_live_per_wall_surface_area_quantities",
    "seal_live_per_wall_surface_area_run",
]

