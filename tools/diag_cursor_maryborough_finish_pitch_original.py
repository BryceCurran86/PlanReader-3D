"""Maryborough original finish + pitched-ceiling readiness (fail-closed)."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_maryborough_finish_pitch_readiness_original import (
    attach_maryborough_finish_pitch_readiness,
)
from tools.diag_gptmax_maryborough_room_first_owner_gate import (
    replay_original_maryborough_room_gate,
)

MARY_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", default=MARY_SHA)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    raw = args.pdf.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != args.sha256:
        raise SystemExit("SHA mismatch")
    room = replay_original_maryborough_room_gate(raw, expected_source_sha=digest)
    attach = attach_maryborough_finish_pitch_readiness(
        room["source_scope_first_failures"],
    )
    report = {
        "status": "UNPUBLISHED_MARYBOROUGH_FINISH_PITCH_ORIGINAL_REPORT",
        "source_sha256": digest,
        "topology_page_id": room.get("topology_page_id"),
        "room_gate": {
            "scope_count": len(room.get("source_scope_first_failures") or ()),
            "authenticated_floor_plan_viewport_count": room.get(
                "authenticated_floor_plan_viewport_count"),
            "room_area_quantity_publication_allowed": room.get(
                "room_area_quantity_publication_allowed"),
        },
        "finish_pitch_attach": {
            "scope_count": attach["scope_count"],
            "finish_gate_sample": sorted({
                r["finish_gate"] for r in attach["scopes"]
            }),
            "pitched_ceiling_gate_sample": sorted({
                r["pitched_ceiling_gate"] for r in attach["scopes"]
            }),
            "plain_floor_treated_as_finish": False,
        },
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
