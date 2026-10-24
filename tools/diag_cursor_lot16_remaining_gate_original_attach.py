"""Lot16 original remaining-gate Cursor shadow attach."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_lot16_remaining_gate_original_attach import attach_lot16_remaining_gate_shadows
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_same_root_f07_g17_original import classify_live_view

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
        raise SystemExit("SHA mismatch")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=raw,
        source_locator="memory://cursor-lot16-remaining-gate.pdf",
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
    existing = _observe(source, published, comp, voids)
    views = segment_source_page_viewports(
        source, revision_id=pub.revision.revision_id, page_id="3",
        physical_plan_view_shadow=True)
    view = classify_live_view(views, expected_page=3)
    root = {k: getattr(pub.revision, k) for k in
            ("document_id", "revision_id", "source_sha256")}
    root["snapshot_id"] = published.snapshot.snapshot_id
    queue = assess_gpt1_opening_candidates(
        existing, before["canonical"], view, source_root=root)
    wall_records = []
    wall_auth = comp.physical_wall_candidate_authority
    for scope in getattr(wall_auth, "_scopes", {}).values():
        for rec in getattr(scope, "records", ()) or ():
            wall_records.append({
                "wall_candidate_id": getattr(rec, "wall_candidate_id", None)
                or getattr(rec, "candidate_id", None),
                "source_primitive_ids": getattr(rec, "source_primitive_ids", ()) or (),
                "centerline_pts": getattr(rec, "centerline_pts", ()) or (),
            })
    wall_records = [r for r in wall_records if r.get("wall_candidate_id")]
    attach = attach_lot16_remaining_gate_shadows(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id={r["physical_opening_id"]: r for r in before["canonical"]},
        observe_rows_by_id={r["physical_opening_id"]: r for r in existing},
        existing_observe_rows=existing,
        existing_canonical=before["canonical"],
        f07_view=view,
        source_root=root,
        customer_quantity_ids=[
            str(q["quantity_id"]) for q in (before.get("quantities") or ())
            if q.get("quantity_id")
        ],
        wall_candidate_records=wall_records,
    )
    report = {
        "status": "UNPUBLISHED_LOT16_REMAINING_GATE_ORIGINAL_REPORT",
        "source_sha256": digest,
        "page_id": "3",
        "remaining_gate_attach": attach,
        "signed_eight_retained": len(before.get("quantities") or ()) == 8,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "remaining_gate_attach": {
            k: attach[k] for k in (
                "inventory", "universe_gate", "signed_id_retention",
                "wall_length_height_gate_counts", "hosted_deduction_gate_counts",
                "frame_unrecorded_competitor_count", "authorised_export",
                "w4_collision_count",
            )
        },
        "signed_eight_retained": report["signed_eight_retained"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
