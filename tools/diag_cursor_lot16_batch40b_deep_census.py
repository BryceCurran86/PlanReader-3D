"""Lot16 original batch40b deep census (one ingest, many shadow proofs)."""
from __future__ import annotations

import argparse
from collections import Counter
from collections.abc import Mapping
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_face_end_role_census_shadow import census_g17_face_end_roles_shadow
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_lot16_batch40b_deep_census_shadow import census_lot16_batch40b_deep
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


def _support_and_parent_kind_counts(ancestry) -> Counter:
    counts: Counter[str] = Counter()
    for row in ancestry:
        for source_row in row.get("source_g17_observations") or ():
            if not isinstance(source_row, Mapping):
                continue
            kind = str(source_row.get("observation_kind") or "")
            counts[f"support:{kind or 'empty'}"] += 1
            for parent_row in source_row.get("authenticated_source_parents") or ():
                if not isinstance(parent_row, Mapping):
                    counts["parent_ref_non_mapping"] += 1
                    continue
                pkind = str(parent_row.get("observation_kind") or "")
                counts[f"parent:{pkind or 'empty'}"] += 1
    return counts


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
        source_locator="memory://cursor-lot16-batch40b.pdf",
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
    parent_kinds = _support_and_parent_kind_counts(ancestry)
    face_end = census_g17_face_end_roles_shadow(
        composition=comp,
        published=published,
        physical_opening_ids=[r["physical_opening_id"] for r in ancestry],
    )
    end_reach = attach_segment_line_end_reach_to_unhosted(
        composition=comp,
        published=published,
        physical_opening_ids=[r["physical_opening_id"] for r in ancestry],
    )
    for row in end_reach.get("openings") or ():
        outcomes = ((row.get("segment_line_shadow") or {}).get("outcome_counts") or {})
        for key, n in outcomes.items():
            parent_kinds[f"segment_line_outcome:{key}"] += int(n)
    visible_ids = list(getattr(published.snapshot, "visible_observation_ids", ()) or ())
    census = census_lot16_batch40b_deep(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id={r["physical_opening_id"]: r for r in before["canonical"]},
        observe_rows_by_id={r["physical_opening_id"]: r for r in existing},
        unhosted_ancestry=ancestry,
        customer_quantity_ids=[
            str(q["quantity_id"]) for q in (before.get("quantities") or ())
            if q.get("quantity_id")
        ],
        parent_kind_counts=parent_kinds,
        visible_observation_id_count=len(visible_ids),
        face_end_support_kind_counts=face_end["support_kind_counts"],
        flank_disposition_counts=end_reach["flank_disposition_counts"],
    )
    report = {
        "status": "UNPUBLISHED_LOT16_BATCH40B_DEEP_CENSUS_REPORT",
        "source_sha256": digest,
        "page_id": "3",
        "census": census,
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
        "signed_eight_retained": report["signed_eight_retained"],
        "single_figured_opening_count": census["single_figured_opening_count"],
        "kind_gate_counts": census["kind_gate_counts"],
        "parent_kind_counts": census["parent_kind_counts"],
        "frame_reason_histogram": census["frame_reason_histogram"],
        "visible_observation_id_count": census["visible_observation_id_count"],
        "flank_disposition_counts": census["flank_disposition_counts"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
