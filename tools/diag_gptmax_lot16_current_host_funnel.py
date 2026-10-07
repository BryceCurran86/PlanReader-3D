from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import pb_opening_host_binding_authority as host
import hashlib
import json
from pathlib import Path

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import _resolve_two_face_lineage_host
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"
SCOPE_ID = "wall-source:page-3"


def state(value):
    return str(getattr(value, "value", value))


def main():
    source_bytes = PDF.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    if actual != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual}")

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{EXPECTED_SHA[:32]}",
        source_bytes=source_bytes,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    current = source.published_snapshot_for_revision(initial.revision.revision_id)
    if current is None:
        raise SystemExit("missing current source snapshot")

    wall_result = composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=SCOPE_ID,
        )
    )

    physical = composition.physical_opening_authority
    binding_status_counts = Counter()
    binding_reason_counts = Counter()
    pattern_counts = Counter()
    pattern_host_counts = Counter()
    pattern_reason_counts = {}
    exact_helper_status_counts = Counter()
    exact_helper_reason_counts = Counter()
    rows = []
    label_dimension = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    swing_label_status_counts = Counter()
    swing_label_reason_counts = Counter()

    for trace in composition.opening_bindings:
        binding_status_counts[state(trace.status)] += 1
        for reason in trace.reason_codes:
            binding_reason_counts[str(reason)] += 1

        opening_selector = ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        existence = physical.prove_existence(opening_selector)
        record = existence.existence_record
        pattern = None if record is None else record.structural_pattern
        label_result = None
        if record is not None and pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION:
            label_result = label_dimension.publish_scope(opening_selector)
            swing_label_status_counts[state(label_result.status)] += 1
            for reason in label_result.reason_codes:
                swing_label_reason_counts[str(reason)] += 1
        pattern_counts[str(pattern)] += 1
        if trace.host_wall_id:
            pattern_host_counts[str(pattern)] += 1
        bucket = pattern_reason_counts.setdefault(str(pattern), Counter())
        for reason in trace.reason_codes:
            bucket[str(reason)] += 1

        helper_status = None
        helper_reasons = ()
        if (
            record is not None
            and record.structural_pattern == JAMB_BOUNDED_TWO_FACE_INTERRUPTION
        ):
            helper = _resolve_two_face_lineage_host(
                physical,
                record,
                wall_result.records,
                wall_result.equivalence,
            )
            if helper is not None:
                helper_status = state(helper.status)
                helper_reasons = helper.reason_codes
                exact_helper_status_counts[helper_status] += 1
                for reason in helper.reason_codes:
                    exact_helper_reason_counts[str(reason)] += 1

        host_diagnostic = None
        if record is not None and pattern in host.RASTER_WALL_BAND_HOST_PATTERNS:
            geometry = host._opening_geometry(physical, record)
            host_diagnostic = {"aperture_bbox_pt": record.aperture_bbox_pt,
                "source_observation_ids": record.source_observation_ids,
                "geometry": None if geometry is None else asdict(geometry)}
            if geometry is not None:
                source_lines = host._authenticated_raster_source_lines(physical, record, wall_result.source_observation_ids)
                edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
                candidates = []
                for candidate in wall_result.records:
                    data = host._candidate_axis_data(candidate, geometry)
                    local_span = host._candidate_locally_owns_opening_span(candidate, geometry, edge_tol=edge_tol)
                    shared_lines = [{"id": pid, "line": source_lines[pid],
                        "axis_data": host._source_line_axis_data(source_lines[pid], geometry)}
                        for pid in candidate.physical_identity.source_primitive_ids if pid in source_lines]
                    near = data is not None and abs(data[2]) <= geometry.thickness / 2 + 5 and data[0] <= geometry.length + 5 and data[1] >= -5
                    near_source = any(item["axis_data"] is not None and abs(item["axis_data"][2]) <= geometry.thickness / 2 + 5 and item["axis_data"][0] <= geometry.length + 5 and item["axis_data"][1] >= -5 for item in shared_lines)
                    if near or near_source or local_span:
                        boundary = wall_result.boundary_evaluation
                        candidates.append({"wall_id": candidate.wall_candidate_id,
                            "centerline": candidate.wall_candidate.centerline_pts,
                            "axis_data": data, "roles": host._candidate_host_roles(candidate, geometry),
                            "whole_wall_role": host._raster_whole_wall_role_data(candidate, geometry),
                            "local_span": local_span, "identity_usable": candidate.physical_identity.usable,
                            "candidate_identity_id": candidate.physical_identity.candidate_identity_id,
                            "source_primitive_ids": candidate.physical_identity.source_primitive_ids,
                            "source_lines": shared_lines,
                            "equivalence_ambiguous": candidate.wall_candidate_id in wall_result.equivalence.ambiguous_wall_ids,
                            "boundary_clean": boundary is not None and candidate.wall_candidate_id in boundary.evaluated_wall_candidate_ids and candidate.wall_candidate_id not in boundary.boundary_tainted_wall_candidate_ids})
                host_diagnostic["candidates"] = candidates
                host_diagnostic["fallbacks"] = {name: asdict(func(wall_result.records, geometry, wall_result.equivalence)) for name, func in (
                    ("bands", host._resolve_host_bands), ("whole", host._resolve_raster_whole_wall_host),
                    ("split", host._resolve_raster_split_centerline_host))}
                host_diagnostic["fallbacks"]["source_band"] = asdict(host._resolve_raster_source_band_host(physical, record, wall_result.records, geometry, wall_result.equivalence, wall_result.source_observation_ids))
                host_diagnostic["fallbacks"]["source"] = asdict(host._resolve_raster_source_primitive_host_from_lines(wall_result.records, geometry, wall_result.equivalence, source_lines))
        rows.append({
            "source_opening": None if record is None else asdict(record),
            "source_opening_geometry": None if record is None else (
                None if host._opening_geometry(physical, record) is None
                else asdict(host._opening_geometry(physical, record))
            ),
            "host_diagnostic": host_diagnostic,
            "opening_identity_id": trace.opening_identity_id,
            "representative_observation_id": trace.representative_observation_id,
            "structural_pattern": pattern,
            "host_wall_id": trace.host_wall_id,
            "binding_status": state(trace.status),
            "binding_reason_codes": list(trace.reason_codes),
            "exact_helper_status": helper_status,
            "exact_helper_reason_codes": list(helper_reasons),
            "label_dimension_status": (
                None if label_result is None else state(label_result.status)
            ),
            "label_dimension_reason_codes": (
                [] if label_result is None else list(label_result.reason_codes)
            ),
            "label_dimension_values_mm": (
                None
                if label_result is None or label_result.evidence is None
                else list(label_result.evidence.dimension_values_mm)
            ),
            "label_raw_text": (
                None
                if label_result is None or label_result.evidence is None
                else label_result.evidence.raw_text
            ),
            "label_semantic_kind": (
                None
                if label_result is None or label_result.evidence is None
                else label_result.evidence.semantic_kind
            ),
        })

    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    areas = publish_live_opening_area_quantities(voids)

    # Preserve the raw hypotheses and exact opposing source receipts in the
    # audit. Annotation opposition never counts as non-existence or closure.
    annotation_opposition = {}
    if wall_result.source_observation_ids:
        seed_selector = ObservationSelector(document_id=current.revision.document_id,
            revision_id=current.revision.revision_id, source_sha256=actual,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=wall_result.source_observation_ids[0])
        structures = physical.visible_candidate_structures(seed_selector)
        for candidate in structures.candidates:
            if candidate.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION:
                continue
            for observation_id in candidate.source_observation_ids:
                result = physical.prove_existence(ObservationSelector(
                    document_id=current.revision.document_id,revision_id=current.revision.revision_id,
                    source_sha256=actual,snapshot_id=current.snapshot.snapshot_id,
                    observation_id=observation_id))
                if result.opposing_evidence_atoms and result.candidate is not None:
                    annotation_opposition[result.candidate.candidate_id] = dict(
                        candidate=asdict(result.candidate), reason_codes=result.reason_codes,
                        opposing_evidence_atoms=[a.to_dict() for a in result.opposing_evidence_atoms])
        # Exact remaining aligned W4 alternatives; no diagnostic fact here
        # modifies the frame's positive DISTINCT requirement.
        for row in rows:
            diagnostic = row['host_diagnostic']
            if diagnostic is None or diagnostic['geometry'] is None:
                continue
            geometry = host._OpeningGeometry(**diagnostic['geometry'])
            aligned = []
            for record in wall_result.records:
                points = record.wall_candidate.centerline_pts
                if any(data is not None and abs(data[2]) <= geometry.thickness/2 + host._RASTER_WHOLE_WALL_CENTER_TOL_PT
                    for data in (host._source_line_axis_data((*a,*b),geometry) for a,b in zip(points,points[1:]))):
                    aligned.append(dict(wall_id=record.wall_candidate_id,
                        centerline=points, source_primitive_ids=record.physical_identity.source_primitive_ids,
                        equivalence_pairs=[list(p) for p in wall_result.equivalence.pair_classifications
                            if record.wall_candidate_id in p[:2]]))
            diagnostic['aligned_wall_scope_candidates'] = aligned

    from pb_live_opening_source_closed_export import seal_live_opening_area_run
    sealed = seal_live_opening_area_run(voids, workspace_id=1, project_id="au_qld_lot16_power")
    Path("lot16-openings-sealed.json").write_text(sealed.to_json())
    from pb_raster_compact_wall_band_segments import COMPACT_WALL_BAND_IDENTITY_VERSION
    from pb_raster_terminal_wall_band_segments import TERMINAL_WALL_BAND_IDENTITY_VERSION
    compact_capture = []
    terminal_capture = []
    for observation_id, observation in source.authority().authenticated_visible_observations(current):
        compact_owned = f':{COMPACT_WALL_BAND_IDENTITY_VERSION}:' in observation.source_primitive_ref
        terminal_owned = f':{TERMINAL_WALL_BAND_IDENTITY_VERSION}:' in observation.source_primitive_ref
        if compact_owned or terminal_owned:
            receipt = source._raster_visibility_receipts[(current.snapshot.snapshot_id, observation_id)]
            (compact_capture if compact_owned else terminal_capture).append(dict(observation_id=observation_id,
                source_primitive_ref=observation.source_primitive_ref,
                geometry=observation.geometry, dpi=receipt.dpi,
                render_sha256=receipt.image_sha256, detector_version=receipt.detector_version,
                visibility_render_sha256=receipt.visibility_render_sha256))
    payload = {
        "source_sha256": actual,
        "snapshot_id": current.snapshot.snapshot_id,
        "compact_raster_source_lines": compact_capture,
        "terminal_raster_source_lines": terminal_capture,
        "native_annotation_opposition": list(annotation_opposition.values()),
        "semantic_status": state(composition.semantic_enumeration_result.status),
        "opening_count": len(composition.opening_bindings),
        "host_bound_count": sum(1 for trace in composition.opening_bindings if trace.host_wall_id),
        "binding_status_counts": dict(binding_status_counts.most_common()),
        "binding_reason_counts": dict(binding_reason_counts.most_common()),
        "structural_pattern_counts": dict(pattern_counts.most_common()),
        "pattern_host_counts": dict(pattern_host_counts.most_common()),
        "pattern_reason_counts": {
            key: dict(value.most_common())
            for key, value in pattern_reason_counts.items()
        },
        "wall_scope_status": state(wall_result.status),
        "wall_scope_complete": bool(wall_result.scope_complete),
        "wall_record_count": len(wall_result.records),
        "equivalence_ambiguous_wall_count": len(wall_result.equivalence.ambiguous_wall_ids),
        "exact_helper_status_counts": dict(exact_helper_status_counts.most_common()),
        "exact_helper_reason_counts": dict(exact_helper_reason_counts.most_common()),
        "swing_label_status_counts": dict(swing_label_status_counts.most_common()),
        "swing_label_reason_counts": dict(swing_label_reason_counts.most_common()),
        "canonical_opening_count": len(voids.canonical_openings),
        "swing_canonical_opening_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
        ),
        "swing_host_frame_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.host_frame_record_id
        ),
        "swing_host_bound_canonical_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.host_wall_id
        ),
        "swing_width_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.width_m is not None
        ),
        "swing_height_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.height_m is not None
        ),
        "swing_kind_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.opening_kind in {"door", "window"}
        ),
        "swing_kind_counts": dict(Counter(
            str(opening.opening_kind or "<none>")
            for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
        ).most_common()),
        "swing_area_resolved_count": sum(
            1 for opening in voids.canonical_openings
            if opening.structural_pattern == RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION
            and opening.area_m2 is not None
        ),
        "area_resolved_count": sum(1 for opening in voids.canonical_openings if opening.area_m2 is not None),
        "opening_area_quantity_count": len(areas),
        "opening_area_values": sorted(float(q.value) for q in areas),
        "canonical_openings": [o.to_dict() for o in voids.canonical_openings],
        "quantity_traces": [asdict(t) for t in voids.traces],
        "host_frame_traces": [asdict(t) for t in composition.host_frames],
        "host_frame_source_role_evidence": [asdict(result.evidence)
            for selector in composition.host_frame_selectors.values()
            for result in (composition.opening_host_frame_authority.resolve(selector),)
            if result.evidence is not None and result.evidence.annotation_exclusion_evidence_atoms],
        "rows": rows,
    }
    # Observability only: enumerate the exact source propositions rejected by
    # the connected-frame geometry gate, including openings outside the raster
    # namespace. No result here is fed back into any producer.
    for selected in rows:
        geometry = selected["source_opening_geometry"]
        if selected["structural_pattern"] != RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION or geometry is None:
            continue
        conflicts = []
        for other in rows:
            candidate = other["source_opening_geometry"]
            if candidate is None or other is selected:
                continue
            cross = geometry["axis"][0]*candidate["axis"][1] - geometry["axis"][1]*candidate["axis"][0]
            offset = sum((candidate["origin"][i]-geometry["origin"][i])*geometry["normal"][i] for i in (0, 1))
            allowance = max(.75, geometry["thickness"]*.15)
            if abs(cross) <= 1e-6 and abs(offset) <= allowance and abs(candidate["thickness"]-geometry["thickness"]) > allowance + 1e-6*geometry["thickness"]:
                conflicts.append({"opening_identity_id": other["opening_identity_id"],
                    "structural_pattern": other["structural_pattern"],
                    "geometry": candidate, "normal_offset_pt": offset,
                    "host_status": other["binding_status"], "host_reasons": other["binding_reason_codes"],
                    "source_opening": other["source_opening"]})
        selected["aligned_frame_geometry_conflicts"] = conflicts
    print(json.dumps(payload, indent=2, sort_keys=True, default=state))


if __name__ == "__main__":
    main()
