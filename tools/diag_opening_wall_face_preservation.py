"""Read-only source-proven wall-face and host handoff without quantity publication."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
import pb_physical_wall_candidate_authority as wall_authority
from pb_source_visibility_authority import SourceVisibilityProducer


def source_face_report(source_bytes: bytes, *, page_ids: tuple[str, ...]) -> dict:
    sha = hashlib.sha256(source_bytes).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{sha[:32]}", source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf", page_ids=page_ids,
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id, page_ids=page_ids,
    )
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    if published is None:
        raise RuntimeError("source snapshot unavailable")
    preservation = getattr(wall_authority, "_producer_proven_opening_wall_face_source_ids", None)
    return {
        "source_sha256": sha,
        "revision_id": published.revision.revision_id,
        "snapshot_id": published.snapshot.snapshot_id,
        "source_decode_coverage": asdict(published.coverage),
        "selected_geometry_page_ids": tuple(composition.page_ids),
        "primitive_safety_cap": wall_authority.MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "preservation_proof_available": preservation is not None,
        "protected_source_wall_face_ids_by_page": ({
            page: sorted(preservation(
                source_producer=source, published=published, page_id=page,
                physical_opening_authority=composition.physical_opening_authority,
            )) for page in page_ids
        } if preservation is not None else None),
        "wall_scopes": [asdict(row) for row in composition.wall_scopes],
        "source_owned_wall_scope_results": [
            asdict(composition.physical_wall_candidate_authority.resolve_scope(
                composition.physical_wall_candidate_authority._selector_for_result(scope)
            )) for scope in composition.physical_wall_candidate_authority._scopes.values()
        ],
        "opening_bindings": [asdict(row) for row in composition.opening_bindings],
        "host_frames": [asdict(row) for row in composition.host_frames],
        "resolved_host_frame_evidence": [
            asdict(result.evidence)
            for selector in composition.host_frame_selectors.values()
            if (result := composition.opening_host_frame_authority.resolve(selector)).evidence is not None
        ],
        "semantic_inventory": asdict(composition.semantic_enumeration_result),
        "summary": {
            "physical_existence_claims": len(composition.opening_bindings),
            "host_bindings": sum(bool(row.host_wall_id) for row in composition.opening_bindings),
            "host_frames": sum(bool(row.record_id) for row in composition.host_frames),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = source_face_report(
        args.pdf.read_bytes(), page_ids=tuple(sorted(set(args.page_id), key=int)),
    )
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True,
                                      default=lambda value: value.value) + "\n")
    print(json.dumps({"source_sha256": result["source_sha256"], **result["summary"]}))


if __name__ == "__main__":
    main()
