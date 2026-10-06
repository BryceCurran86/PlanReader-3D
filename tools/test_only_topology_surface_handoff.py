"""TEST ONLY: topology-only surface-family source-closed handoff.

This diagnostic intentionally does not alter production extraction authority.
It asks the existing live authority whether topology pages alone already carry
enough authenticated numeric evidence to publish/seal floor and ceiling
quantities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from pb_ceiling_lining_review_promotion import (
    collect_ceiling_lining_review_candidates,
)
from pb_live_ceiling_source_closed_export import seal_live_ceiling_review_run
from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
)
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_source_closed_run_export import combine_source_closed_runs
from tools.run_source_closed_project_handoff import _source_page_scopes


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _write(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(*, pdf: Path, project_id: str, workspace_id: int, output_dir: Path) -> dict[str, Any]:
    topology_pages, support_pages, page_count = _source_page_scopes(pdf)
    source_sha = _sha256(pdf)
    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "source_sha256": source_sha,
        "page_count": page_count,
        "topology_pages": [p + 1 for p in topology_pages],
        "source_support_pages": [p + 1 for p in support_pages],
        "execution_mode": "topology_only_surfaces",
        "floor_quantity_count": 0,
        "ceiling_quantity_count": 0,
        "family_run_files": {},
        "combined_run_file": None,
        "combined_quantity_count": 0,
        "status": "unavailable",
    }
    output_dir.mkdir(parents=True, exist_ok=True)

    if not topology_pages:
        summary["status"] = "no_source_topology_scope"
        _write(output_dir / "production_summary.json", summary)
        return summary

    claim = collect_live_physical_net_wall_claim(
        pdf,
        pages=tuple(topology_pages),
        topology_pages=tuple(topology_pages),
        room_area_support_pages=None,
    )
    summary["claim_status"] = getattr(
        getattr(claim, "status", None),
        "value",
        str(getattr(claim, "status", "")),
    )
    summary["claim_reason_codes"] = list(getattr(claim, "reason_codes", ()) or ())
    summary["canonical_counts"] = {
        "walls": len(tuple(getattr(claim, "canonical_walls", ()) or ())),
        "openings": len(tuple(getattr(claim, "canonical_openings", ()) or ())),
        "rooms": len(tuple(getattr(claim, "canonical_rooms", ()) or ())),
        "floors": len(tuple(getattr(claim, "canonical_floors", ()) or ())),
        "spaces": len(tuple(getattr(claim, "canonical_spaces", ()) or ())),
    }

    family_runs = []

    floor_quantities = tuple(
        q for q in publish_live_floor_area_quantities(claim)
        if not q.abstained and q.value is not None
    )
    summary["floor_quantity_count"] = len(floor_quantities)
    if floor_quantities:
        floor_run = seal_live_floor_area_run(
            claim,
            workspace_id=workspace_id,
            project_id=project_id,
        )
        floor_path = output_dir / "family_runs" / "floor_area.sealed.json"
        floor_path.parent.mkdir(parents=True, exist_ok=True)
        floor_path.write_text(floor_run.to_json(), encoding="utf-8")
        summary["family_run_files"]["floor_area"] = str(floor_path)
        family_runs.append(floor_run)

    ceiling_candidates = collect_ceiling_lining_review_candidates(
        pdf,
        pages=tuple(topology_pages),
        workspace_id=workspace_id,
        project_id=project_id,
        authoritative_area_quantities=tuple(
            getattr(claim, "room_area_quantity_evidence", ()) or ()
        ),
    )
    summary["ceiling_quantity_count"] = len(ceiling_candidates)
    if ceiling_candidates:
        ceiling_run = seal_live_ceiling_review_run(
            ceiling_candidates,
            project_id=project_id,
        )
        ceiling_path = output_dir / "family_runs" / "ceiling_lining.sealed.json"
        ceiling_path.parent.mkdir(parents=True, exist_ok=True)
        ceiling_path.write_text(ceiling_run.to_json(), encoding="utf-8")
        summary["family_run_files"]["ceiling_lining"] = str(ceiling_path)
        family_runs.append(ceiling_run)

    if family_runs:
        combined = combine_source_closed_runs(family_runs, project_id=project_id)
        combined_path = output_dir / f"{project_id}.surfaces.topology.json"
        combined_path.write_text(combined.to_json(), encoding="utf-8")
        summary["combined_run_file"] = str(combined_path)
        summary["combined_quantity_count"] = len(combined.quantities)
        summary["combined_run_id"] = combined.run_id
        if source_sha not in set(combined.source_sha256s):
            raise RuntimeError("combined surface run does not bind to input source SHA")
        summary["status"] = "sealed"
    else:
        summary["status"] = "no_sealable_topology_surfaces"

    _write(output_dir / "production_summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary = run(
        pdf=args.pdf,
        project_id=args.project_id,
        workspace_id=args.workspace_id,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
