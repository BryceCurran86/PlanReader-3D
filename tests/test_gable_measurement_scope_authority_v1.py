"""Mutation tests for pb_gable_measurement_scope_authority.

No KSTVET (or any other benchmark project) expected quantity appears
anywhere in this file -- all fixtures are synthetic.
"""
from __future__ import annotations

import pytest

from pb_gable_polygon_geometry import GablePolygon
from pb_gable_measurement_scope_authority import (
    GableMeasurementScopeStatus,
    LowerDatumEvidence,
    resolve_gable_measurement_scope,
)

TRIANGLE = GablePolygon(
    vertices=((0.0, 100.0), (50.0, 50.0), (100.0, 100.0)),
    source_segment_ids=("left", "right"),
    status="resolved",
)


def _resolve(**overrides):
    kwargs = dict(
        wall_identity="wall-1",
        elevation_identity="E-TEST",
        document_id="doc-1",
        revision_id="rev-1",
        page_id="1",
        roofline_polygon=TRIANGLE,
        boq_item_is_residual_of=None,
        boq_item_wording="",
        distinguishing_intermediate_feature_found=False,
        candidate_lower_datums=(),
    )
    kwargs.update(overrides)
    return resolve_gable_measurement_scope(**kwargs)


def test_gable_measured_strictly_above_eaves():
    result = _resolve(
        boq_item_is_residual_of="BASE-WALL-A",
        boq_item_wording="Ditto gable walling.",
        distinguishing_intermediate_feature_found=False,
    )
    assert result.status == GableMeasurementScopeStatus.ABOVE_EAVES.value
    assert result.completeness == "complete"
    assert result.scope_polygon.vertices == TRIANGLE.vertices


def test_gable_measured_above_wall_plate_with_geometry():
    # Eaves sit at y=100 (base of TRIANGLE), ridge at y=50 (smaller y is
    # "higher" in this fixture's own coordinate convention). A wall-plate
    # datum genuinely BELOW the eaves therefore has a LARGER y (110).
    plate = (
        LowerDatumEvidence(
            datum_kind=GableMeasurementScopeStatus.ABOVE_WALL_PLATE.value,
            accepted=True,
            reason="drawn wall-plate line below the roofline's own eaves intersection",
            lower_boundary_vertices=((0.0, 110.0), (100.0, 110.0)),
        ),
    )
    result = _resolve(candidate_lower_datums=plate)
    assert result.status == GableMeasurementScopeStatus.ABOVE_WALL_PLATE.value
    assert result.completeness == "complete"
    assert result.scope_polygon is not None
    # Larger than the bare roofline triangle since the lower boundary sits
    # below the eaves (a deeper region than the bare roofline-above-eaves
    # triangle).
    assert result.scope_polygon.area_pt2() >= TRIANGLE.area_pt2()


def test_gable_measured_above_independently_evidenced_structural_beam():
    beam = (
        LowerDatumEvidence(
            datum_kind=GableMeasurementScopeStatus.ABOVE_STRUCTURAL_BEAM.value,
            accepted=True,
            reason="ring beam soffit line independently dimensioned on structural detail",
            lower_boundary_vertices=((0.0, 95.0), (100.0, 95.0)),
        ),
    )
    result = _resolve(candidate_lower_datums=beam)
    assert result.status == GableMeasurementScopeStatus.ABOVE_STRUCTURAL_BEAM.value
    assert result.completeness == "complete"


def test_sloping_lower_datum():
    sloped = (
        LowerDatumEvidence(
            datum_kind=GableMeasurementScopeStatus.EXPLICIT_POLYGON.value,
            accepted=True,
            reason="sloping ring beam soffit independently measured",
            lower_boundary_vertices=((0.0, 92.0), (100.0, 88.0)),
        ),
    )
    result = _resolve(candidate_lower_datums=sloped)
    assert result.status == GableMeasurementScopeStatus.EXPLICIT_POLYGON.value
    assert result.scope_polygon.vertices[-2:] == ((100.0, 88.0), (0.0, 92.0))


