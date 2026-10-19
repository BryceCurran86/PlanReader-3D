"""Original Lot16 page-3 kind + axis ownership attach (mission 9–12 shadow).

Default-off diagnostic over existing host/frame handoff receipts. Never invents
door height or publishes measurement.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_same_root_f07_g17_original import classify_live_view

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def lot16_kind_axis_shadow_report(pdf: bytes, *, expected_sha256: str = LOT16_SHA) -> dict:
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
        source_locator="memory://cursor-lot16-kind-axis.pdf",
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
    existing = _observe(source, published, comp, voids)
    views = segment_source_page_viewports(
        source, revision_id=pub.revision.revision_id, page_id=PAGE_ID,
        physical_plan_view_shadow=True)
    view = classify_live_view(views, expected_page=3)
    root = {k: getattr(pub.revision, k) for k in
            ("document_id", "revision_id", "source_sha256")}
    root["snapshot_id"] = published.snapshot.snapshot_id
    queue = assess_gpt1_opening_candidates(
        existing, before["canonical"], view, source_root=root)

    canonical_by_id = {r["physical_opening_id"]: r for r in before["canonical"]}
    observe_by_id = {r["physical_opening_id"]: r for r in existing}
    attach = attach_kind_and_axis_shadows(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id=canonical_by_id,
        observe_rows_by_id=observe_by_id,
    )
    signed = {
        str(r["prior_signed_quantity_id"])
        for r in queue["opening_decisions"]
        if r.get("prior_signed_quantity_id")
    }
    quantity_ids = {str(q["quantity_id"]) for q in before.get("quantities") or ()}
    return {
        "status": "UNPUBLISHED_LOT16_KIND_AXIS_SHADOW",
        "source_sha256": digest,
        "page_id": PAGE_ID,
        "first_gate_counts": dict(queue.get("first_gate_counts") or {}),
        "original_physical_opening_count": queue.get("original_physical_opening_count"),
        "original_signed_area_quantities": queue.get("original_signed_area_quantities"),
        "signed_eight_quantity_ids_retained": (
            len(signed) == 8 and signed <= quantity_ids
        ),
        "kind_axis_attach": {
            "status": attach["status"],
            "opening_count": attach["opening_count"],
            "kind_gate_counts": attach["kind_gate_counts"],
            "axis_gate_counts": attach["axis_gate_counts"],
            # Compact per-opening view (no full nested dumps).
            "openings": [
                {
                    "physical_opening_id": row["physical_opening_id"],
                    "handoff_first_remaining_gate": row["handoff_first_remaining_gate"],
                    "prior_signed_quantity_id": row["prior_signed_quantity_id"],
                    "kind_gate": row["kind_shadow"]["first_remaining_gate"],
                    "axis_gate": row["axis_shadow"]["first_remaining_gate"],
                    "figured_value_count": row["axis_shadow"]["figured_value_count"],
                    "invented_second_axis": False,
                }
                for row in attach["openings"]
            ],
        },
        "measurement_published": False,
        "customer_seal_granted": False,
        "opening_count_granted": False,
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
    report = lot16_kind_axis_shadow_report(raw, expected_sha256=args.sha256)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "first_gate_counts": report["first_gate_counts"],
        "kind_gate_counts": report["kind_axis_attach"]["kind_gate_counts"],
        "axis_gate_counts": report["kind_axis_attach"]["axis_gate_counts"],
        "signed_eight_quantity_ids_retained": report["signed_eight_quantity_ids_retained"],
        "measurement_published": False,
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
