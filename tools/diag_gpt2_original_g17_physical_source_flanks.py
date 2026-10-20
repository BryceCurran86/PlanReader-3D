"""Source-closed GPT2→GPT MAX original physical G17 flank evidence (shadow).

python -m tools.diag_gpt2_original_g17_physical_source_flanks \
  --pdf /private/owner-original.pdf --expected-sha256 <sha> \
  --page 3 --output /private/original-g17-flank-receipts.json

The original source PDF stays on the owner-authorized runner. The JSON is
SOURCE-ONLY. No structural W4 host/frame, door area, count, BOQ, customer
release, or benchmark publication.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_gpt2_g17_opening_source_band_ownership_shadow import (
    bind_original_g17_flanks_to_physical_opening_shadow,
    quarantine_overlapping_g17_physical_source_claims_shadow,
)
from pb_gpt2_raster_opening_parent_source_shadow import (
    recover_original_raster_opening_parent_lines_shadow,
)
from pb_gpt2_raster_source_flank_band_shadow import (
    reconstruct_raster_source_flank_bands_shadow,
)
from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from tools.diag_gptmax_raster_unhosted_flank_source import (
    UNMAPPED_G17_FLANK_REASONS,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def original_physical_g17_source_flank_report(
    original_pdf_bytes: bytes, *, expected_sha256: str, page_id: str,
) -> dict:
    if type(original_pdf_bytes) is not bytes or not original_pdf_bytes:
        raise ValueError("original PDF bytes required")
    digest = sha256(original_pdf_bytes).hexdigest()
    if type(expected_sha256) is not str or digest != expected_sha256:
        raise ValueError("exact immutable original source SHA mismatch")
    if (type(page_id) is not str or not page_id.isdecimal()
            or int(page_id) <= 0 or str(int(page_id)) != page_id):
        raise ValueError("canonical original page number required")

    producer = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial = producer.ingest_native_pdf_bytes(
        document_id="live-source:" + digest[:32],
        source_bytes=original_pdf_bytes,
        source_locator="memory://gpt2-original-g17-physical-source.pdf",
        page_ids=(int(page_id),),
    )
    live = compose_live_wall_opening_authority(
        source_visibility_producer=producer,
        revision_id=initial.revision.revision_id,
        page_ids=(page_id,),
    )
    published = producer.published_snapshot_for_revision(initial.revision.revision_id)
    if (published is None or published.revision.source_sha256 != digest
            or live.revision_id != published.revision.revision_id
            or tuple(live.page_ids) != (page_id,)):
        raise RuntimeError("original G17 source producer root not stable")
    visibility = producer.authority()
    opening_authority = live.physical_opening_authority
    root = dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=digest,
        snapshot_id=published.snapshot.snapshot_id,
    )

    observed: dict[str, str] = {}
    unresolved: list[dict] = []
    physical = []
    for trace in sorted(live.opening_bindings, key=lambda row: (
        str(row.opening_identity_id), str(row.representative_observation_id),
    )):
        # A producer page roster is NOT the exact unhosted G17 physical
        # opening universe. Only the existing host authority's authentic
        # first-failing G17 flank stage may nominate this bridge.
        if (
            trace.status is not EvidenceResolutionStatus.ABSTAINED
            or trace.record_id is not None
            or trace.host_wall_id is not None
            or not set(trace.reason_codes).intersection(UNMAPPED_G17_FLANK_REASONS)
            or not trace.opening_identity_id
        ):
            continue
        physical_id = str(trace.opening_identity_id)
        representative = str(trace.representative_observation_id)
        prior = observed.get(physical_id)
        if prior is not None:
            if prior != representative:
                raise RuntimeError("duplicate physical G17 opening identity with competing source observations")
            continue
        observed[physical_id] = representative
        selector = ObservationSelector(
            **root, observation_id=representative,
        )
        proof = opening_authority.prove_existence(selector)
        original = proof.existence_record
        if (proof.status is not EvidenceResolutionStatus.CORROBORATED
                or original is None
                or original.record_id != physical_id
                or original.page_id != page_id
                or original.source_sha256 != digest
                or original.snapshot_id != root["snapshot_id"]
                or original.structural_pattern not in (
                    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
                    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
                )
                or not original.source_observation_ids):
            unresolved.append({
                "physical_opening_id": physical_id,
                "reason": "original_g17_physical_existence_unproven",
            })
            continue

        # Never use text proximity, W4 candidate IDs or source render pixels
        # as a shortcut for this physical opening's own G17 support universe.
        parents: list[str] = []
        present = 0
        for obs_id in original.source_observation_ids:
            response = visibility.resolve_raster_opening_primitive(
                ObservationSelector(**root, observation_id=str(obs_id))
            )
            visible = response.observation
            if (response.status is not EvidenceResolutionStatus.CORROBORATED
                    or visible is None):
                continue
            present += 1
            if (visible.page_id != page_id
                    or len(visible.derivation_parent_ids) != 1):
                break
            parents.append(visible.derivation_parent_ids[0])
        if present == 0:
            # A real G17 raster structural pattern cannot disappear just
            # because its supporting source receipts were corrupted. Other
            # non-raster opening families are independently handled elsewhere.
            if "raster" in str(original.structural_pattern).lower():
                unresolved.append({
                    "physical_opening_id": physical_id,
                    "reason": "original_g17_raster_source_support_unavailable",
                })
            continue
        if (present != len(original.source_observation_ids)
                or len(parents) != present
                or len(set(parents)) != len(parents)):
            unresolved.append({
                "physical_opening_id": physical_id,
                "reason": "original_g17_source_support_incomplete_or_ambiguous",
            })
            continue

        source = recover_original_raster_opening_parent_lines_shadow(
            producer, revision_id=root["revision_id"],
            snapshot_id=root["snapshot_id"], page_id=page_id,
            required_parent_ids=tuple(parents),
        )
        bands = reconstruct_raster_source_flank_bands_shadow(source)
        owned = bind_original_g17_flanks_to_physical_opening_shadow(
            opening_authority, original_selector=selector,
            parent_source=source, source_bands=bands,
        )
        physical.append(owned)

    reconciled = quarantine_overlapping_g17_physical_source_claims_shadow(
        tuple(physical)
    )
    for source_owner in reconciled:
        if source_owner.status is not EvidenceResolutionStatus.CORROBORATED:
            unresolved.append({
                "physical_opening_id": source_owner.physical_opening_id,
                "reason": ",".join(source_owner.reason_codes),
            })
    return {
        "source_sha256": digest,
        "revision_id": root["revision_id"],
        "snapshot_id": root["snapshot_id"],
        "page_id": page_id,
        "host_abstained_g17_candidate_physical_count": len(reconciled),
        "original_source_owned_two_flank_count": sum(
            x.status is EvidenceResolutionStatus.CORROBORATED
            for x in reconciled
        ),
        "unresolved": unresolved,
        "source_owner_claims": [asdict(x) for x in reconciled],
        "shadow_only": True,
        "structural_host_granted": False,
        "whole_wall_frame_granted": False,
        "opening_count_granted": False,
        "metric_quantity_granted": False,
        "customer_publication_granted": False,
        "benchmark_score_granted": False,
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pdf", type=Path, required=True)
    p.add_argument("--expected-sha256", required=True)
    p.add_argument("--page", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    if not args.pdf.is_file() or args.page <= 0:
        raise ValueError("original PDF or source page unavailable")
    report = original_physical_g17_source_flank_report(
        args.pdf.read_bytes(), expected_sha256=args.expected_sha256,
        page_id=str(args.page),
    )
    if args.output.exists():
        raise FileExistsError("refuse to overwrite existing original-source proof")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "g17_source_candidate_count": report["host_abstained_g17_candidate_physical_count"],
        "original_two_flank_owned": report["original_source_owned_two_flank_count"],
        "no_new_host_or_quantity": True,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
