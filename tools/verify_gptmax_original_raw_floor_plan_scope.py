"""Original-SHA production retention around source-only raw G17/F07 scope audit."""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_g17_raw_floor_plan_scope_shadow import audit_original_g17_raw_plan_view_scope
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention


def verify_original_raw_floor_plan_scope(source_bytes: bytes, *, page_id: str) -> dict:
    digest = sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://original-raw-floor-plan-scope.pdf",
    )
    revision = initial.revision.revision_id

    def compose():
        composition = compose_live_wall_opening_authority(
            source_visibility_producer=source, revision_id=revision, page_ids=(page_id,)
        )
        voids = compose_live_physical_opening_voids(
            source_visibility_producer=source, wall_opening_composition=composition
        )
        return composition, voids

    original_composition, original_voids = compose()
    published = source.published_snapshot_for_revision(revision)
    if published is None or published.revision.source_sha256 != digest:
        raise RuntimeError("immutable original source not present in source producer")
    baseline = _retention(original_composition, original_voids, verify_customer_rows=True)
    report = audit_original_g17_raw_plan_view_scope(
        source, revision_id=revision, page_id=page_id
    )
    after_composition, after_voids = compose()
    after = _retention(after_composition, after_voids, verify_customer_rows=True)
    if (baseline != after or published != source.published_snapshot_for_revision(revision)
            or report["source_sha256"] != digest):
        raise RuntimeError("source audit altered original host/frame/customer receipts")
    verification = baseline["customer_verification"]
    if not verification.get("valid_quantity_count") == len(baseline["customer_rows"]):
        raise RuntimeError("original customer receipts failed quantity verification")
    return dict(
        source_sha256=digest,
        snapshot_id=published.snapshot.snapshot_id,
        original_production_wall_host_frame_canonical_quantity_seal_customer_unchanged=True,
        original_signed_customer_row_count=verification["valid_quantity_count"],
        original_source_raw_floor_plan_audit=report,
        new_physical_host_granted=False,
        new_quantity_granted=False,
        opening_count_granted=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    payload = verify_original_raw_floor_plan_scope(args.pdf.read_bytes(), page_id=args.page_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n")
    print(json.dumps(dict(
        source_sha256=payload["source_sha256"],
        original_signed_customer_row_count=payload["original_signed_customer_row_count"],
        membership_census=dict(
            (key, sum(1 for g in payload["original_source_raw_floor_plan_audit"]["raw_groups"]
                      if g["authenticated_floor_plan_membership"] == key))
            for key in ("inside_this_authenticated_floor_plan",
                        "outside_this_authenticated_floor_plan_other_role_unproven",
                        "crossing_or_competing_view_owner_unproven")
        ),
    )))


if __name__ == "__main__":
    main()
