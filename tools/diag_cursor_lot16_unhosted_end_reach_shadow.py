"""Original Lot16: G17→W4 end-reach ledgers for unhosted openings."""
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
from pb_unhosted_end_reach_original import attach_end_reach_to_unhosted_openings
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_raster_unhosted_flank_source import (
    attach_end_reach_shadow_to_unhosted_rows,
    audit_g17_unhosted_flank_original_ancestry,
)

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def lot16_unhosted_end_reach_shadow_report(
    pdf: bytes, *, expected_sha256: str = LOT16_SHA,
) -> dict:
    if type(pdf) is not bytes or not pdf:
        raise TypeError("original PDF bytes required")
    digest = sha256(pdf).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original Lot16 source SHA mismatch")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf,
        source_locator="memory://cursor-lot16-end-reach.pdf",
        page_ids=(3,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=comp)
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    before = _retention(comp, voids, verify_customer_rows=True)
    ancestry = audit_g17_unhosted_flank_original_ancestry(source, published, comp)
    ids = [row["physical_opening_id"] for row in ancestry]
    attach = attach_end_reach_to_unhosted_openings(
        composition=comp, published=published, physical_opening_ids=ids,
    )
    by_id = {
        row["physical_opening_id"]: row["end_reach_ledger"]
        for row in attach["openings"]
        if row.get("end_reach_ledger") is not None
    }
    wired = attach_end_reach_shadow_to_unhosted_rows(ancestry, by_id)
    quantity_ids = {str(q["quantity_id"]) for q in before.get("quantities") or ()}
    return {
        "status": "UNPUBLISHED_LOT16_UNHOSTED_END_REACH_SHADOW",
        "source_sha256": digest,
        "page_id": PAGE_ID,
        "unhosted_opening_count": len(ancestry),
        "end_reach_attach": {
            "status": attach["status"],
            "opening_count": attach["opening_count"],
            "flank_disposition_counts": attach["flank_disposition_counts"],
            "source_line_gate_counts": dict(sorted(Counter(
                (row.get("source_line_census") or {}).get(
                    "source_line_first_gate") or "unavailable"
                for row in attach["openings"]
            ).items())),
            "openings": [
                {
                    "physical_opening_id": row["physical_opening_id"],
                    "first_remaining_gate": row["first_remaining_gate"],
                    "flank_dispositions": row.get("flank_dispositions") or [],
                    "source_line_census": row.get("source_line_census"),
                    "host_granted": False,
                }
                for row in attach["openings"]
            ],
        },
        "ancestry_rows_with_end_reach": sum(
            1 for row in wired if "g17_flank_w4_end_reach_shadow" in row
        ),
        "signed_eight_retained": len(quantity_ids) == 8,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", default=LOT16_SHA)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    raw = args.pdf.read_bytes()
    if sha256(raw).hexdigest() != args.sha256:
        raise SystemExit("source SHA mismatch")
    report = lot16_unhosted_end_reach_shadow_report(raw, expected_sha256=args.sha256)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "unhosted_opening_count": report["unhosted_opening_count"],
        "flank_disposition_counts": report["end_reach_attach"]["flank_disposition_counts"],
        "source_line_gate_counts": report["end_reach_attach"]["source_line_gate_counts"],
        "ancestry_rows_with_end_reach": report["ancestry_rows_with_end_reach"],
        "signed_eight_retained": report["signed_eight_retained"],
        "host_granted": False,
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
