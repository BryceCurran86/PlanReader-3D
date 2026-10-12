"""Independent GPT3 Lot16 source-identity *readiness*, never a V2 score.

Reads already sealed, SHA-bound production and already projected customer bytes.
The frozen manifest supplies only a separate inventory of eligible *identities*.
No area/value, description, label or ordinal matching is performed. The seven
source-owned opening IDs cannot become benchmark item bindings in this tool.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from scripts.report_full_plan_v2_readiness import (
    _object, _parse_evidence_json, _write_readiness_report,
)

ROOT = Path(__file__).resolve().parents[1]
FROZEN_ROOT = ROOT / "benchmarks/frozen_holdout/full_plan_v2"
PROJECT = "au_qld_lot16_power"
MANIFEST = FROZEN_ROOT / "projects" / PROJECT / "source_manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _original_architectural_document(manifest: dict) -> dict:
    if manifest.get("project_id") != PROJECT:
        raise ValueError("not the Lot16 frozen source manifest")
    docs = manifest.get("source_documents")
    if not isinstance(docs, list) or not docs:
        raise ValueError("missing frozen source document universe")
    architecture = [doc for doc in docs if isinstance(doc, dict)
                    and doc.get("role") == "architectural_drawings"]
    if len(architecture) != 1:
        raise ValueError("not exactly one frozen original architectural source")
    doc = architecture[0]
    if (type(doc.get("name")) is not str or not doc["name"]
            or Path(doc["name"]).name != doc["name"]
            or type(doc.get("size_bytes")) is not int
            or doc["size_bytes"] < 0
            or type(doc.get("sha256")) is not str
            or len(doc["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in doc["sha256"])):
        raise ValueError("malformed frozen original source receipt")
    return doc


def _reference_inventory(manifest: dict) -> tuple[list[str], list[str]]:
    """Reference IDs only, strictly after production was sealed.

    This never reads or returns reference quantities, labels or tolerances.
    """
    items = manifest.get("verified_takeoff_items")
    if not isinstance(items, list):
        raise ValueError("frozen denominator item inventory unavailable")
    item_ids: list[str] = []
    refs: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("frozen denominator item is not an object")
        if item.get("denominator_eligible") is not True:
            continue
        item_id = item.get("item_id")
        object_refs = item.get("expected_object_refs")
        if (type(item_id) is not str or not item_id
                or type(object_refs) is not list or not object_refs
                or any(type(ref) is not str or not ref for ref in object_refs)):
            raise ValueError("invalid frozen denominator identity")
        item_ids.append(item_id)
        refs.extend(object_refs)
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("duplicate frozen denominator item")
    return sorted(item_ids), sorted(set(refs))


def _source_stage_parity(stage: dict, *, source_sha: str, quantities: tuple) -> dict[str, str]:
    """Compare SOURCE producer's physical quantity IDs, never frozen item IDs."""
    if (stage.get("pdf_sha256") != source_sha
            or stage.get("diagnostic_only") is not True
            or stage.get("source_page_index_zero_based") != 2):
        raise ValueError("original source-stage SHA/page/diagnostic provenance mismatch")
    opening = stage.get("opening_quantity_diagnostic")
    observed = opening.get("per_opening") if isinstance(opening, dict) else None
    if type(observed) is not list:
        raise ValueError("original opening source-stage inventory unavailable")
    seen: dict[str, dict] = {}
    matched_ids: list[str] = []
    published_ids: list[str] = []
    for item in observed:
        if not isinstance(item, dict):
            raise ValueError("malformed original source opening")
        physical = item.get("physical_opening_id")
        if type(physical) is not str or not physical or physical in seen:
            raise ValueError("duplicate/noncanonical source-stage physical opening")
        seen[physical] = item
        for field, sink in (
            ("production_matched_area_quantity_ids", matched_ids),
            ("published_area_quantity_ids", published_ids),
        ):
            claimed = item.get(field)
            if (type(claimed) is not list or any(type(v) is not str or not v for v in claimed)
                    or len(claimed) != len(set(claimed))):
                raise ValueError("malformed original source-stage published quantity IDs")
            sink.extend(claimed)

    expected_ids = {quantity.quantity_id for quantity in quantities}
    if (len(matched_ids) != len(expected_ids)
            or len(published_ids) != len(expected_ids)
            or set(matched_ids) != expected_ids
            or set(published_ids) != expected_ids):
        raise ValueError("original source-stage and signed opening quantity sets differ")

    host_receipts: dict[str, str] = {}
    for row in quantities:
        physical = row.object_identity_refs[0]
        item = seen.get(physical)
        if item is None:
            raise ValueError("signed opening missing from original source stage")
        host = item.get("host_wall_id")
        if (item.get("canonical_opening_id") != physical
                or item.get("page_id") != row.source_page
                or item.get("viewport_id") != row.viewport_id
                or item.get("production_matched_area_quantity_ids") != [row.quantity_id]
                or item.get("published_area_quantity_ids") != [row.quantity_id]
                or item.get("first_missing_prerequisite")
                    != "opening_area_quantity_prerequisites_resolved"
                or item.get("host_receipt_available") is not True
                or type(host) is not str
                or not host.startswith("opening_host_binding_group_")):
            raise ValueError("source-stage physical host and sealed quantity parity unproven")
        host_receipts[physical] = host
    return host_receipts