def test_stepped_lower_boundary():
    stepped = (
        LowerDatumEvidence(
            datum_kind=GableMeasurementScopeStatus.EXPLICIT_POLYGON.value,
            accepted=True,
            reason="stepped beam soffit independently measured",
            lower_boundary_vertices=((0.0, 95.0), (40.0, 95.0), (40.0, 90.0), (100.0, 90.0)),
        ),
    )
    result = _resolve(candidate_lower_datums=stepped)
    assert result.status == GableMeasurementScopeStatus.EXPLICIT_POLYGON.value
    assert len(result.scope_polygon.vertices) == 3 + 4


def test_conflicting_datum_evidence_unresolved():
    conflicting = (
        LowerDatumEvidence(
            datum_kind=GableMeasurementScopeStatus.ABOVE_WALL_PLATE.value,
            accepted=True,
            reason="drawn wall plate",
            lower_boundary_vertices=((0.0, 90.0), (100.0, 90.0)),
        ),
        LowerDatumEvidence(
            datum_kind=GableMeasurementScopeStatus.ABOVE_STRUCTURAL_BEAM.value,
            accepted=True,
            reason="also-plausible ring beam soffit at a different level",
            lower_boundary_vertices=((0.0, 95.0), (100.0, 95.0)),
        ),
    )
    result = _resolve(candidate_lower_datums=conflicting)
    assert result.status == GableMeasurementScopeStatus.UNRESOLVED.value
    assert result.scope_polygon is None


def test_missing_datum_no_residual_wording_unresolved():
    """No accepted non-default datum, and the BOQ item is NOT worded as a
    residual of any base walling item -- ABOVE_EAVES must not be assumed
    as a silent fallback."""
    result = _resolve(boq_item_is_residual_of=None)
    assert result.status == GableMeasurementScopeStatus.UNRESOLVED.value
    assert result.scope_polygon is None


def test_distinguishing_feature_blocks_default_eaves_assumption():
    """Even with residual BOQ wording, a genuinely distinguishing
    intermediate feature (band/beam/parapet/ceiling drawn between eaves
    and roofline) must block the default ABOVE_EAVES resolution -- it
    signals a datum question that needs its own evidenced answer, not
    silently the bare roofline."""
    result = _resolve(
        boq_item_is_residual_of="BASE-WALL-A",
        distinguishing_intermediate_feature_found=True,
    )
    assert result.status == GableMeasurementScopeStatus.UNRESOLVED.value


def test_different_elevations_independent_scopes():
    """Two different elevation identities each resolve their own scope --
    no cross-contamination of datum evidence between them."""
    result_a = _resolve(elevation_identity="E-03", wall_identity="wall-A",
                         boq_item_is_residual_of="BASE-WALL-A")
    result_b = _resolve(elevation_identity="E-05", wall_identity="wall-D",
                         boq_item_is_residual_of="BASE-WALL-A",
                         distinguishing_intermediate_feature_found=True)
    assert result_a.status == GableMeasurementScopeStatus.ABOVE_EAVES.value
    assert result_b.status == GableMeasurementScopeStatus.UNRESOLVED.value
    assert result_a.elevation_identity != result_b.elevation_identity


def test_duplicated_elevation_same_inputs_same_result():
    result_1 = _resolve(boq_item_is_residual_of="BASE-WALL-A")
    result_2 = _resolve(boq_item_is_residual_of="BASE-WALL-A")
    assert result_1.status == result_2.status
    assert result_1.scope_polygon.vertices == result_2.scope_polygon.vertices


