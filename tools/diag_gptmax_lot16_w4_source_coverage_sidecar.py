from __future__ import annotations

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
from pb_physical_opening_authority import JAMB_BOUNDED_TWO_FACE_INTERRUPTION
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateSelector,
    _opening_raw_relation_sets,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _equivalence_group(equivalence, wall_id: str) -> tuple[str, ...]:
    for group in equivalence.equivalence_groups:
        if wall_id in group:
            return tuple(sorted(group))
    return (wall_id,)


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
    equivalence = wall_result.equivalence
    assert equivalence is not None
    ambiguous_ids = set(equivalence.ambiguous_wall_ids)

    identity_owners: dict[str, list[object]] = {}
    coverage_owners: dict[str, list[object]] = {}
    for record in wall_result.records:
        for raw_id in record.physical_identity.source_primitive_ids:
            identity_owners.setdefault(str(raw_id), []).append(record)
        for raw_id in record.source_coverage_primitive_ids:
            coverage_owners.setdefault(str(raw_id), []).append(record)

    visibility = composition.physical_opening_authority.source_visibility_authority()
    assert visibility is not None

    role_counts = Counter()
    opening_counts = Counter()
    rows = []

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

        raw_lines = {}
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
            if len(geometry) == 4:
                raw_lines[raw_id] = geometry

        relations = _opening_raw_relation_sets(raw_lines)
        same_pairs = tuple(
            pair
            for pair, classes in sorted(relations.items())
            if classes == {PhysicalEquivalenceClass.SAME_PHYSICAL_WALL}
        )
        face_raw_ids = tuple(
            sorted({raw_id for pair in same_pairs for raw_id in pair})
        )
        if len(same_pairs) != 2 or len(face_raw_ids) != 4:
            opening_counts["two_face_relation_shape_unavailable"] += 1
            rows.append(
                {
                    "opening_identity_id": opening.record_id,
                    "face_raw_ids": list(face_raw_ids),
                    "same_pairs": [list(pair) for pair in same_pairs],
                    "classification": "relation_shape_unavailable",
                }
            )
            continue

        role_rows = []
        all_coverage_mapped = True
        all_coverage_unique_group = True
        any_recovered = False
        for raw_id in face_raw_ids:
            identity = tuple(identity_owners.get(raw_id, ()))
            coverage = tuple(coverage_owners.get(raw_id, ()))
            if not identity:
                role_counts["identity_unmapped"] += 1
            else:
                role_counts["identity_mapped"] += 1
            if not coverage:
                role_counts["coverage_unmapped"] += 1
                all_coverage_mapped = False
            else:
                role_counts["coverage_mapped"] += 1
            if not identity and coverage:
                role_counts["recovered_by_sidecar"] += 1
                any_recovered = True

            groups = {
                _equivalence_group(equivalence, record.wall_candidate_id)
                for record in coverage
            }
            ambiguous_owner_ids = sorted(
                record.wall_candidate_id
                for record in coverage
                if record.wall_candidate_id in ambiguous_ids
            )
            if len(groups) != 1 or ambiguous_owner_ids:
                all_coverage_unique_group = False

            role_rows.append(
                {
                    "raw_id": raw_id,
                    "identity_owner_ids": sorted(
                        record.wall_candidate_id for record in identity
                    ),
                    "coverage_owner_ids": sorted(
                        record.wall_candidate_id for record in coverage
                    ),
                    "coverage_equivalence_groups": [
                        list(group) for group in sorted(groups)
                    ],
                    "ambiguous_coverage_owner_ids": ambiguous_owner_ids,
                }
            )

        if all_coverage_mapped and all_coverage_unique_group:
            opening_counts["sidecar_host_lineage_eligible"] += 1
        elif all_coverage_mapped:
            opening_counts["sidecar_host_lineage_conflict"] += 1
        else:
            opening_counts["sidecar_host_lineage_unmapped"] += 1
        if any_recovered:
            opening_counts["openings_with_recovered_roles"] += 1

        rows.append(
            {
                "opening_identity_id": opening.record_id,
                "binding_status": str(
                    getattr(trace.status, "value", trace.status)
                ),
                "binding_reason_codes": list(trace.reason_codes),
                "face_raw_ids": list(face_raw_ids),
                "roles": role_rows,
            }
        )

    print(
        json.dumps(
            {
                "source_sha256": actual,
                "snapshot_id": current.snapshot.snapshot_id,
                "wall_candidate_count": len(wall_result.records),
                "wall_scope_complete": wall_result.scope_complete,
                "ambiguous_wall_count": len(ambiguous_ids),
                "two_face_opening_count": len(rows),
                "role_counts": dict(role_counts.most_common()),
                "opening_counts": dict(opening_counts.most_common()),
                "openings": rows,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
