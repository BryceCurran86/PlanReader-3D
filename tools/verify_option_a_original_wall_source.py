"""Independent exact-source, same-snapshot regression for Option A walls.

Run on ORIGINAL immutable plan bytes. Recreate the old final canonical collision
guard by selectively disabling only the candidate-rekey helper, then exercise
the actual Option A producer using the SAME already materialized source W4
scope, revision, and snapshot. Never consult frozen benchmark answers or mint
commercial quantities. Every result is a diagnostic / merge gate only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import fitz

from pb_live_canonical_wall_composition import (
    LIVE_CANONICAL_WALL_ID_COLLISION_CANDIDATE,
    compose_live_canonical_walls,
)
from pb_live_physical_net_wall_integration import (
    LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
)
from pb_live_wall_opening_authority_composition import (
    compose_live_wall_opening_authority,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_visibility_authority import SourceVisibilityProducer

SOURCES = {
    "3laurel": (
        "documents/sources/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf",
        "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e",
        18,
        False,
    ),
    "lot16": (
        "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf",
        "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
        13,
        True,
    ),
}


def verify(project: str) -> dict:
    if project not in SOURCES:
        raise ValueError("unknown source project")
    filename, expected_sha, expected_pages, all_pages = SOURCES[project]
    pdf = Path(filename)
    payload = pdf.read_bytes()
    actual_sha = hashlib.sha256(payload).hexdigest()
    assert actual_sha == expected_sha, "immutable original PDF bytes changed"
    with fitz.open(stream=payload, filetype="pdf") as document:
        assert document.page_count == expected_pages
    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall",
        producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{expected_sha[:32]}",
        source_bytes=payload,
        source_locator="memory://live-physical-net-wall-source.pdf",
        page_ids=None if all_pages else ("3",),
    )
    authority = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("3",),
    )
    post_ingest = source.published_snapshot_for_revision(published.revision.revision_id)
    assert post_ingest is not None
    assert post_ingest.revision.source_sha256 == expected_sha
    selector = PhysicalWallCandidateSelector(
        document_id=post_ingest.revision.document_id,
        revision_id=post_ingest.revision.revision_id,
        source_sha256=expected_sha,
        snapshot_id=post_ingest.snapshot.snapshot_id,
        page_id="3",
        decision_scope_id="wall-source:page-3",
    )
    scope = authority.physical_wall_candidate_authority.resolve_scope(selector)
    assert scope.source_sha256 == expected_sha
    assert scope.snapshot_id == post_ingest.snapshot.snapshot_id
    assert scope.page_id == "3"
    wall_ids = [r.wall_candidate_id for r in scope.records]
    assert len(wall_ids) == len(set(wall_ids)), (
        "unexpected W4 member-address collision; do not conflate with canonical ID"
    )
    from pb_live_canonical_wall_composition import (
        _localize_candidate_id_collisions,
    )
    # Simulate ONLY the original end-stage behavior. All W4/opening sources,
    # canonical producer inputs, revision, source snapshot and host authorities
    # remain exactly the same in both runs.
    with patch(
        "pb_live_canonical_wall_composition._localize_candidate_id_collisions",
        lambda walls, mapping: (walls, dict(mapping), False),
    ):
        before = compose_live_canonical_walls(
            source_visibility_producer=source,
            wall_opening_composition=authority,
        )
    assert _localize_candidate_id_collisions is not None
    after = compose_live_canonical_walls(
        source_visibility_producer=source,
        wall_opening_composition=authority,
    )
    final_snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    assert final_snapshot is not None
    assert final_snapshot.snapshot.snapshot_id == post_ingest.snapshot.snapshot_id, (
        "source snapshot changed across exact before/after comparison"
    )
    assert final_snapshot.revision.source_sha256 == expected_sha
    assert before.source_pages == after.source_pages
    # The output carries diagnostic identities only; no measured, sellable
    # net/gross wall area or resolved physical wall is possible from rekeying.
    for wall in after.walls:
        if wall.identity_status == "candidate_canonical_id_collision_unresolved":
            assert not wall.physical_identity_resolved
            assert wall.physical_wall_id is None
            assert wall.length_m is None and wall.height_m is None
            assert wall.gross_area_m2 is None and wall.net_area_m2 is None
            assert not wall.quantity_complete
    after_ids = [w.canonical_wall_id for w in after.walls]
    assert len(after_ids) == len(set(after_ids)), "still-colliding IDs must fail closed"
    detail = {
        "project": project,
        "original_source_sha256": expected_sha,
        "original_pdf_page": 3,
        "source_revision_id": final_snapshot.revision.revision_id,
        "source_snapshot_id": final_snapshot.snapshot.snapshot_id,
        "source_page_is_original_vector_pdf": project == "3laurel",
        "original_w4_member_record_count": len(wall_ids),
        "scope_complete": scope.scope_complete,
        "before_status": before.status.value,
        "after_status": after.status.value,
        "before_canonical_wall_count": len(before.walls),
        "after_canonical_wall_count": len(after.walls),
        "before_reason_codes": list(before.reason_codes),
        "after_reason_codes": list(after.reason_codes),
        "unresolved_member_count": len(after.unresolved_wall_candidate_ids),
        "collision_candidate_count": sum(
            w.identity_status == "candidate_canonical_id_collision_unresolved"
            for w in after.walls
        ),
        "same_source_snapshot_before_after": True,
        "commercial_wall_quantities_created": False,
        "benchmark_score_granted": False,
    }
    if project == "3laurel":
        assert scope.status is EvidenceResolutionStatus.CORROBORATED
        assert len(wall_ids) == 1559
        assert not scope.scope_complete
        evaluation = scope.boundary_evaluation
        assert evaluation is not None
        clean_ids = set(evaluation.evaluated_wall_candidate_ids) - set(
            evaluation.boundary_tainted_wall_candidate_ids
        )
        assert len(evaluation.boundary_tainted_wall_candidate_ids) == 114
        assert len(clean_ids) == 1445
        assert before.status is EvidenceResolutionStatus.CONFLICT
        assert before.walls == ()
        assert dict(before.candidate_to_canonical_wall_id) == {}
        assert after.status is EvidenceResolutionStatus.CANDIDATE
        assert len(after.walls) == 1445
        assert len(after.unresolved_wall_candidate_ids) == 1559
        assert set(after.candidate_to_canonical_wall_id) == clean_ids
        assert all(not w.physical_identity_resolved for w in after.walls)
        assert sum(w.identity_status == "candidate_canonical_id_collision_unresolved"
                   for w in after.walls) == 2
        assert LIVE_CANONICAL_WALL_ID_COLLISION_CANDIDATE in after.reason_codes
        assert all(w.length_m is None and w.height_m is None
                   and w.gross_area_m2 is None and w.net_area_m2 is None
                   and not w.quantity_complete for w in after.walls)
        assert all(w.wall_local_frame_id is None for w in after.walls)
        assert not any(w.member_wall_candidate_ids[0] in set(
            evaluation.boundary_tainted_wall_candidate_ids
        ) for w in after.walls)
        detail["boundary_tainted_w4_count"] = 114
        detail["boundary_clean_w4_count"] = len(clean_ids)
    else:
        assert len(wall_ids) == 2094
        assert before.status == after.status
        assert before.reason_codes == after.reason_codes
        assert before.walls == after.walls
        assert before.unresolved_wall_candidate_ids == after.unresolved_wall_candidate_ids
        assert dict(before.candidate_to_canonical_wall_id) == dict(
            after.candidate_to_canonical_wall_id
        )
        assert not any(
            w.identity_status == "candidate_canonical_id_collision_unresolved"
            for w in after.walls
        )
        detail["lot16_exact_canonical_wall_state_unchanged"] = True
    return detail


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", choices=sorted(SOURCES), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.project)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print("ORIGINAL_OPTION_A_SOURCE_SAME_SNAPSHOT_PROOF", json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
