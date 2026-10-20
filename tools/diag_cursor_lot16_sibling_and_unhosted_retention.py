"""Lot16: visible-segment sibling search + unhosted vs signed-eight retention."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import RASTER_PDF_VISIBLE_SEGMENT, SourceVisibilityProducer
from pb_unhosted_vs_signed_eight_retention_shadow import (
    prove_unhosted_retention_vs_signed_eight,
)
from pb_visible_segment_sibling_search_shadow import (
    search_visible_segment_siblings_shadow,
    summarize_sibling_search_rows,
)
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_raster_unhosted_flank_source import (
    audit_g17_unhosted_flank_original_ancestry,
)
from tools.diag_gptmax_same_root_f07_g17_original import classify_live_view
from pb_viewport_segmentation import segment_source_page_viewports

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
        source_locator="memory://cursor-lot16-sibling-retention.pdf",
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
    ancestry = audit_g17_unhosted_flank_original_ancestry(source, published, comp)
    visibility = source.authority()
    page_visible = []
    for oid in list(getattr(published.snapshot, "visible_observation_ids", ()) or ()):
        # Only keep candidates that resolve as visible segments.
        page_visible.append(str(oid))
    sibling_rows = []
    for row in ancestry:
        supports = [
            str(x) for x in (row.get("authenticated_source_observation_ids") or ())
            if str(x).strip()
        ]
        sibling_rows.append(search_visible_segment_siblings_shadow(
            visibility=visibility,
            document_id=root["document_id"],
            revision_id=root["revision_id"],
            source_sha256=root["source_sha256"],
            snapshot_id=root["snapshot_id"],
            opening_support_observation_ids=supports,
            page_visible_segment_observation_ids=page_visible,
        ))
    sibling_summary = summarize_sibling_search_rows(sibling_rows)
    retention = prove_unhosted_retention_vs_signed_eight(
        unhosted_physical_opening_ids=[r["physical_opening_id"] for r in ancestry],
        all_physical_opening_ids=[
            d["physical_opening_id"] for d in queue["opening_decisions"]
        ],
        required_signed_quantity_ids=[
            str(q["quantity_id"]) for q in (before.get("quantities") or ())
            if q.get("quantity_id")
        ],
        observed_signed_quantity_ids=[
            str(d["prior_signed_quantity_id"])
            for d in queue["opening_decisions"]
            if d.get("prior_signed_quantity_id")
        ],
    )
    report = {
        "status": "UNPUBLISHED_LOT16_SIBLING_AND_UNHOSTED_RETENTION",
        "source_sha256": digest,
        "page_id": "3",
        "sibling_summary": sibling_summary,
        "visible_segment_kind_token": RASTER_PDF_VISIBLE_SEGMENT,
        "unhosted_vs_signed_eight": retention,
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
        "sibling_summary": sibling_summary,
        "unhosted_vs_signed_eight": {
            k: retention[k] for k in (
                "unhosted_opening_count", "all_opening_count",
                "signed_id_retention", "host_granted_to_unhosted",
            )
        },
        "signed_eight_retained": report["signed_eight_retained"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
