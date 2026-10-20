"""GPT3 producer-owned opening lineage supplement; never changes v1 seals.

Version 1 sealed source-closed quantities authenticate their original page,
viewport, document, revision, physical ID and evidence IDs. This separately
fingerprinted audit receipt adds only the snapshot and *source-producer-owned*
decision scope, without altering any original signed quantity or customer row.
It is not a benchmark crosswalk, new issuer, or commercial release authority.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject, LivePhysicalOpeningVoidComposition,
)
from pb_live_wall_opening_authority_composition import LiveOpeningHostTrace
from pb_migration_contracts import EvidenceResolutionStatus, canonical_contract_json
from pb_opening_host_binding_authority import OpeningHostBindingSelector
from pb_source_closed_run_export import (
    SealedSourceClosedRun, sealed_source_closed_run_from_dict,
)


GPT3_OPENING_SCOPE_SUPPLEMENT_SCHEMA_VERSION = "gpt3.opening_producer_scope.v1"


class ProducerScopeLineageConflict(ValueError):
    """Missing, stale, ambiguous or contradictory original source identity."""


def _index(rows, field: str, *, role: str) -> dict[str, object]:
    result = {}
    if type(rows) not in (tuple, list):
        raise ProducerScopeLineageConflict(f"{role} must be a source-owned sequence")
    for row in rows:
        identifier = getattr(row, field, None)
        if (type(identifier) is not str or not identifier
                or identifier != identifier.strip() or identifier in result):
            raise ProducerScopeLineageConflict(f"{role} has duplicate/unusable identity")
        result[identifier] = row
    return result


def source_owned_opening_scope_supplement(
    composition: LivePhysicalOpeningVoidComposition,
    *,
    producer_binding_selectors: Mapping[str, OpeningHostBindingSelector],
    producer_host_traces: Sequence[LiveOpeningHostTrace],
    sealed_run: SealedSourceClosedRun,
    customer_rows: Sequence[Mapping[str, object]],
) -> dict:
    """Prove exact snapshot+decision scope on an already sealed opening run.

    The complete source producer's opening selector universe, rather than
    user-supplied scope tokens, is required. No token is inferred from a page,
    physical label, wall proximity, quantity metadata or archive contents.
    """
    if (type(composition) is not LivePhysicalOpeningVoidComposition
            or type(sealed_run) is not SealedSourceClosedRun
            or not isinstance(producer_binding_selectors, Mapping)):
        raise TypeError("typed source composition, producer selectors and sealed run required")
    valid_seal = sealed_source_closed_run_from_dict(sealed_run.to_dict())
    customer_verification = verify_sealed_customer_output(
        valid_seal, customer_rows
    )
    original_quantities = publish_live_opening_area_quantities(composition)
    issuer = _index(original_quantities, "quantity_id", role="real opening-area issuer")
    sealed = _index(valid_seal.quantities, "quantity_id", role="v1 signed quantity")
    if (not issuer or set(issuer) != set(sealed)
            or set(issuer) != set(customer_verification.verified_quantity_ids)):
        raise ProducerScopeLineageConflict(
            "original issuer, v1 sealed and customer quantity universes differ"
        )
    physical = _index(
        composition.canonical_openings, "physical_opening_id",
        role="complete physical opening producer inventory",
    )
    if (not physical or any(
        type(item) is not LiveCanonicalOpeningObject
        or item.canonical_opening_id != identifier
        or item.revision_id != composition.revision_id
        for identifier, item in physical.items()
    )):
        raise ProducerScopeLineageConflict(
            "canonical/physical source opening inventory is inconsistent"
        )
    if set(producer_binding_selectors) != set(physical):
        raise ProducerScopeLineageConflict(
            "missing or foreign producer decision scope for physical opening"
        )
    hosts = _index(
        producer_host_traces, "opening_identity_id",
        role="producer opening-to-host trace",
    )
    if set(hosts) != set(physical):
        raise ProducerScopeLineageConflict(
            "complete producer host trace universe differs from physical openings"
        )
    if sealed_run.project_id != customer_verification.project_id:
        raise ProducerScopeLineageConflict("source project/customer verification mismatch")

    # Every source-owned scope supplement also binds the exact existing V1
    # customer projection fingerprint. The customer adapter's independent
    # verifier has already checked those original fingerprints and notes.
    # Never derive a projection identity from a label or quantity amount.
    customer_by_id: dict[str, Mapping[str, object]] = {}
    for customer in customer_rows:
        if not isinstance(customer, Mapping):
            raise ProducerScopeLineageConflict(
                "source customer projection must be a mapping"
            )
        quantity_id = customer.get("quantity_id")
        if (
            type(quantity_id) is not str
            or not quantity_id or quantity_id != quantity_id.strip()
            or quantity_id in customer_by_id
        ):
            raise ProducerScopeLineageConflict(
                "missing or reused original source customer quantity ID"
            )
        customer_by_id[quantity_id] = customer
    if set(customer_by_id) != set(issuer):
        raise ProducerScopeLineageConflict(
            "source quantity/customer projection identity mapping changed"
        )

    owner_ids = set()
    entries = []
    for quantity in sorted(original_quantities, key=lambda row: row.quantity_id):
        row = sealed[quantity.quantity_id]
        if (
            len(quantity.input_entity_ids) != 1
            or quantity.family != "opening_area"
            or quantity.abstained
            or not row.lineage_ok
            or tuple(row.object_identity_refs) != tuple(quantity.input_entity_ids)
            or tuple(sorted(row.evidence_ids)) != tuple(sorted(quantity.evidence_ids))
            or row.value != quantity.value
            or row.authority != quantity.authority
            or row.source_sha256 != quantity.metadata.get("source_sha256")
        ):
            raise ProducerScopeLineageConflict(
                "original producer area differs from immutable v1 signed source receipt"
            )
        opening_id = quantity.input_entity_ids[0]
        if opening_id in owner_ids or opening_id not in physical:
            raise ProducerScopeLineageConflict(
                "duplicate or foreign physical source opening quantity"
            )
        owner_ids.add(opening_id)
        opening = physical[opening_id]
        selector = producer_binding_selectors[opening_id]
        host = hosts[opening_id]
        if (
            type(selector) is not OpeningHostBindingSelector
            or type(host) is not LiveOpeningHostTrace
            or host.opening_identity_id != opening_id
            or host.representative_observation_id
            != opening.representative_observation_id
            or host.page_id != opening.page_id
            or host.record_id != opening.host_binding_record_id
            or host.host_wall_id != opening.host_wall_id
            or (
                host.record_id is not None
                and host.status is not EvidenceResolutionStatus.CORROBORATED
            )
            or not selector.decision_scope_id
            or not selector.snapshot_id
            or selector.opening_identity_id != opening_id
            or any(
                getattr(selector, field) != getattr(opening, field)
                for field in (
                    "document_id", "revision_id", "source_sha256",
                    "snapshot_id", "page_id",
                )
            )
            or row.document_id != selector.document_id
            or row.revision_id != selector.revision_id
            or row.source_sha256 != selector.source_sha256
            or row.source_page != selector.page_id
            or row.viewport_id != opening.viewport_id
        ):
            raise ProducerScopeLineageConflict(
                "source issuer does not own exact snapshot/decision scope/host lineage"
            )
        customer_fingerprint = customer_by_id[quantity.quantity_id].get(
            "commercial_projection_fingerprint"
        )
        if (
            type(customer_fingerprint) is not str
            or len(customer_fingerprint) != 64
            or any(ch not in "0123456789abcdef" for ch in customer_fingerprint)
        ):
            raise ProducerScopeLineageConflict(
                "existing V1 customer projection fingerprint unavailable"
            )
        entries.append({
            "quantity_id": quantity.quantity_id,
            "v1_customer_projection_fingerprint": customer_fingerprint,
            "v1_signed_quantity_fingerprint": row.fingerprint,
            "physical_opening_id": opening_id,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": opening.viewport_id,
            "decision_scope_id": selector.decision_scope_id,
            "host_binding_record_id": opening.host_binding_record_id,
            "host_frame_record_id": opening.host_frame_record_id,
            "representative_observation_id": opening.representative_observation_id,
        })
    payload = {
        "schema_version": GPT3_OPENING_SCOPE_SUPPLEMENT_SCHEMA_VERSION,
        "project_id": sealed_run.project_id,
        "parent_v1_source_closed_run_id": sealed_run.run_id,
        "parent_v1_source_closed_fingerprint": sealed_run.fingerprint,
        "original_verified_customer_quantity_ids": list(
            customer_verification.verified_quantity_ids
        ),
        "producer_scope_entries": entries,
        "benchmark_identity_mapping_authorized": False,
        "customer_release_authorized": False,
    }
    return {
        **payload,
        "fingerprint": sha256(
            canonical_contract_json(payload).encode("utf-8")
        ).hexdigest(),
    }


def verify_source_owned_opening_scope_supplement(
    supplement: Mapping[str, object],
    composition: LivePhysicalOpeningVoidComposition,
    *,
    producer_binding_selectors: Mapping[str, OpeningHostBindingSelector],
    producer_host_traces: Sequence[LiveOpeningHostTrace],
    sealed_run: SealedSourceClosedRun,
    customer_rows: Sequence[Mapping[str, object]],
) -> None:
    """Reprove every source record and reject even self-consistent fake scope."""
    if type(supplement) is not dict:
        raise ProducerScopeLineageConflict("original source lineage supplement must be a JSON object")
    try:
        canonical_wire = json.loads(canonical_contract_json(supplement))
    except (TypeError, ValueError, OverflowError) as exc:
        raise ProducerScopeLineageConflict("source lineage supplement is not strict JSON") from exc
    authentic = source_owned_opening_scope_supplement(
        composition,
        producer_binding_selectors=producer_binding_selectors,
        producer_host_traces=producer_host_traces,
        sealed_run=sealed_run,
        customer_rows=customer_rows,
    )
    if canonical_wire != authentic:
        raise ProducerScopeLineageConflict(
            "scope sidecar or parent receipt differs from the live source producer"
        )
