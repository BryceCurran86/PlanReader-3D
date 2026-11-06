"""Append newly re-proven opening areas without reissuing previous receipts.

This composes existing canonical/quantity contracts. It does not relax an
issuer, resolve a scale, import an archive, or assign benchmark identities.
Each retained object keeps its own real source snapshot; no snapshot alias is
created between the two internally replayed original-source producers.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import math

from pb_live_opening_area_quantity_publication import (
    _opening_quantity, publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject, compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _indexed(rows, field, required_type):
    result = {}
    for row in rows:
        if type(row) is not required_type:
            raise TypeError("typed original opening source inventory required")
        key = getattr(row, field)
        if type(key) is not str or not key or key != key.strip() or key in result:
            raise SourceClosedRunConflictError("duplicate or invalid opening source identity")
        result[key] = row
    return result


def _physical_core(opening):
    return tuple(getattr(opening, field) for field in (
        "canonical_opening_id", "physical_opening_id", "document_id",
        "revision_id", "source_sha256", "page_id", "viewport_id",
        "semantic_class", "structural_pattern", "source_geometries",
    ))


def _measurement_core(quantity):
    return (
        *(getattr(quantity, field) for field in (
            "quantity_id", "family", "semantic_key", "value", "unit",
            "input_entity_ids", "formula", "formula_version", "authority",
            "status", "confidence", "abstained", "blocking_reasons",
        )),
        *(quantity.metadata.get(field) for field in (
            "document_id", "revision_id", "source_sha256", "page_no",
            "viewport_id", "physical_opening_id", "canonical_opening_id",
            "opening_kind", "area_basis",
        )),
    )


def _source_owned_metric_voids_overlap(left, right):
    """A negative only: two complete voids cannot occupy the same wall-local patch.

    Incomplete or differently scoped coordinates establish nothing. This is
    not an assertion of physical DISTINCT for disjoint figures, or a substitute
    for the physical-opening producer's opening-local versus wall-face proof.
    """
    if (
        left.geometry_complete is not True
        or right.geometry_complete is not True
        or not left.wall_local_frame_id
        or left.wall_local_frame_id != right.wall_local_frame_id
        or left.coordinate_unit != "metre"
        or right.coordinate_unit != "metre"
        or left.profile_kind != "rectangular_rough_opening"
        or right.profile_kind != "rectangular_rough_opening"
    ):
        return False
    intervals = tuple(
        (getattr(obj, a), getattr(obj, b))
        for obj in (left, right)
        for a, b in (("u0", "u1"), ("z0", "z1"))
    )
    if any(
        type(lo) not in (int, float) or type(hi) not in (int, float)
        or not math.isfinite(lo) or not math.isfinite(hi) or hi <= lo
        for lo, hi in intervals
    ):
        return False
    (lu0, lu1), (lz0, lz1), (ru0, ru1), (rz0, rz1) = intervals
    return (
        min(lu1, ru1) > max(lu0, ru0)
        and min(lz1, rz1) > max(lz0, rz0)
    )


def _canonical_source_proof(authority, opening):
    """An independently reissued physical record for this exact canonical source."""
    from pb_page_view_class_source_adapter import page_viewport_id
    from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority

    if type(authority) is not PhysicalOpeningAuthority:
        return None
    selector = ObservationSelector(
        document_id=opening.document_id, revision_id=opening.revision_id,
        source_sha256=opening.source_sha256, snapshot_id=opening.snapshot_id,
        observation_id=opening.representative_observation_id,
    )
    proof = authority.prove_existence(selector)
    record = proof.existence_record
    observation = getattr(proof.source_observation, "observation", None)
    viewport = (record.viewport_id if record is not None and record.viewport_id is not None
                else page_viewport_id(opening.page_id))
    if (
        proof.status is not EvidenceResolutionStatus.CORROBORATED
        or proof.proposition != PHYSICAL_OPENING_EXISTS
        or record is None or observation is None
        or record.record_id != opening.physical_opening_id
        or opening.canonical_opening_id != record.record_id
        or any(getattr(record, field) != getattr(opening, field) for field in (
            "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id",
            "semantic_class", "structural_pattern",
            "source_observation_ids", "source_lineage_root_ids",
        ))
        or opening.viewport_id != viewport
        or observation.observation_id != opening.representative_observation_id
        or opening.source_geometries != (tuple(float(v) for v in observation.geometry),)
    ):
        return None
    return selector, record


def _source_representative_reissue_is_authenticated(authority, previous, current):
    """Preserve an old unsupported object when only its source address reissues.

    The old line remains exact raw support of the same physical record. It is
    not forced to become a uniquely resolving physical selector in the fresh
    policy; the fresh representative independently re-proves that record.
    """
    from pb_source_observation_authority import SOURCE_OBSERVATION_EXISTS
    from pb_source_visibility_authority import (
        RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS, RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND,
        VISIBLE_SOURCE_OBSERVATION_EXISTS,
    )

    # Geometry here is the representative LINE, not an aperture boundary.
    readdressed = replace(previous, source_geometries=current.source_geometries)
    if (
        _physical_core(readdressed) != _physical_core(current)
        or previous.source_observation_ids != current.source_observation_ids
        or previous.source_lineage_root_ids != current.source_lineage_root_ids
        or previous.representative_observation_id not in current.source_observation_ids
    ):
        return False
    try:
        fresh = _canonical_source_proof(authority, current)
        if fresh is None:
            return False
        selector, _record = fresh
        old = authority.prove_existence(replace(
            selector, observation_id=previous.representative_observation_id,
        )).source_observation
        observation = getattr(old, "observation", None)
        return (
            old is not None and old.status is EvidenceResolutionStatus.CORROBORATED
            and observation is not None
            and (
                old.proposition == VISIBLE_SOURCE_OBSERVATION_EXISTS
                or (
                    # The physical authority obtains raster support through
                    # resolve_raster_opening_primitive, which revalidates its
                    # source/parent/geometry receipt then returns this raw
                    # proposition. It is not a native visibility receipt.
                    old.proposition == SOURCE_OBSERVATION_EXISTS
                    and observation.observation_kind in RASTER_OPENING_VISIBLE_PRIMITIVE_KINDS
                    and observation.origin_kind == RASTER_OPENING_VISIBLE_PRIMITIVE_ORIGIN_KIND
                )
            )
            and observation.observation_id == previous.representative_observation_id
            and all(getattr(observation, field) == getattr(current, field) for field in (
                "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id",
            ))
            and previous.source_geometries == (tuple(float(v) for v in observation.geometry),)
        )
    except Exception:
        return False


def _source_partition_proves_distinct(authority, left, right):
    """Reprove the exact canonical pair; never consume a caller receipt list."""
    from pb_physical_opening_authority import PhysicalOpeningPartitionReceipt

    selectors = []
    records = {}
    try:
        for opening in (left, right):
            proof = _canonical_source_proof(authority, opening)
            if proof is None:
                return False
            selector, record = proof
            selectors.append(selector)
            records[record.record_id] = record
        if len(records) != 2:
            return False
        receipt = authority.partition_receipt(*selectors)
        if (
            type(receipt) is not PhysicalOpeningPartitionReceipt
            or not receipt.is_physically_distinct
            or authority.verify_partition_receipt(receipt, *selectors) is not True
            or set(records) != {receipt.left_record_id, receipt.right_record_id}
            or receipt.grants_quantity is not False or receipt.grants_firm_authority is not False
        ):
            return False
        for side in ("left", "right"):
            record = records[getattr(receipt, f"{side}_record_id")]
            if (
                any(getattr(receipt, field) != getattr(record, field) for field in (
                    "document_id", "revision_id", "source_sha256", "snapshot_id", "page_id",
                    "producer_method", "producer_version", "producer_generation",
                ))
                or getattr(receipt, f"{side}_viewport_id") != record.viewport_id
                or getattr(receipt, f"{side}_source_observation_ids")
                != tuple(sorted(record.source_observation_ids))
            ):
                return False
        return receipt.shared_source_observation_ids == tuple(sorted(
            set(left.source_observation_ids) & set(right.source_observation_ids)
        ))
    except Exception:
        # Unreadable source or a failed receipt recomputation cannot partition
        # a rival. This never converts an upstream exception into a positive.
        return False


def _append_reproved_areas(baseline, openings, quantities, *, physical_opening_authority=None):
    """Composition only; caller owns original-source/host reauthentication."""
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim

    if type(baseline) is not LivePhysicalNetWallClaim:
        raise TypeError("original live claim required")
    old_objects = _indexed(baseline.canonical_openings, "canonical_opening_id", LiveCanonicalOpeningObject)
    fresh_objects = _indexed(openings, "canonical_opening_id", LiveCanonicalOpeningObject)
    old = _indexed(baseline.opening_quantity_evidence, "quantity_id", QuantityEvidence)
    fresh = _indexed(quantities, "quantity_id", QuantityEvidence)
    physical_claims = set()
    for inventory, objects in ((old, old_objects), (fresh, fresh_objects)):
        seen = set()
        for quantity in inventory.values():
            if quantity.family != "opening_area" or len(quantity.input_entity_ids) != 1:
                raise SourceClosedRunConflictError("foreign opening measurement family or identity")
            oid = quantity.input_entity_ids[0]
            if oid in seen:
                raise SourceClosedRunConflictError("duplicate measured physical opening")
            seen.add(oid)
            opening = objects.get(oid)
            authentic = _opening_quantity(opening) if opening is not None else None
            if authentic is None or authentic.to_dict() != quantity.to_dict():
                raise SourceClosedRunConflictError("opening measurement differs from canonical issuer")
            if inventory is old:
                physical_claims.add(oid)
    for qid, previous in old.items():
        current = fresh.get(qid)
        if current is None or _measurement_core(previous) != _measurement_core(current):
            raise SourceClosedRunConflictError("previously published opening measurement changed or disappeared")
        oid = previous.input_entity_ids[0]
        before, after = old_objects[oid], fresh_objects[oid]
        if (_physical_core(before) != _physical_core(after)
                or before.source_observation_ids != after.source_observation_ids
                or before.source_lineage_root_ids != after.source_lineage_root_ids):
            raise SourceClosedRunConflictError("previously published physical source ownership changed")
    additions = tuple(q for qid, q in sorted(fresh.items()) if qid not in old)
    if not additions:
        return baseline
    # This operation re-proves areas only. A complete count or net-wall
    # publication also depends on the opening universe and its semantics or
    # metric voids. Retaining those totals while enriching that universe would
    # require their own source-authority replay; never silently stale them.
    if baseline.opening_count_quantity_evidence or baseline.quantity_m2 is not None:
        raise SourceClosedRunConflictError(
            "opening recovery requires reproof of published count or net-wall scope"
        )
    replacements = {}
    roots = {(o.document_id, o.revision_id, o.source_sha256) for o in old_objects.values()}
    if len(roots) != 1:
        raise SourceClosedRunConflictError("original opening source root unavailable or ambiguous")
    # This source replay includes measured and unmeasured physical rivals. A
    # complete, independently re-proved roster must belong to ONE real source
    # snapshot; never turn mixed or copied snapshots into an append receipt.
    replay_scopes = {
        (o.document_id, o.revision_id, o.source_sha256, o.snapshot_id)
        for o in fresh_objects.values()
    }
    if (len(replay_scopes) != 1
            or any(type(value) is not str or not value or value != value.strip()
                   for scope in replay_scopes for value in scope)
            or next(iter(replay_scopes))[:3] not in roots
            or len({o.physical_opening_id for o in fresh_objects.values()}) != len(fresh_objects)):
        raise SourceClosedRunConflictError("complete opening replay source scope missing or conflicting")
    # The first producer's unsupported historical candidates are negative
    # evidence too. A second producer cannot assert its source replay is
    # complete while silently dropping one; an old measurement is not the
    # only kind of source rival that must survive. Independent source-owned
    # identity retirement is a different authority and must be explicit.
    missing_historical = set(old_objects) - set(fresh_objects)
    if missing_historical:
        raise SourceClosedRunConflictError(
            "historical opening competitor missing from complete source replay"
        )
    # Preserve every previously observed physical hypothesis, not just those
    # that already minted an area. A fresh replay may legitimately reissue
    # host or snapshot receipts; it may not quietly rewrite an old rival's
    # physical instance, representative, original ink, or source lineage to
    # conceal a conflict. A source-owned retirement would need its own
    # explicit, authenticated authority; no such authority is assumed here.
    for oid, previous in old_objects.items():
        current = fresh_objects[oid]
        if (
            _physical_core(previous) != _physical_core(current)
            or previous.representative_observation_id
            != current.representative_observation_id
            or previous.source_observation_ids != current.source_observation_ids
            or previous.source_lineage_root_ids != current.source_lineage_root_ids
        ):
            if (oid in physical_claims or physical_opening_authority is None
                    or not _source_representative_reissue_is_authenticated(
                        physical_opening_authority, previous, current,
                    )):
                raise SourceClosedRunConflictError(
                    "historical opening source identity changed during replay"
                )
    fresh_measured_ids = {q.input_entity_ids[0] for q in fresh.values()}
    # An unsupported-only sibling is negative evidence, never quietly omitted
    # from a new area. Shared exact observation members require a source-owned
    # physical partition; neither a different record ID nor a partial roster
    # intersection proves distinct apertures. Other rivals stay in the replay
    # inventory for downstream source-owned identity decisions.
    # An old canonical rival can be unmeasured too. Its presence in the
    # historical inventory does not certify the new measured aperture as
    # distinct, so preserve it in this negative-evidence census.
    unmeasured_rivals = tuple(
        o for oid, o in fresh_objects.items()
        if oid not in fresh_measured_ids
    )
    # A complete producer roster may have two *measured* source identities
    # that share an exact original observation. Different physical IDs or
    # quantities do not establish two openings. The composition step cannot
    # authenticate shared wall-face support versus a second reading of one
    # gap, so keep this source-partition-dependent case unissued. A future
    # positive exception must arrive through source-owned identity authority,
    # not a caller-supplied ID or an omitted rival.
    measured_openings = tuple(
        fresh_objects[q.input_entity_ids[0]] for q in fresh.values()
    )
    for quantity in additions:
        oid = quantity.input_entity_ids[0]
        if oid in physical_claims:
            raise SourceClosedRunConflictError("new quantity aliases an already measured physical opening")
        opening = fresh_objects[oid]
        if physical_opening_authority is not None:
            # Every fresh hypothesis counts, including unsupported candidates
            # absent from the old claim. An unequal ID or geometry is not a
            # physical partition. Only this replay's actual source authority
            # can release the shared-wall-support veto below.
            for peer in fresh_objects.values():
                if peer.canonical_opening_id != oid and not _source_partition_proves_distinct(
                    physical_opening_authority, opening, peer,
                ):
                    raise SourceClosedRunConflictError(
                        "fresh opening rival source partition unproven"
                    )
        for other in measured_openings:
            if other.canonical_opening_id == oid:
                continue
            if (
                other.physical_opening_id == opening.physical_opening_id
                or (
                    physical_opening_authority is None
                    and other.source_observation_ids
                    and opening.source_observation_ids
                    and not set(other.source_observation_ids).isdisjoint(
                        opening.source_observation_ids
                    )
                )
                or (
                    other.source_geometries
                    and other.source_geometries == opening.source_geometries
                )
                or _source_owned_metric_voids_overlap(other, opening)
            ):
                raise SourceClosedRunConflictError(
                    "measured opening rival requires source-owned physical partition"
                )
        for sibling in unmeasured_rivals:
            if (sibling.physical_opening_id == opening.physical_opening_id
                    or (
                        physical_opening_authority is None
                        and sibling.source_observation_ids
                        and opening.source_observation_ids
                        and not set(sibling.source_observation_ids).isdisjoint(
                            opening.source_observation_ids
                        )
                    )
                    or (
                        sibling.source_geometries
                        and sibling.source_geometries == opening.source_geometries
                    )
                    or _source_owned_metric_voids_overlap(sibling, opening)):
                raise SourceClosedRunConflictError(
                    "unmeasured opening rival aliases a new area"
                )
        if (opening.document_id, opening.revision_id, opening.source_sha256) not in roots:
            raise SourceClosedRunConflictError("new opening belongs to a foreign source root")
        if (
            oid in old_objects
            and _physical_core(old_objects[oid]) != _physical_core(opening)
            and (
                physical_opening_authority is None
                or not _source_representative_reissue_is_authenticated(
                    physical_opening_authority, old_objects[oid], opening,
                )
            )
        ):
            raise SourceClosedRunConflictError("new measurement changes an existing physical opening")
        if any(other.physical_opening_id != oid
               and other.source_observation_ids == opening.source_observation_ids
               and other.source_lineage_root_ids == opening.source_lineage_root_ids
               and other.source_geometries == opening.source_geometries
               for other in old_objects.values()):
            raise SourceClosedRunConflictError("new opening duplicates original physical source support")
        replacements[oid] = opening
    retained = tuple(replacements.pop(o.canonical_opening_id, o) for o in baseline.canonical_openings)
    return replace(
        baseline,
        canonical_openings=retained + tuple(replacements[key] for key in sorted(replacements)),
        opening_quantity_evidence=baseline.opening_quantity_evidence + additions,
        # Keep every exact fresh canonical sibling (including still-abstained
        # rivals), not only objects granted a new area. The customer seal
        # continues to consume canonical_openings/quantity_evidence only.
        opening_area_replay_source_inventory=tuple(
            fresh_objects[key] for key in sorted(fresh_objects)
        ),
    )


def recover_source_opening_areas(baseline, pdf_bytes, *, page_id, producer_version, single_width_uniform_page_door_height_shadow: bool = False):
    """Re-prove a single original topology page, then append only new areas."""
    digest = sha256(pdf_bytes).hexdigest()
    if not baseline.canonical_openings:
        return baseline
    if any(o.source_sha256 != digest for o in baseline.canonical_openings):
        raise SourceClosedRunConflictError("original PDF changed during opening source replay")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version=producer_version,
        raster_paired_outer_faces_shadow=True,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}", source_bytes=pdf_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(int(page_id),),
    )
    if not source.raster_opening_image_placements(published.revision.revision_id, page_id):
        # This recovery policy consumes original raster image evidence only.
        # An image-free native drawing keeps its independently valid native
        # claim; an empty raster universe never grants a new measurement.
        return baseline
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=(page_id,), include_unmeasured_ink_closed_flanks_shadow=True,
        source_fragment_roles_shadow=True,
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=composition,
        single_width_uniform_page_door_height_shadow=single_width_uniform_page_door_height_shadow,
    )
    quantities = publish_live_opening_area_quantities(voids)
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    for opening in voids.canonical_openings:
        if not any(q.input_entity_ids == (opening.canonical_opening_id,) for q in quantities):
            continue
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=opening.representative_observation_id,
        )
        proof = composition.physical_opening_authority.prove_existence(selector)
        record = proof.existence_record
        binding_selector = composition.binding_selectors.get(opening.physical_opening_id)
        host = (composition.opening_host_binding_authority.resolve(binding_selector)
                if binding_selector is not None else None)
        if (proof.status is not EvidenceResolutionStatus.CORROBORATED or record is None
                or record.record_id != opening.physical_opening_id
                or record.snapshot_id != opening.snapshot_id
                or record.source_observation_ids != opening.source_observation_ids
                or record.source_lineage_root_ids != opening.source_lineage_root_ids
                or host is None or host.status is not EvidenceResolutionStatus.CORROBORATED
                or host.record is None or host.record.record_id != opening.host_binding_record_id
                or host.record.host_wall_id != opening.host_wall_id):
            raise SourceClosedRunConflictError("recovered opening source or host receipt not authenticated")
    result = _append_reproved_areas(
        baseline, voids.canonical_openings, quantities,
        physical_opening_authority=composition.physical_opening_authority,
    )
    if source.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise SourceClosedRunConflictError("opening source snapshot changed during reproof")
    return result
