"""Run additional source hypotheses without rewriting the original issuer.

The original and alternate source roots remain independent. Original quantity,
seal and customer bodies are frozen before any additional source hypothesis.
New objects remain unapproved audit candidates; this command never merges,
re-signs, publishes, aliases a physical identity or runs a benchmark scorer.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_physical_opening_void_composition import LivePhysicalOpeningVoidComposition
from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_migration_contracts import canonical_contract_json
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_opening_source_review_shadow import (
    build_opening_review_packets, compare_opening_source_correspondence,
)
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_unmeasured_flank_capture_shadow import compare_original_g17_release_receipts


def _freeze(value):
    return canonical_contract_json(value).encode("utf-8")


def opening_quantity_addition_review(original_voids, alternate_voids, *,
        original_packets, alternate_packets):
    """Separate new producer-owned areas from reissued original source rows.

    Figured-label area and complete rough-opening geometry are different
    authority seams. Use the existing area publisher to nominate measurable
    additions; never require its unrelated 3D frame/placement gates here.
    This review projection cannot append, sign, alias or publish a quantity.
    """
    if (type(original_voids) is not LivePhysicalOpeningVoidComposition
            or type(alternate_voids) is not LivePhysicalOpeningVoidComposition):
        raise TypeError("original producer-owned opening compositions required")
    original = publish_live_opening_area_quantities(original_voids)
    alternate = publish_live_opening_area_quantities(alternate_voids)
    original_ids = {q.quantity_id for q in original}
    original_objects = {o.physical_opening_id for o in original_voids.canonical_openings}
    original_sources = {(o.document_id, o.revision_id, o.source_sha256)
                        for o in original_voids.canonical_openings}
    if (not original_sources or any(
            (o.document_id, o.revision_id, o.source_sha256) not in original_sources
            for o in alternate_voids.canonical_openings)):
        raise ValueError("additional source review must retain the original document/revision/SHA")
    correspondence = compare_opening_source_correspondence(original_packets, alternate_packets)
    packet_by_opening = {}
    for packet in alternate_packets:
        physical = packet["opening_identity_id"]
        if physical is None:
            continue
        if physical in packet_by_opening:
            raise ValueError("duplicate physical opening in additional source review")
        packet_by_opening[physical] = packet
    matches = {r["alternate_opening_id"]: r["exact_source_support_original_ids"]
               for r in correspondence}
    packet_complete = {r["alternate_opening_id"]: r["source_support_packet_complete"]
                       for r in correspondence}
    reviews = []
    for quantity in alternate:
        # An existing signed identity never becomes an addition just because
        # its metadata was reissued on a different source-policy snapshot.
        if quantity.quantity_id in original_ids:
            continue
        if len(quantity.input_entity_ids) != 1:
            raise ValueError("one producer-owned physical opening required per addition")
        physical = quantity.input_entity_ids[0]
        packet = packet_by_opening.get(physical)
        if packet is None or packet.get("physical_opening") is None:
            raise ValueError("additional area lacks its original physical source packet")
        opening = packet["physical_opening"]
        if (opening.get("record_id") != physical or any(
                opening.get(k) != quantity.metadata.get(k)
                for k in ("document_id", "revision_id", "source_sha256", "snapshot_id"))
                or opening.get("page_id") != quantity.metadata.get("page_no")):
            raise ValueError("additional quantity and physical source packet disagree")
        lineage = packet.get("source_lineage") or {}
        closed = packet_complete.get(physical) is True
        continuation = physical in original_objects or bool(matches.get(physical))
        if not closed:
            gate = "original_source_parent_dag_required"
        elif continuation:
            gate = "existing_physical_identity_continuation_review_required"
        else:
            gate = "independent_additive_area_authority_review_required"
        basis = quantity.metadata["area_basis"]
        reviews.append({
            "status": "candidate",
            "physical_opening_id": physical,
            "proposed_quantity_id": quantity.quantity_id,
            "family": quantity.family,
            "semantic_key": quantity.semantic_key,
            "value": quantity.value,
            "unit": quantity.unit,
            "area_basis": basis,
            "measurement_record_id": quantity.metadata["measurement_record_id"],
            "source_packet_id": packet["packet_id"],
            "source_sha256": opening["source_sha256"],
            "revision_id": opening["revision_id"],
            "snapshot_id": opening["snapshot_id"],
            "source_parent_dag_closed": closed,
            "unresolved_parent_ids": list(lineage.get("unresolved_parent_ids", ())),
            "exact_source_support_original_ids": list(matches.get(physical, ())),
            "existing_physical_identity": physical in original_objects,
            "first_remaining_gate": gate,
            "complete_frame_required_by_area_basis": basis == "resolved_opening_geometry",
            "complete_frame_available": bool((packet.get("whole_wall_frame") or {}).get("record_id")),
            "geometry_work_remaining": list(packet["next_required_evidence"]),
            "original_signed_rows_reissued": False,
            "append_authority_granted": False,
            "commercial_projection_allowed": False,
            "opening_count_granted": False,
            "benchmark_match_granted": False,
        })
    return {
        "status": "candidate",
        "original_quantity_ids_retained_separately": sorted(original_ids),
        "excluded_reissued_quantity_ids": sorted(
            original_ids & {q.quantity_id for q in alternate}),
        "additional_area_reviews": sorted(reviews, key=lambda r: r["proposed_quantity_id"]),
        "original_signed_rows_reissued": False,
        "aggregate_sealed_output_created": False,
        "commercial_projection_allowed": False,
        "opening_count_granted": False,
    }


def recover_source_preserving_openings_shadow(source, *, revision_id, page_ids,
        exact_nomination_shadow=False, source_fragment_roles_shadow=False,
        include_revision_ancestry_shadow=False):
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("original source must be producer-owned")
    if any(type(flag) is not bool for flag in (
            exact_nomination_shadow, source_fragment_roles_shadow, include_revision_ancestry_shadow)):
        raise ValueError("recovery policies must be explicit booleans")
    if source._raster_paired_outer_faces_shadow or source._exact_g17_nomination_shadow:
        raise ValueError("original issuer must use its default source policy")
    if (not isinstance(page_ids, tuple) or len(page_ids)!=1
            or any(type(p) is not str or not p.isdigit() or str(int(p))!=p or int(p)<1 for p in page_ids)
            or len(set(page_ids))!=len(page_ids)):
        raise ValueError("one positive original topology page required; use page-isolated batch for multiple pages")
    page_ids=tuple(sorted(page_ids,key=int))
    baseline = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=revision_id, page_ids=page_ids,
        source_revision_scope_shadow=True)
    original_voids = compose_live_physical_opening_voids(
        source_visibility_producer=source, wall_opening_composition=baseline)
    original_receipt = _freeze(_retention(baseline, original_voids, verify_customer_rows=True))
    original_snapshot = source.published_snapshot_for_revision(revision_id)
    fork, published = source.fork_native_source_shadow(revision_id,
        raster_paired_outer_faces_shadow=True,
        exact_g17_nomination_shadow=exact_nomination_shadow,
        include_revision_ancestry_shadow=include_revision_ancestry_shadow)
    candidate = compose_live_wall_opening_authority(
        source_visibility_producer=fork, revision_id=published.revision.revision_id,
        page_ids=page_ids, include_unmeasured_ink_closed_flanks_shadow=True,
        source_revision_scope_shadow=True,
        **({"source_fragment_roles_shadow": True} if source_fragment_roles_shadow else {}))
    candidate_voids = compose_live_physical_opening_voids(
        source_visibility_producer=fork, wall_opening_composition=candidate)
    candidate_receipt = _freeze(_retention(candidate, candidate_voids, verify_customer_rows=True))
    original_after = _freeze(_retention(baseline, original_voids, verify_customer_rows=True))
    if (original_after != original_receipt
            or source.published_snapshot_for_revision(revision_id) is not original_snapshot):
        raise RuntimeError("alternate source policy rewrote original issuer")
    old = json.loads(original_receipt)
    alternate = json.loads(candidate_receipt)
    original_ids = {o.canonical_opening_id for o in original_voids.canonical_openings}
    new_objects = tuple(o.to_dict() for o in candidate_voids.canonical_openings
                        if o.canonical_opening_id not in original_ids)
    supplemental = candidate.supplemental_physical_wall_candidate_authority
    # This is an actual sealed source authority, not a caller-built wall roster.
    # Export its complete retained records and negatives for frame consumers.
    supplemental_scopes = [] if supplemental is None else [
        asdict(scope) for scope in supplemental._scopes.values()]
    original_packets=build_opening_review_packets(source,baseline)
    alternate_packets=build_opening_review_packets(fork,candidate,
        source_fragment_roles_shadow=source_fragment_roles_shadow)
    addition_review = opening_quantity_addition_review(original_voids, candidate_voids,
        original_packets=original_packets, alternate_packets=alternate_packets)
    if (_freeze(_retention(baseline, original_voids, verify_customer_rows=True)) != original_receipt
            or source.published_snapshot_for_revision(revision_id) is not original_snapshot):
        raise RuntimeError("source review projections rewrote original issuer")
    return {
        "status": "original_issuer_preserved_additional_source_shadow",
        "original_source_sha256": original_snapshot.revision.source_sha256,
        "original_snapshot_id": original_snapshot.snapshot.snapshot_id,
        "alternate_snapshot_id": fork.published_snapshot_for_revision(
            published.revision.revision_id).snapshot.snapshot_id,
        "policies": {"exact_nomination_shadow": exact_nomination_shadow,
                     "source_fragment_roles_shadow": source_fragment_roles_shadow,
                     "include_revision_ancestry_shadow":include_revision_ancestry_shadow},
        "page_ids":page_ids,
        "original_issuer_body_unchanged_during_fork": True,
        "historical_archive_authenticated": False,
        "original_receipt_sha256": sha256(original_receipt).hexdigest(),
        "original_receipt": old,
        "alternate_receipt": alternate,
        "alternate_supplemental_wall_scopes": supplemental_scopes,
        "source_rekey_comparison": compare_original_g17_release_receipts(old, alternate),
        "new_unapproved_physical_objects": new_objects,
        "original_opening_review_packets":original_packets,
        "alternate_opening_review_packets":alternate_packets,
        "source_correspondence":compare_opening_source_correspondence(original_packets,alternate_packets),
        "quantity_addition_review": addition_review,
        "original_signed_rows_reissued": False,
        "new_authority_promotion_granted": False,
        "customer_publication_granted": False,
        "official_benchmark_executed": False,
    }


def recover_source_preserving_openings_pages_shadow(source,*,revision_id,page_ids,
        exact_nomination_shadow=False,source_fragment_roles_shadow=False,
        include_revision_ancestry_shadow=False):
    """Preserve the multi-page original; isolate each new page hypothesis.

    Page reports deliberately retain separate snapshots/seals. They are not a
    new cross-page opening universe or an aggregate signed customer output.
    """
    if (not isinstance(page_ids,tuple) or not page_ids or len(set(page_ids))!=len(page_ids)
            or any(type(p) is not str or not p.isdigit() or str(int(p))!=p or int(p)<1 for p in page_ids)):
        raise ValueError("unique positive original topology page addresses required")
    page_ids=tuple(sorted(page_ids,key=int))
    original=compose_live_wall_opening_authority(source_visibility_producer=source,
        revision_id=revision_id,page_ids=page_ids,source_revision_scope_shadow=True)
    voids=compose_live_physical_opening_voids(source_visibility_producer=source,
        wall_opening_composition=original)
    receipt=_freeze(_retention(original,voids,verify_customer_rows=True))
    published=source.published_snapshot_for_revision(revision_id)
    pages=[]
    for page in page_ids:
        isolated,replay=source.fork_native_source_shadow(revision_id,
            include_revision_ancestry_shadow=include_revision_ancestry_shadow)
        pages.append(recover_source_preserving_openings_shadow(isolated,
            revision_id=replay.revision.revision_id,page_ids=(page,),
            exact_nomination_shadow=exact_nomination_shadow,
            source_fragment_roles_shadow=source_fragment_roles_shadow,
            include_revision_ancestry_shadow=include_revision_ancestry_shadow))
    if (_freeze(_retention(original,voids,verify_customer_rows=True))!=receipt
            or source.published_snapshot_for_revision(revision_id) is not published):
        raise RuntimeError("page-isolated hypotheses rewrote multi-page original issuer")
    return {"status":"original_issuer_preserved_page_isolated_source_shadows",
        "page_ids":page_ids,"original_source_sha256":published.revision.source_sha256,
        "original_issuer_body_unchanged_during_fork":True,
        "original_receipt_sha256":sha256(receipt).hexdigest(),
        "original_receipt":json.loads(receipt),"page_reports":pages,
        "cross_page_identity_granted":False,"aggregate_signed_output_created":False,
        "new_authority_promotion_granted":False,"customer_publication_granted":False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--page", required=True, type=int, action="append")
    parser.add_argument("--exact-nomination", action="store_true")
    parser.add_argument("--source-fragment-roles", action="store_true")
    parser.add_argument("--include-revision-ancestry", action="store_true",
        help="Replay original revision ancestry when present; missing derivation parents remain unresolved")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = args.pdf.read_bytes()
    if sha256(payload).hexdigest() != args.expected_sha256:
        raise ValueError("original source SHA mismatch")
    if args.output.resolve() == args.pdf.resolve():
        raise ValueError("source PDF cannot be an audit output")
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    published = source.ingest_native_pdf_bytes(
        document_id="live-source:"+args.expected_sha256[:32], source_bytes=payload,
        source_locator="memory://source-preserving-opening-shadow.pdf", page_ids=tuple(args.page))
    recover=(recover_source_preserving_openings_shadow if len(args.page)==1
             else recover_source_preserving_openings_pages_shadow)
    result = recover(source,
        revision_id=published.revision.revision_id, page_ids=tuple(str(p) for p in args.page),
        exact_nomination_shadow=args.exact_nomination,
        source_fragment_roles_shadow=args.source_fragment_roles,
        include_revision_ancestry_shadow=args.include_revision_ancestry)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False)+"\n")
    print(json.dumps({"original_issuer_preserved":True,"page_count":len(args.page),
                     "authority_promotion":False}))


if __name__ == "__main__":
    main()
