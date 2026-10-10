from __future__ import annotations

from types import SimpleNamespace

import pb_physical_wall_candidate_authority as module
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_raster_opening_source_primitives import RASTER_WALL_BAND_FACE
from pb_source_visibility_authority import RASTER_PDF_VISIBLE_SEGMENT


PARTITION = "source-partition:1"


def _ordinary(
    raw_id: str,
    geometry: tuple[float, float, float, float],
    *,
    partition: str = PARTITION,
):
    return (
        f"visible:{raw_id}",
        SimpleNamespace(
            observation_kind=RASTER_PDF_VISIBLE_SEGMENT,
            source_primitive_ref=f"visible:{raw_id}",
            source_partition_id=partition,
            geometry=geometry,
            page_id="1",
        ),
    )


def _face(
    observation_id: str,
    geometry: tuple[float, float, float, float],
    *,
    partition: str = PARTITION,
):
    return SimpleNamespace(
        observation_id=observation_id,
        observation_kind=RASTER_WALL_BAND_FACE,
        source_partition_id=partition,
        geometry=geometry,
        page_id="1",
    )


def _record(wall_id: str, raw_id: str):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        physical_identity=SimpleNamespace(
            usable=True,
            source_primitive_ids=(raw_id,),
        ),
    )


def _fixture(*, low_partition: str = PARTITION, low_cross_delta: float = 0.5):
    faces = {
        "face-left-low": _face("face-left-low", (20.0, 50.0, 99.76, 50.0)),
        "face-left-high": _face("face-left-high", (20.0, 60.0, 99.76, 60.0)),
        "face-right-low": _face("face-right-low", (140.24, 50.0, 220.0, 50.0)),
        "face-right-high": _face("face-right-high", (140.24, 60.0, 220.0, 60.0)),
    }
    existence = SimpleNamespace(
        record_id="raster-opening:1",
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        structural_pattern=RASTER_FRAMED_WALL_BAND_INTERRUPTION,
        aperture_bbox_pt=(100.0, 50.0, 140.0, 60.0),
        source_observation_ids=tuple(faces),
    )

    class Visibility:
        def resolve_raster_opening_primitive(self, selector):
            observation = faces.get(selector.observation_id)
            if observation is None:
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    observation=None,
                )
            return SimpleNamespace(
                status=EvidenceResolutionStatus.CORROBORATED,
                observation=observation,
            )

    class OpeningAuthority:
        def prove_existence(self, selector):
            if selector.observation_id in faces:
                return SimpleNamespace(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    proposition=PHYSICAL_OPENING_EXISTS,
                    existence_record=existence,
                )
            return SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                existence_record=None,
            )

    source = SimpleNamespace(authority=lambda: Visibility())
    published = SimpleNamespace(
        revision=SimpleNamespace(
            document_id="doc",
            revision_id="rev",
            source_sha256="a" * 64,
        ),
        snapshot=SimpleNamespace(snapshot_id="snap"),
        raster_opening_primitive_observation_ids=tuple(faces),
    )

    ordinary = (
        _ordinary(
            "raster_segment:low-left",
            (10.0, 50.0 + low_cross_delta, 100.0, 50.0 + low_cross_delta),
            partition=low_partition,
        ),
        _ordinary("raster_segment:high-left", (10.0, 59.5, 100.0, 59.5)),
        _ordinary(
            "raster_segment:low-right",
            (140.0, 50.0 + low_cross_delta, 230.0, 50.0 + low_cross_delta),
            partition=low_partition,
        ),
        _ordinary("raster_segment:high-right", (140.0, 59.5, 230.0, 59.5)),
    )
    rows = tuple(row for item in ordinary for row in (item,))
    records = (
        _record("wall-low-left", "raster_segment:low-left"),
        _record("wall-high-left", "raster_segment:high-left"),
        _record("wall-low-right", "raster_segment:low-right"),
        _record("wall-high-right", "raster_segment:high-right"),
    )
    return source, published, OpeningAuthority(), rows, records


def _resolve(*, low_partition: str = PARTITION, low_cross_delta: float = 0.5, extra_records=()):
    source, published, opening, rows, records = _fixture(
        low_partition=low_partition,
        low_cross_delta=low_cross_delta,
    )
    return module._producer_raster_opening_relation_overrides(
        source_producer=source,
        published=published,
        page_id="1",
        records=records + tuple(extra_records),
        resolved_visible_observations=rows,
        physical_opening_authority=opening,
    )


def test_raster_opening_proves_two_same_wall_face_relations() -> None:
    result = _resolve()
    assert result == {
        ("wall-low-left", "wall-low-right"):
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
        ("wall-high-left", "wall-high-right"):
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
    }


def test_competing_w4_owner_blocks_only_its_face_relation() -> None:
    result = _resolve(
        extra_records=(
            _record("wall-low-left-competitor", "raster_segment:low-left"),
        )
    )
    assert result == {
        ("wall-high-left", "wall-high-right"):
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
    }


def test_cross_partition_raster_segment_cannot_own_g17_face() -> None:
    result = _resolve(low_partition="other-partition")
    assert result == {
        ("wall-high-left", "wall-high-right"):
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
    }


def test_cross_render_face_tolerance_is_not_a_general_proximity_match() -> None:
    outside = module._RASTER_OPENING_TO_W4_FACE_TOLERANCE_PT + 0.05
    result = _resolve(low_cross_delta=outside)
    assert result == {
        ("wall-high-left", "wall-high-right"):
            module.PhysicalEquivalenceClass.SAME_PHYSICAL_WALL,
    }


def test_unrelated_raster_wall_ids_are_never_ranked_or_selected() -> None:
    result = _resolve(
        extra_records=(
            _record("unrelated-a", "raster_segment:unrelated-a"),
            _record("unrelated-b", "raster_segment:unrelated-b"),
        )
    )
    assert set(result) == {
        ("wall-low-left", "wall-low-right"),
        ("wall-high-left", "wall-high-right"),
    }
