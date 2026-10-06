"""Generate source-closed floor/ceiling family handoffs from positive source views.

This runner is deliberately narrower than the full project handoff. It uses only
positively source-classified floor-plan sheets for topology and positively
classified cross-view sheets (elevation/section/detail) as optional room-area
support. It seals only final floor-area and promoted ceiling-area quantities.

The result is a *partial family handoff*, not a claim that the whole project was
executed. Unproven or unsupported pages are never converted to zero or treated
as absent benchmark objects.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import fitz

from pb_ceiling_lining_review_promotion import (
    collect_ceiling_lining_review_candidates,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_live_ceiling_source_closed_export import seal_live_ceiling_review_run
from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
)
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    combine_source_closed_runs,
)
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope


ROOM_SUPPORT_VIEW_TYPES = frozenset(
    {
        DrawingViewType.ELEVATION.value,
        DrawingViewType.SECTION.value,
        DrawingViewType.DETAIL.value,
    }
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _positive_room_surface_scope(
    pdf_path: Path,
) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    """Return positive floor topology and positive cross-view support pages.

    This is intentionally stricter than the whole-project page scope. The
    returned scope is valid only for this partial room-surface handoff.
    """
    doc = fitz.open(str(pdf_path))
    try:
        page_count = int(doc.page_count)
    finally:
        doc.close()

    selected = tuple(range(page_count))
    scope = source_floor_plan_topology_scope(pdf_path, selected)
    if scope is None:
        return (), (), page_count

    floor_pages = tuple(
        sorted(
            {
                int(value)
                for value in tuple(scope.floor_plan_page_indices or ())
                if 0 <= int(value) < page_count
            }
        )
    )
    support_pages = tuple(
        sorted(
            {
                int(decision.page_index)
                for decision in tuple(scope.decisions or ())
                if int(decision.page_index) not in set(floor_pages)
                and bool(
                    set(tuple(decision.view_types or ()))
                    & ROOM_SUPPORT_VIEW_TYPES
                )
            }
        )
    )
    return floor_pages, support_pages, page_count


def _write_run(
    output_dir: Path,
    family: str,
    run: SealedSourceClosedRun,
) -> str:
    path = output_dir / "family_runs" / f"{family}.sealed.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(run.to_json(), encoding="utf-8")
    return str(path)


def generate_room_surface_handoff(
    *,
    pdf_path: Path,
    project_id: str,
    workspace_id: int,
    output_dir: Path,
) -> dict[str, Any]:
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    project_id = str(project_id or "").strip()
    if not project_id:
        raise ValueError("project_id must be non-empty")
    if isinstance(workspace_id, bool) or int(workspace_id) <= 0:
        raise ValueError("workspace_id must be a positive integer")

    source_sha256 = _sha256(pdf_path)
    floor_pages, support_pages, page_count = _positive_room_surface_scope(pdf_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "handoff_scope": "partial_room_surfaces",
        "project_id": project_id,
        "source_path": str(pdf_path),
        "source_sha256": source_sha256,
        "page_count": page_count,
        "floor_plan_pages": [value + 1 for value in floor_pages],
        "room_support_pages": [value + 1 for value in support_pages],
        "family_counts": {"floor_area": 0, "ceiling_lining": 0},
        "family_run_ids": {},
        "family_run_files": {},
        "combined_run_id": None,
        "combined_run_file": None,
        "claim_status": None,
        "claim_reason_codes": [],
        "status": "unavailable",
        "scope_complete_for_project": False,
    }

    if not floor_pages:
        summary["claim_reason_codes"] = [
            "no_positively_classified_floor_plan_page"
        ]
        _write_json(output_dir / "room_surface_summary.json", summary)
        return summary

    try:
        claim = collect_live_physical_net_wall_claim(
            pdf_path,
            pages=floor_pages,
            topology_pages=floor_pages,
            room_area_support_pages=(support_pages if support_pages else None),
        )
    except Exception as exc:
        summary["status"] = "production_failed"
        summary["production_error_type"] = type(exc).__name__
        summary["production_error_message"] = str(exc)
        summary["claim_reason_codes"] = [
            f"production_extraction_error:{type(exc).__name__}"
        ]
        _write_json(output_dir / "room_surface_summary.json", summary)
        raise

    summary["claim_status"] = getattr(
        getattr(claim, "status", None),
        "value",
        str(getattr(claim, "status", "")),
    )
    summary["claim_reason_codes"] = list(
        tuple(getattr(claim, "reason_codes", ()) or ())
    )

    family_runs: list[tuple[str, SealedSourceClosedRun]] = []

    floor_quantities = tuple(
        quantity
        for quantity in publish_live_floor_area_quantities(claim)
        if not quantity.abstained and quantity.value is not None
    )
    summary["family_counts"]["floor_area"] = len(floor_quantities)
    if floor_quantities:
        floor_run = seal_live_floor_area_run(
            claim,
            workspace_id=int(workspace_id),
            project_id=project_id,
        )
        family_runs.append(("floor_area", floor_run))

    ceiling_candidates = collect_ceiling_lining_review_candidates(
        pdf_path,
        pages=floor_pages,
        workspace_id=int(workspace_id),
        project_id=project_id,
        authoritative_area_quantities=tuple(
            getattr(claim, "room_area_quantity_evidence", ()) or ()
        ),
    )
    summary["family_counts"]["ceiling_lining"] = len(ceiling_candidates)
    if ceiling_candidates:
        ceiling_run = seal_live_ceiling_review_run(
            ceiling_candidates,
            project_id=project_id,
        )
        family_runs.append(("ceiling_lining", ceiling_run))

    for family, run in family_runs:
        if source_sha256 not in set(run.source_sha256s):
            raise RuntimeError(
                f"{family} sealed run does not bind to input source SHA"
            )
        summary["family_run_ids"][family] = run.run_id
        summary["family_run_files"][family] = _write_run(
            output_dir,
            family,
            run,
        )

    if family_runs:
        combined = combine_source_closed_runs(
            tuple(run for _, run in family_runs),
            project_id=project_id,
        )
        combined_path = output_dir / f"{project_id}.room_surfaces.json"
        combined_path.write_text(combined.to_json(), encoding="utf-8")
        summary["combined_run_id"] = combined.run_id
        summary["combined_run_file"] = str(combined_path)
        summary["combined_quantity_count"] = len(combined.quantities)
        summary["status"] = "sealed_partial_family_scope"
    else:
        summary["combined_quantity_count"] = 0
        summary["status"] = "no_sealable_room_surface_quantities"

    _write_json(output_dir / "room_surface_summary.json", summary)
    return summary


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate source-closed floor/ceiling family handoff JSON."
    )
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--workspace-id", type=int, default=1)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = generate_room_surface_handoff(
        pdf_path=args.pdf,
        project_id=args.project_id,
        workspace_id=args.workspace_id,
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
