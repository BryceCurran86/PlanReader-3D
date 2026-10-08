"""Real-project sealed quantity -> customer row verification.

Diagnostic only. Uses production quantities and production-owned source traces;
does not read benchmark truth or score expected values.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_ceiling_lining_source_closed_export import (
    build_live_ceiling_lining_source_traces,
    seal_live_ceiling_lining_run,
)
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
    seal_live_floor_area_run,
)
from pb_live_floor_finish_area_source_closed_export import (
    build_live_floor_finish_area_source_traces,
    seal_live_floor_finish_area_run,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    quantities_to_takeoff_output_rows,
)
from pb_source_closed_run_export import combine_source_closed_runs
from tools.run_source_closed_project_handoff import _source_page_scopes


def _clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def _non_abstained(values) -> tuple[QuantityEvidence, ...]:
    return tuple(
        value
        for value in values
        if isinstance(value, QuantityEvidence)
        and not value.abstained
        and value.value is not None
    )


def _measurement_authority(quantity: QuantityEvidence) -> CommercialMeasurementAuthority:
    metadata = quantity.metadata if isinstance(quantity.metadata, dict) else {}
    authority = _clean(quantity.authority).lower().replace("-", "_").replace(" ", "_")
    figured_ids = tuple(
        sorted(
            {
                _clean(value)
                for value in (metadata.get("figured_dimension_ids") or ())
                if _clean(value)
            }
        )
    )
    if authority in {"documented_dimension", "figured_dimension"} or "figured" in authority:
        if len(figured_ids) < 1:
            raise RuntimeError(
                f"{quantity.quantity_id}: documented quantity lacks figured_dimension_ids"
            )
        return CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=figured_ids,
        )

    if "scale" in authority or "geometry" in authority:
        scale_id = _clean(
            metadata.get("resolved_scale_id")
            or metadata.get("physical_scale_record_id")
            or metadata.get("scale_record_id")
            or metadata.get("scale_fingerprint")
        )
        scale_status = _clean(
            metadata.get("scale_status")
            or metadata.get("physical_scale_status")
        )
        if not scale_id or not scale_status:
            raise RuntimeError(
                f"{quantity.quantity_id}: scaled/geometry quantity lacks explicit scale authority"
            )
        return CommercialMeasurementAuthority(
            method="scaled_geometry",
            resolved_scale_id=scale_id,
            scale_status=scale_status,
            scale_conflicts=tuple(metadata.get("scale_conflicts") or ()),
        )

    return CommercialMeasurementAuthority(method="direct_evidence")


def verify_project(pdf_path: Path, project_id: str, output: Path) -> dict:
    topology_pages, support_pages, page_count = _source_page_scopes(pdf_path)
    all_pages = tuple(range(page_count))
    topology_restricted = tuple(topology_pages) != all_pages
    if topology_restricted:
        claim_pages = tuple(sorted(set(topology_pages) | set(support_pages)))
    else:
        claim_pages = all_pages

    claim = collect_live_physical_net_wall_claim(
        pdf_path,
        pages=claim_pages,
        topology_pages=(tuple(topology_pages) if topology_restricted else None),
        room_area_support_pages=(tuple(support_pages) if support_pages else None),
        surface_semantic_pages=all_pages,
    )

    floor_quantities = _non_abstained(publish_live_floor_area_quantities(claim))
    finish_quantities = _non_abstained(claim.floor_finish_quantity_evidence)
    ceiling_quantities = _non_abstained(claim.ceiling_lining_quantity_evidence)

    quantities = (*floor_quantities, *finish_quantities, *ceiling_quantities)
    quantity_ids = [q.quantity_id for q in quantities]
    if len(quantity_ids) != len(set(quantity_ids)):
        raise RuntimeError("duplicate quantity ids across surface families")

    traces = {}
    sealed_runs = []
    family_counts = {
        "floor_area": len(floor_quantities),
        "floor_finish_area": len(finish_quantities),
        "ceiling_lining": len(ceiling_quantities),
    }
    if floor_quantities:
        traces.update(
            build_live_floor_area_source_traces(
                claim, workspace_id=1, project_id=project_id
            )
        )
        sealed_runs.append(
            seal_live_floor_area_run(claim, workspace_id=1, project_id=project_id)
        )
    if finish_quantities:
        traces.update(
            build_live_floor_finish_area_source_traces(
                claim, workspace_id=1, project_id=project_id
            )
        )
        sealed_runs.append(
            seal_live_floor_finish_area_run(
                claim, workspace_id=1, project_id=project_id
            )
        )
    if ceiling_quantities:
        traces.update(
            build_live_ceiling_lining_source_traces(
                claim, workspace_id=1, project_id=project_id
            )
        )
        sealed_runs.append(
            seal_live_ceiling_lining_run(
                claim, workspace_id=1, project_id=project_id
            )
        )

    if not sealed_runs:
        return {
            "project_id": project_id,
            "family_counts": family_counts,
            "quantity_count": 0,
            "customer_row_count": 0,
            "status": "no_surface_quantities",
        }

    sealed = (
        sealed_runs[0]
        if len(sealed_runs) == 1
        else combine_source_closed_runs(sealed_runs, project_id=project_id)
    )
    authorities = {
        quantity.quantity_id: _measurement_authority(quantity)
        for quantity in quantities
    }
    rows = quantities_to_takeoff_output_rows(
        quantities,
        traces_by_quantity_id=traces,
        authorities_by_quantity_id=authorities,
    )
    live_report = verify_sealed_customer_output(sealed, rows)

    output.mkdir(parents=True, exist_ok=True)
    rows_path = output / f"{project_id}.customer_rows.json"
    rows_path.write_text(json.dumps(rows, indent=2, sort_keys=True) + "\n")
    persisted_rows = json.loads(rows_path.read_text())
    persisted_report = verify_sealed_customer_output(sealed, persisted_rows)

    result = {
        "project_id": project_id,
        "family_counts": family_counts,
        "quantity_count": len(quantities),
        "customer_row_count": len(rows),
        "sealed_run_id": sealed.run_id,
        "source_sha256s": list(sealed.source_sha256s),
        "live_verification": live_report.to_dict(),
        "persisted_verification": persisted_report.to_dict(),
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
    (output / f"{project_id}.customer_output_audit.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    result = verify_project(args.pdf, args.project_id, args.output_dir)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
