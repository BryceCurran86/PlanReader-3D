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
from pb_g17_w4_equivalence_competitor_shadow import compare_g17_to_ordinary_w4_shadow
from pb_g17_dual_dpi_source_correspondence_shadow import g17_144_300_source_correspondence_shadow
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _retention(composition, voids, *, verify_customer_rows=False):
    result = {
        "hosts": [asdict(r) for r in composition.opening_bindings],
        "frames": [asdict(r) for r in composition.host_frames],
        "walls": [asdict(scope) for scope in composition.physical_wall_candidate_authority._scopes.values()],
        "canonical": [r.to_dict() for r in voids.canonical_openings],
    }
    if verify_customer_rows:
        # Reuse actual publication, trace, seal, projection and verification
        # contracts. These read-only audit rows are never sent to a customer.
        from pb_customer_output_verification import verify_sealed_customer_output
        from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
        from pb_live_opening_source_closed_export import (
            build_live_opening_area_source_traces, seal_live_opening_area_run,
        )
        from pb_quantity_takeoff_adapter import (
            CommercialMeasurementAuthority, quantities_to_takeoff_output_rows,
        )
        quantities = publish_live_opening_area_quantities(voids)
        traces = build_live_opening_area_source_traces(
            voids, workspace_id=1, project_id="original-source-retention")
        authorities = {}
        for q in quantities:
            record_id = q.metadata.get("measurement_record_id")
            figured = q.metadata.get("area_basis") == "figured_opening_label" and bool(record_id)
            authorities[q.quantity_id] = CommercialMeasurementAuthority(
                method="figured_dimension" if figured else "direct_evidence",
                figured_dimension_ids=(record_id,) if figured else ())
        rows = quantities_to_takeoff_output_rows(quantities,
            traces_by_quantity_id=traces, authorities_by_quantity_id=authorities)
        sealed = seal_live_opening_area_run(
            voids, workspace_id=1, project_id="original-source-retention")
        verified = verify_sealed_customer_output(sealed, rows)
        result.update(quantities=[q.to_dict() for q in quantities],
            sealed_run=sealed.to_dict(), customer_rows=rows,
            customer_verification=asdict(verified))
    return result


def producer_owned_wall_shadow_report(original_pdf: bytes, *, page_id: str,
                                    include_plan_wall_scope: bool = False) -> dict:
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
    before = _retention(composition,voids,verify_customer_rows=include_plan_wall_scope)
    original_source_claims = {}
    for trace in composition.opening_bindings:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id, source_sha256=digest,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        record = composition.physical_opening_authority.prove_existence(selector).existence_record
        if record is None or record.record_id != trace.opening_identity_id:
            raise ValueError("original source opening universe no longer authenticates")
        original_source_claims[record.record_id] = frozenset(record.source_observation_ids)
    # Only original, producer-owned page W4 candidates are inspected.
    # Even a unique geometric match is not cross-source wall authority.
    ordinary_w4_records = tuple(
        record
        for _, scope in sorted(
            composition.physical_wall_candidate_authority._scopes.items(),
            key=lambda pair: str(pair[0]),
        )
        for record in scope.records
    )
    shadows = []
    authenticated_flank_shadows = []
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
        authenticated_flank_shadows.append(shadow)
        serialized = asdict(shadow)
        serialized["ordinary_w4_competitor_shadow"] = (
            compare_g17_to_ordinary_w4_shadow(shadow.flanks, ordinary_w4_records)
        )
        own_sources = original_source_claims[shadow.physical_opening_id]
        serialized['shared_original_source_observations'] = {
            other: sorted(own_sources & sources)
            for other,sources in sorted(original_source_claims.items())
            if other != shadow.physical_opening_id and own_sources & sources
        }
        # Shared source observations are retained competitors, never permission
        # to transfer another opening's host, figure label or metric quantity.
        shadows.append(serialized)
    dual_dpi = g17_144_300_source_correspondence_shadow(
        source, published, page_id=page_id,
        opening_shadows=tuple(authenticated_flank_shadows),
        ordinary_w4_records=ordinary_w4_records,
    )
    plan_wall_scope = None
    if include_plan_wall_scope:
        from pb_g17_plan_wall_scope_shadow import build_g17_plan_wall_scope_shadow
        plan_wall_scope = build_g17_plan_wall_scope_shadow(
            source, revision_id=published.revision.revision_id, page_id=page_id)
    recomposed, revoids = compose()
    if _retention(recomposed,revoids,verify_customer_rows=include_plan_wall_scope) != before:
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
        "original_144_300_correspondence_shadow":dual_dpi,
        "isolated_300_dpi_plan_wall_scope_shadow":plan_wall_scope,
        "original_opening_measurement_traces":(
            [asdict(row) for row in voids.traces] if include_plan_wall_scope else None),
        "original_semantic_enumeration_result":(
            asdict(composition.semantic_enumeration_result) if include_plan_wall_scope else None),
        "original_sealed_customer_receipts":(
            {k:before[k] for k in ("quantities","sealed_run","customer_rows","customer_verification")}
            if include_plan_wall_scope else None),
        "all_original_sealed_customer_rows_unchanged":include_plan_wall_scope,
        "published_source_snapshot_unchanged":True,
        "all_original_wall_host_frame_area_receipts_unchanged":True,
        "new_physical_host_or_metric_granted":False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--plan-wall-scope", action="store_true")
    args = parser.parse_args()
    report = producer_owned_wall_shadow_report(args.pdf.read_bytes(),page_id=args.page_id,
                                              include_plan_wall_scope=args.plan_wall_scope)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2,sort_keys=True)+"\n")
    print(json.dumps({k:v for k,v in report.items() if k not in (
        "opening_local_source_shadows", "original_144_300_correspondence_shadow",
        "isolated_300_dpi_plan_wall_scope_shadow")},sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
