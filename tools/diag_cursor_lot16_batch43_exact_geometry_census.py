"""Lot16 original: exact geometry identity census + kind/870mm joint ledgers."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_segment_w4_exact_geometry_identity_shadow import summarize_exact_geometry_rows
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_unhosted_end_reach_segment_line_shadow import (
    attach_segment_line_end_reach_to_unhosted,
)
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_raster_unhosted_flank_source import (
    audit_g17_unhosted_flank_original_ancestry,
)
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
        source_locator="memory://cursor-lot16-batch43.pdf",
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
    end_reach = attach_segment_line_end_reach_to_unhosted(
        composition=comp,
        published=published,
        physical_opening_ids=[r["physical_opening_id"] for r in ancestry],
    )
    geom_rows = []
    for row in end_reach.get("openings") or ():
        g = row.get("segment_w4_exact_geometry_identity") or {}
        geom_rows.append({
            "physical_opening_id": row["physical_opening_id"],
            "first_remaining_gate": g.get("first_remaining_gate"),
            "exact_match_count": g.get("exact_match_count"),
            "matched_wall_candidate_ids": g.get("matched_wall_candidate_ids") or [],
            "segment_line_count": g.get("segment_line_count"),
            "w4_centerline_edge_count": g.get("w4_centerline_edge_count"),
            "matches_sample": g.get("matches_sample") or [],
            "gptmax_3412_fragment_field_present": row.get(
                "gptmax_3412_fragment_field_present"),
            "host_granted": False,
        })
    geom_summary = summarize_exact_geometry_rows(geom_rows)

    kind_axis = attach_kind_and_axis_shadows(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id={r["physical_opening_id"]: r for r in before["canonical"]},
        observe_rows_by_id={r["physical_opening_id"]: r for r in existing},
    )
    kind_unproven = []
    single_870 = []
    for row in kind_axis["openings"]:
        oid = row["physical_opening_id"]
        kg = row["kind_shadow"]["first_remaining_gate"]
        if "unproven" in kg:
            kind_unproven.append({
                "physical_opening_id": oid,
                "kind_gate": kg,
                "source_kind_evidence_ids": row["kind_shadow"].get(
                    "source_kind_evidence_ids") or [],
                "handoff_first_remaining_gate": row.get("handoff_first_remaining_gate"),
            })
        observed = next(r for r in existing if r["physical_opening_id"] == oid)
        evidence = (observed.get("original_label_dimension_result") or {}).get(
            "evidence") or {}
        values = evidence.get("dimension_values_mm") or ()
        if len(values) == 1 and float(values[0]) == 870.0:
            single_870.append(oid)

    report = {
        "status": "UNPUBLISHED_LOT16_BATCH43_EXACT_GEOMETRY_CENSUS",
        "source_sha256": digest,
        "page_id": "3",
        "exact_geometry_summary": geom_summary,
        "exact_geometry_openings": geom_rows,
        "kind_unproven_ledger": kind_unproven,
        "single_figured_870mm_opening_ids": single_870,
        "single_figured_870mm_count": len(single_870),
        "invented_second_axis": False,
        "flank_disposition_counts": end_reach["flank_disposition_counts"],
        "gptmax_3412_fragment_field_present_any": any(
            r.get("gptmax_3412_fragment_field_present") for r in geom_rows
        ),
        "gptmax_3412_sync_note": (
            "PR #3412 adds owned W2 fragment end-reach fields; not present on "
            "this Cursor branch until GPT MAX lands — Cursor does not cherry-pick "
            "as host authority"
        ),
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
        "exact_geometry_summary": geom_summary,
        "kind_unproven_count": len(kind_unproven),
        "single_figured_870mm_count": len(single_870),
        "gptmax_3412_fragment_field_present_any": report[
            "gptmax_3412_fragment_field_present_any"],
        "signed_eight_retained": report["signed_eight_retained"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
