"""Comprehensive unit and regression tests for pb_source_figured_dimension_wall_witness_shadow (Item 18)."""
from __future__ import annotations

import pytest
from shapely import wkb

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_figured_dimension_wall_witness_shadow import (
    AMBIGUOUS_WALL_WITNESS_BINDING,
    DEGENERATE_DIMENSION_GEOMETRY,
    DIMENSION_FIGURE_MISMATCH,
    FIGURED_DIMENSION_RECORD_UNAVAILABLE,
    FIGURED_WALL_WITNESS_CHAIN_RESOLVED,
    SOURCE_FIGURED_DIMENSION_WITNESS_SCHEMA_VERSION,
    WITNESS_LINE_DISCONTINUOUS_OR_MISSING,
    WITNESS_WALL_CONTACT_UNRESOLVED,
    SourceFiguredDimensionWitnessAuthority,
    SourceFiguredDimensionWitnessProducer,
    SourceFiguredDimensionWitnessRecord,
    SourceFiguredDimensionWitnessResult,
    SourceFiguredDimensionWitnessSelector,
)

DOC = "doc-lot16"
REV = "rev-001"
SHA = "f" * 64
SNAP = "snap-001"
PAGE = "11"
SCOPE = f"wall-source:page-{PAGE}"
DIM_OBS = "dim-obs-3570"


def _make_selector(obs_id: str = DIM_OBS) -> SourceFiguredDimensionWitnessSelector:
    return SourceFiguredDimensionWitnessSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id=SCOPE,
        dimension_observation_id=obs_id,
    )


def test_positive_figured_dimension_witness_chain() -> None:
    selector = _make_selector()
    producer = SourceFiguredDimensionWitnessProducer.create()

    # Dimension line: horizontal along y = 150, from x = 100 to x = 457 (length 357 pt)
    dim_line = {"id": "dim-line-1", "p1": (100.0, 150.0), "p2": (457.0, 150.0)}

    # Two perpendicular vertical witness lines extending upward from y = 150 to y = 180 (wall face)
    wit1 = {"id": "wit-1", "p1": (100.0, 150.0), "p2": (100.0, 180.0)}
    wit2 = {"id": "wit-2", "p1": (457.0, 150.0), "p2": (457.0, 180.0)}

    # Wall 1 at x = 100: vertical wall from y = 100 to y = 300
    # Wall 2 at x = 457: vertical wall from y = 100 to y = 300
    wall1 = {"id": "wall-left", "p1": (100.0, 100.0), "p2": (100.0, 300.0)}
    wall2 = {"id": "wall-right", "p1": (457.0, 100.0), "p2": (457.0, 300.0)}

    res = producer.evaluate_and_publish(
        selector,
        figured_text="3570",
        figured_dimension_m=3.570,
        dimension_line=dim_line,
        witness_strokes=[wit1, wit2],
        candidate_walls=[wall1, wall2],
        scale_px_per_m=100.0,  # 357 pt / 100 = 3.57 m
    )

    assert res.status == EvidenceResolutionStatus.CANDIDATE
    assert FIGURED_WALL_WITNESS_CHAIN_RESOLVED in res.reason_codes
    assert res.record is not None

    rec = res.record
    assert rec.figured_text == "3570"
    assert rec.dimension_m == 3.570
    assert rec.scaled_length_m == 3.570
    assert rec.witnessed_wall_1_id == "wall-left"
    assert rec.witnessed_wall_2_id == "wall-right"
    assert rec.commercial_projection_allowed is False
    assert rec.takeoff_eligible is False

    # WKB MultiLineString validation
    geom = wkb.loads(bytes.fromhex(rec.witness_chain_wkb_hex))
    assert geom.geom_type == "MultiLineString"
    assert len(geom.geoms) == 3


