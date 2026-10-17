"""Source-pinned G17 capture counterfactual: one opt-in page, no default replay.

No new publisher, score or customer change is permitted by this command.
A recovered W4 *candidate* is not a structural host. This explicitly exposes
source/host churn rather than waiving signed identity retention.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"

def _exact_index(rows, field):
    if not isinstance(rows, list):
        raise ValueError("original issuer rows must be a list")
    index = {}
    for row in rows:
        key = row.get(field) if isinstance(row, dict) else None
        if not isinstance(key, str) or not key or key in index:
            raise ValueError("duplicate or malformed original issuer identity")
        index[key] = row
    return index


def compare_original_g17_release_receipts(original, alternate):
    """Strict, source-neutral comparison; rekeys are reported, not blessed."""
    categories = (
        ("hosts", "opening_identity_id"),
        ("frames", "opening_identity_id"),
        ("canonical", "canonical_opening_id"),
        ("quantities", "quantity_id"),
    )
    checks = {}
    for section, key in categories:
        first = _exact_index(original.get(section), key)
        second = _exact_index(alternate.get(section), key)
        missing = sorted(set(first) - set(second))
        extra = sorted(set(second) - set(first))
        changed = sorted(k for k in set(first)&set(second)
                         if first[k] != second[k])
        checks[section] = {
            "original_count":len(first),
            "new_count":len(second),
            "lost_original_ids":missing,
            "new_ids":extra,
            "changed_original_ids":changed,
            "original_exact":not (missing or changed),
        }
    customer_sections=("sealed_run","customer_rows","customer_verification")
    customer = {k:(k in original and k in alternate
                   and original[k] == alternate[k])
                for k in customer_sections}
    return {
        "original_authority":checks,
        "signed_customer_exact":customer,
        "all_original_issuer_receipts_exact":(
            all(x["original_exact"] for x in checks.values())
            and all(customer.values())),
        "new_host_or_frame_authority_granted":False,
        "signed_snapshot_rekey_approved":False,
        "new_gpt1_metric_authority_granted":False,
        "new_benchmark_match_granted":False,
    }


def _one_source_policy(pdf, digest, *, shadow):
    source=SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published=source.ingest_native_pdf_bytes(
        document_id="live-source:" + digest[:32],
        source_bytes=pdf,
        source_locator=("memory://optin-original-source.pdf"
                        if shadow else "memory://baseline-original-source.pdf"),
        page_ids=(3,),
    )
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
        include_unmeasured_ink_closed_flanks_shadow=shadow,
    )
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,wall_opening_composition=composition)
    current=source.published_snapshot_for_revision(published.revision.revision_id)
    if current is None or sha256(source._producer._store.source_bytes_by_revision[
            published.revision.revision_id]).hexdigest()!=digest:
        raise RuntimeError("immutable original source hash or scope lost")
    report=_retention(composition,voids,verify_customer_rows=True)
    if source.published_snapshot_for_revision(published.revision.revision_id)!=current:
        raise RuntimeError("source changed during receipt verification")
    return current,composition,report




def replay_opt_in(pdf: bytes, *, expected_sha256: str = SOURCE_SHA) -> dict:
    if type(pdf) is not bytes or sha256(pdf).hexdigest() != expected_sha256:
        raise ValueError("immutable original Lot16 source SHA mismatch")
    old_source, old_composition, old_receipt = _one_source_policy(
        pdf, expected_sha256, shadow=False,
    )
    snapshot, comp, new_receipt = _one_source_policy(
        pdf, expected_sha256, shadow=True,
    )
    parity = compare_original_g17_release_receipts(old_receipt,new_receipt)
    if old_source.revision.source_sha256 != snapshot.revision.source_sha256:
        raise RuntimeError("different source SHA in paired policy")
    if any(x.page_id not in ("3", None) for x in comp.opening_bindings):
        raise RuntimeError("nonplan opening introduced")
    rows = sorted(
        ({"opening_id": t.opening_identity_id, "host_proven": bool(t.record_id),
          "first_reasons": list(t.reason_codes), "host_members": list(t.member_wall_candidate_ids)}
         for t in comp.opening_bindings),
        key=lambda row: row["opening_id"],
    )
    return {
        "status": "original_source_ink_closed_g17_capture_counterfactual",
        "source_sha256": expected_sha256,
        "source_snapshot_id": snapshot.snapshot.snapshot_id,
        "baseline_source_snapshot_id": old_source.snapshot.snapshot_id,
        "original_change_receipt_parity": parity,
        "source_changed_policy_paired_to_fresh_original":True,
        "old_source_snapshot_may_differ": True,
        "old_21_15_9_8_source_baseline_NOT_replayed_or_assumed": True,
        "opt_in_physical_opening_count": len(rows),
        "opt_in_authenticated_host_count": sum(x["host_proven"] for x in rows),
        "opt_in_opening_host_rows": rows,
        "retained_original_source_bytes": True,
        "original_quantity_receipt_retention_proven": parity["original_authority"]["quantities"]["original_exact"],
        "original_8_signed_areas_proven_unchanged": parity["original_authority"]["quantities"]["original_exact"],
        "new_metric_handoff_granted": False,
        "new_signed_area_granted": False,
        "new_benchmark_match_granted": False,
        "global_capture_default_changed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--sha256", default=SOURCE_SHA)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = replay_opt_in(args.pdf.read_bytes(), expected_sha256=args.sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print("opt-in original host count:", result["opt_in_authenticated_host_count"])
    print("strict original customer parity:",result["original_change_receipt_parity"]["all_original_issuer_receipts_exact"])


if __name__ == "__main__":
    main()
