"""Replay original producer opening scopes for #2297; never a signed sidecar.

Only original PDF bytes and page selectors enter this boundary. No caller's
quantity, canonical object, source record or scope metadata is accepted. The
existing producer composes every object; the observer copies its real records.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def _pages(values):
    if type(values) not in (tuple, list):
        raise ValueError("source page selector sequence required")
    values = tuple(values)
    if not values or any(type(v) is not str or not v.isdecimal()
                         or int(v) < 1 or str(int(v)) != v for v in values):
        raise ValueError("canonical source page selectors required")
    if len(set(values)) != len(values):
        raise ValueError("duplicate source page selector")
    return tuple(sorted(values, key=int))


def _unique(rows, field):
    result = {}
    for row in rows:
        identity = getattr(row, field)
        if type(identity) is not str or not identity or identity in result:
            raise RuntimeError("missing or duplicate producer identity: " + field)
        result[identity] = row
    return result


def _observe(source, published, composition, voids):
    """Private observer; its inputs are freshly built in the public replay below."""
    root = {k: getattr(published.revision, k)
            for k in ("document_id", "revision_id", "source_sha256")}
    root["snapshot_id"] = published.snapshot.snapshot_id
    openings = _unique(voids.canonical_openings, "physical_opening_id")
    bindings = _unique(composition.opening_bindings, "opening_identity_id")
    frames = _unique(composition.host_frames, "opening_identity_id")
    traces = _unique(voids.traces, "opening_identity_id")
    if not (openings.keys() == bindings.keys() == frames.keys() == traces.keys()
            == composition.binding_selectors.keys()):
        raise RuntimeError("producer opening scope inventory disagreement")
    quantities = publish_live_opening_area_quantities(voids)
    _unique(quantities, "quantity_id")
    quantity_by_opening = {}
    for quantity in quantities:
        if len(quantity.input_entity_ids) != 1:
            raise RuntimeError("quantity physical identity unavailable")
        identity = quantity.input_entity_ids[0]
        if identity not in openings or identity in quantity_by_opening:
            raise RuntimeError("duplicate or foreign quantity physical identity")
        quantity_by_opening[identity] = quantity
    rows = []
    labels = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    for identity, opening in sorted(openings.items()):
        if any(getattr(opening, k) != v for k, v in root.items()):
            raise RuntimeError("canonical opening source root disagreement")
        selector = ObservationSelector(**root, observation_id=opening.representative_observation_id)
        proof = composition.physical_opening_authority.prove_existence(selector)
        record = proof.existence_record
        if (proof.status is not EvidenceResolutionStatus.CORROBORATED
                or proof.proposition != PHYSICAL_OPENING_EXISTS or record is None
                or record.record_id != identity or opening.canonical_opening_id != identity
                or any(getattr(record, k) != v for k, v in root.items())
                or record.page_id != opening.page_id
                or set(record.source_observation_ids) != set(opening.source_observation_ids)):
            raise RuntimeError("original physical opening receipt no longer authenticates")
        scope = composition.binding_selectors[identity]
        if (any(getattr(scope, k) != v for k, v in root.items())
                or scope.opening_identity_id != identity or scope.page_id != opening.page_id):
            raise RuntimeError("producer host selector source disagreement")
        binding = composition.opening_host_binding_authority.resolve(scope)
        host = binding.record
        if host is not None:
            if (binding.status is not EvidenceResolutionStatus.CORROBORATED
                    or any(getattr(host, k) != v for k, v in asdict(scope).items())
                    or host.record_id != opening.host_binding_record_id
                    or host.host_wall_id != opening.host_wall_id
                    or host.record_id != bindings[identity].record_id):
                raise RuntimeError("producer host record source disagreement")
        elif opening.host_binding_record_id is not None or opening.host_wall_id is not None:
            raise RuntimeError("canonical host has no original producer receipt")
        frame_selector = composition.host_frame_selectors.get(identity)
        frame = (composition.opening_host_frame_authority.resolve(frame_selector)
                 if frame_selector is not None else None)
        evidence = frame.evidence if frame is not None else None
        if evidence is not None:
            if (frame.status is not EvidenceResolutionStatus.CORROBORATED or host is None
                    or any(getattr(evidence.selector, k) != v for k, v in asdict(scope).items())
                    or evidence.host_binding_record_id != host.record_id
                    or evidence.host_wall_id != host.host_wall_id
                    or evidence.record_id != opening.host_frame_record_id
                    or evidence.record_id != frames[identity].record_id):
                raise RuntimeError("producer frame record source disagreement")
        elif opening.host_frame_record_id is not None:
            raise RuntimeError("canonical frame has no original producer receipt")
        quantity = quantity_by_opening.get(identity)
        label = labels.publish_scope(selector)
        if (quantity is not None and opening.area_basis == "figured_opening_label"
                and (label.status is not EvidenceResolutionStatus.CORROBORATED
                     or label.evidence is None
                     or label.evidence.opening_record_id != identity
                     or label.evidence.evidence_id != quantity.metadata.get("measurement_record_id")
                     or label.evidence.area_m2 != quantity.value)):
            raise RuntimeError("original figured measurement receipt no longer authenticates")
        trace = traces[identity]
        first_gate = ("host_wall_identity" if host is None else
                      "host_frame" if evidence is None else
                      "source_supported_area_measurement" if quantity is None else
                      "versioned_signed_scope_consumer")
        rows.append({
            "physical_opening_id": identity,
            "canonical_opening_id": opening.canonical_opening_id,
            **root, "page_id": opening.page_id, "viewport_id": opening.viewport_id,
            # A selector can exist while its positive host record does not.
            "decision_scope_id": host.decision_scope_id if host is not None else None,
            "attempted_host_selector": asdict(scope),
            "physical_existence_record": asdict(record),
            "host_record": asdict(host) if host is not None else None,
            "frame_record": asdict(evidence) if evidence is not None else None,
            "host_status": binding.status.value, "host_reason_codes": binding.reason_codes,
            "frame_status": frame.status.value if frame is not None else "abstained",
            "frame_reason_codes": frame.reason_codes if frame is not None else ("frame_selector_unavailable",),
            "measurement_trace": asdict(trace),
            "original_label_dimension_result": asdict(label),
            "quantity_id": quantity.quantity_id if quantity is not None else None,
            "quantity_measurement_record_id": (quantity.metadata.get("measurement_record_id")
                                               if quantity is not None else None),
            "first_failing_authority_stage": first_gate,
            "source_scope_record_replayed": host is not None,
            "signed_scope_verified": False,
        })
    return rows


def producer_opening_scope_receipt_report(original_pdf: bytes, *, page_ids,
                                         decoded_page_ids=None) -> dict:
    """Original-source replay, with explicit root selection and retained negatives.

    All-page and selected-page roots can differ. They are never aliased here.
    JSON output is portable evidence for independent review, not an authority
    token, signed quantity scope, new host, count, or benchmark match.
    """
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("original PDF bytes required; metadata is not source")
    selected = _pages(page_ids)
    decoded = _pages(decoded_page_ids) if decoded_page_ids is not None else None
    if decoded is not None and not set(selected) <= set(decoded):
        raise ValueError("topology pages must be decoded original pages")
    digest = sha256(original_pdf).hexdigest()
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub = source.ingest_native_pdf_bytes(document_id=f"live-source:{digest[:32]}",
        source_bytes=original_pdf, source_locator="memory://original-opening-scope.pdf",
        page_ids=decoded)
    if not {int(page) for page in selected} <= set(pub.coverage.decoded_pages):
        raise ValueError("selected source pages were not decoded")
    def compose():
        composition = compose_live_wall_opening_authority(source_visibility_producer=source,
            revision_id=pub.revision.revision_id, page_ids=selected)
        voids = compose_live_physical_opening_voids(source_visibility_producer=source,
            wall_opening_composition=composition)
        return composition, voids
    composition, voids = compose()
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    before = _retention(composition, voids, verify_customer_rows=True)
    rows = _observe(source, published, composition, voids)
    after_composition, after_voids = compose()
    if (_retention(after_composition, after_voids, verify_customer_rows=True) != before
            or source.published_snapshot_for_revision(pub.revision.revision_id) != published
            or source._producer.current_revision_id(published.revision.document_id) != pub.revision.revision_id
            or sha256(source._producer._store.source_bytes_by_revision[pub.revision.revision_id]).hexdigest() != digest
            or _observe(source, published, after_composition, after_voids) != rows):
        raise RuntimeError("original source scope or signed output changed during receipt read")
    return {"schema_version": "1.0.0", "status": "SOURCE_REPLAY_UNSIGNED_UNPUBLISHED",
        "source_sha256": digest, "document_id": published.revision.document_id,
        "revision_id": pub.revision.revision_id, "snapshot_id": published.snapshot.snapshot_id,
        "decoded_page_ids": tuple(str(v) for v in published.coverage.decoded_pages),
        "topology_page_ids": selected, "openings": rows,
        "opening_universe_results": {page: asdict(result) for page, result in
                                     sorted(composition.opening_universe_results.items())},
        "original_production_receipts": before,
        "all_original_source_host_frame_quantity_seal_customer_receipts_unchanged": True,
        "signed_scope_verified": False, "new_host_granted": False,
        "new_quantity_granted": False, "count_granted": False,
        "benchmark_score_granted": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--decoded-page-id", action="append")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = producer_opening_scope_receipt_report(args.pdf.read_bytes(), page_ids=args.page_id,
                                                  decoded_page_ids=args.decoded_page_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"openings": len(report["openings"]),
                      "host_scopes": sum(r["source_scope_record_replayed"] for r in report["openings"]),
                      "quantity_ids": sum(r["quantity_id"] is not None for r in report["openings"]),
                      "signed_scope_verified": False}))


if __name__ == "__main__":
    main()
