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

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def replay_opt_in(pdf: bytes, *, expected_sha256: str = SOURCE_SHA) -> dict:
    if type(pdf) is not bytes or sha256(pdf).hexdigest() != expected_sha256:
        raise ValueError("immutable original Lot16 source SHA mismatch")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    pub = source.ingest_native_pdf_bytes(
        document_id="live-source:" + expected_sha256[:32],
        source_bytes=pdf,
        source_locator="memory://gptmax-ink-closed-g17-opt-in-shadow.pdf",
        page_ids=(3,),
    )
    comp = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=pub.revision.revision_id,
        page_ids=("3",), include_unmeasured_ink_closed_flanks_shadow=True,
    )
    snapshot = source.published_snapshot_for_revision(pub.revision.revision_id)
    if snapshot is None or sha256(pdf).hexdigest() != snapshot.revision.source_sha256:
        raise RuntimeError("source producer root invalid after opt-in")
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
        "old_source_snapshot_may_differ": True,
        "old_21_15_9_8_source_baseline_NOT_replayed_or_assumed": True,
        "opt_in_physical_opening_count": len(rows),
        "opt_in_authenticated_host_count": sum(x["host_proven"] for x in rows),
        "opt_in_opening_host_rows": rows,
        "retained_original_source_bytes": True,
        "original_quantity_receipt_retention_proven": False,
        "original_8_signed_areas_proven_unchanged": False,
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
    print("original signed source receipts require independent comparison")


if __name__ == "__main__":
    main()
