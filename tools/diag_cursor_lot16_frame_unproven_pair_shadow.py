"""Original Lot16 page-3 wire: attach unproven frame-pair ledger (mission 3).

Default-off diagnostic. Opt-in ``--source-fragment-roles`` enables the #3338
fragment-role shadow that emits ``opening_host_frame_unproven_wall_pair`` codes.
Signed quantity IDs must remain retained vs the default host/frame handoff.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_frame_unproven_pair_original_attach import attach_frame_unproven_pair_ledgers
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    assess_gpt1_opening_candidates,
    original_host_frame_dimension_report,
)
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_same_root_f07_g17_original import classify_live_view

LOT16_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _quantity_ids(receipt: dict) -> set[str]:
    return {str(row["quantity_id"]) for row in receipt.get("quantities") or ()}


def _compose_page3(pdf: bytes, digest: str, *, fragment_roles: bool):
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        **({"raster_paired_outer_faces_shadow": True} if fragment_roles else {}),
    )
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf,
        source_locator="memory://cursor-lot16-frame-pair.pdf",
        page_ids=(3,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=pub.revision.revision_id,
        page_ids=(PAGE_ID,),
        **({
            "include_unmeasured_ink_closed_flanks_shadow": True,
            "source_fragment_roles_shadow": True,
        } if fragment_roles else {}),
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
    return queue, before


def lot16_frame_unproven_pair_shadow_report(
    pdf: bytes,
    *,
    expected_sha256: str = LOT16_SHA,
    source_fragment_roles: bool = False,
) -> dict:
    if type(pdf) is not bytes or not pdf:
        raise TypeError("original PDF bytes required")
    digest = sha256(pdf).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original Lot16 source SHA mismatch")
    if type(source_fragment_roles) is not bool:
        raise TypeError("source_fragment_roles must be an explicit bool")

    baseline_queue = original_host_frame_dimension_report(pdf, page_id=PAGE_ID)
    baseline_signed = {
        str(r["prior_signed_quantity_id"])
        for r in baseline_queue["opening_decisions"]
        if r.get("prior_signed_quantity_id")
    }
    if len(baseline_signed) != 8:
        raise RuntimeError("baseline signed opening inventory is not eight")

    queue, receipt = _compose_page3(pdf, digest, fragment_roles=source_fragment_roles)
    current_ids = _quantity_ids(receipt)
    signed_retained = baseline_signed <= current_ids

    attach = attach_frame_unproven_pair_ledgers(
        opening_rows=list(queue.get("opening_decisions") or ()),
        wall_scopes=receipt["walls"],
    )
    return {
        "status": "UNPUBLISHED_LOT16_FRAME_UNPROVEN_PAIR_SHADOW",
        "source_sha256": digest,
        "page_id": PAGE_ID,
        "source_fragment_roles_shadow": source_fragment_roles,
        "first_gate_counts": dict(queue.get("first_gate_counts") or {}),
        "original_physical_opening_count": queue.get("original_physical_opening_count"),
        "original_signed_area_quantities": queue.get("original_signed_area_quantities"),
        "signed_eight_quantity_ids_retained": bool(signed_retained),
        "frame_unproven_pair_attach": attach,
        "frame_granted": False,
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
    p.add_argument("--source-fragment-roles", action="store_true")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args(argv)
    raw = args.pdf.read_bytes()
    if sha256(raw).hexdigest() != args.sha256:
        raise SystemExit("source SHA mismatch")
    report = lot16_frame_unproven_pair_shadow_report(
        raw,
        expected_sha256=args.sha256,
        source_fragment_roles=bool(args.source_fragment_roles),
    )
    # Persist summary only — full pair ledgers can be huge.
    summary = {
        "status": report["status"],
        "source_sha256": report["source_sha256"],
        "page_id": report["page_id"],
        "source_fragment_roles_shadow": report["source_fragment_roles_shadow"],
        "first_gate_counts": report["first_gate_counts"],
        "original_physical_opening_count": report["original_physical_opening_count"],
        "original_signed_area_quantities": report["original_signed_area_quantities"],
        "signed_eight_quantity_ids_retained": report["signed_eight_quantity_ids_retained"],
        "frame_blocked_openings_with_ledger": report["frame_unproven_pair_attach"][
            "frame_blocked_openings_with_ledger"],
        "relation_counts": report["frame_unproven_pair_attach"]["relation_counts"],
        "producer_equivalence_pair_count": report["frame_unproven_pair_attach"][
            "producer_equivalence_pair_count"],
        "frame_granted": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
    args.output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
