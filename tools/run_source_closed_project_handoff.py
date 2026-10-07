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

from pb_live_ceiling_area_quantity_publication import (
    publish_live_ceiling_area_quantities,
)
from pb_live_ceiling_area_source_closed_export import seal_live_ceiling_area_run
from pb_live_ceiling_lining_integration import collect_live_ceiling_lining_claims
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_live_opening_count_source_closed_export import (
    seal_live_opening_count_run,
)
from pb_live_opening_source_closed_export import (
    seal_live_opening_area_claim_run,
)
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_live_floor_area_quantity_publication import (
    publish_live_floor_area_quantities,
)
from pb_live_floor_area_source_closed_export import seal_live_floor_area_run
from pb_live_floor_finish_area_source_closed_export import (
    seal_live_floor_finish_area_run,
)
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


def _source_page_scopes(
    path: Path,
) -> tuple[tuple[int, ...], tuple[int, ...], int]:
    """Return production topology + cross-view support scopes from source evidence.

    This mirrors the customer runtime contract:
    - topology narrows only when source classification positively proves it;
    - cross-view room-area support receives only positively classified evidence
      pages;
    - when scope is unavailable/unproven, topology remains the full universe and
      no extra room-area support pages are invented.
    """
    doc = fitz.open(path)
    try:
        page_count = int(doc.page_count)
    finally:
        doc.close()

    selected = tuple(range(page_count))
    if not selected:
        return (), (), page_count

    scope = source_floor_plan_topology_scope(path, selected)
    if scope is None:
        return selected, (), page_count

    topology = scope.topology_page_indices()
    support = tuple(
        getattr(
            scope,
            "room_area_support_page_indices",
            getattr(scope, "evidence_page_indices", ()),
        )
        or ()
    )
    if topology is None:
        return selected, (), page_count
    return tuple(topology), support, page_count


