"""Lot16 original: end-reach with segment-parent line shadow (host lever)."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_unhosted_end_reach_segment_line_shadow import (
    attach_segment_line_end_reach_to_unhosted,
)
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_raster_unhosted_flank_source import (
    audit_g17_unhosted_flank_original_ancestry,
)

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", default=LOT16_SHA)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    raw = args.pdf.read_bytes()
    digest = sha256(raw).hexdigest()
    if digest != args.sha256:
        raise SystemExit("source SHA mismatch")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=raw,
        source_locator="memory://cursor-lot16-segment-line-end-reach.pdf",
        page_ids=(3,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        page_ids=("3",),
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=comp)
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    before = _retention(comp, voids, verify_customer_rows=True)
    ancestry = audit_g17_unhosted_flank_original_ancestry(source, published, comp)
    attach = attach_segment_line_end_reach_to_unhosted(
        composition=comp,
        published=published,
        physical_opening_ids=[r["physical_opening_id"] for r in ancestry],
    )
    report = {
        "status": "UNPUBLISHED_LOT16_SEGMENT_LINE_END_REACH_SHADOW",
        "source_sha256": digest,
        "page_id": "3",
        "unhosted_opening_count": len(ancestry),
        "flank_disposition_counts": attach["flank_disposition_counts"],
        "openings": [
            {
                "physical_opening_id": row["physical_opening_id"],
                "segment_line_count": (row.get("segment_line_shadow") or {}).get(
                    "authenticated_segment_line_count"),
                "segment_w4_id_gate": (row.get("segment_w4_id_intersection") or {}).get(
                    "first_remaining_gate"),
                "exact_intersection_count": (row.get("segment_w4_id_intersection") or {}).get(
                    "exact_intersection_count"),
                "sample_segment_line_ids": (row.get("segment_w4_id_intersection") or {}).get(
                    "sample_segment_line_ids"),
                "sample_w4_primitive_ids": (row.get("segment_w4_id_intersection") or {}).get(
                    "sample_w4_primitive_ids"),
                "flank_dispositions": row.get("flank_dispositions") or [],
                "host_granted": False,
            }
            for row in attach["openings"]
        ],
        "segment_w4_id_gate_counts": dict(sorted(Counter(
            (row.get("segment_w4_id_intersection") or {}).get(
                "first_remaining_gate") or "unavailable"
            for row in attach["openings"]
        ).items())),
        "signed_eight_retained": len(before.get("quantities") or ()) == 8,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "unhosted_opening_count": report["unhosted_opening_count"],
        "flank_disposition_counts": report["flank_disposition_counts"],
        "signed_eight_retained": report["signed_eight_retained"],
        "host_granted": False,
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
