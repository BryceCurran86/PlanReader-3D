"""Original-source selector disposition matrix for a pre-existing opening.

Read-only diagnosis of whether an opt-in source policy changes WHICH exact
producer-owned G17 observations independently re-prove the original physical
opening. Never forces or reuses a stale representative or publishes a host.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_physical_opening_authority import PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def _run_policy(pdf: bytes, digest: str, page: str, *, shadow: bool):
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
        raster_paired_outer_faces_shadow=shadow,
    )
    p = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=pdf,
        source_locator="memory://original-selector-policy-matrix.pdf",
        page_ids=(int(page),),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=p.revision.revision_id,
        page_ids=(page,),
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    p = source.published_snapshot_for_revision(p.revision.revision_id)
    receipt = _retention(composition, voids, verify_customer_rows=True)
    if sha256(source._producer._store.source_bytes_by_revision[p.revision.revision_id]).hexdigest() != digest:
        raise ValueError("original source PDF bytes mutated")
    return source, p, composition, receipt


def _selectors(source, published, composition, target: str, observation_ids: tuple[str, ...]):
    physical = composition.physical_opening_authority
    rows = []
    for oid in sorted(observation_ids):
        address = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=oid,
        )
        disposition = physical.classify_disposition(address)
        existence = physical.prove_existence(address)
        d_record = disposition.existence_record
        e_record = existence.existence_record
        positive = (
            disposition.status is EvidenceResolutionStatus.CORROBORATED
            and disposition.disposition == PHYSICAL_OPENING_DISPOSITION_OPENING_SUPPORT
            and d_record is not None
            and d_record.record_id == target
        )
        rows.append({
            "source_observation_id": oid,
            "disposition_status": disposition.status.value,
            "disposition": disposition.disposition,
            "disposition_reason_codes": list(disposition.reason_codes),
            "disposition_candidate_ids": list(disposition.candidate_ids),
            "proven_exact_target_record": positive,
            "disposition_existence_record_id": None if d_record is None else d_record.record_id,
            "existence_status": existence.status.value,
            "existence_reason_codes": list(existence.reason_codes),
            "existence_record_id": None if e_record is None else e_record.record_id,
        })
    return rows


def summarize_source_selection(rows: list[dict], target: str) -> dict:
    """A diagnostic reproduction of the existing semantic enumeration policy."""
    if len({r["source_observation_id"] for r in rows}) != len(rows):
        raise ValueError("duplicate source observation selector")
    eligible = sorted(r["source_observation_id"] for r in rows
                      if r["proven_exact_target_record"]
                      and r["disposition_existence_record_id"] == target)
    return {
        "eligible_source_observation_ids": eligible,
        "recomputed_representative_id": eligible[0] if eligible else None,
        "recomputed_selection_grants_authority": False,
    }



def audit_original_new_source_overlaps(old_canonical: list[dict], new_canonical: list[dict]) -> list[dict]:
    """Collision is an audit fact, NEVER proof of sameness or distinctness."""
    old_by_id = {row["physical_opening_id"]: row for row in old_canonical}
    new_by_id = {row["physical_opening_id"]: row for row in new_canonical}
    if len(old_by_id) != len(old_canonical) or len(new_by_id) != len(new_canonical):
        raise ValueError("duplicate original or candidate physical identity")
    collisions = []
    for new_id in sorted(set(new_by_id) - set(old_by_id)):
        new_source = new_by_id[new_id]["source_observation_ids"]
        if len(new_source) != len(set(new_source)):
            raise ValueError("duplicate new physical source membership")
        for old_id, old_row in sorted(old_by_id.items()):
            old_source = old_row["source_observation_ids"]
            if len(old_source) != len(set(old_source)):
                raise ValueError("duplicate old physical source membership")
            overlap = sorted(set(old_source).intersection(new_source))
            if overlap:
                collisions.append({
                    "new_physical_opening_id": new_id,
                    "original_physical_opening_id": old_id,
                    "shared_source_observation_ids": overlap,
                    "shared_observation_count": len(overlap),
                    "independent_identity_proven": False,
                    "source_member_partition_proven": False,
                    "publication_granted": False,
                })
    return collisions


def original_selector_policy_matrix(
    original_pdf: bytes, *, page_id: str, expected_sha256: str, existing_physical_id: str,
) -> dict:
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("actual original PDF bytes required")
    digest = sha256(original_pdf).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original source SHA mismatch")
    if (type(page_id) is not str or not page_id.isdecimal()
            or int(page_id) < 1 or str(int(page_id)) != page_id
            or type(existing_physical_id) is not str or not existing_physical_id.startswith("physical_opening_existence_")):
        raise ValueError("valid exact existing source physical opening and page required")
    runs = [_run_policy(original_pdf, digest, page_id, shadow=flag) for flag in (False, True)]
    old_source, old_pub, old_comp, old = runs[0]
    new_source, new_pub, new_comp, new = runs[1]
    if old_pub != new_pub or old["walls"] != new["walls"]:
        raise ValueError("published original source snapshot or W4 evidence changed")
    previous = {r["physical_opening_id"]: r for r in old["canonical"]}
    current = {r["physical_opening_id"]: r for r in new["canonical"]}
    if (len(previous) != len(old["canonical"]) or len(current) != len(new["canonical"])
            or existing_physical_id not in previous or existing_physical_id not in current):
        raise ValueError("original physical identity no longer uniquely published")
    before, after = previous[existing_physical_id], current[existing_physical_id]
    source_ids = tuple(before["source_observation_ids"])
    if (not source_ids or len(set(source_ids)) != len(source_ids)
            or tuple(after["source_observation_ids"]) != source_ids
            or before["evidence_ids"] != after["evidence_ids"]):
        raise ValueError("original source membership / canonical evidence changed")
    old_rows = _selectors(old_source, old_pub, old_comp, existing_physical_id, source_ids)
    new_rows = _selectors(new_source, new_pub, new_comp, existing_physical_id, source_ids)
    old_choice = summarize_source_selection(old_rows, existing_physical_id)
    new_choice = summarize_source_selection(new_rows, existing_physical_id)
    if (old_choice["recomputed_representative_id"] != before["representative_observation_id"]
            or new_choice["recomputed_representative_id"] != after["representative_observation_id"]):
        raise ValueError("original independent semantic representative proof does not reproduce")
    if (old["quantities"] != new["quantities"] or old["customer_rows"] != new["customer_rows"]
            or old["sealed_run"] != new["sealed_run"]
            or old["customer_verification"] != new["customer_verification"]):
        raise ValueError("signed customer receipt protection failed")
    collisions = audit_original_new_source_overlaps(old["canonical"], new["canonical"])
    compared = [
        {
            "source_observation_id": a["source_observation_id"],
            "before": a,
            "after": b,
            "actual_source_decision_changed": a != b,
        }
        for a, b in zip(old_rows, new_rows)
    ]
    return {
        "status": "UNPUBLISHED_ORIGINAL_SELECTOR_POLICY_TRANSITION_AUDIT",
        "source_sha256": digest,
        "snapshot_id": old_pub.snapshot.snapshot_id,
        "page_id": page_id,
        "physical_opening_id": existing_physical_id,
        "original_source_observation_count": len(source_ids),
        "old_representative": before["representative_observation_id"],
        "shadow_representative": after["representative_observation_id"],
        "original_canonical_source_geometry": before["source_geometries"],
        "shadow_canonical_source_geometry": after["source_geometries"],
        "original_policy": old_choice,
        "shadow_policy": new_choice,
        "per_observation": compared,
        "new_physical_vs_original_source_member_collisions": collisions,
        "source_member_collision_count": len(collisions),
        "changed_observation_decision_count": sum(x["actual_source_decision_changed"] for x in compared),
        "original_physical_count": len(old["canonical"]),
        "shadow_physical_count": len(new["canonical"]),
        "original_host_count": sum(bool(h["host_wall_id"]) for h in old["hosts"]),
        "shadow_host_count": sum(bool(h["host_wall_id"]) for h in new["hosts"]),
        "original_frame_count": sum(bool(f["record_id"]) for f in old["frames"]),
        "shadow_frame_count": sum(bool(f["record_id"]) for f in new["frames"]),
        "original_signed_quantity_count": len(old["quantities"]),
        "signed_customer_receipts_preserved": True,
        "strict_existing_canonical_receipt_retained": before == after,
        "primitive_safety_cap": 20000,
        "authority_grants": {key: False for key in (
            "semantic_representative_reuse", "host", "frame", "metric",
            "quantity", "customer", "count", "release")},
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--sha256", required=True)
    p.add_argument("--page-id", required=True)
    p.add_argument("--existing-physical-id", required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    r = original_selector_policy_matrix(
        args.pdf.read_bytes(), page_id=args.page_id,
        expected_sha256=args.sha256, existing_physical_id=args.existing_physical_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(r, indent=2, sort_keys=True)+"\n")
    print({k:r[k] for k in ("status", "original_source_observation_count",
                              "changed_observation_decision_count",
                              "strict_existing_canonical_receipt_retained")})


if __name__ == "__main__":
    main()
