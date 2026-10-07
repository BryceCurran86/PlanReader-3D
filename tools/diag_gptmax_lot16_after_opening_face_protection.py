from __future__ import annotations

from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import JAMB_BOUNDED_TWO_FACE_INTERRUPTION
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateSelector,
    _filter_proven_wall_strip_geometry,
    _filter_repeated_non_physical_drafting_primitives,
    _opening_raw_relation_sets,
    _proven_filled_wall_strips,
    _producer_opening_wall_face_source_ids,
    _source_page_segments,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    is_structural_candidate_segment,
)


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"
SCOPE_ID = "wall-source:page-3"


def state(value):
    return str(getattr(value, "value", value))


def raw_id_for_observation(observation):
    ref = str(observation.source_primitive_ref or "")
    if observation.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT:
        prefix = "visible:segment:"
        return ref[len(prefix):] if ref.startswith(prefix) else None
    if observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT:
        prefix = "visible:"
        return ref[len(prefix):] if ref.startswith(prefix) else None
    return None


def edge_lineage_raw_ids(graph):
    by_raw = defaultdict(list)
    for edge in tuple(graph.get("edges") or ()):
        lineage = edge.get(LINEAGE_KEY) or {}
        for raw_id in tuple(lineage.get("source_primitive_ids") or ()):
            by_raw[str(raw_id)].append(str(edge.get("id") or ""))
    return by_raw


