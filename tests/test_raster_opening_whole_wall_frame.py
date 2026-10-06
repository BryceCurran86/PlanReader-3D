from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_host_binding_authority as host
import pb_opening_host_frame_authority as frame
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
)
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution


GEOMETRY = host._OpeningGeometry(
    origin=(100.0, 55.0),
    axis=(1.0, 0.0),
    normal=(0.0, 1.0),
    length=40.0,
    thickness=10.0,
)


def _record(wall_id: str, *, offset: float = 0.0):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            is_curved=False,
            centerline_pts=((20.0, 55.0 + offset), (220.0, 55.0 + offset)),
            reason_codes=(),
        ),
        physical_identity=SimpleNamespace(
            candidate_identity_id=f"candidate:{wall_id}",
        ),
    )


def _equivalence(records):
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="wall-source:page-1",
        representative_wall_ids=tuple(r.wall_candidate_id for r in records),
        abstained_wall_ids=(),
        equivalence_groups=(),
        ambiguous_wall_ids=(),
        same_wall_ids=(),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )


def _scope(records, *, complete: bool = True):
    return SimpleNamespace(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=complete,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        records=tuple(records),
        equivalence=_equivalence(records),
    )


def _binding(wall_id: str = "wall:host"):
    return SimpleNamespace(
        record_id="binding:1",
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        decision_scope_id="wall-source:page-1",
        member_wall_candidate_ids=(wall_id,),
    )


def _opening(*, pattern: str = RASTER_FRAMED_WALL_BAND_INTERRUPTION):
    return SimpleNamespace(
        record_id="opening:1",
        structural_pattern=pattern,
        source_observation_ids=("face:a", "face:b", "frame:a"),
    )


def _producer(scope):
    producer = object.__new__(frame.OpeningHostFrameProducer)
    producer._walls = SimpleNamespace(resolve_scope=lambda _selector: scope)
    return producer


def test_raster_whole_wall_binding_produces_source_space_frame() -> None:
    records = (_record("wall:host"),)
    result = _producer(_scope(records))._raster_whole_wall_frame(
        binding=_binding(),
        opening=_opening(),
        geometry=GEOMETRY,
    )

    assert result is not None
    assert result.origin == pytest.approx((20.0, 55.0))
    assert result.axis == (1.0, 0.0)
    assert result.normal == (0.0, 1.0)
    assert result.u0 == pytest.approx(80.0)
    assert result.u1 == pytest.approx(120.0)
    assert result.wall_thickness == pytest.approx(10.0)
    assert result.whole_wall_length == pytest.approx(200.0)
    assert result.candidate_ids == ("wall:host",)
    assert result.source_observation_ids == ("face:a", "face:b", "frame:a")


def test_raster_swing_whole_wall_binding_uses_same_source_space_frame() -> None:
    records = (_record("wall:host"),)
    result = _producer(_scope(records))._raster_whole_wall_frame(
        binding=_binding(),
        opening=_opening(pattern=RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION),
        geometry=GEOMETRY,
    )

    assert result is not None
    assert result.origin == pytest.approx((20.0, 55.0))
    assert result.axis == (1.0, 0.0)
    assert result.normal == (0.0, 1.0)
    assert result.candidate_ids == ("wall:host",)


def test_binding_member_must_match_reproved_whole_wall_host() -> None:
    records = (_record("wall:host"),)
    result = _producer(_scope(records))._raster_whole_wall_frame(
        binding=_binding("wall:other"),
        opening=_opening(),
        geometry=GEOMETRY,
    )
    assert result is None


def test_off_center_whole_wall_cannot_mint_host_frame() -> None:
    records = (
        _record(
            "wall:host",
            offset=host._RASTER_WHOLE_WALL_CENTER_TOL_PT + 0.05,
        ),
    )
    result = _producer(_scope(records))._raster_whole_wall_frame(
        binding=_binding(),
        opening=_opening(),
        geometry=GEOMETRY,
    )
    assert result is None


def test_incomplete_wall_scope_cannot_mint_host_frame() -> None:
    records = (_record("wall:host"),)
    result = _producer(_scope(records, complete=False))._raster_whole_wall_frame(
        binding=_binding(),
        opening=_opening(),
        geometry=GEOMETRY,
    )
    assert result is None


def test_non_raster_opening_cannot_use_whole_wall_frame_shortcut() -> None:
    records = (_record("wall:host"),)
    result = _producer(_scope(records))._raster_whole_wall_frame(
        binding=_binding(),
        opening=_opening(pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION),
        geometry=GEOMETRY,
    )
    assert result is None
