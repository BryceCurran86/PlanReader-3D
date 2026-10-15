"""Read-only GPT3 consumer join: live original producer scope -> verified V1 customer.

This is NOT a v2 source signature. Only original PDF bytes enter the producer
replay; a caller-provided exported scope JSON is never accepted as authority.
An output digest, if added downstream, cannot authenticate its own issuer.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from scripts.report_full_plan_v2_readiness import _parse_evidence_json
from tools.diag_gptmax_producer_opening_scope_receipts import (
    producer_opening_scope_receipt_report,
)

_SHA = re.compile(r"[0-9a-f]{64}\Z")
SCHEMA_VERSION = "gpt3.original_source_v1_consumer_diagnostic.v1"


class OriginalSourceScopeConsumerError(ValueError):
    """A supposedly bound source-scope / sealed-customer association disagrees."""


def _require(condition: bool, explanation: str) -> None:
    if not condition:
        raise OriginalSourceScopeConsumerError(explanation)


def _unique(rows: Sequence[Mapping[str, Any]], field: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        identity = row.get(field)
        _require(
            type(identity) is str and bool(identity) and identity == identity.strip()
            and identity not in result,
            "missing or reused original source identity: " + field,
        )
        result[identity] = row
    return result


def _is_stale(record: Mapping[str, Any]) -> bool:
    if record.get("is_stale") is True or record.get("is_superseded") is True:
        return True
    metadata = record.get("metadata")
    return isinstance(metadata, Mapping) and (
        metadata.get("is_stale") is True or metadata.get("is_superseded") is True
    )


def _verified_join(
    report: Mapping[str, Any],
    sealed_payload: Mapping[str, Any],
    customer_rows: Sequence[Mapping[str, Any]],
    *,
    expected_source_sha256: str,
    expected_snapshot_id: str,
    expected_project_id: str,
) -> dict[str, Any]:
    """Internal comparator. Only the public API below may issue its outcome."""
    _require(
        report.get("status") == "SOURCE_REPLAY_UNSIGNED_UNPUBLISHED"
        and report.get("signed_scope_verified") is False
        and report.get("all_original_source_host_frame_quantity_seal_customer_receipts_unchanged") is True,
        "original producer replay or retention status unavailable",
    )
    _require(
        report.get("source_sha256") == expected_source_sha256
        and report.get("snapshot_id") == expected_snapshot_id,
        "producer source SHA or selected source snapshot disagreement",
    )
    sealed = sealed_source_closed_run_from_dict(sealed_payload)
    verified = verify_sealed_customer_output(sealed, customer_rows)
    _require(
        sealed.project_id == expected_project_id
        and verified.project_id == expected_project_id
        and tuple(sealed.source_sha256s) == (expected_source_sha256,)
        and verified.valid_quantity_count == len(sealed.quantities)
        and verified.customer_row_count == len(sealed.quantities)
        and len(verified.verified_quantity_ids) == len(sealed.quantities),
        "V1 source, project or customer bijection disagreement",
    )
    _require(
        len(sealed.quantities) > 0
        and all(row.lineage_ok and not row.abstained for row in sealed.quantities),
        "scope proof requires only existing FIRM non-abstained V1 quantities",
    )
    producer = report.get("original_production_receipts")
    _require(isinstance(producer, Mapping), "original producer quantities unavailable")
    originals = _unique(producer.get("quantities", ()), "quantity_id")
    observed = _unique(
        [row for row in report.get("openings", ()) if row.get("quantity_id") is not None],
        "quantity_id",
    )
    sealed_by_id = {row.quantity_id: row for row in sealed.quantities}
    customers = _unique(customer_rows, "quantity_id")
    _require(
        set(originals) == set(observed) == set(sealed_by_id) == set(customers)
        and set(verified.verified_quantity_ids) == set(originals),
        "extra, missing, or unissued opening quantity/customer identity",
    )
    issued_hosts: set[str] = set()
    issued_measurements: set[str] = set()
    associations: list[dict[str, Any]] = []
    for quantity_id in sorted(originals):
        original = originals[quantity_id]
        observed_row = observed[quantity_id]
        sealed_row = sealed_by_id[quantity_id]
        customer = customers[quantity_id]
        host = observed_row.get("host_record")
        frame = observed_row.get("frame_record")
        physical = observed_row.get("physical_existence_record")
        _require(
            isinstance(host, Mapping) and isinstance(physical, Mapping)
            and observed_row.get("source_scope_record_replayed") is True
            and observed_row.get("signed_scope_verified") is False,
            "source-positive host/physical scope unavailable",
        )
        physical_id = observed_row.get("physical_opening_id")
        measurement_id = observed_row.get("quantity_measurement_record_id")
        host_id = host.get("record_id")
        scope_id = host.get("decision_scope_id")
        _require(
            all(type(x) is str and x and x == x.strip()
                for x in (physical_id, measurement_id, host_id, scope_id)),
            "physical host/measurement/decision scope not issued",
        )
        _require(
            host_id not in issued_hosts and measurement_id not in issued_measurements,
            "source host or measurement receipt reused across quantities",
        )
        issued_hosts.add(host_id)
        issued_measurements.add(measurement_id)
        root = {
            "document_id": report["document_id"],
            "source_sha256": expected_source_sha256,
            "revision_id": report["revision_id"],
            "snapshot_id": expected_snapshot_id,
        }
        _require(
            all(observed_row.get(k) == v and host.get(k) == v
                and physical.get(k) == v for k, v in root.items())
            and physical.get("record_id") == physical_id
            and host.get("opening_identity_id") == physical_id
            and host.get("page_id") == observed_row.get("page_id")
            and host.get("decision_scope_id") == observed_row.get("decision_scope_id"),
            "foreign physical/host source root or selector",
        )
        _require(
            (frame is None or (
                isinstance(frame, Mapping)
                and frame.get("host_binding_record_id") == host_id
                and frame.get("host_wall_id") == host.get("host_wall_id")
                and not _is_stale(frame)
            ))
            and not any(_is_stale(x) for x in (host, physical, original)),
            "superseded or conflicting positive producer source record",
        )
        _require(
            original.get("family") == sealed_row.family == "opening_area"
            and original.get("quantity_id") == sealed_row.quantity_id
            and original.get("semantic_key") == sealed_row.semantic_key
            and original.get("authority") == sealed_row.authority
            and original.get("status") == sealed_row.status
            and original.get("unit") == sealed_row.unit
            and original.get("value") == sealed_row.value
            and original.get("confidence") == sealed_row.confidence
            and sorted(original.get("input_entity_ids", ())) == [physical_id]
            and tuple(sealed_row.object_identity_refs) == (physical_id,)
            and set(original.get("evidence_ids", ())) == set(sealed_row.evidence_ids)
            and host_id in sealed_row.evidence_ids
            and measurement_id in sealed_row.evidence_ids,
            "V1 quantity is not the exact original producer-issued measured opening",
        )
        _require(
            sealed_row.document_id == report["document_id"]
            and sealed_row.source_sha256 == expected_source_sha256
            and sealed_row.revision_id == report["revision_id"]
            and sealed_row.source_page == str(observed_row.get("page_id"))
            and sealed_row.viewport_id == observed_row.get("viewport_id"),
            "foreign V1 document/revision/page/viewport",
        )
        projection_fp = customer.get("commercial_projection_fingerprint")
        _require(
            type(projection_fp) is str and bool(_SHA.fullmatch(projection_fp)),
            "independent V1 commercial projection fingerprint unavailable",
        )
        associations.append({
            "quantity_id": quantity_id,
            "physical_opening_id": physical_id,
            "original_existence_record_id": physical.get("record_id"),
            "host_binding_record_id": host_id,
            "measurement_record_id": measurement_id,
            "document_id": sealed_row.document_id,
            "source_sha256": expected_source_sha256,
            "revision_id": sealed_row.revision_id,
            "snapshot_id": expected_snapshot_id,
            "decision_scope_id": scope_id,
            "source_page": sealed_row.source_page,
            "viewport_id": sealed_row.viewport_id,
            "v1_sealed_quantity_fingerprint": sealed_row.fingerprint,
            "v1_customer_projection_fingerprint": projection_fp,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "SOURCE_REPLAY_CONSISTENT_UNSIGNED_UNPUBLISHED",
        "signed_scope_verified": False,
        "customer_scope_signature_issued": False,
        "benchmark_score_granted": False,
        "project_id": expected_project_id,
        "source_sha256": expected_source_sha256,
        "snapshot_id": expected_snapshot_id,
        "decoded_page_ids": report["decoded_page_ids"],
        "topology_page_ids": report["topology_page_ids"],
        "v1_sealed_run_fingerprint": sealed.fingerprint,
        "source_owned_quantity_count": len(associations),
        "customer_bijection_verified": True,
        "associations": associations,
    }


def verify_original_scope_to_v1_customer(
    original_pdf: bytes,
    *,
    page_ids: Sequence[str],
    decoded_page_ids: Sequence[str] | None = None,
    sealed_payload: Mapping[str, Any],
    customer_rows: Sequence[Mapping[str, Any]],
    expected_source_sha256: str,
    expected_snapshot_id: str,
    expected_project_id: str,
) -> dict[str, Any]:
    """Reissue scope IN PROCESS from original bytes, never from exported JSON."""
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("original PDF bytes required for scope verification")
    if type(expected_source_sha256) is not str or not _SHA.fullmatch(expected_source_sha256):
        raise OriginalSourceScopeConsumerError("canonical pinned source SHA required")
    if sha256(original_pdf).hexdigest() != expected_source_sha256:
        raise OriginalSourceScopeConsumerError("original PDF SHA does not match pinned input")
    if (
        type(expected_snapshot_id) is not str or not expected_snapshot_id.startswith("source_snapshot_")
        or type(expected_project_id) is not str or not expected_project_id
        or type(page_ids) not in (list, tuple)
        or (decoded_page_ids is not None and type(decoded_page_ids) not in (list, tuple))
    ):
        raise OriginalSourceScopeConsumerError("original scope/project/page selectors unavailable")
    if not isinstance(sealed_payload, Mapping) or isinstance(customer_rows, (str, bytes, Mapping)):
        raise OriginalSourceScopeConsumerError("persisted V1 run and customer rows required")
    # This producer runs original PDF ingress, authentic host/frame selectors,
    # independently reissues figured labels and repeats original receipt checks.
    report = producer_opening_scope_receipt_report(
        original_pdf, page_ids=page_ids, decoded_page_ids=decoded_page_ids,
    )
    return _verified_join(
        report, sealed_payload, customer_rows,
        expected_source_sha256=expected_source_sha256,
        expected_snapshot_id=expected_snapshot_id,
        expected_project_id=expected_project_id,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--decoded-page-id", action="append")
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--customer-rows", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--expected-snapshot-id", required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    sealed_payload = _parse_evidence_json(args.sealed_run.read_text(encoding="utf-8"))
    customer_rows = _parse_evidence_json(args.customer_rows.read_text(encoding="utf-8"))
    output = verify_original_scope_to_v1_customer(
        args.pdf.read_bytes(), page_ids=args.page_id,
        decoded_page_ids=args.decoded_page_id, sealed_payload=sealed_payload,
        customer_rows=customer_rows, expected_source_sha256=args.expected_source_sha256,
        expected_snapshot_id=args.expected_snapshot_id, expected_project_id=args.project_id,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": output["status"],
        "existing_v1_customer_rows": output["source_owned_quantity_count"],
        "signed_scope_verified": False, "benchmark_score_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
