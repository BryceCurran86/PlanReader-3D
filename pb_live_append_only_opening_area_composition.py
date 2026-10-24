"""Append newly re-proven opening areas without reissuing previous receipts.

This composes existing canonical/quantity contracts. It does not relax an
issuer, resolve a scale, import an archive, or assign benchmark identities.
Each retained object keeps its own real source snapshot; no snapshot alias is
created between the two internally replayed original-source producers.
"""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

from pb_live_opening_area_quantity_publication import (
    _opening_quantity, publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject, compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_physical_opening_authority import PHYSICAL_OPENING_IDENTITIES_DISTINCT
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


def _append_reproved_areas(baseline, openings, quantities):
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
    for quantity in additions:
        oid = quantity.input_entity_ids[0]
        if oid in physical_claims:
            raise SourceClosedRunConflictError("new quantity aliases an already measured physical opening")
        opening = fresh_objects[oid]
        if (opening.document_id, opening.revision_id, opening.source_sha256) not in roots:
            raise SourceClosedRunConflictError("new opening belongs to a foreign source root")
        if oid in old_objects and _physical_core(old_objects[oid]) != _physical_core(opening):
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
    )


def recover_source_opening_areas(baseline, pdf_bytes, *, page_id, producer_version):
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
    )
    quantities = publish_live_opening_area_quantities(voids)
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    fresh_by_id = _indexed(voids.canonical_openings, "canonical_opening_id", LiveCanonicalOpeningObject)
    old_quantity_ids = {q.quantity_id for q in baseline.opening_quantity_evidence}
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
        if not any(q.quantity_id not in old_quantity_ids
                   and q.input_entity_ids == (opening.canonical_opening_id,) for q in quantities):
            continue
        # Distinctness is issued by the existing physical-opening authority,
        # within the fresh producer scope. Never infer it from a new string ID
        # or from a changed render/snapshot. Retain all baseline competitors.
        for previous in baseline.canonical_openings:
            if previous.physical_opening_id == opening.physical_opening_id:
                continue
            peer = fresh_by_id.get(previous.physical_opening_id)
            if peer is None:
                raise SourceClosedRunConflictError("original physical competitor missing from source replay")
            peer_selector = ObservationSelector(
                document_id=selector.document_id, revision_id=selector.revision_id,
                source_sha256=selector.source_sha256, snapshot_id=selector.snapshot_id,
                observation_id=peer.representative_observation_id,
            )
            distinct = composition.physical_opening_authority.compare_identity(selector, peer_selector)
            if (distinct.status is not EvidenceResolutionStatus.CORROBORATED
                    or distinct.proven_same
                    or distinct.physical_opening_identity != PHYSICAL_OPENING_IDENTITIES_DISTINCT):
                raise SourceClosedRunConflictError("new physical opening distinctness unproven")
    if source.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise SourceClosedRunConflictError("opening source snapshot changed during reproof")
    return _append_reproved_areas(baseline, voids.canonical_openings, quantities)
