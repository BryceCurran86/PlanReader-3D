"""Original Maryborough source -> sealed floor-area score input.

Production-side source handoff only. This module authenticates the immutable
architectural PDF, runs the existing physical-room/floor pipeline, seals every
source-supported floor-area quantity, and verifies exact customer-row parity.
It never reads frozen expected quantities or assigns benchmark object IDs.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_area_customer_projection import (
    project_live_floor_area_customer_rows,
)
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from tools.diag_gpt2_room_measurement_gates import inspect_room_measurement_gates

PROJECT = "au_qld_maryborough_service_station"
MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/frozen_holdout/full_plan_v2/projects"
    / PROJECT
    / "source_manifest.json"
)


def _verify_original_source(pdf: Path, manifest_path: Path) -> str:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("project_id") != PROJECT:
        raise ValueError("incorrect Maryborough source manifest project")
    architectural = [
        item
        for item in manifest.get("source_documents", ())
        if item.get("role") == "architectural_drawings"
    ]
    if len(architectural) != 1:
        raise ValueError("ambiguous or missing Maryborough architectural source")
    original = architectural[0]
    if not pdf.is_file() or pdf.name != original.get("name"):
        raise ValueError("wrong Maryborough architectural source filename")
    if pdf.stat().st_size != original.get("size_bytes"):
        raise ValueError("Maryborough original source size mismatch")
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != original.get("sha256"):
        raise ValueError("Maryborough original source SHA mismatch")
    return digest


def _clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _validate_sealed_customer_handoff(
    sealed: Any,
    rows: Any,
    verified: Any,
    source_sha: str,
) -> dict[str, Any]:
    if sealed.project_id != PROJECT or tuple(sealed.source_sha256s) != (source_sha,):
        raise ValueError("sealed Maryborough source scope contradicts original PDF")
    quantities = tuple(sealed.quantities)
    if not quantities:
        raise ValueError("empty Maryborough floor-area source seal")

    quantity_ids = [q.quantity_id for q in quantities]
    if (
        any(type(qid) is not str or not qid or qid != qid.strip() for qid in quantity_ids)
        or len(quantity_ids) != len(set(quantity_ids))
    ):
        raise ValueError("invalid or duplicate Maryborough sealed quantity IDs")
    if not isinstance(rows, (tuple, list)) or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Maryborough customer rows malformed")
    row_ids = [row.get("quantity_id") for row in rows]
    verified_ids = list(verified.verified_quantity_ids)
    if (
        any(type(qid) is not str or not qid or qid != qid.strip() for qid in row_ids)
        or len(row_ids) != len(set(row_ids))
        or set(row_ids) != set(quantity_ids)
        or len(row_ids) != len(quantity_ids)
        or set(verified_ids) != set(quantity_ids)
        or len(verified_ids) != len(quantity_ids)
        or verified.valid_quantity_count != len(quantity_ids)
        or verified.customer_row_count != len(quantity_ids)
    ):
        raise ValueError("Maryborough sealed quantities/customer rows do not agree")

    identities: list[dict[str, Any]] = []
    seen_physical: set[str] = set()
    for quantity in sorted(quantities, key=lambda item: item.quantity_id):
        refs = tuple(quantity.object_identity_refs)
        trace_refs = tuple(quantity.trace_canonical_entity_ids)
        if (
            quantity.project_id != PROJECT
            or quantity.source_sha256 != source_sha
            or quantity.family != "floor_area"
            or quantity.unit not in {"m2", "m²"}
            or type(quantity.value) not in (int, float)
            or not math.isfinite(float(quantity.value))
            or float(quantity.value) <= 0.0
            or quantity.abstained is not False
            or quantity.lineage_ok is not True
            or len(refs) != 1
            or type(refs[0]) is not str
            or not refs[0]
            or refs[0] != refs[0].strip()
            or refs[0] in seen_physical
            or refs[0] not in trace_refs
            or not trace_refs
            or len(trace_refs) != len(set(trace_refs))
            or any(type(ref) is not str or not ref or ref != ref.strip() for ref in trace_refs)
            or not tuple(quantity.evidence_ids)
            or not _clean(quantity.fingerprint)
        ):
            raise ValueError("Maryborough source floor identity/lineage unverified")
        customer = next(row for row in rows if row["quantity_id"] == quantity.quantity_id)
        if (
            customer.get("project_id") != PROJECT
            or customer.get("source_sha256") != source_sha
            or tuple(customer.get("canonical_entity_ids", ())) != trace_refs
            or customer.get("quantity_family") != "floor_area"
            or customer.get("quantity_status") != "To review"
            or customer.get("origin") != "AI"
            or customer.get("row_role") != "floor_area"
        ):
            raise ValueError("Maryborough customer row identity does not match seal")
        seen_physical.add(refs[0])
        identities.append(
            {
                "quantity_id": quantity.quantity_id,
                "physical_floor_surface_id": refs[0],
                "trace_canonical_entity_ids": list(trace_refs),
                "source_page": quantity.source_page,
                "value": float(quantity.value),
                "unit": quantity.unit,
                "source_authority": quantity.authority,
                "source_evidence_ids": list(quantity.evidence_ids),
                "source_quantity_fingerprint": quantity.fingerprint,
            }
        )

    return {
        "project_id": PROJECT,
        "source_sha256": source_sha,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "quantity_count": len(quantities),
        "sealed_quantity_ids": sorted(quantity_ids),
        "customer_verified_quantity_ids": sorted(verified_ids),
        "source_floor_identities": identities,
        "signed_run_and_customer_parity": True,
        "identity_map_status": "INDEPENDENT_ORIGINAL_SOURCE_BINDINGS_REQUIRED",
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "frozen_v2_reconciliation_complete": False,
    }


def _publish_new(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n"
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def run_original_maryborough_floor_handoff(
    pdf: Path,
    output_dir: Path,
    *,
    manifest_path: Path = MANIFEST,
) -> dict[str, Any]:
    source_sha = _verify_original_source(pdf, manifest_path)
    if output_dir.is_symlink() or (output_dir.exists() and any(output_dir.iterdir())):
        raise FileExistsError("Maryborough sealed score-input directory must be fresh")
    output_dir.mkdir(parents=True, exist_ok=True)

    claim = collect_live_physical_net_wall_claim(
        pdf,
        pages=(6,),
        topology_pages=(6,),
        room_area_support_pages=(10,),
    )
    sealed = seal_live_floor_area_run(
        claim,
        workspace_id=1,
        project_id=PROJECT,
    )
    rows = project_live_floor_area_customer_rows(
        claim,
        workspace_id=1,
        project_id=PROJECT,
    )
    verified = verify_sealed_customer_output(sealed, rows)
    receipt = _validate_sealed_customer_handoff(
        sealed,
        rows,
        verified,
        source_sha,
    )
    source_stage = inspect_room_measurement_gates(claim)
    if (
        source_stage.get("benchmark_accuracy") is not None
        or source_stage.get("commercial_estimator_approved") is not False
    ):
        raise ValueError("source-stage diagnostic unexpectedly grants benchmark/commercial authority")

    _publish_new(output_dir / "source_sealed_run.json", sealed.to_dict())
    _publish_new(output_dir / "verified_customer_rows.json", list(rows))
    _publish_new(output_dir / "source_stage_diagnostic.json", source_stage)
    _publish_new(output_dir / "source_score_readiness_UNPUBLISHED.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run_original_maryborough_floor_handoff(args.pdf, args.output_dir)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
