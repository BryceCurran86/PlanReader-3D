"""Owner-original Lot16 GPT3 read-only MAX opening-area source-to-issuer replay.

Only the SHA-256 authenticated original client PDF creates physical opening
identity, live host bindings, figured areas, source traces, quantities and
customer output. No caller-provided candidate report or object-sidecar enters
this trust boundary. Customer quantities and frozen gold are never emitted.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_physical_opening_void_composition import (
    compose_live_physical_opening_voids,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import segment_source_page_viewports
from tools.diag_gptmax_producer_opening_scope_receipts import _observe
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from tools.diag_gptmax_same_root_f07_g17_original import classify_live_view
from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import (
    assess_gpt1_opening_candidates,
)
from tools.diag_gpt3_max_area_review_source_issuer_bijection import (
    ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT,
    ORIGINAL_LOT16_PROJECT_ID,
    ORIGINAL_LOT16_SOURCE_SHA256,
    audit_max_area_review_against_live_issuer,
)


ORIGINAL_PAGE_ID = "3"
ARCHIVED_SOURCE = Path(
    "docs/engineering/lot16_original_signed_eight_row_20261015/production"
)


def replay_owner_original_lot16_area_convergence(
    original_pdf: bytes, *,
    archived_signed_run: dict,
    archived_customer_rows: list,
) -> dict[str, object]:
    """Independently reconcile original signed predecessors on a live run.

    The actual PDF byte digest is checked BEFORE the first source operation.
    Private source bytes never enter the JSON report or public repository.
    """
    if type(original_pdf) is not bytes or not original_pdf:
        raise TypeError("owner-original PDF bytes are mandatory")
    source_digest = sha256(original_pdf).hexdigest()
    if source_digest != ORIGINAL_LOT16_SOURCE_SHA256:
        raise ValueError("original Lot16 source PDF SHA-256 mismatch")
    if (type(archived_signed_run) is not dict
            or archived_signed_run.get("fingerprint")
            != ORIGINAL_LOT16_ARCHIVED_EIGHT_FINGERPRINT
            or archived_signed_run.get("project_id") != ORIGINAL_LOT16_PROJECT_ID
            or type(archived_customer_rows) is not list):
        raise ValueError("immutable original Lot16 eight signed/customer archive required")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published_revision = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{source_digest[:32]}",
        source_bytes=original_pdf,
        source_locator="memory://gpt3-owner-original-lot16-area-convergence.pdf",
        # Critical physical source identity: the historical signed original
        # eight were produced from the FULL original document snapshot.
        # Page-subset ingest produces a different source snapshot identity,
        # changing opening/host/quantity IDs even if its p3 ink is identical.
        # Select p3 at COMPOSITION only, never at the original ingest gate.
    )
    revision = published_revision.revision.revision_id

    wall_composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=revision,
        page_ids=(ORIGINAL_PAGE_ID,),
    )
    void_composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_composition,
    )
    # Opening host/void composition can add DERIVED original observations
    # and fork a producer snapshot. The authoritative opening IDs, canonical
    # selectors and figured area receipts belong to that FINAL source
    # snapshot, not the earlier native-word-only ingest snapshot.
    source_snapshot = source.published_snapshot_for_revision(revision)
    # The actual production serializer builds the signed/customer receipts;
    # there is no independent reconstruction from a candidate's numbers.
    original_retention = _retention(
        wall_composition, void_composition, verify_customer_rows=True,
        audit_project_id=ORIGINAL_LOT16_PROJECT_ID,
    )
    observed = _observe(
        source, source_snapshot, wall_composition, void_composition,
    )
    candidate_views = segment_source_page_viewports(
        source, revision_id=revision, page_id=ORIGINAL_PAGE_ID,
        physical_plan_view_shadow=True,
    )
    f07 = classify_live_view(
        candidate_views, expected_page=int(ORIGINAL_PAGE_ID),
    )
    owner = {
        key: getattr(published_revision.revision, key)
        for key in ("document_id", "revision_id", "source_sha256")
    }
    owner["snapshot_id"] = source_snapshot.snapshot.snapshot_id
    max_source_review = assess_gpt1_opening_candidates(
        observed, original_retention["canonical"],
        f07, source_root=owner,
    )
    report = audit_max_area_review_against_live_issuer(
        max_source_review, void_composition,
        archived_signed_run=archived_signed_run,
        archived_customer_rows=archived_customer_rows,
        current_source_retention=original_retention,
    )
    # An original replay must preserve its own exact snapshot/canonical/seal;
    # independently reproduce customer receipts AFTER the audit as an output
    # immutability check, not to manufacture new evidence.
    if (
        source.published_snapshot_for_revision(revision) != source_snapshot
        or sha256(
            source._producer._store.source_bytes_by_revision[revision]
        ).hexdigest() != source_digest
        or _retention(
            wall_composition, void_composition, verify_customer_rows=True,
            audit_project_id=ORIGINAL_LOT16_PROJECT_ID,
        ) != original_retention
    ):
        raise RuntimeError("original producer source snapshot or signed receipt mutated")

    return {
        **report,
        "original_source_pdf_sha256_verified": True,
        "owner_original_source_sha256": source_digest,
        "original_source_page_id": ORIGINAL_PAGE_ID,
        "original_producer_snapshot_id": owner["snapshot_id"],
        "original_source_customer_retention_unchanged": True,
        "original_max_source_view_support_only": f07.get("status"),
        "original_max_source_opening_count": (
            max_source_review["original_physical_opening_count"]
        ),
        "original_max_host_binding_count": (
            max_source_review["original_authenticated_hosts"]
        ),
        "original_max_complete_frame_count": (
            max_source_review["original_complete_host_frames"]
        ),
        "original_max_issuer_quantity_count": (
            max_source_review["original_signed_area_quantities"]
        ),
        "original_max_review_area_first_gates": (
            max_source_review["area_first_gate_counts"]
        ),
        "real_original_source_replayed": True,
        "new_firm_or_benchmark_score_granted": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--archive-root", type=Path, default=ARCHIVED_SOURCE)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    original = json.loads(
        (args.archive_root / "source_sealed_run.json").read_text()
    )
    customers = json.loads(
        (args.archive_root / "verified_customer_rows.json").read_text()
    )
    report = replay_owner_original_lot16_area_convergence(
        args.pdf.read_bytes(),
        archived_signed_run=original,
        archived_customer_rows=customers,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
    )
    print({
        "sha_verified": report["original_source_pdf_sha256_verified"],
        "source_issued": report["real_producer_issued_opening_area_count"],
        "new_issued_verified": report["source_verified_new_quantity_count"],
        "accuracy_score_granted": report["benchmark_score_authorized"],
    })


if __name__ == "__main__":
    main()
