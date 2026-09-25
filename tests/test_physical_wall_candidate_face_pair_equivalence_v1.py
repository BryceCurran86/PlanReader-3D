from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateRecord,
    _merge_relation_overrides,
    _producer_double_line_relation_overrides,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass, PhysicalWallIdentity
from pb_source_visibility_authority import RASTER_PDF_VISIBLE_SEGMENT


def _segment(seg_id: str, x1: float, y1: float, x2: float, y2: float, **extra):
    row = {
        "id": seg_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": 0.5,
        "layer": "",
        "dashes": "",
    }
    row.update(extra)
    return row


def _record(wall_id: str, *raw_ids: str) -> PhysicalWallCandidateRecord:
    identity = PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id="viewport",
        candidate_identity_id=f"identity-{wall_id}",
        path_fingerprint=((0.0, 0.0), (100.0, 0.0)),
        source_primitive_ids=tuple(raw_ids),
        edge_ids=(f"edge-{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )
    return PhysicalWallCandidateRecord(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(candidate_id=wall_id),
        physical_identity=identity,
    )


def test_unique_reciprocal_native_face_pair_promotes_same_physical_wall() -> None:
    segments = (
        _segment("face-a", 0.0, 0.0, 100.0, 0.0),
        _segment("face-b", 0.0, 6.0, 100.0, 6.0),
    )
    overrides = _producer_double_line_relation_overrides(
        segments=segments,
        records=(_record("wall-a", "face-a"), _record("wall-b", "face-b")),
    )
    assert overrides == {
        ("wall-a", "wall-b"): PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
    }


def test_three_parallel_faces_do_not_rank_or_choose_a_partner() -> None:
    segments = (
        _segment("face-a", 0.0, 0.0, 100.0, 0.0),
        _segment("face-b", 0.0, 6.0, 100.0, 6.0),
        _segment("face-c", 0.0, 12.0, 100.0, 12.0),
    )
    overrides = _producer_double_line_relation_overrides(
        segments=segments,
        records=(
            _record("wall-a", "face-a"),
            _record("wall-b", "face-b"),
            _record("wall-c", "face-c"),
        ),
    )
    assert overrides == {}


def test_raster_line_cannot_mint_native_face_equivalence() -> None:
    segments = (
        _segment(
            "face-a",
            0.0,
            0.0,
            100.0,
            0.0,
            source_kind=RASTER_PDF_VISIBLE_SEGMENT,
        ),
        _segment("face-b", 0.0, 6.0, 100.0, 6.0),
    )
    overrides = _producer_double_line_relation_overrides(
        segments=segments,
        records=(_record("wall-a", "face-a"), _record("wall-b", "face-b")),
    )
    assert overrides == {}


def test_non_bijective_raw_face_to_candidate_mapping_abstains() -> None:
    segments = (
        _segment("face-a", 0.0, 0.0, 100.0, 0.0),
        _segment("face-b", 0.0, 6.0, 100.0, 6.0),
    )
    overrides = _producer_double_line_relation_overrides(
        segments=segments,
        records=(
            _record("wall-a", "face-a"),
            _record("wall-a-duplicate", "face-a"),
            _record("wall-b", "face-b"),
        ),
    )
    assert overrides == {}


def test_independent_positive_proofs_must_agree_before_merge() -> None:
    pair = ("wall-a", "wall-b")
    merged = _merge_relation_overrides(
        {pair: PhysicalEquivalenceClass.SAME_PHYSICAL_WALL},
        {pair: PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS},
        {
            ("wall-c", "wall-d"):
                PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
        },
    )
    assert pair not in merged
    assert merged[("wall-c", "wall-d")] is PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
