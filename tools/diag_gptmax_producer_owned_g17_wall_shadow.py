"""Run producer-owned G17 candidates and verify exact production retention."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _retention(composition, voids):
    return {
        "hosts": [asdict(r) for r in composition.opening_bindings],
        "frames": [asdict(r) for r in composition.host_frames],
        "walls": [asdict(scope) for scope in composition.physical_wall_candidate_authority._scopes.values()],
        "canonical": [r.to_dict() for r in voids.canonical_openings],
    }


def producer_owned_wall_shadow_report(original_pdf: bytes, *, page_id: str) -> dict:
    digest = sha256(original_pdf).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}", source_bytes=original_pdf,
        source_locator="memory://original-g17-wall-shadow.pdf",
    )
    def compose():
        c = compose_live_wall_opening_authority(
            source_visibility_producer=source,
            revision_id=published.revision.revision_id, page_ids=(page_id,),
        )
        v = compose_live_physical_opening_voids(
            source_visibility_producer=source, wall_opening_composition=c)
        return c,v
    composition, voids = compose()
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    before = _retention(composition,voids)
    shadows = []
    for trace in composition.opening_bindings:
        if trace.host_wall_id is not None:
            continue
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        shadow = build_opening_local_g17_wall_shadow(source,selector)
        if shadow.physical_opening_id != trace.opening_identity_id:
            raise ValueError("source shadow opening identity changed")
        shadows.append(asdict(shadow))
    recomposed, revoids = compose()
    if _retention(recomposed,revoids) != before:
        raise RuntimeError("G17 shadow changed original wall/host/frame/area receipts")
    if source.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise RuntimeError("G17 shadow changed published source snapshot")
    return {
        "source_sha256": digest, "snapshot_id":published.snapshot.snapshot_id,
        "page_id":page_id, "primitive_safety_cap":MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        "original_physical_opening_count":len(composition.opening_bindings),
        "original_host_count":sum(bool(r.host_wall_id) for r in composition.opening_bindings),
        "original_frame_count":sum(bool(r.record_id) for r in composition.host_frames),
        "original_w4_count":sum(len(s.records) for s in composition.physical_wall_candidate_authority._scopes.values()),
        "original_area_count":sum(r.area_m2 is not None for r in voids.canonical_openings),
        "original_area_values":sorted(r.area_m2 for r in voids.canonical_openings if r.area_m2 is not None),
        "opening_local_source_shadows":shadows,
        "published_source_snapshot_unchanged":True,
        "all_original_wall_host_frame_area_receipts_unchanged":True,
        "new_physical_host_or_metric_granted":False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = producer_owned_wall_shadow_report(args.pdf.read_bytes(),page_id=args.page_id)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k != "opening_local_source_shadows"},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