def _source_topology_pages(path: Path) -> tuple[tuple[int, ...], int]:
    """Compatibility helper for diagnostics that need only topology pages."""
    topology, _support, page_count = _source_page_scopes(path)
    return topology, page_count


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
    family_group: str = "all",
) -> dict[str, Any]:
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)
    project_id = _clean(project_id)
    if not project_id:
        raise ValueError("project_id must be non-empty")
    if isinstance(workspace_id, bool) or int(workspace_id) <= 0:
        raise ValueError("workspace_id must be a positive integer")

    clean_family_group = str(family_group or "").strip().lower()
    if clean_family_group not in {"all", "core", "surfaces"}:
        raise ValueError(
            "family_group must be one of: all, core, surfaces"
        )

    source_sha256 = _sha256(pdf_path)
    topology_pages, room_area_support_pages, page_count = _source_page_scopes(
        pdf_path
    )
    all_pages = tuple(range(page_count))
    topology_restricted = bool(topology_pages) and (
        tuple(topology_pages) != tuple(all_pages)
    )
    topology_mode = (
        "source_classified_scope"
        if topology_restricted
        else "live_authority_all_pages_fallback"
    )

    if topology_restricted:
        if clean_family_group == "core":
            # Core execution is intentionally topology-only.
            execution_pages = tuple(topology_pages)
            execution_room_support_pages = None
        else:
            # Surface semantics may be authenticated by schedules, legends,
            # reflected-ceiling plans and other non-topology source pages.
            # Keep the full selected source universe visible to semantic
            # authorities while topology remains restricted by topology_pages
            # and room measurement remains restricted by the explicit support
            # page set below.
            execution_pages = tuple(all_pages)
            execution_room_support_pages = (
                room_area_support_pages
                if room_area_support_pages
                else None
            )
    else:
        execution_pages = all_pages
        execution_room_support_pages = (
            room_area_support_pages
            if room_area_support_pages
            else None
        )

    summary: dict[str, Any] = {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "source_path": str(pdf_path),
        "source_sha256": source_sha256,
        "page_count": page_count,
        "topology_pages": [page + 1 for page in topology_pages],
        "room_area_support_pages": [
            page + 1 for page in room_area_support_pages
        ],
        "topology_mode": topology_mode,
        "family_group": clean_family_group,
        "complete_project_handoff": clean_family_group == "all",
        "execution_pages": [page + 1 for page in execution_pages],
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

    try:
        claim = collect_live_physical_net_wall_claim(
            pdf_path,
            pages=execution_pages,
            topology_pages=(topology_pages if topology_restricted else None),
            # Core-family execution never activates cross-view room-area
            # measurement. Surface/all execution retains the source-classified
            # support-page contract.
            room_area_support_pages=execution_room_support_pages,
        )
    except Exception as exc:
        summary["status"] = "production_failed"
        summary["production_error_type"] = type(exc).__name__
        summary["production_error_message"] = str(exc)
        summary["claim_reason_codes"] = [
            f"production_extraction_error:{type(exc).__name__}"
        ]
        _write_json(output_dir / "production_summary.json", summary)
        raise
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

    if clean_family_group in {"all", "surfaces"}:
        floor_quantities = _non_abstained(
            publish_live_floor_area_quantities(claim)
        )
    else:
        floor_quantities = ()
    summary["family_counts"]["floor_area"] = len(floor_quantities)
    if floor_quantities:
        family_runs.append(
            (
                "floor_area",
                seal_live_floor_area_run(
                    claim,
                    workspace_id=int(workspace_id),
                    project_id=project_id,
                ),
            )
        )

    if clean_family_group in {"all", "surfaces"}:
        floor_finish_quantities = _non_abstained(
            getattr(claim, "floor_finish_quantity_evidence", ())
        )
    else:
        floor_finish_quantities = ()
    summary["family_counts"]["floor_finish_area"] = len(
        floor_finish_quantities
    )
    if floor_finish_quantities:
        family_runs.append(
            (
                "floor_finish_area",
                seal_live_floor_finish_area_run(
                    claim,
                    workspace_id=int(workspace_id),
                    project_id=project_id,
                ),
            )
        )

    if clean_family_group in {"all", "core"}:
        opening_area_quantities = _non_abstained(
            getattr(claim, "opening_quantity_evidence", ())
        )
    else:
        opening_area_quantities = ()
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

    if clean_family_group in {"all", "core"}:
        opening_count_quantities = _non_abstained(
            getattr(claim, "opening_count_quantity_evidence", ())
        )
    else:
        opening_count_quantities = ()
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

    if clean_family_group in {"all", "surfaces"}:
        ceiling_result = collect_live_ceiling_lining_claims(
            pdf_path,
            # Keep the full source evidence universe available to ceiling
            # semantics, while restricting expensive topology to the already
            # source-classified physical drawing pages.
            pages=execution_pages,
            topology_pages=(
                topology_pages if topology_pages else execution_pages
            ),
            authoritative_room_area_quantities=tuple(
                getattr(claim, "room_area_quantity_evidence", ()) or ()
            ),
        )
        ceiling_quantities = _non_abstained(
            publish_live_ceiling_area_quantities(ceiling_result)
        )
    else:
        ceiling_result = None
        ceiling_quantities = ()
    summary["family_counts"]["ceiling_area"] = len(ceiling_quantities)
    if ceiling_quantities and ceiling_result is not None:
        family_runs.append(
            (
                "ceiling_area",
                seal_live_ceiling_area_run(
                    ceiling_result,
                    workspace_id=int(workspace_id),
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
        combined_filename = (
            f"{project_id}.json"
            if clean_family_group == "all"
            else f"{project_id}.{clean_family_group}.json"
        )
        combined_path = output_dir / combined_filename
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
    parser.add_argument(
        "--family-group",
        choices=("all", "core", "surfaces"),
        default="all",
        help=(
            "Families to seal: all=current behavior, "
            "core=opening area/count only, surfaces=floor/ceiling only"
        ),
    )
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    summary = generate_project_handoff(
        pdf_path=args.pdf,
        project_id=args.project_id,
        workspace_id=args.workspace_id,
        output_dir=args.output_dir,
        family_group=args.family_group,
    )
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
