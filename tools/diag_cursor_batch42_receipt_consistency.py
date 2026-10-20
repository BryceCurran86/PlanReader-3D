"""Cross-batch receipt invariants (no PDF, no score)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


LOT16 = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
MARY = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--multi-gate", type=Path, required=True)
    p.add_argument("--remaining", type=Path, required=True)
    p.add_argument("--batch41", type=Path, required=True)
    p.add_argument("--batch42", type=Path, required=True)
    p.add_argument("--maryborough", type=Path, required=True)
    p.add_argument("--four-project", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)

    multi = json.loads(args.multi_gate.read_text(encoding="utf-8"))
    remaining = json.loads(args.remaining.read_text(encoding="utf-8"))
    b41 = json.loads(args.batch41.read_text(encoding="utf-8"))
    b42 = json.loads(args.batch42.read_text(encoding="utf-8"))
    mary = json.loads(args.maryborough.read_text(encoding="utf-8"))
    four = json.loads(args.four_project.read_text(encoding="utf-8"))
    attach = remaining.get("remaining_gate_attach") or {}
    blockers = []

    for label, rep in (("multi", multi), ("remaining", remaining),
                       ("b41", b41), ("b42", b42)):
        if rep.get("source_sha256") != LOT16:
            blockers.append(f"{label}_sha")
        if rep.get("signed_eight_retained") is not True:
            blockers.append(f"{label}_signed_eight")
        if rep.get("benchmark_score_granted") is not False:
            blockers.append(f"{label}_score")
    if mary.get("source_sha256") != MARY:
        blockers.append("mary_sha")
    if attach.get("universe_gate") != "opening_universe_incomplete":
        blockers.append("universe")
    if (attach.get("authorised_export") or {}).get("exportable_count") != 8:
        blockers.append("exportable")
    if (attach.get("authorised_export") or {}).get("withheld_count") != 13:
        blockers.append("withheld")
    if attach.get("w4_collision_count") != 0:
        blockers.append("w4_collision")
    if (attach.get("wall_length_height_gate_counts") or {}).get(
            "wall_length_authority_unproven") != 21:
        blockers.append("wall_length")
    if b41.get("visible_observation_id_count") != 0:
        blockers.append("visible_ids")
    if b42.get("visible_observation_id_count") != 0:
        blockers.append("visible_ids_b42")
    if b42.get("parent_kind_counts") != {"raster_opening_primitive_segment": 48}:
        blockers.append("parent_kind")
    if list(b42.get("segment_line_counts") or ()) != [8, 8, 8, 8, 8, 8]:
        blockers.append("segment_line_counts")
    flank = b42.get("flank_disposition_counts") or {}
    if flank.get("raster_source_band_left_source_primitive_unmapped") != 6:
        blockers.append("flank_left")
    if flank.get("raster_source_band_right_source_primitive_unmapped") != 6:
        blockers.append("flank_right")
    if (b41.get("geometric_proximity_abstain") or {}).get(
            "nearest_wins_applied") is not False:
        blockers.append("proximity")
    gates = (multi.get("multi_gate_attach") or {}).get("gate_counts") or {}
    if (gates.get("door_height") or {}).get("door_height_second_axis_unavailable") != 21:
        blockers.append("door_height")
    if (gates.get("bifold_kind") or {}).get("bifold_plan_filling_role_unproven") != 21:
        blockers.append("bifold")
    if (multi.get("multi_gate_attach") or {}).get("source_lineage_status") != (
            "SOURCE_LINEAGE_FIELDS_PRESENT_REVIEW_ONLY"):
        blockers.append("lineage")
    if (multi.get("multi_gate_attach") or {}).get("frozen_v2_eval_gate") != (
            "eval_retention_check_only_no_score_claim"):
        blockers.append("frozen_v2")
    missing = set((four.get("stub_report") or {}).get("missing_project_keys") or ())
    if "au_qld_3laurel" not in missing or "au_qld_q5446" not in missing:
        blockers.append("stubs")
    finish = mary.get("finish_pitch_attach") or {}
    if finish.get("finish_gate_sample") != ["source_room_face_unavailable"]:
        blockers.append("mary_finish")
    if finish.get("pitched_ceiling_gate_sample") != ["ceiling_plan_area_authority_unproven"]:
        blockers.append("mary_pitch")
    if b42.get("namespace_bridge_gate_counts") != {
            "digit_tail_collision_ambiguous_abstain": 6}:
        blockers.append("ns_bridge")

    report = {
        "status": (
            "BATCH42_RECEIPT_CONSISTENCY_BLOCKED" if blockers
            else "BATCH42_RECEIPT_CONSISTENCY_OK"
        ),
        "blockers": blockers,
        "seg_vs_raster_segment_digit_tail_counts": b42.get(
            "seg_vs_raster_segment_digit_tail_counts"),
        "seg_vs_d_index_digit_tail_counts": b42.get("seg_vs_d_index_digit_tail_counts"),
        "kind_supported_opening_kind_tokens": b42.get(
            "kind_supported_opening_kind_tokens"),
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