def test_section_contradicts_elevation_conflict_unresolved():
    """A candidate accepted from a section view directly conflicts with
    one accepted from the elevation view -- must not silently prefer
    either."""
    from_elevation = LowerDatumEvidence(
        datum_kind=GableMeasurementScopeStatus.ABOVE_WALL_PLATE.value,
        accepted=True,
        reason="elevation shows wall plate line",
        lower_boundary_vertices=((0.0, 90.0), (100.0, 90.0)),
    )
    from_section = LowerDatumEvidence(
        datum_kind=GableMeasurementScopeStatus.ABOVE_CEILING_DATUM.value,
        accepted=True,
        reason="section shows a lower ceiling line",
        lower_boundary_vertices=((0.0, 96.0), (100.0, 96.0)),
    )
    result = _resolve(candidate_lower_datums=(from_elevation, from_section))
    assert result.status == GableMeasurementScopeStatus.UNRESOLVED.value


def test_beam_below_roofline_excluded_when_not_proven_part_of_scope():
    """A rejected candidate datum (present but not accepted -- e.g. a beam
    that is structurally below the wall but not proven to bound THIS
    commercial item) must not silently expand the scope."""
    rejected_beam = LowerDatumEvidence(
        datum_kind=GableMeasurementScopeStatus.ABOVE_STRUCTURAL_BEAM.value,
        accepted=False,
        reason="beam depth is underdetermined (volume+formwork without an "
                "independently known width) -- cannot uniquely fix a datum",
    )
    result = _resolve(
        boq_item_is_residual_of="BASE-WALL-A",
        candidate_lower_datums=(rejected_beam,),
    )
    assert result.status == GableMeasurementScopeStatus.ABOVE_EAVES.value
    assert result.scope_polygon.vertices == TRIANGLE.vertices
    assert any(not e.accepted for e in result.datum_evidence)


def test_beam_included_only_when_measurement_contract_proves_inclusion():
    proven_beam = LowerDatumEvidence(
        datum_kind=GableMeasurementScopeStatus.ABOVE_STRUCTURAL_BEAM.value,
        accepted=True,
        reason="beam cross-section uniquely determined from a structural detail",
        lower_boundary_vertices=((0.0, 93.0), (100.0, 93.0)),
    )
    result = _resolve(candidate_lower_datums=(proven_beam,))
    assert result.status == GableMeasurementScopeStatus.ABOVE_STRUCTURAL_BEAM.value
    assert result.scope_polygon is not None


def test_translation_invariance():
    dx, dy = 1000.0, -400.0
    translated_triangle = GablePolygon(
        vertices=tuple((x + dx, y + dy) for x, y in TRIANGLE.vertices),
        source_segment_ids=TRIANGLE.source_segment_ids,
        status="resolved",
    )
    result_a = _resolve(boq_item_is_residual_of="BASE-WALL-A")
    result_b = _resolve(boq_item_is_residual_of="BASE-WALL-A", roofline_polygon=translated_triangle)
    assert result_a.scope_polygon.area_pt2() == pytest.approx(result_b.scope_polygon.area_pt2())


def test_scale_invariance():
    k = 3.0
    scaled_triangle = GablePolygon(
        vertices=tuple((x * k, y * k) for x, y in TRIANGLE.vertices),
        source_segment_ids=TRIANGLE.source_segment_ids,
        status="resolved",
    )
    result_a = _resolve(boq_item_is_residual_of="BASE-WALL-A")
    result_b = _resolve(boq_item_is_residual_of="BASE-WALL-A", roofline_polygon=scaled_triangle)
    assert result_b.scope_polygon.area_pt2() == pytest.approx(result_a.scope_polygon.area_pt2() * (k ** 2))


def test_reordered_source_primitives_same_result():
    reordered_triangle = GablePolygon(
        vertices=TRIANGLE.vertices,
        source_segment_ids=tuple(reversed(TRIANGLE.source_segment_ids)),
        status="resolved",
    )
    result_a = _resolve(boq_item_is_residual_of="BASE-WALL-A")
    result_b = _resolve(boq_item_is_residual_of="BASE-WALL-A", roofline_polygon=reordered_triangle)
    assert result_a.scope_polygon.vertices == result_b.scope_polygon.vertices
