"""Default-off compose of Cursor quantity-recovery shadow gates for one opening.

Does not call sealers, JobHub, or commercial exporters. Emits a ledger of
first_remaining_gate values only.
"""
from __future__ import annotations

import argparse
import json
from typing import Any, Mapping

from pb_bifold_filling_kind_shadow import assess_bifold_filling_kind_shadow
from pb_door_height_owner_gate_shadow import assess_door_height_owner_gate_shadow
from pb_stacker_host_frame_readiness_shadow import assess_stacker_host_frame_readiness_shadow


def compose_quantity_recovery_shadow_row(row: Mapping[str, Any]) -> dict[str, Any]:
    oid = str(row.get("physical_opening_id") or "").strip()
    if not oid:
        raise ValueError("physical_opening_id required")
    assessments = {
        "stacker_host_frame": assess_stacker_host_frame_readiness_shadow(
            physical_opening_id=oid,
            unique_image_frame_present=bool(row.get("unique_image_frame_present")),
            structural_host_wall_id=row.get("structural_host_wall_id"),
            host_binding_evidence_ids=tuple(row.get("host_binding_evidence_ids") or ()),
            host_frame_evidence_ids=tuple(row.get("host_frame_evidence_ids") or ()),
            competing_host_wall_ids=tuple(row.get("competing_host_wall_ids") or ()),
        ),
        "bifold_filling_kind": assess_bifold_filling_kind_shadow(
            physical_opening_id=oid,
            plan_filling_role_evidence_ids=tuple(
                row.get("plan_filling_role_evidence_ids") or ()
            ),
            manufacturer_or_elevation_evidence_ids=tuple(
                row.get("manufacturer_or_elevation_evidence_ids") or ()
            ),
            gap_geometry_present=bool(row.get("gap_geometry_present")),
        ),
        "door_height_owner_gate": assess_door_height_owner_gate_shadow(
            physical_opening_id=oid,
            owned_height_evidence_ids=tuple(row.get("owned_height_evidence_ids") or ()),
            owned_height_mm=row.get("owned_height_mm"),
            user_approved_height=bool(row.get("user_approved_height")),
            label_width_only_mm=row.get("label_width_only_mm"),
        ),
    }
    gates = {name: a["first_remaining_gate"] for name, a in assessments.items()}
    return {
        "physical_opening_id": oid,
        "assessments": assessments,
        "first_remaining_gates": gates,
        "any_measurement_published": False,
        "shadow_only": True,
        "benchmark_score_granted": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--row-json",
        required=True,
        help="Path to a single opening row JSON (diagnostic input only).",
    )
    args = parser.parse_args(argv)
    with open(args.row_json, encoding="utf-8") as fh:
        row = json.load(fh)
    print(json.dumps(compose_quantity_recovery_shadow_row(row), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
