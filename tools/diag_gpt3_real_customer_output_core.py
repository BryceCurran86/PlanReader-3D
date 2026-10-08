"""Real-project core sealed quantity -> customer row verification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_opening_count_source_closed_export import (
    build_live_opening_count_source_traces,
    seal_live_opening_count_run,
)
from pb_live_opening_source_closed_export import (
    build_live_opening_area_claim_source_traces,
    seal_live_opening_area_claim_run,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)
from pb_source_closed_run_export import combine_source_closed_runs
from tools.run_source_closed_project_handoff import _source_page_scopes


def _non_abstained(values) -> tuple[QuantityEvidence, ...]:
    return tuple(
        value
        for value in values
        if isinstance(value, QuantityEvidence)
        and not value.abstained
        and value.value is not None
        and not value.blocking_reasons
    )


def verify_project(pdf_path: Path, project_id: str, output: Path) -> dict:
    topology_pages, _support_pages, page_count = _source_page_scopes(pdf_path)
    all_pages = tuple(range(page_count))
    topology_restricted = tuple(topology_pages) != all_pages
    claim_pages = tuple(topology_pages) if topology_restricted else all_pages

    claim = collect_live_physical_net_wall_claim(
        pdf_path,
        pages=claim_pages,
        topology_pages=(tuple(topology_pages) if topology_restricted else None),
        room_area_support_pages=None,
        surface_semantic_pages=claim_pages,
    )

    area_quantities = _non_abstained(claim.opening_quantity_evidence)
    count_quantities = _non_abstained(claim.opening_count_quantity_evidence)
    quantities = (*area_quantities, *count_quantities)

    ids = [q.quantity_id for q in quantities]
    if len(ids) != len(set(ids)):
        raise RuntimeError("duplicate quantity ids across core families")

    traces = {}
    runs = []
    if area_quantities:
        traces.update(
            build_live_opening_area_claim_source_traces(
                claim,
                workspace_id=1,
                project_id=project_id,
            )
        )
        runs.append(
            seal_live_opening_area_claim_run(
                claim,
                workspace_id=1,
                project_id=project_id,
            )
        )
    if count_quantities:
        traces.update(
            build_live_opening_count_source_traces(
                claim,
                workspace_id=1,
                project_id=project_id,
            )
        )
        runs.append(
            seal_live_opening_count_run(
                claim,
                workspace_id=1,
                project_id=project_id,
            )
        )

    family_counts = {
        "opening_area": len(area_quantities),
        "opening_count": len(count_quantities),
    }
    if not runs:
        result = {
            "project_id": project_id,
            "family_counts": family_counts,
            "quantity_count": 0,
            "customer_row_count": 0,
            "status": "no_core_quantities",
        }
        output.mkdir(parents=True, exist_ok=True)
        (output / f"{project_id}.core_customer_output_audit.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return result

    sealed = runs[0] if len(runs) == 1 else combine_source_closed_runs(
        runs,
        project_id=project_id,
    )
    authorities = {
        quantity.quantity_id: CommercialMeasurementAuthority(method="direct_evidence")
        for quantity in quantities
    }
    rows = quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id=traces,
        authorities_by_quantity_id=authorities,
    )
    live = verify_sealed_customer_output(sealed, rows)

    output.mkdir(parents=True, exist_ok=True)
    rows_path = output / f"{project_id}.core_customer_rows.json"
    rows_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    persisted_rows = json.loads(rows_path.read_text())
    persisted = verify_sealed_customer_output(sealed, persisted_rows)

    result = {
        "project_id": project_id,
        "family_counts": family_counts,
        "quantity_count": len(quantities),
        "customer_row_count": len(rows),
        "sealed_run_id": sealed.run_id,
        "source_sha256s": list(sealed.source_sha256s),
        "live_verification": live.to_dict(),
        "persisted_verification": persisted.to_dict(),
        "rows": [
            {
                "quantity_id": row["quantity_id"],
                "quantity_family": row["quantity_family"],
                "quantity": row["quantity"],
                "unit": row["unit"],
                "source_sha256": row["source_sha256"],
                "source_page": row["source_page"],
                "viewport_id": row["viewport_id"],
                "revision_id": row["revision_id"],
                "canonical_entity_ids": row["canonical_entity_ids"],
                "evidence_ids": row["evidence_ids"],
                "commercial_projection_fingerprint": row[
                    "commercial_projection_fingerprint"
                ],
            }
            for row in rows
        ],
        "status": "verified",
    }
    (output / f"{project_id}.core_customer_output_audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    verify_project(args.pdf, args.project_id, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
