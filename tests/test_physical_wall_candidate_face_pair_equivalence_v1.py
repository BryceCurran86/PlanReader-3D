from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateRecord,
    _merge_relation_overrides,
    _producer_closed_bearing_wall_strip_relation_overrides,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass, PhysicalWallIdentity
from pb_source_visibility_authority import RASTER_PDF_VISIBLE_SEGMENT


def _segment(
    seg_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    path_index: int = 10,
    layer: str = "Structural - Bearing",
    **extra,
):
    row = {
        "id": seg_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": 0.5,
        "layer": layer,
        "dashes": "",
        "path_index": path_index,
    }
    row.update(extra)
    return row


def _strip(*, path_index: int = 10, layer: str = "Structural - Bearing"):
    # Two 100pt faces separated by a 6pt wall width. The two 6pt end caps
    # deliberately remain below detect_wall_pairs' long-segment gate.
    return (
        _segment("cap-top", 0.0, 0.0, 6.0, 0.0, path_index=path_index, layer=layer),
        _segment("face-a", 6.0, 0.0, 6.0, 100.0, path_index=path_index, layer=layer),
        _segment("cap-bottom", 6.0, 100.0, 0.0, 100.0, path_index=path_index, layer=layer),
        _segment("face-b", 0.0, 100.0, 0.0, 0.0, path_index=path_index, layer=layer),
    )


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


def test_closed_structural_bearing_strip_proves_one_physical_wall() -> None:
    overrides = _producer_closed_bearing_wall_strip_relation_overrides(
        segments=_strip(),
        records=(_record("wall-a", "face-a"), _record("wall-b", "face-b")),
    )
    assert overrides == {
        ("wall-a", "wall-b"): PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
    }


def test_split_fragments_on_one_proven_face_join_same_physical_wall_group() -> None:
    overrides = _producer_closed_bearing_wall_strip_relation_overrides(
        segments=_strip(),
        records=(
            _record("wall-a", "face-a"),
            _record("wall-b1", "face-b"),
            _record("wall-b2", "face-b"),
        ),
    )
    expected = {
        ("wall-a", "wall-b1"),
        ("wall-a", "wall-b2"),
        ("wall-b1", "wall-b2"),
    }
    assert set(overrides) == expected
    assert set(overrides.values()) == {PhysicalEquivalenceClass.SAME_PHYSICAL_WALL}


def test_open_source_path_cannot_mint_wall_equivalence() -> None:
    segments = list(_strip())
    segments[-1] = _segment("face-b", 0.0, 99.0, 0.0, 1.0)
    overrides = _producer_closed_bearing_wall_strip_relation_overrides(
        segments=segments,
        records=(_record("wall-a", "face-a"), _record("wall-b", "face-b")),
    )
    assert overrides == {}


def test_bare_bearing_or_grid_name_is_not_structural_bearing_proof() -> None:
    for layer in ("A-BEARING", "A-GRID", "Structural - Grid"):
        overrides = _producer_closed_bearing_wall_strip_relation_overrides(
            segments=_strip(layer=layer),
            records=(_record("wall-a", "face-a"), _record("wall-b", "face-b")),
        )
        assert overrides == {}


def test_multiply_pairable_closed_shape_abstains_instead_of_ranking() -> None:
    # A 17x17 square makes both opposite side pairs long enough and close
    # enough for candidate generation. There is no unique wall-face pair, so
    # the producer must abstain rather than select one orientation.
    segments = (
        _segment("top", 0.0, 0.0, 17.0, 0.0),
        _segment("right", 17.0, 0.0, 17.0, 17.0),
        _segment("bottom", 17.0, 17.0, 0.0, 17.0),
        _segment("left", 0.0, 17.0, 0.0, 0.0),
    )
    overrides = _producer_closed_bearing_wall_strip_relation_overrides(
        segments=segments,
        records=(
            _record("wall-top", "top"),
            _record("wall-right", "right"),
            _record("wall-bottom", "bottom"),
            _record("wall-left", "left"),
        ),
    )
    assert overrides == {}


def test_raster_geometry_cannot_mint_native_wall_strip_equivalence() -> None:
    segments = list(_strip())
    segments[1] = _segment(
        "face-a",
        6.0,
        0.0,
        6.0,
        100.0,
        source_kind=RASTER_PDF_VISIBLE_SEGMENT,
    )
    overrides = _producer_closed_bearing_wall_strip_relation_overrides(
        segments=segments,
        records=(_record("wall-a", "face-a"), _record("wall-b", "face-b")),
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