def build_unpublished_lot16_identity_readiness(
    *, sealed_run_path: Path, customer_rows_path: Path,
    original_pdf: Path | None = None, source_stage_path: Path | None = None,
    manifest_path: Path = MANIFEST,
) -> dict:
    """Create a non-scoring, exact-identity work order from authenticated bytes."""
    # The expected manifest is always the immutable repository path, not an
    # arbitrary caller-provided fixture or rewritten reference.
    if manifest_path.resolve() != MANIFEST.resolve():
        raise ValueError("must use exact frozen Lot16 source manifest")
    immutable_inputs = [manifest_path, sealed_run_path, customer_rows_path]
    if source_stage_path is not None:
        immutable_inputs.append(source_stage_path)
    before = tuple(_sha256(path) for path in immutable_inputs)
    manifest = _object(manifest_path)
    original = _original_architectural_document(manifest)
    raw = _object(sealed_run_path)
    sealed = sealed_source_closed_run_from_dict(raw)
    rows = _parse_evidence_json(customer_rows_path.read_text(encoding="utf-8"))
    if type(rows) is not list or any(type(row) is not dict for row in rows):
        raise ValueError("customer projection must be an array of rows")

    if sealed.project_id != PROJECT:
        raise ValueError("sealed source run belongs to another project")
    original_sha = original["sha256"]
    if set(sealed.source_sha256s) != {original_sha}:
        raise ValueError("signed source-run SHA is not frozen Lot16 architectural SHA")
    verified = verify_sealed_customer_output(sealed, rows)
    quantity_ids = [row.quantity_id for row in sealed.quantities]
    if (not quantity_ids or len(quantity_ids) != len(set(quantity_ids))
            or len(rows) != len(quantity_ids)
            or verified.valid_quantity_count != len(quantity_ids)
            or len(verified.verified_quantity_ids) != len(quantity_ids)
            or set(verified.verified_quantity_ids) != set(quantity_ids)):
        raise ValueError("source-sealed quantity/customer-row bijection failed")

    physical_seen: set[str] = set()
    work_order: list[dict] = []
    for row in sealed.quantities:
        if (row.family != "opening_area"
                or row.abstained or row.status.lower() not in {"corroborated", "firm"}
                or row.value is None or not row.lineage_ok
                or row.blocking_reasons or row.lineage_reason_codes
                or row.source_sha256 != original_sha
                or len(row.object_identity_refs) != 1):
            raise ValueError("Lot16 opening has unavailable FIRM source identity")
        physical_id = row.object_identity_refs[0]
        if (not physical_id.startswith("physical_opening_existence_")
                or physical_id in physical_seen):
            raise ValueError("duplicate/nonphysical sealed opening identity")
        physical_seen.add(physical_id)
        work_order.append({
            "production_quantity_id": row.quantity_id,
            "physical_opening_id": physical_id,
            "signed_source_page": row.source_page,
            "signed_viewport_id": row.viewport_id,
            "signed_canonical_entity_ids": list(row.trace_canonical_entity_ids),
            "signed_observation_evidence_ids": list(row.evidence_ids),
            "signed_trace_evidence_ids": list(row.trace_evidence_ids),
            "crosswalk_status": "UNPROVEN",
            "required_next_receipts": [
                "original_source_owned_opening_position_and_bbox",
                "native_callout_and_floor_plan_viewport_ownership",
                "exact_source_host_wall_and_dimension_ancestry",
                "independent_frozen_item_identity_attestation",
            ],
            "benchmark_item_id": None,
        })
    source_stage_host_receipts: dict[str, str] = {}
    source_stage_parity_verified = False
    if source_stage_path is not None:
        source_stage_host_receipts = _source_stage_parity(
            _object(source_stage_path),
            source_sha=original_sha,
            quantities=sealed.quantities,
        )
        source_stage_parity_verified = True
        for item in work_order:
            item["signed_source_stage_host_binding_group_id"] = (
                source_stage_host_receipts[item["physical_opening_id"]]
            )
    item_ids, object_refs = _reference_inventory(manifest)
    source_bytes_verified = False
    if original_pdf is not None:
        if (original_pdf.name != original["name"]
                or not original_pdf.is_file()
                or original_pdf.stat().st_size != original["size_bytes"]
                or _sha256(original_pdf) != original_sha):
            raise ValueError("original PDF is not frozen architectural source bytes")
        source_bytes_verified = True
    if (tuple(_sha256(path) for path in immutable_inputs) != before
            or (original_pdf is not None and _sha256(original_pdf) != original_sha)):
        raise ValueError("signed or original evidence changed during readiness check")

    # Structural PDF is another source document; neither this architectural
    # original proof nor a signed opening-area subset proves the complete suite.
    return {
        "project_id": PROJECT,
        "producer_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "source_architectural_sha256": original_sha,
        "original_architectural_pdf_bytes_verified": source_bytes_verified,
        "source_package_document_count": len(manifest["source_documents"]),
        "sealed_source_document_count": len(sealed.source_sha256s),
        "full_source_package_verified": False,
        "source_stage_physical_quantity_parity_verified": source_stage_parity_verified,
        "frozen_manifest_status_unchanged": manifest.get("status"),
        "frozen_denominator_item_count": len(item_ids),
        "frozen_item_ids_not_yet_physically_bound": item_ids,
        "frozen_object_refs_not_yet_physically_bound": object_refs,
        "source_firm_sealed_quantity_count": len(quantity_ids),
        "customer_verified_quantity_count": verified.valid_quantity_count,
        "source_physical_openings_requiring_independent_crosswalk": sorted(
            work_order, key=lambda row: row["physical_opening_id"]
        ),
        "benchmark_status": "NOT_EVALUATED",
        "benchmark_score_granted": False,
        "frozen_v2_reconciliation_complete": False,
        "matched_within_tolerance": None,
        "matched_outside_tolerance": None,
        "missed": None,
        "partial": None,
        "unresolved": None,
        "unsupported_extra": None,
        "coverage_accuracy": None,
        "precision_adjusted_accuracy": None,
        "first_reporting_gate": "INDEPENDENT_PHYSICAL_TO_FROZEN_IDENTITY_BINDING_UNPROVEN",
        "reason_codes": [
            "all_physical_to_frozen_identity_bindings_unproven",
            "frozen_project_universe_incomplete"
            if manifest.get("status") != "VERIFIED" else
            "full_source_package_and_suite_proof_missing",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", required=True, type=Path)
    parser.add_argument("--customer-rows", required=True, type=Path)
    parser.add_argument("--original-pdf", type=Path)
    parser.add_argument("--source-stage", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    receipt = build_unpublished_lot16_identity_readiness(
        sealed_run_path=args.sealed_run,
        customer_rows_path=args.customer_rows,
        original_pdf=args.original_pdf,
        source_stage_path=args.source_stage,
    )
    _write_readiness_report(
        args.output,
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        protected_roots=(
            FROZEN_ROOT, args.sealed_run, args.customer_rows,
            *((args.source_stage,) if args.source_stage else ()),
            *((args.original_pdf,) if args.original_pdf else ()),
        ),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
