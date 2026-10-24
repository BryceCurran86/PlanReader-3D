"""Original Lot16 page-3 source → SEALED production input for exact frozen V2.

This is a production-source evidence handoff, NOT benchmark reconciliation.
It reads only source-manifest PDF hashes, never reference quantities or labels.
The frozen identity map must be established separately from original ancestry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_opening_customer_projection import project_live_opening_customer_rows
from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
from tools.diag_lot16_room_face_scope import inspect_source

PROJECT = "au_qld_lot16_power"
MANIFEST = (
    Path(__file__).resolve().parents[1]
    / "benchmarks/frozen_holdout/full_plan_v2/projects"
    / PROJECT / "source_manifest.json"
)


def _verify_original_source(pdf: Path, manifest_path: Path) -> str:
    """Authenticate the ORIGINAL architectural PDF by immutable source SHA."""
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("project_id") != PROJECT:
        raise ValueError("incorrect original source project manifest")
    architectural = [
        item for item in manifest.get("source_documents", ())
        if item.get("role") == "architectural_drawings"
    ]
    if len(architectural) != 1:
        raise ValueError("ambiguous or missing original architectural source")
    original = architectural[0]
    if not pdf.is_file() or pdf.name != original["name"]:
        raise ValueError("wrong original architectural source filename")
    if pdf.stat().st_size != original["size_bytes"]:
        raise ValueError("original source size mismatch")
    digest = hashlib.sha256(pdf.read_bytes()).hexdigest()
    if digest != original["sha256"]:
        raise ValueError("original source SHA mismatch")
    return digest


def _validate_sealed_customer_handoff(sealed, rows, verified, source_sha: str) -> dict:
    """Check exact source→quantity→customer bijection, without benchmark IDs."""
    if sealed.project_id != PROJECT or set(sealed.source_sha256s) != {source_sha}:
        raise ValueError("sealed production source scope contradicts original PDF")
    quantity_ids = [row.quantity_id for row in sealed.quantities]
    if not quantity_ids or len(quantity_ids) != len(set(quantity_ids)):
        raise ValueError("empty or duplicated sealed Lot16 physical quantities")
    verified_ids = list(verified.verified_quantity_ids)
    if (
        set(verified_ids) != set(quantity_ids)
        or len(verified_ids) != len(quantity_ids)
        or verified.valid_quantity_count != len(quantity_ids)
        or len(rows) != len(quantity_ids)
    ):
        raise ValueError("original sealed quantities and customer rows do not agree")
    if any(row.family != "opening_area" for row in sealed.quantities):
        raise ValueError("unexpected produced quantity family in Lot16 source handoff")
    # A physical identity is not a V2 item binding; do not guess a map.
    return {
        "project_id": PROJECT,
        "source_sha256": source_sha,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "quantity_count": len(quantity_ids),
        "sealed_quantity_ids": sorted(quantity_ids),
        "customer_verified_quantity_ids": sorted(verified_ids),
        "signed_run_and_customer_parity": True,
        "identity_map_status": "INDEPENDENT_ORIGINAL_SOURCE_BINDINGS_REQUIRED",
        "benchmark_score_granted": False,
        "benchmark_accuracy": None,
        "frozen_v2_reconciliation_complete": False,
    }


def _publish_new(path: Path, data: object) -> None:
    """Atomic create-only: no old signed source artifact can be overwritten."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, sort_keys=True, indent=2, allow_nan=False) + "\n"
    temp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=path.parent,
            prefix=f".{path.name}.", suffix=".tmp", delete=False,
        ) as stream:
            temp = Path(stream.name)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temp, path)
    finally:
        if temp is not None:
            temp.unlink(missing_ok=True)


def run_original_lot16_sealed_handoff(
    pdf: Path, output_dir: Path, *, manifest_path: Path = MANIFEST
) -> dict:
    sha = _verify_original_source(pdf, manifest_path)
    if output_dir.is_symlink() or (output_dir.exists() and any(output_dir.iterdir())):
        raise FileExistsError("original Lot16 sealed output directory must be fresh")
    output_dir.mkdir(parents=True, exist_ok=True)
    received: list[tuple] = []
    claim_source_openings: list[tuple] = []

    def source_seal(claim):
        claim_source_openings.append(tuple(claim.canonical_openings))
        # The production-original claim is passed directly, once, from the
        # unchanged single-page source collector. There is no benchmark input.
        sealed = seal_live_opening_area_claim_run(
            claim, workspace_id=1, project_id=PROJECT,
        )
        rows = project_live_opening_customer_rows(
            claim, workspace_id=1, project_id=PROJECT,
        )
        verified = verify_sealed_customer_output(sealed, rows)
        receipt = _validate_sealed_customer_handoff(sealed, rows, verified, sha)
        received.append((sealed, rows, receipt))

    source_diagnostic = inspect_source(pdf, 2, on_original_claim=source_seal)
    if len(claim_source_openings) != 1 or len(received) != 1 or source_diagnostic["pdf_sha256"] != sha:
        raise ValueError("original source production did not return one verified seal")
    if source_diagnostic["opening_sealing_diagnostic"]["status"] != (
        "source_sealed_and_customer_rows_verified"
    ):
        raise ValueError("independent original source diagnostic/customer proof failed")
    sealed, rows, receipt = received[0]
    expected_ids = sorted(source_diagnostic["opening_sealing_diagnostic"]["sealed_quantity_ids"])
    if receipt["sealed_quantity_ids"] != expected_ids:
        raise ValueError("real-project seal diverges from source diagnostic seal")
    # Read-only source witness from the SAME original single-page collector that
    # emitted the sealed quantities. The separate all-pages diagnostic uses
    # different host-receipt scopes and must not stand in for this claim.
    # This does not publish any additional quantity, count or host.
    _publish_new(
        output_dir / "source_production_openings.json",
        [opening.to_dict() for opening in claim_source_openings[0]],
    )
    _publish_new(output_dir / "source_sealed_run.json", sealed.to_dict())
    _publish_new(output_dir / "verified_customer_rows.json", list(rows))
    _publish_new(output_dir / "source_stage_diagnostic.json", source_diagnostic)
    _publish_new(output_dir / "source_score_readiness_UNPUBLISHED.json", receipt)
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    receipt = run_original_lot16_sealed_handoff(args.pdf, args.output_dir)
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
