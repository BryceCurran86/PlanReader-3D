"""Lot16 original batch42: raster_segment bridge split + joint gate censuses."""
from __future__ import annotations

import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_face_end_span_length_census_shadow import (
    census_g17_face_end_span_lengths_shadow,
)
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_source_observation_authority import ObservationSelector
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
        source_locator="memory://cursor-lot16-batch42.pdf",
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
    unhosted_set = set(unhosted_ids)

    span = census_g17_face_end_span_lengths_shadow(
        composition=comp, published=published, physical_opening_ids=unhosted_ids,
    )
    end_reach = attach_segment_line_end_reach_to_unhosted(
        composition=comp, published=published, physical_opening_ids=unhosted_ids,
    )
    kind_axis = attach_kind_and_axis_shadows(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id={r["physical_opening_id"]: r for r in before["canonical"]},
        observe_rows_by_id={r["physical_opening_id"]: r for r in existing},
    )
    by_kind = {r["physical_opening_id"]: r for r in kind_axis["openings"]}

    # W4 usable vs unusable on page-3 wall scope (first unhosted page).
    wall_auth = comp.physical_wall_candidate_authority
    usable = 0
    unusable = 0
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
    page_id = str(ancestry[0]["page_id"]) if ancestry else "3"
    wall_scope = wall_auth.resolve_scope(PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=f"wall-source:page-{page_id}",
    ))
    if wall_scope.status is EvidenceResolutionStatus.CORROBORATED:
        for record in wall_scope.records:
            if record.physical_identity.usable:
                usable += 1
            else:
                unusable += 1

    bridge_rows = []
    face_end_ratios = []
    for opening in span["openings"]:
        face_lens = [
            s["span_length_pdf_pts"] for s in opening["spans"]
            if s.get("observation_kind") == "raster_wall_band_face"
            and s.get("span_length_pdf_pts") is not None
        ]
        end_lens = [
            s["span_length_pdf_pts"] for s in opening["spans"]
            if s.get("observation_kind") == "raster_wall_band_end"
            and s.get("span_length_pdf_pts") is not None
        ]
        face_end_ratios.append({
            "physical_opening_id": opening["physical_opening_id"],
            "face_count": len(face_lens),
            "end_count": len(end_lens),
            "face_mean_pdf_pts": (sum(face_lens) / len(face_lens)) if face_lens else None,
            "end_mean_pdf_pts": (sum(end_lens) / len(end_lens)) if end_lens else None,
            "end_over_face_mean_ratio": (
                (sum(end_lens) / len(end_lens)) / (sum(face_lens) / len(face_lens))
                if face_lens and end_lens else None
            ),
        })

    for row in end_reach.get("openings") or ():
        inter = row.get("segment_w4_id_intersection") or {}
        bridge_rows.append({
            "physical_opening_id": row["physical_opening_id"],
            "namespace_bridge_gate": inter.get("namespace_bridge_gate"),
            "digit_tail_collision_count": inter.get("digit_tail_collision_count"),
            "digit_tail_collision_pairs_sample": inter.get(
                "digit_tail_collision_pairs_sample") or [],
            "seg_vs_raster_segment_digit_tail_count": inter.get(
                "seg_vs_raster_segment_digit_tail_count"),
            "seg_vs_d_index_digit_tail_count": inter.get(
                "seg_vs_d_index_digit_tail_count"),
            "w4_raster_segment_id_count": inter.get("w4_raster_segment_id_count"),
            "w4_d_index_id_count": inter.get("w4_d_index_id_count"),
            "segment_line_id_count": inter.get("segment_line_id_count"),
            "host_granted": False,
        })

    kind_tokens: Counter[str] = Counter()
    kind_unproven_joint = []
    signed_gates: Counter[str] = Counter()
    unsigned_gates: Counter[str] = Counter()
    frame_resolved_ids = []
    kind_empty_ids = []
    kind_label_ids = []
    label_bound_unsigned = []
    single_figured = []
    for decision in queue["opening_decisions"]:
        oid = str(decision["physical_opening_id"])
        gate = str(decision.get("first_remaining_gate") or "")
        if decision.get("prior_signed_quantity_id"):
            signed_gates[gate] += 1
        else:
            unsigned_gates[gate] += 1
        reasons = [str(r) for r in (decision.get("frame_reason_codes") or ())]
        if "opening_host_frame_resolved" in reasons:
            frame_resolved_ids.append(oid)
        canonical = next(r for r in before["canonical"] if r["physical_opening_id"] == oid)
        kind_token = str(canonical.get("opening_kind") or "") or "empty"
        ka = by_kind[oid]
        kind_gate = ka["kind_shadow"]["first_remaining_gate"]
        if kind_gate == "opening_filling_kind_source_supported":
            kind_tokens[kind_token] += 1
        eids = ka["kind_shadow"].get("source_kind_evidence_ids") or []
        if "unproven" in kind_gate:
            kind_unproven_joint.append({
                "physical_opening_id": oid,
                "handoff_first_remaining_gate": gate,
                "kind_gate": kind_gate,
                "unhosted": oid in unhosted_set,
                "evidence_id_count": len(eids),
            })
            if eids:
                kind_label_ids.append(oid)
            else:
                kind_empty_ids.append(oid)
        observed = next(r for r in existing if r["physical_opening_id"] == oid)
        evidence = (observed.get("original_label_dimension_result") or {}).get(
            "evidence") or {}
        if evidence.get("evidence_id") and not decision.get("prior_signed_quantity_id"):
            label_bound_unsigned.append(oid)
        values = evidence.get("dimension_values_mm") or ()
        if len(values) == 1:
            single_figured.append({
                "physical_opening_id": oid,
                "single_value_mm": float(values[0]),
                "door_height_would_need_second_axis": True,
            })

    parent_kind = Counter()
    for row in ancestry:
        for source_row in row.get("source_g17_observations") or ():
            for parent in source_row.get("authenticated_source_parents") or ():
                parent_kind[str(parent.get("observation_kind") or "")] += 1

    report = {
        "status": "UNPUBLISHED_LOT16_BATCH42_NAMESPACE_JOINT_CENSUS",
        "source_sha256": digest,
        "page_id": "3",
        "namespace_bridge_rows": bridge_rows,
        "namespace_bridge_gate_counts": dict(sorted(Counter(
            r["namespace_bridge_gate"] for r in bridge_rows
        ).items())),
        "seg_vs_raster_segment_digit_tail_counts": [
            r["seg_vs_raster_segment_digit_tail_count"] for r in bridge_rows
        ],
        "seg_vs_d_index_digit_tail_counts": [
            r["seg_vs_d_index_digit_tail_count"] for r in bridge_rows
        ],
        "digit_tail_collision_count_distribution": [
            r["digit_tail_collision_count"] for r in bridge_rows
        ],
        "face_end_ratios_per_opening": face_end_ratios,
        "wall_candidate_usable_count": usable,
        "wall_candidate_unusable_count": unusable,
        "kind_supported_opening_kind_tokens": dict(sorted(kind_tokens.items())),
        "kind_unproven_joint": kind_unproven_joint,
        "kind_empty_evidence_ids": kind_empty_ids,
        "kind_label_only_ids": kind_label_ids,
        "signed_first_gate_counts": dict(sorted(signed_gates.items())),
        "unsigned_first_gate_counts": dict(sorted(unsigned_gates.items())),
        "frame_resolved_opening_ids": frame_resolved_ids,
        "label_bound_unsigned_opening_ids": label_bound_unsigned,
        "single_figured_mm_values": single_figured,
        "parent_kind_counts": dict(sorted(parent_kind.items())),
        "flank_disposition_counts": end_reach["flank_disposition_counts"],
        "visible_observation_id_count": len(
            list(getattr(published.snapshot, "visible_observation_ids", ()) or ())),
        "segment_line_counts": [
            (row.get("segment_w4_id_intersection") or {}).get("segment_line_id_count")
            for row in (end_reach.get("openings") or ())
        ],
        "gptmax_pr_sync_note": {
            "3412": (
                "GPT MAX requires owned W2 fragments for local G17-to-W4 end-reach; "
                "Cursor digit-tail abstain remains independent — do not merge as host"
            ),
            "3405": "cached opening invalidation — complementary, not host grant",
            "merged_into_cursor_branch": False,
        },
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
        "namespace_bridge_gate_counts": report["namespace_bridge_gate_counts"],
        "seg_vs_raster_segment_digit_tail_counts": report[
            "seg_vs_raster_segment_digit_tail_counts"],
        "seg_vs_d_index_digit_tail_counts": report["seg_vs_d_index_digit_tail_counts"],
        "digit_tail_collision_count_distribution": report[
            "digit_tail_collision_count_distribution"],
        "kind_supported_opening_kind_tokens": report["kind_supported_opening_kind_tokens"],
        "wall_candidate_usable_count": usable,
        "wall_candidate_unusable_count": unusable,
        "parent_kind_counts": report["parent_kind_counts"],
        "signed_eight_retained": report["signed_eight_retained"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
