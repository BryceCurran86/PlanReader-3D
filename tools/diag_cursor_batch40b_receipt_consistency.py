"""Assert consistency across batch40 original receipts (no PDF, no score)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
MARY_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--multi-gate", type=Path, required=True)
    p.add_argument("--remaining", type=Path, required=True)
    p.add_argument("--face-end", type=Path, required=True)
    p.add_argument("--sibling", type=Path, required=True)
    p.add_argument("--maryborough", type=Path, required=True)
    p.add_argument("--four-project", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)

    multi = json.loads(args.multi_gate.read_text(encoding="utf-8"))
    remaining = json.loads(args.remaining.read_text(encoding="utf-8"))
    face = json.loads(args.face_end.read_text(encoding="utf-8"))
    sibling = json.loads(args.sibling.read_text(encoding="utf-8"))
    mary = json.loads(args.maryborough.read_text(encoding="utf-8"))
    four = json.loads(args.four_project.read_text(encoding="utf-8"))

    blockers = []
    for label, report, sha in (
        ("multi", multi, LOT16_SHA),
        ("remaining", remaining, LOT16_SHA),
        ("face", face, LOT16_SHA),
        ("sibling", sibling, LOT16_SHA),
    ):
        if report.get("source_sha256") != sha:
            blockers.append(f"{label}_sha_mismatch")
        if report.get("signed_eight_retained") is not True:
            blockers.append(f"{label}_signed_eight_not_retained")
        if report.get("benchmark_score_granted") is not False:
            blockers.append(f"{label}_score_flag")
    if mary.get("source_sha256") != MARY_SHA:
        blockers.append("mary_sha_mismatch")
    if mary.get("finish_pitch_attach", {}).get("plain_floor_treated_as_finish") is not False:
        blockers.append("mary_plain_floor_treated_as_finish")
    attach = remaining.get("remaining_gate_attach") or {}
    if attach.get("universe_gate") != "opening_universe_incomplete":
        blockers.append("universe_not_incomplete")
    if (attach.get("authorised_export") or {}).get("exportable_count") != 8:
        blockers.append("authorised_exportable_not_8")
    if (attach.get("authorised_export") or {}).get("withheld_count") != 13:
        blockers.append("authorised_withheld_not_13")
    if attach.get("w4_collision_count") != 0:
        blockers.append("w4_collision_nonzero")
    stub = (four.get("stub_report") or {})
    missing = set(stub.get("missing_project_keys") or ())
    if "au_qld_3laurel" not in missing or "au_qld_q5446" not in missing:
        blockers.append("stubs_not_explicit")

    report = {
        "status": (
            "BATCH40B_RECEIPT_CONSISTENCY_BLOCKED"
            if blockers
            else "BATCH40B_RECEIPT_CONSISTENCY_OK"
        ),
        "blockers": blockers,
        "multi_gate_opening_count": (multi.get("multi_gate_attach") or {}).get("opening_count"),
        "remaining_universe_gate": attach.get("universe_gate"),
        "face_end_opening_count": face.get("opening_count"),
        "sibling_hits": (sibling.get("sibling_summary") or {}).get("total_sibling_hits"),
        "four_project_missing": sorted(missing),
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
