"""Generate benchmark-neutral source-closed production handoff artifacts.

This command runs source-owned production extraction against one PDF, discovers
eligible floor-plan topology from source evidence, seals every currently
supported production family, and combines those family runs into one project
handoff.

It deliberately has no dependency on frozen benchmark truth, expected
quantities, tolerances, denominator eligibility, identity maps, or scoring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

import fitz

from pb_ceiling_lining_review_promotion import (
    collect_ceiling_lining_review_candidates,
)
from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
from pb_live_ceiling_source_closed_export import seal_live_ceiling_review_run
from pb_live_opening_count_source_closed_export import (
    seal_live_opening_count_run,
)
from pb_live_opening_source_closed_export import (
    seal_live_opening_area_claim_run,
)
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_live_room_area_source_closed_export import seal_live_room_area_run
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    combine_source_closed_runs,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_topology_pages(path: Path) -> tuple[tuple[int, ...], int]:
    """Return zero-based pages that source authority recognizes as floor plans."""
    doc = fitz.open(path)
    try:
        page_count = int(doc.page_count)
        selected: list[int] = []
        for index in range(page_count):
            try:
                candidates = authoritative_floor_plan_viewports(
                    doc[index],
                    page_number=index + 1,
                )
            except Exception:
                continue
            if any(
                getattr(candidate, "bounding_box", None) is not None
                for candidate in candidates
            ):
                selected.append(index)
        return tuple(selected), page_count
    finally:
        doc.close()


def _non_abstained(
    quantities: Iterable[QuantityEvidence],
) -> tuple[QuantityEvidence, ...]:
    return tuple(
        quantity
        for quantity in quantities
        if isinstance(quantity, QuantityEvidence)
        and not quantity.abstained
        and quantity.value is not None
    )


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _write_run(
    directory: Path,
    family: str,
    run: SealedSourceClosedRun,
) -> Path:
    path = directory / "family_runs" / f"{family}.sealed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.to_json(), encoding="utf-8")
    return path


def generate_project_handoff(
    *,
    pdf_path: Path,
    project_id: str,
    workspace_id: int,
    output_dir: Path,
) -> dict[str, Any]:
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    project_id = _clean(project_id)
    if not project_id:
        raise ValueError("project_id must be non-empty")
    if isinstance(workspace_id, bool) or int(workspace_id) <= 0:
        raise ValueError("workspace_id must be a positive integer")

    source_sha256 = _sha256(pdf_path)
    topology_pages, page_count = _source_topology_pages(pdf_path)
    all_pages = tuple(range(page_count))
    topology_mode = (
        "source_viewport_hints"
        if topology_pages
        else "live_authority_all_pages_fallback"
    )

    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "source_path": str(pdf_path),
        "source_sha256": source_sha256,
        "page_count": page_count,
        "topology_pages": [page + 1 for page in topology_pages],
        "topology_mode": topology_mode,
        "status": "unavailable",
        "family_counts": {},
        "family_run_ids": {},
        "family_run_files": {},
        "combined_run_file": None,
        "combined_run_id": None,
        "canonical_counts": {},
        "claim_status": None,
        "claim_reason_codes": [],
    }

    output_dir.mkdir(parents=True, exist_ok=True)

    claim = collect_live_physical_net_wall_claim(
        pdf_path,
        pages=all_pages,
        topology_pages=(topology_pages if topology_pages else None),
        # Enable source-owned cross-view room measurement using the complete
        # source package. The producer itself remains responsible for deciding
        # which pages/evidence are authoritative.
        room_area_support_pages=all_pages,
    )
    summary["claim_status"] = getattr(
        getattr(claim, "status", None),
        "value",
        str(getattr(claim, "status", "")),
    )
    summary["claim_reason_codes"] = list(
        getattr(claim, "reason_codes", ()) or ()
    )
    summary["canonical_counts"] = {
        "walls": len(tuple(getattr(claim, "canonical_walls", ()) or ())),
        "openings": len(tuple(getattr(claim, "canonical_openings", ()) or ())),
        "rooms": len(tuple(getattr(claim, "canonical_rooms", ()) or ())),
        "floors": len(tuple(getattr(claim, "canonical_floors", ()) or ())),
        "spaces": len(tuple(getattr(claim, "canonical_spaces", ()) or ())),
    }

    family_runs: list[tuple[str, SealedSourceClosedRun]] = []

    room_quantities = _non_abstained(
        getattr(claim, "room_area_quantity_evidence", ())
    )
    summary["family_counts"]["room_area"] = len(room_quantities)
    if room_quantities:
        family_runs.append(
            (
                "room_area",
                seal_live_room_area_run(
                    claim,
                    workspace_id=int(workspace_id),
                    project_id=project_id,
                ),
            )
        )

    opening_area_quantities = _non_abstained(
        getattr(claim, "opening_quantity_evidence", ())
    )
    summary["family_counts"]["opening_area"] = len(
        opening_area_quantities
    )
    if opening_area_quantities:
        family_runs.append(
            (
                "opening_area",
                seal_live_opening_area_claim_run(
                    claim,
                    workspace_id=int(workspace_id),
                    project_id=project_id,
                ),
            )
        )

    opening_count_quantities = _non_abstained(
        getattr(claim, "opening_count_quantity_evidence", ())
    )
    summary["family_counts"]["opening_count"] = len(
        opening_count_quantities
    )
    if opening_count_quantities:
        family_runs.append(
            (
                "opening_count",
                seal_live_opening_count_run(
                    claim,
                    workspace_id=int(workspace_id),
                    project_id=project_id,
                ),
            )
        )

    ceiling_candidates = collect_ceiling_lining_review_candidates(
        pdf_path,
        pages=(topology_pages if topology_pages else all_pages),
        workspace_id=int(workspace_id),
        project_id=project_id,
        authoritative_area_quantities=tuple(
            getattr(claim, "room_area_quantity_evidence", ()) or ()
        ),
    )
    summary["family_counts"]["ceiling_lining"] = len(ceiling_candidates)
    if ceiling_candidates:
        family_runs.append(
            (
                "ceiling_lining",
                seal_live_ceiling_review_run(
                    ceiling_candidates,
                    project_id=project_id,
                ),
            )
        )

    for family, run in family_runs:
        run_path = _write_run(output_dir, family, run)
        summary["family_run_ids"][family] = run.run_id
        summary["family_run_files"][family] = str(run_path)
        # Every family handoff must still bind to the input PDF's exact bytes.
        if source_sha256 not in set(run.source_sha256s):
            raise RuntimeError(
                f"{family} sealed run does not bind to input source SHA"
            )

    if family_runs:
        combined = combine_source_closed_runs(
            tuple(run for _, run in family_runs),
            project_id=project_id,
        )
        combined_path = output_dir / f"{project_id}.sealed.json"
        combined_path.write_text(combined.to_json(), encoding="utf-8")
        summary["combined_run_file"] = str(combined_path)
        summary["combined_run_id"] = combined.run_id
        summary["combined_quantity_count"] = len(combined.quantities)
        summary["status"] = "sealed"
    else:
        summary["combined_quantity_count"] = 0
        summary["status"] = "no_sealable_quantities"

    _write_json(output_dir / "production_summary.json", summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate source-closed production handoff JSON."
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = generate_project_handoff(
        pdf_path=args.pdf,
        project_id=args.project_id,
        workspace_id=args.workspace_id,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