def main():
    source_bytes = PDF.read_bytes()
    actual = hashlib.sha256(source_bytes).hexdigest()
    assert actual == EXPECTED_SHA

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
    assert current is not None

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

    segments, _, page_width, page_height = _source_page_segments(
        source_producer=source,
        published=current,
        source_bytes=source_bytes,
        page_id=PAGE_ID,
        decision_scope_id=SCOPE_ID,
    )
    raw_segment = {str(s.get("id") or ""): s for s in segments if str(s.get("id") or "")}
    protected_face_ids = _producer_opening_wall_face_source_ids(
        source_producer=source,
        published=current,
        page_id=PAGE_ID,
        resolved_visible_observations=tuple(
            (observation_id, observation)
            for observation_id, observation in (
                (
                    observation_id,
                    composition.physical_opening_authority
                    .source_visibility_authority()
                    .resolve_visible(
                        ObservationSelector(
                            document_id=current.revision.document_id,
                            revision_id=current.revision.revision_id,
                            source_sha256=current.revision.source_sha256,
                            snapshot_id=current.snapshot.snapshot_id,
                            observation_id=observation_id,
                        )
                    ).observation,
                )
                for observation_id in current.visible_observation_ids
            )
            if observation is not None and str(observation.page_id) == PAGE_ID
        ),
        physical_opening_authority=composition.physical_opening_authority,
    )
    motif_filtered = _filter_repeated_non_physical_drafting_primitives(
        segments,
        page_width=page_width,
        page_height=page_height,
        protected_source_primitive_ids=protected_face_ids,
    )
    motif_ids = {str(s.get("id") or "") for s in motif_filtered}
    strips = _proven_filled_wall_strips(motif_filtered)
    graph_segments = _filter_proven_wall_strip_geometry(motif_filtered, strips)
    graph_segment_ids = {str(s.get("id") or "") for s in graph_segments}
    graph = build_wall_graph_for_viewport(graph_segments)
    graph_lineage = edge_lineage_raw_ids(graph)

    owners_by_raw = defaultdict(list)
    usable_owners_by_raw = defaultdict(list)
    for record in wall_result.records:
        for raw_id in record.physical_identity.source_primitive_ids:
            owners_by_raw[str(raw_id)].append(record)
            if record.physical_identity.usable:
                usable_owners_by_raw[str(raw_id)].append(record)

    equivalence = wall_result.equivalence
    ambiguous_ids = set(() if equivalence is None else equivalence.ambiguous_wall_ids)

    visibility = composition.physical_opening_authority.source_visibility_authority()
    opening_rows = []
    stage_counts = Counter()
    owner_count_distribution = Counter()
    pair_class_counts = Counter()

    for trace in composition.opening_bindings:
        existence = composition.physical_opening_authority.prove_existence(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=trace.representative_observation_id,
            )
        )
        opening = existence.existence_record
        if (
            existence.status is not EvidenceResolutionStatus.CORROBORATED
            or opening is None
            or opening.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION
        ):
            continue

        observations = []
        raw_lines = {}
        for observation_id in opening.source_observation_ids:
            resolved = visibility.resolve_visible(
                ObservationSelector(
                    document_id=current.revision.document_id,
                    revision_id=current.revision.revision_id,
                    source_sha256=current.revision.source_sha256,
                    snapshot_id=current.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = resolved.observation
            if resolved.status is not EvidenceResolutionStatus.CORROBORATED or observation is None:
                continue
            raw_id = raw_id_for_observation(observation)
            if raw_id is None:
                continue
            geometry = tuple(float(v) for v in observation.geometry)
            if len(geometry) != 4:
                continue
            observations.append((observation_id, observation, raw_id))
            raw_lines[raw_id] = geometry

        relations = _opening_raw_relation_sets(raw_lines)
        same_pairs = sorted(
            pair
            for pair, classes in relations.items()
            if {state(value) for value in classes} == {"same_physical_wall"}
        )
        face_raw_ids = sorted({raw for pair in same_pairs for raw in pair})
        if len(face_raw_ids) != 4:
            pair_class_counts["face_role_unresolved"] += 1
            continue

        face_rows = []
        for raw_id in face_raw_ids:
            segment = raw_segment.get(raw_id)
            structural = None
            structural_reasons = []
            if segment is not None:
                structural, structural_reasons = is_structural_candidate_segment(segment)
            owners = owners_by_raw.get(raw_id, [])
            usable = usable_owners_by_raw.get(raw_id, [])
            owner_ids = sorted(record.wall_candidate_id for record in owners)
            usable_ids = sorted(record.wall_candidate_id for record in usable)
            ambiguous_owner_ids = sorted(set(owner_ids) & ambiguous_ids)

            if raw_id not in raw_segment:
                stage = "missing_from_w2_source_segments"
            elif raw_id not in motif_ids:
                stage = "filtered_repeated_motif"
            elif raw_id not in graph_segment_ids:
                stage = "filtered_wall_strip_geometry"
            elif not structural:
                stage = "non_structural_candidate"
            elif not graph_lineage.get(raw_id):
                stage = "absent_from_wall_graph_lineage"
            elif not owners:
                stage = "graph_lineage_no_w4_owner"
            elif not usable:
                stage = "w4_owner_identity_unusable"
            elif ambiguous_owner_ids:
                stage = "w4_owner_equivalence_ambiguous"
            elif len(usable_ids) > 1:
                stage = "multiple_usable_w4_owners"
            else:
                stage = "single_usable_w4_owner"

            stage_counts[stage] += 1
            owner_count_distribution[str(len(usable_ids))] += 1
            face_rows.append({
                "raw_id": raw_id,
                "protected_by_g17": raw_id in protected_face_ids,
                "stage": stage,
                "source_kind": None if segment is None else str(segment.get("source_kind") or "native"),
                "layer": None if segment is None else str(segment.get("layer") or ""),
                "structural_candidate": structural,
                "structural_reasons": list(structural_reasons or ()),
                "motif_survives": raw_id in motif_ids,
                "wall_strip_survives": raw_id in graph_segment_ids,
                "graph_edge_ids": sorted(graph_lineage.get(raw_id, ())),
                "w4_owner_ids": owner_ids,
                "usable_w4_owner_ids": usable_ids,
                "ambiguous_owner_ids": ambiguous_owner_ids,
            })

        opening_rows.append({
            "opening_identity_id": trace.opening_identity_id,
            "host_binding_status": state(trace.status),
            "host_binding_reason_codes": list(trace.reason_codes),
            "same_face_pairs": [list(pair) for pair in same_pairs],
            "face_rows": face_rows,
        })

    protected_occurrences = [
        face
        for opening in opening_rows
        for face in opening["face_rows"]
        if face["protected_by_g17"]
    ]
    unprotected_occurrences = [
        face
        for opening in opening_rows
        for face in opening["face_rows"]
        if not face["protected_by_g17"]
    ]
    opening_protection_counts = Counter(
        sum(1 for face in opening["face_rows"] if face["protected_by_g17"])
        for opening in opening_rows
    )
    payload = {
        "source_sha256": actual,
        "snapshot_id": current.snapshot.snapshot_id,
        "wall_scope_status": state(wall_result.status),
        "wall_scope_complete": bool(wall_result.scope_complete),
        "wall_scope_reason_codes": list(wall_result.reason_codes),
        "protected_face_source_id_count": len(protected_face_ids),
        "protected_face_occurrence_count": len(protected_occurrences),
        "unprotected_face_occurrence_count": len(unprotected_occurrences),
        "opening_protected_face_count_distribution": dict(sorted(
            (str(key), value) for key, value in opening_protection_counts.items()
        )),
        "unprotected_face_stage_counts": dict(Counter(
            face["stage"] for face in unprotected_occurrences
        ).most_common()),
        "unprotected_face_source_ids": sorted({
            face["raw_id"] for face in unprotected_occurrences
        }),
        "wall_candidate_count": len(wall_result.records),
        "equivalence_ambiguous_wall_count": 0 if equivalence is None else len(equivalence.ambiguous_wall_ids),
        "host_bound_count": sum(1 for trace in composition.opening_bindings if trace.host_wall_id),
        "host_binding_reason_counts": dict(Counter(
            reason
            for trace in composition.opening_bindings
            for reason in trace.reason_codes
        ).most_common()),
        "two_face_opening_count": len(opening_rows),
        "interrupted_face_primitive_count": sum(len(row["face_rows"]) for row in opening_rows),
        "face_stage_counts": dict(stage_counts.most_common()),
        "usable_owner_count_distribution": dict(sorted(owner_count_distribution.items())),
        "opening_rows": opening_rows,
    }
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    area_quantities = publish_live_opening_area_quantities(voids)
    payload.update({
        "canonical_opening_count": len(voids.canonical_openings),
        "area_resolved_count": sum(
            1 for opening in voids.canonical_openings if opening.area_m2 is not None
        ),
        "opening_area_quantity_count": len(area_quantities),
        "opening_area_values": [float(quantity.value) for quantity in area_quantities],
    })
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
