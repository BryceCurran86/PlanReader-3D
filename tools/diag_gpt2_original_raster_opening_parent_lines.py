"""Original-PDF GPT2→GPT MAX raster-opening parent source proof (shadow only).

Usage:
  python -m tools.diag_gpt2_original_raster_opening_parent_lines \
    --pdf /private/original.pdf --expected-sha256 <sha256> --page 3 \
    --output /private/raster-opening-parent-lines.json
Optional --parents-json contains a JSON list of required original parent
observation IDs from an independently generated opening derivation census.

This emits only producer-authenticated original opening-primitive ink lines.
No W4 wall, host, 3D frame, opening count, measured area, customer row or
benchmark authority is conferred by this tool.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_gpt2_raster_opening_parent_source_shadow import (
    recover_original_raster_opening_parent_lines_shadow,
)
from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def original_raster_parent_source_report(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    page_id: str, requested_parents: tuple[str, ...] = (),
) -> dict:
    """Run the existing source-owning wall/opening producer before reading lines."""
    if type(original_pdf_bytes) is not bytes or not original_pdf_bytes:
        raise ValueError("original PDF required")
    digest = sha256(original_pdf_bytes).hexdigest()
    if digest != expected_sha256:
        raise ValueError("original PDF SHA-256 mismatch")
    if type(page_id) is not str or not page_id.isdecimal() or int(page_id) <= 0:
        raise ValueError("canonical source page required")
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="live-source:" + digest[:32],
        source_bytes=original_pdf_bytes,
        source_locator="memory://original-gpt2-raster-opening-parent-source.pdf",
        page_ids=(int(page_id),),
    )
    # The live composition is used ONLY to trigger its producer-owned original
    # raster primitive inventory; no composer wall/host records are promoted.
    compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(page_id,),
    )
    pub = source.published_snapshot_for_revision(initial.revision.revision_id)
    if pub is None or pub.revision.source_sha256 != digest:
        raise ValueError("source snapshot mismatch")
    snapshot_id = pub.snapshot.snapshot_id
    parents = tuple(requested_parents)
    if not parents:
        # A list of source-native parent IDs is only an address universe. The
        # typed source authority below must reauthenticate EVERY item.
        collected = set()
        for visible_id in sorted(
            source.raster_opening_primitive_observation_ids_for_snapshot(snapshot_id)
        ):
            result = source.resolve_raster_opening_primitive(ObservationSelector(
                document_id=pub.revision.document_id,
                revision_id=pub.revision.revision_id,
                source_sha256=pub.revision.source_sha256,
                snapshot_id=snapshot_id, observation_id=visible_id,
            ))
            row = result.observation
            if (result.status is EvidenceResolutionStatus.CORROBORATED
                    and row is not None and row.page_id == page_id
                    and len(row.derivation_parent_ids) == 1):
                collected.add(row.derivation_parent_ids[0])
        parents = tuple(sorted(collected))
    if not parents:
        raise ValueError("no original raster-opening parent evidence in page scope")
    receipt = recover_original_raster_opening_parent_lines_shadow(
        source, revision_id=pub.revision.revision_id,
        snapshot_id=snapshot_id, page_id=page_id,
        required_parent_ids=parents,
    )
    return {
        "source_sha256": digest,
        "revision_id": pub.revision.revision_id,
        "snapshot_id": snapshot_id,
        "page_id": page_id,
        "original_source_receipts": asdict(receipt),
        "exact_source_parent_candidate_count": len(receipt.lines),
        "missing_or_ambiguous_source_parent_count": len(receipt.unresolved_parent_ids),
        "structural_w4_binding_not_proven": True,
        "host_frame_metric_count_and_customer_granted": False,
        "shadow_only": True,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--parents-json", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.pdf.is_file() or args.page <= 0:
        raise ValueError("original source PDF/page unavailable")
    parents: tuple[str, ...] = ()
    if args.parents_json is not None:
        provided = json.loads(args.parents_json.read_text(encoding="utf-8"))
        if type(provided) is not list or not provided:
            raise ValueError("exact original source parent ID list required")
        parents = tuple(provided)
    report = original_raster_parent_source_report(
        args.pdf.read_bytes(), expected_sha256=args.expected_sha256,
        page_id=str(args.page), requested_parents=parents,
    )
    if args.output.exists():
        raise FileExistsError("refusing to overwrite existing source proof")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps({
        "source_only_lines": report["exact_source_parent_candidate_count"],
        "unresolved": report["missing_or_ambiguous_source_parent_count"],
        "no_structural_host_or_quantity_published": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
