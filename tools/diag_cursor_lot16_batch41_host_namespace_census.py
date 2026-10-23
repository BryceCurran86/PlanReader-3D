"""Lot16 original batch41: FACE/END spans + segment↔W4 namespace bridges."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_face_end_span_length_census_shadow import (
    census_g17_face_end_span_lengths_shadow,
    geometric_proximity_abstain_shadow,
)
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_segment_w4_id_namespace_bridge_shadow import summarize_namespace_bridge_rows
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
        source_locator="memory://cursor-lot16-batch41.pdf",
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
    unhosted_ids = [r["physical_opening_id"] for r in ancestry]

    span = census_g17_face_end_span_lengths_shadow(
        composition=comp, published=published, physical_opening_ids=unhosted_ids,
    )
    end_reach = attach_segment_line_end_reach_to_unhosted(
        composition=comp, published=published, physical_opening_ids=unhosted_ids,
    )
    bridge_rows = []
    for row in end_reach.get("openings") or ():
        inter = row.get("segment_w4_id_intersection") or {}
        # Intersection now runs the full-set namespace bridge internally.
        bridge_rows.append({
            "physical_opening_id": row["physical_opening_id"],
            "first_remaining_gate": inter.get("namespace_bridge_gate")
            or inter.get("first_remaining_gate"),
            "digit_tail_collision_count": inter.get("digit_tail_collision_count") or 0,
            "digit_tail_collision_sample": inter.get("digit_tail_collision_sample") or [],
            "taxonomy": inter.get("namespace_taxonomy") or {},
            "exact_intersection_count": inter.get("exact_intersection_count") or 0,
            "usable_w4_primitive_id_count": inter.get("usable_w4_primitive_id_count"),
            "segment_line_id_count": inter.get("segment_line_id_count"),
            "host_granted": False,
        })
    bridge_summary = summarize_namespace_bridge_rows(bridge_rows)

    kind_axis = attach_kind_and_axis_shadows(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id={r["physical_opening_id"]: r for r in before["canonical"]},
        observe_rows_by_id={r["physical_opening_id"]: r for r in existing},
    )
    kind_empty = 0
    kind_label_only = 0
    single_figured_mm = []
    label_bound = []
    label_unbound = []
    unhosted_set = set(unhosted_ids)
    hosted_gates: Counter[str] = Counter()
    unhosted_gates: Counter[str] = Counter()
    frame_cooccur: Counter[str] = Counter()
    for decision in queue["opening_decisions"]:
        oid = str(decision["physical_opening_id"])
        gate = str(decision.get("first_remaining_gate") or "")
        if oid in unhosted_set:
            unhosted_gates[gate] += 1
        else:
            hosted_gates[gate] += 1
        reasons = sorted(str(r) for r in (decision.get("frame_reason_codes") or ()))
        if reasons:
            frame_cooccur["|".join(reasons)] += 1
        observed = next(r for r in existing if r["physical_opening_id"] == oid)
        evidence = (observed.get("original_label_dimension_result") or {}).get(
            "evidence") or {}
        if evidence.get("evidence_id"):
            label_bound.append(oid)
        else:
            label_unbound.append(oid)
        values = evidence.get("dimension_values_mm") or ()
        if len(values) == 1:
            try:
                single_figured_mm.append({
                    "physical_opening_id": oid,
                    "single_value_mm": float(values[0]),
                })
            except (TypeError, ValueError):
                pass

    for row in kind_axis["openings"]:
        gate = row["kind_shadow"]["first_remaining_gate"]
        eids = row["kind_shadow"].get("source_kind_evidence_ids") or []
        if "unproven" in gate:
            if eids:
                kind_label_only += 1
            else:
                kind_empty += 1

    # Synthetic proximity abstain on multi-candidate distances (no PDF geometry pick).
    proximity = geometric_proximity_abstain_shadow(
        candidate_distances_pdf_pts=[
            {"wall_candidate_id": "w:a", "distance_pdf_pts": 1.5},
            {"wall_candidate_id": "w:b", "distance_pdf_pts": 1.2},
            {"wall_candidate_id": "w:c", "distance_pdf_pts": 3.0},
        ],
    )

    customer_ids = [
        str(q["quantity_id"]) for q in (before.get("quantities") or ())
        if q.get("quantity_id")
    ]
    signed_from_decisions = [
        str(d["prior_signed_quantity_id"])
        for d in queue["opening_decisions"] if d.get("prior_signed_quantity_id")
    ]
    report = {
        "status": "UNPUBLISHED_LOT16_BATCH41_HOST_NAMESPACE_CENSUS",
        "source_sha256": digest,
        "page_id": "3",
        "span_summary_by_kind": span["span_summary_by_kind"],
        "namespace_bridge_summary": bridge_summary,
        "namespace_bridge_sample": [
            {
                "physical_opening_id": r["physical_opening_id"],
                "first_remaining_gate": r["first_remaining_gate"],
                "digit_tail_collision_count": r["digit_tail_collision_count"],
                "taxonomy": r["taxonomy"],
            }
            for r in bridge_rows
        ],
        "kind_unproven_empty_evidence_count": kind_empty,
        "kind_unproven_label_only_count": kind_label_only,
        "single_figured_mm_values": single_figured_mm,
        "label_bound_opening_count": len(label_bound),
        "label_unbound_opening_count": len(label_unbound),
        "unhosted_first_gate_counts": dict(sorted(unhosted_gates.items())),
        "hosted_first_gate_counts": dict(sorted(hosted_gates.items())),
        "frame_reason_cooccurrence_top": dict(sorted(
            frame_cooccur.items(), key=lambda kv: (-kv[1], kv[0]))[:12]),
        "geometric_proximity_abstain": {
            "first_remaining_gate": proximity["first_remaining_gate"],
            "nearest_wins_applied": proximity["nearest_wins_applied"],
            "selected_wall_candidate_id": proximity["selected_wall_candidate_id"],
        },
        "signed_quantity_ids_customer": customer_ids,
        "signed_quantity_ids_from_decisions": signed_from_decisions,
        "signed_id_sets_equal": sorted(customer_ids) == sorted(signed_from_decisions),
        "visible_observation_id_count": len(
            list(getattr(published.snapshot, "visible_observation_ids", ()) or ())),
        "flank_disposition_counts": end_reach["flank_disposition_counts"],
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
        "span_summary_by_kind": report["span_summary_by_kind"],
        "namespace_bridge_summary": report["namespace_bridge_summary"],
        "kind_unproven_empty_evidence_count": kind_empty,
        "kind_unproven_label_only_count": kind_label_only,
        "single_figured_mm_count": len(single_figured_mm),
        "signed_id_sets_equal": report["signed_id_sets_equal"],
        "visible_observation_id_count": report["visible_observation_id_count"],
        "signed_eight_retained": report["signed_eight_retained"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
