from __future__ import annotations

# Diagnostic-only W4 lineage census; no production authority is changed.

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import _raw_source_primitive_id
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateSelector,
    _filter_proven_wall_strip_geometry,
    _filter_repeated_non_physical_drafting_primitives,
    _opening_raw_relation_sets,
    _proven_filled_wall_strips,
    _source_page_segments,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    is_structural_candidate_segment,
)


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _state(value):
    return str(getattr(value, "value", value))


def main() -> None:
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
            decision_scope_id=f"wall-source:page-{PAGE_ID}",
        )
    )

    segments, _observation_ids, page_width, page_height = _source_page_segments(
        source_producer=source,
        published=current,
        source_bytes=source_bytes,
        page_id=PAGE_ID,
        decision_scope_id=f"wall-source:page-{PAGE_ID}",
    )
    topology_segments = _filter_repeated_non_physical_drafting_primitives(
        segments,
        page_width=page_width,
        page_height=page_height,
    )
    wall_strips = _proven_filled_wall_strips(topology_segments)
    graph_segments = _filter_proven_wall_strip_geometry(
        topology_segments,
        wall_strips,
    )
    graph = build_wall_graph_for_viewport(graph_segments)

    initial_by_id = {
        str(segment.get("id") or ""): segment
        for segment in segments
        if str(segment.get("id") or "")
    }
    topology_ids = {
        str(segment.get("id") or "")
        for segment in topology_segments
        if str(segment.get("id") or "")
    }
    graph_input_ids = {
        str(segment.get("id") or "")
        for segment in graph_segments
        if str(segment.get("id") or "")
    }

    graph_edges_by_raw: dict[str, list[str]] = {}
    for edge in tuple(graph.get("edges") or ()):
        lineage = edge.get(LINEAGE_KEY) or {}
        for raw_id in tuple(lineage.get("source_primitive_ids") or ()):
            graph_edges_by_raw.setdefault(str(raw_id), []).append(
                str(edge.get("id") or "")
            )

    owners_by_raw: dict[str, list[object]] = {}
    for record in wall_result.records:
        for raw_id in record.physical_identity.source_primitive_ids:
            owners_by_raw.setdefault(str(raw_id), []).append(record)

    visibility = composition.physical_opening_authority.source_visibility_authority()
    assert visibility is not None
    equivalence = wall_result.equivalence
    ambiguous_wall_ids = (
        set()
        if equivalence is None
        else set(equivalence.ambiguous_wall_ids)
    )

    stage_counts = Counter()
    owner_count_counts = Counter()
    structural_reason_counts = Counter()
    rows = []
    two_face_count = 0
    face_role_count = 0

    for trace in composition.opening_bindings:
        selector = ObservationSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            observation_id=trace.representative_observation_id,
        )
        existence = composition.physical_opening_authority.prove_existence(selector)
        opening = existence.existence_record
        if (
            existence.status is not EvidenceResolutionStatus.CORROBORATED
            or opening is None
            or opening.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION
        ):
            continue
        two_face_count += 1

        source_records = []
        raw_lines = {}
        observation_by_raw = {}
        for observation_id in opening.source_observation_ids:
            visible = visibility.resolve_visible(
                ObservationSelector(
                    document_id=current.revision.document_id,
                    revision_id=current.revision.revision_id,
                    source_sha256=current.revision.source_sha256,
                    snapshot_id=current.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            observation = visible.observation
            if (
                visible.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
            ):
                continue
            raw_id = _raw_source_primitive_id(observation)
            if raw_id is None:
                continue
            geometry = tuple(float(v) for v in observation.geometry)
            if len(geometry) != 4:
                continue
            source_records.append(observation)
            raw_lines[raw_id] = geometry
            observation_by_raw[raw_id] = observation

        relations = _opening_raw_relation_sets(raw_lines)
        same_pairs = tuple(
            pair
            for pair, classes in sorted(relations.items())
            if classes == {PhysicalEquivalenceClass.SAME_PHYSICAL_WALL}
        )
        face_raw_ids = sorted({raw_id for pair in same_pairs for raw_id in pair})

        opening_rows = []
        for raw_id in face_raw_ids:
            face_role_count += 1
            segment = initial_by_id.get(raw_id)
            structural = False
            structural_reasons = []
            if segment is not None:
                structural, structural_reasons = is_structural_candidate_segment(
                    segment
                )
            structural_reason_counts.update(structural_reasons)

            graph_edge_ids = sorted(
                edge_id
                for edge_id in graph_edges_by_raw.get(raw_id, ())
                if edge_id
            )
            owners = sorted(
                owners_by_raw.get(raw_id, ()),
                key=lambda record: record.wall_candidate_id,
            )
            owner_ids = [record.wall_candidate_id for record in owners]
            owner_count_counts[len(owner_ids)] += 1
            owner_ambiguous = [
                wall_id for wall_id in owner_ids if wall_id in ambiguous_wall_ids
            ]
            owner_blockers = {
                wall_id: (
                    []
                    if equivalence is None
                    else list(equivalence.blockers_for(wall_id))
                )
                for wall_id in owner_ids
            }

            if segment is None:
                stage = "source_segment_missing"
            elif not structural:
                stage = "structural_eligibility_rejected"
            elif raw_id not in topology_ids:
                stage = "repeated_motif_filtered"
            elif raw_id not in graph_input_ids:
                stage = "wall_strip_geometry_filtered"
            elif not graph_edge_ids:
                stage = "graph_lineage_absent"
            elif not owner_ids:
                stage = "w4_identity_lineage_absent"
            elif len(owner_ids) > 1:
                stage = "multiple_w4_owners"
            elif owner_ambiguous:
                stage = "w4_owner_equivalence_ambiguous"
            else:
                stage = "w4_owner_resolved"
            stage_counts[stage] += 1

            observation = observation_by_raw.get(raw_id)
            opening_rows.append(
                {
                    "raw_id": raw_id,
                    "observation_id": (
                        None if observation is None else observation.observation_id
                    ),
                    "observation_kind": (
                        None if observation is None else observation.observation_kind
                    ),
                    "source_primitive_ref": (
                        None
                        if observation is None
                        else observation.source_primitive_ref
                    ),
                    "geometry": (
                        None
                        if observation is None
                        else [float(v) for v in observation.geometry]
                    ),
                    "structural_eligible": bool(structural),
                    "structural_reason_codes": list(structural_reasons),
                    "present_after_repeated_motif_filter": raw_id in topology_ids,
                    "present_in_wall_graph_input": raw_id in graph_input_ids,
                    "graph_edge_ids": graph_edge_ids,
                    "w4_owner_ids": owner_ids,
                    "w4_owner_ambiguous_ids": owner_ambiguous,
                    "w4_owner_blockers": owner_blockers,
                    "first_missing_stage": stage,
                }
            )

        rows.append(
            {
                "opening_identity_id": opening.record_id,
                "binding_status": _state(trace.status),
                "binding_reason_codes": list(trace.reason_codes),
                "same_face_pairs": [list(pair) for pair in same_pairs],
                "face_roles": opening_rows,
            }
        )

    payload = {
        "source_sha256": actual,
        "snapshot_id": current.snapshot.snapshot_id,
        "wall_scope_status": _state(wall_result.status),
        "wall_scope_complete": bool(wall_result.scope_complete),
        "wall_scope_reason_codes": list(wall_result.reason_codes),
        "wall_candidate_count": len(wall_result.records),
        "wall_equivalence_ambiguous_count": len(ambiguous_wall_ids),
        "two_face_opening_count": two_face_count,
        "interrupted_face_role_count": face_role_count,
        "first_missing_stage_counts": dict(stage_counts.most_common()),
        "w4_owner_count_distribution": {
            str(key): value for key, value in sorted(owner_count_counts.items())
        },
        "structural_rejection_reason_counts": dict(
            structural_reason_counts.most_common()
        ),
        "openings": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
