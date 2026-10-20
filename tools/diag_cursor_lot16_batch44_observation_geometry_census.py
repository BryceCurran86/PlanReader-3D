"""Lot16 original: producer visible-segment geometry identity + kind/height gaps."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_door_height_owner_gate_shadow import assess_door_height_owner_gate_shadow
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_kind_axis_original_attach import attach_kind_and_axis_shadows
from pb_segment_w4_observation_geometry_identity_shadow import (
    assess_segment_w4_observation_geometry_identity_shadow,
    summarize_observation_geometry_rows,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_unhosted_end_reach_segment_line_shadow import (
    attach_segment_line_end_reach_to_unhosted,
)
from pb_viewport_segmentation import segment_source_page_viewports
from pb_w4_raster_segment_geometry_index_shadow import (
    index_published_visible_segment_geometries_shadow,
)
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
        source_locator="memory://cursor-lot16-batch44.pdf",
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
    visibility = source.authority()
    index = index_published_visible_segment_geometries_shadow(
        visibility=visibility, published=published,
    )
    geom_by_ref = index["geometries_by_ref"]

    # Rebuild W4 wall maps once from the first opening's end-reach wall records
    # already computed inside attach; fall back to composition page scope.
    obs_rows = []
    for row in end_reach.get("openings") or ():
        lines = ((row.get("segment_line_shadow") or {}).get(
            "lines_by_raw_primitive_id") or {})
        w4_maps = []
        # End-reach does not currently emit wall maps; recover from intersection samples
        # plus composition wall scope via the same page as ancestry.
        obs_rows.append((row["physical_opening_id"], lines, row))

    from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
    from pb_migration_contracts import EvidenceResolutionStatus
    page_id = str(ancestry[0]["page_id"]) if ancestry else "3"
    wall_scope = comp.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
    )
    w4_maps = []
    if wall_scope.status is EvidenceResolutionStatus.CORROBORATED:
        for record in wall_scope.records:
            if not record.physical_identity.usable:
                continue
            w4_maps.append({
                "wall_candidate_id": record.wall_candidate_id,
                "source_primitive_ids": list(
                    record.physical_identity.source_primitive_ids or ()),
            })

    identity_rows = []
    for oid, lines, _row in obs_rows:
        assessed = assess_segment_w4_observation_geometry_identity_shadow(
            physical_opening_id=oid,
            segment_lines_by_id=lines,
            w4_wall_records=w4_maps,
            geometries_by_ref=geom_by_ref,
        )
        identity_rows.append({
            "physical_opening_id": oid,
            "first_remaining_gate": assessed["first_remaining_gate"],
            "exact_match_count": assessed["exact_match_count"],
            "collinear_overlap_match_count": assessed["collinear_overlap_match_count"],
            "exact_matched_wall_candidate_ids": assessed["exact_matched_wall_candidate_ids"],
            "overlap_matched_wall_candidate_ids": assessed[
                "overlap_matched_wall_candidate_ids"],
            "w4_primitives_with_indexed_geometry": assessed[
                "w4_primitives_with_indexed_geometry"],
            "w4_primitives_missing_indexed_geometry": assessed[
                "w4_primitives_missing_indexed_geometry"],
            "host_granted": False,
        })
    summary = summarize_observation_geometry_rows(identity_rows)

    kind_axis = attach_kind_and_axis_shadows(
        opening_decisions=queue["opening_decisions"],
        canonical_by_id={r["physical_opening_id"]: r for r in before["canonical"]},
        observe_rows_by_id={r["physical_opening_id"]: r for r in existing},
    )
    kind_unproven_split = {"empty_kind": [], "token_without_evidence": []}
    height_rows = []
    for row in kind_axis["openings"]:
        oid = row["physical_opening_id"]
        kg = row["kind_shadow"]["first_remaining_gate"]
        token = row["kind_shadow"].get("opening_kind")
        if kg == "opening_filling_kind_unproven":
            kind_unproven_split["empty_kind"].append(oid)
        elif kg == "opening_filling_kind_evidence_unproven":
            kind_unproven_split["token_without_evidence"].append({
                "physical_opening_id": oid,
                "opening_kind": token,
            })
        observed = next(r for r in existing if r["physical_opening_id"] == oid)
        evidence = (observed.get("original_label_dimension_result") or {}).get(
            "evidence") or {}
        values = evidence.get("dimension_values_mm") or ()
        canonical = next(c for c in before["canonical"] if c["physical_opening_id"] == oid)
        width_only = float(values[0]) if len(values) == 1 else None
        height_gate = assess_door_height_owner_gate_shadow(
            physical_opening_id=oid,
            owned_height_evidence_ids=(
                (str(canonical["height_record_id"]),)
                if canonical.get("height_record_id") else ()
            ),
            owned_height_mm=canonical.get("height_m"),
            user_approved_height=False,
            label_width_only_mm=width_only,
        )
        if width_only is not None:
            height_rows.append({
                "physical_opening_id": oid,
                "label_width_only_mm": width_only,
                "canonical_height_record_id": canonical.get("height_record_id"),
                "canonical_height_m": canonical.get("height_m"),
                "door_height_gate": height_gate["first_remaining_gate"],
                "invented_second_axis_mm": height_gate["invented_second_axis_mm"],
            })

    report = {
        "status": "UNPUBLISHED_LOT16_BATCH44_OBSERVATION_GEOMETRY_CENSUS",
        "source_sha256": digest,
        "page_id": "3",
        "producer_visible_observation_id_count": index[
            "producer_visible_observation_id_count"],
        "snapshot_visible_observation_id_count": index[
            "snapshot_visible_observation_id_count"],
        "indexed_ref_count": index["indexed_ref_count"],
        "index_kind_counts": index["kind_counts"],
        "observation_geometry_summary": summary,
        "observation_geometry_openings": identity_rows,
        "kind_unproven_split": kind_unproven_split,
        "single_figured_height_gap": height_rows,
        "invented_second_axis": False,
        "signed_eight_retained": len(before.get("quantities") or ()) == 8,
        "host_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    # Drop huge geometry map from on-disk receipt.
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "status": report["status"],
        "producer_visible_observation_id_count": report[
            "producer_visible_observation_id_count"],
        "snapshot_visible_observation_id_count": report[
            "snapshot_visible_observation_id_count"],
        "indexed_ref_count": report["indexed_ref_count"],
        "index_kind_counts": report["index_kind_counts"],
        "observation_geometry_summary": summary,
        "kind_unproven_empty_count": len(kind_unproven_split["empty_kind"]),
        "kind_token_without_evidence_count": len(
            kind_unproven_split["token_without_evidence"]),
        "single_figured_height_gap_count": len(height_rows),
        "signed_eight_retained": report["signed_eight_retained"],
        "benchmark_score_granted": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
