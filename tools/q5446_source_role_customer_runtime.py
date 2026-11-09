"""Original source-owned Q5446 role -> ordinary full-project customer artifacts.

A source-specific issuer previously ran only in its isolated test. This adapter
makes its independently source-verified floor-area receipt a normal *one-document*
role result, without borrowing seals/quantities for any other source document.

The all-role runner selects this adapter only from an already SHA-authenticated
source-document roster; never from a filename, project name or expected score.
The issuer itself authenticates all original PDF bytes/physical/figured receipts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from pb_gpt1_q5446_alfresco_original_customer import (
    OriginalQ5446AlfrescoCustomerResult,
    issue_original_q5446_alfresco_customer_area,
)
from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256
from pb_gpt1_q5446_source_declared_area_firm_handoff import (
    Q5446_DOCUMENT_ID,
    Q5446_PROJECT_ID,
)


def source_owned_role_module(source_sha256: str, *, family_group: str) -> str:
    """Choose a registered, SHA-owned one-role producer, or the generic one.

    The SHA is an immutable input-file identity authenticated by the owner
    roster, not a quantity feature, floor classification, benchmark value or
    permission to count this role's result as the other source roles.
    """
    if type(source_sha256) is not str or type(family_group) is not str:
        raise TypeError("authenticated source sha and family group required")
    if source_sha256 == SOURCE_SHA256 and family_group == "all":
        return "tools.q5446_source_role_customer_runtime"
    return "tools.run_source_closed_project_handoff"


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _write_new(path: Path, value: str) -> None:
    # A role directory is pre-created by the owner launcher. Never replace an
    # earlier signed body or follow a symlink to foreign customer/source data.
    with path.open("x", encoding="utf-8") as out:
        out.write(value)


def _summary(output_dir: Path, data: dict[str, Any]) -> None:
    _write_new(
        output_dir / "production_summary.json",
        json.dumps(data, sort_keys=True, indent=2) + "\n",
    )


def produce_q5446_source_role(
    *, pdf_path: Path, project_id: str, output_dir: Path,
    family_group: str = "all", workspace_id: int = 1,
) -> dict[str, Any]:
    """Produce only an authenticated original-source ALFRESCO floor role.

    Does not inspect evaluator truth, substitute an expected value, infer a
    tile finish or say that the other five original Q5446 roles completed.
    """
    if type(workspace_id) is not int or workspace_id <= 0:
        raise ValueError("authenticated workspace required")
    if not isinstance(pdf_path, Path) or not isinstance(output_dir, Path):
        raise TypeError("source/output paths must be Path")
    if output_dir.is_symlink() or not output_dir.is_dir():
        raise ValueError("new real role output directory required")
    if any(output_dir.iterdir()):
        raise FileExistsError("role output directory must be empty")
    if not pdf_path.is_file() or pdf_path.is_symlink():
        raise FileNotFoundError("authenticated source file unavailable")
    if output_dir.resolve().is_relative_to(pdf_path.resolve().parent):
        raise ValueError("cannot write role output inside source directory")

    result: dict[str, Any] = {
        "status": "no_sealable_quantities",
        "combined_run_file": None,
        "customer_rows_file": None,
        "customer_rows_verified": False,
        "verified_customer_row_count": 0,
        "full_project_customer_first_gate": "SOURCE_AUTHORITY_UNAVAILABLE",
        "family_counts": {"floor_area": 0},
        "benchmark_score_granted": False,
        "official_four_project_accuracy": None,
    }

    # A file with the same name, one lexical source word or an unrelated
    # revision cannot select the original-source issuer. SHA alone also does
    # not grant any quantity: all of the issuer's gates still apply.
    if (project_id != Q5446_PROJECT_ID or family_group != "all"
            or _digest(pdf_path) != SOURCE_SHA256):
        _summary(output_dir, result)
        return result

    try:
        receipt = issue_original_q5446_alfresco_customer_area(
            str(pdf_path), workspace_id=workspace_id,
        )
        if (type(receipt) is not OriginalQ5446AlfrescoCustomerResult
                or receipt.status != "FIRM_SOURCE_CUSTOMER_TO_REVIEW"
                or receipt.quantity is None or receipt.trace is None
                or receipt.sealed_run is None):
            _summary(output_dir, result)
            return result
        quantity, trace, sealed = receipt.quantity, receipt.trace, receipt.sealed_run
        if (
            quantity.family != "floor_area"
            or quantity.abstained or quantity.status != "firm"
            or quantity.metadata.get("commercial_projection_allowed") is not True
            or quantity.metadata.get("tiled_floor_finish_authorized") is not False
            or quantity.metadata.get("net_internal_finished_face_authorized") is not False
            or quantity.metadata.get("canonical_physical_floor_owner_authenticated") is not True
            or quantity.metadata.get("source_sha256") != SOURCE_SHA256
            or trace.workspace_id != workspace_id
            or trace.project_id != project_id
            or trace.document_id != Q5446_DOCUMENT_ID
            or trace.source_sha256 != SOURCE_SHA256
            or trace.revision_id != trace.current_revision_id
            or sealed.project_id != project_id
            or set(sealed.source_sha256s) != {SOURCE_SHA256}
            or len(sealed.quantities) != 1
            or sealed.quantities[0].quantity_id != quantity.quantity_id
            or not sealed.quantities[0].lineage_ok
            or len(receipt.customer_rows) != 1
        ):
            _summary(output_dir, result)
            return result
        verified = verify_sealed_customer_output(sealed, receipt.customer_rows)
        if (
            verified.customer_row_count != 1
            or set(verified.verified_quantity_ids) != {quantity.quantity_id}
        ):
            _summary(output_dir, result)
            return result
        # Everything below is an authenticated, ordinary canonical role
        # output consumed by the *existing* exact-bijection aggregate reader.
        # Never label one original document as a completed six-role project.
        seal_path = output_dir / (project_id + ".json")
        rows_path = output_dir / "verified_customer_rows.json"
        _write_new(seal_path, sealed.to_json())
        # Re-read via the same real verifier used by the owner role combiner.
        reloaded = load_verified_sealed_run(seal_path)
        if (reloaded.run_id != sealed.run_id
                or set(reloaded.source_sha256s) != {SOURCE_SHA256}):
            raise ValueError("serialized original role seal differs")
        verify_sealed_customer_output(reloaded, receipt.customer_rows)
        _write_new(
            rows_path, json.dumps(list(receipt.customer_rows), sort_keys=True) + "\n",
        )
    except (OSError, ValueError, TypeError, RuntimeError):
        # A failed issuer or seal cannot be converted into a commercial row.
        # Any unexpected failure after seal creation propagates, so the owner
        # process is marked FAILED rather than reporting a partial role sealed.
        if (output_dir / (project_id + ".json")).exists():
            raise
        _summary(output_dir, result)
        return result

    result.update({
        "status": "sealed",
        "combined_run_file": str(seal_path),
        "customer_rows_file": str(rows_path),
        "customer_rows_verified": True,
        "verified_customer_row_count": 1,
        "full_project_customer_first_gate": "PROJECT_VERIFIED",
        "combined_quantity_count": 1,
        "family_counts": {"floor_area": 1},
    })
    _summary(output_dir, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--family-group", default="all")
    parser.add_argument("--workspace-id", type=int, default=1)
    args = parser.parse_args(argv)
    result = produce_q5446_source_role(
        pdf_path=args.pdf, project_id=args.project_id,
        output_dir=args.output_dir, family_group=args.family_group,
        workspace_id=args.workspace_id,
    )
    print(json.dumps({
        "status": result["status"],
        "customer_rows_verified": result["customer_rows_verified"],
        "verified_customer_row_count": result["verified_customer_row_count"],
        "benchmark_score_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