def test_dimension_figure_mismatch_rejected() -> None:
    selector = _make_selector()
    producer = SourceFiguredDimensionWitnessProducer.create()

    # Dimension line length is 357 pt (3.57 m at scale 100 pt/m), but figured text says 5.00 m
    dim_line = {"id": "dim-line-1", "p1": (100.0, 150.0), "p2": (457.0, 150.0)}
    wit1 = {"id": "wit-1", "p1": (100.0, 150.0), "p2": (100.0, 180.0)}
    wit2 = {"id": "wit-2", "p1": (457.0, 150.0), "p2": (457.0, 180.0)}
    wall1 = {"id": "wall-left", "p1": (100.0, 100.0), "p2": (100.0, 300.0)}
    wall2 = {"id": "wall-right", "p1": (457.0, 100.0), "p2": (457.0, 300.0)}

    res = producer.evaluate_and_publish(
        selector,
        figured_text="5000",
        figured_dimension_m=5.000,
        dimension_line=dim_line,
        witness_strokes=[wit1, wit2],
        candidate_walls=[wall1, wall2],
        scale_px_per_m=100.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert DIMENSION_FIGURE_MISMATCH in res.reason_codes
    assert res.record is None


def test_missing_or_discontinuous_witness_rejected() -> None:
    selector = _make_selector()
    producer = SourceFiguredDimensionWitnessProducer.create()

    dim_line = {"id": "dim-line-1", "p1": (100.0, 150.0), "p2": (457.0, 150.0)}
    # wit1 is displaced by 10 pt from dim endpoint (gap > 2.5 pt)
    wit1_displaced = {"id": "wit-1", "p1": (110.0, 150.0), "p2": (110.0, 180.0)}
    wit2 = {"id": "wit-2", "p1": (457.0, 150.0), "p2": (457.0, 180.0)}
    wall1 = {"id": "wall-left", "p1": (100.0, 100.0), "p2": (100.0, 300.0)}
    wall2 = {"id": "wall-right", "p1": (457.0, 100.0), "p2": (457.0, 300.0)}

    res = producer.evaluate_and_publish(
        selector,
        figured_text="3570",
        figured_dimension_m=3.570,
        dimension_line=dim_line,
        witness_strokes=[wit1_displaced, wit2],
        candidate_walls=[wall1, wall2],
        scale_px_per_m=100.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert WITNESS_LINE_DISCONTINUOUS_OR_MISSING in res.reason_codes
    assert res.record is None


def test_witness_wall_contact_unresolved_rejected() -> None:
    selector = _make_selector()
    producer = SourceFiguredDimensionWitnessProducer.create()

    dim_line = {"id": "dim-line-1", "p1": (100.0, 150.0), "p2": (457.0, 150.0)}
    wit1 = {"id": "wit-1", "p1": (100.0, 150.0), "p2": (100.0, 180.0)}
    wit2 = {"id": "wit-2", "p1": (457.0, 150.0), "p2": (457.0, 180.0)}
    wall1 = {"id": "wall-left", "p1": (100.0, 100.0), "p2": (100.0, 300.0)}
    # Wall 2 is far away (at x = 600, so wit2 terminal at x = 457 touches no wall)
    wall2_far = {"id": "wall-far", "p1": (600.0, 100.0), "p2": (600.0, 300.0)}

    res = producer.evaluate_and_publish(
        selector,
        figured_text="3570",
        figured_dimension_m=3.570,
        dimension_line=dim_line,
        witness_strokes=[wit1, wit2],
        candidate_walls=[wall1, wall2_far],
        scale_px_per_m=100.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert WITNESS_WALL_CONTACT_UNRESOLVED in res.reason_codes
    assert res.record is None


def test_ambiguous_wall_witness_binding_rejected() -> None:
    selector = _make_selector()
    producer = SourceFiguredDimensionWitnessProducer.create()

    # Dimension line where both witnesses connect to the SAME single wall
    dim_line = {"id": "dim-line-1", "p1": (100.0, 150.0), "p2": (200.0, 150.0)}
    wit1 = {"id": "wit-1", "p1": (100.0, 150.0), "p2": (100.0, 160.0)}
    wit2 = {"id": "wit-2", "p1": (200.0, 150.0), "p2": (200.0, 160.0)}
    # Horizontal wall at y = 160 spanning both witnesses
    wall_same = {"id": "wall-same", "p1": (50.0, 160.0), "p2": (250.0, 160.0)}

    res = producer.evaluate_and_publish(
        selector,
        figured_text="1000",
        figured_dimension_m=1.000,
        dimension_line=dim_line,
        witness_strokes=[wit1, wit2],
        candidate_walls=[wall_same],
        scale_px_per_m=100.0,
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert AMBIGUOUS_WALL_WITNESS_BINDING in res.reason_codes
    assert res.record is None


def test_degenerate_dimension_geometry_rejected() -> None:
    selector = _make_selector()
    producer = SourceFiguredDimensionWitnessProducer.create()

    # 0-length dimension line
    dim_line = {"id": "dim-0", "p1": (100.0, 150.0), "p2": (100.0, 150.0)}
    res = producer.evaluate_and_publish(
        selector,
        figured_text="0",
        figured_dimension_m=0.0,
        dimension_line=dim_line,
        witness_strokes=[],
        candidate_walls=[],
    )

    assert res.status == EvidenceResolutionStatus.ABSTAINED
    assert DEGENERATE_DIMENSION_GEOMETRY in res.reason_codes


def test_authority_lookup_and_unknown_selector() -> None:
    selector = _make_selector("dim-known")
    producer = SourceFiguredDimensionWitnessProducer.create()

    dim_line = {"id": "dim-1", "p1": (100.0, 150.0), "p2": (457.0, 150.0)}
    wit1 = {"id": "w1", "p1": (100.0, 150.0), "p2": (100.0, 180.0)}
    wit2 = {"id": "w2", "p1": (457.0, 150.0), "p2": (457.0, 180.0)}
    wall1 = {"id": "wall-1", "p1": (100.0, 100.0), "p2": (100.0, 300.0)}
    wall2 = {"id": "wall-2", "p1": (457.0, 100.0), "p2": (457.0, 300.0)}

    producer.evaluate_and_publish(
        selector,
        figured_text="3570",
        figured_dimension_m=3.570,
        dimension_line=dim_line,
        witness_strokes=[wit1, wit2],
        candidate_walls=[wall1, wall2],
        scale_px_per_m=100.0,
    )

    auth = producer.authority()
    assert type(auth) is SourceFiguredDimensionWitnessAuthority

    res_known = auth.resolve(selector)
    assert res_known.status == EvidenceResolutionStatus.CANDIDATE
    assert res_known.record is not None

    unknown_sel = _make_selector("dim-unknown")
    res_unknown = auth.resolve(unknown_sel)
    assert res_unknown.status == EvidenceResolutionStatus.ABSTAINED
    assert FIGURED_DIMENSION_RECORD_UNAVAILABLE in res_unknown.reason_codes


def test_sealed_record_and_authority_forbids_direct_construction() -> None:
    with pytest.raises(TypeError, match="producer-owned"):
        SourceFiguredDimensionWitnessRecord(
            record_id="r1",
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            page_id=PAGE,
            decision_scope_id=SCOPE,
            dimension_observation_id="dim-1",
            figured_text="3570",
            dimension_m=3.570,
            scaled_length_m=3.570,
            dimension_line_pts=((100.0, 150.0), (457.0, 150.0)),
            witness_1_pts=((100.0, 150.0), (100.0, 180.0)),
            witness_2_pts=((457.0, 150.0), (457.0, 180.0)),
            witnessed_wall_1_id="w1",
            witnessed_wall_2_id="w2",
            witness_chain_wkb_hex="01",
            corroborating_evidence_ids=(),
        )

    with pytest.raises(TypeError, match="producer-owned"):
        SourceFiguredDimensionWitnessAuthority({})

    with pytest.raises(TypeError, match="create()"):
        SourceFiguredDimensionWitnessProducer()
