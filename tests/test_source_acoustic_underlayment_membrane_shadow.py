"""
test_source_acoustic_underlayment_membrane_shadow.py

Unit tests for SourceAcousticUnderlaymentMembraneShadowAuthority.
"""

import pytest
from pb_source_acoustic_underlayment_membrane_shadow import (
    SourceAcousticUnderlaymentMembraneShadowAuthority,
    AcousticUnderlaymentType,
    AcousticUnderlaymentSpec,
    AcousticUnderlaymentExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_acoustic_underlayment_callout_parsing():
    parsed1 = SourceAcousticUnderlaymentMembraneShadowAuthority.parse_callout(
        "5mm RECYCLED RUBBER CRUMB ACOUSTIC UNDERLAYMENT W/ 100mm PERIMETER FLANKING STRIP IIC=62"
    )
    assert parsed1["underlayment_type"] == AcousticUnderlaymentType.RECYCLED_RUBBER_CRUMB
    assert parsed1["thickness_mm"] == 5.0
    assert parsed1["impact_rating_iic"] == 62
    assert parsed1["flanking_strip_required"] is True
    assert parsed1["flanking_strip_height_mm"] == 100.0

    parsed2 = SourceAcousticUnderlaymentMembraneShadowAuthority.parse_callout(
        "8mm CROSSLINKED PE FOAM MEMBRANE NO FLANKING"
    )
    assert parsed2["underlayment_type"] == AcousticUnderlaymentType.CROSSLINKED_PE_FOAM
    assert parsed2["thickness_mm"] == 8.0
    assert parsed2["flanking_strip_required"] is False

    parsed3 = SourceAcousticUnderlaymentMembraneShadowAuthority.parse_callout(
        "3mm CORK ELASTOMER COMPOSITE UNDERLAY IIC=58"
    )
    assert parsed3["underlayment_type"] == AcousticUnderlaymentType.CORK_ELASTOMER_COMPOSITE
    assert parsed3["thickness_mm"] == 3.0
    assert parsed3["impact_rating_iic"] == 58

    parsed4 = SourceAcousticUnderlaymentMembraneShadowAuthority.parse_callout(
        "RESILIENT ACOUSTIC CRADLE AND BATTEN SYSTEM 45mm"
    )
    assert parsed4["underlayment_type"] == AcousticUnderlaymentType.RESILIENT_CRADLE_BATTEN
    assert parsed4["thickness_mm"] == 45.0

    parsed5 = SourceAcousticUnderlaymentMembraneShadowAuthority.parse_callout(
        "UNCOUPLING ACOUSTIC WATERPROOF MATTING"
    )
    assert parsed5["underlayment_type"] == AcousticUnderlaymentType.UNCOUPLING_ACOUSTIC_MAT


def test_acoustic_underlayment_point_snapping():
    pt = (102.3, 204.8)
    snapped = SourceAcousticUnderlaymentMembraneShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (102.5, 205.0)


def test_acoustic_underlayment_area_and_perimeter():
    # 5m x 4m room: area = 20 m2, perimeter = 18 m
    poly = [
        (0.0, 0.0),
        (5000.0, 0.0),
        (5000.0, 4000.0),
        (0.0, 4000.0),
    ]
    area, perim = SourceAcousticUnderlaymentMembraneShadowAuthority.calculate_polygon_area_and_perimeter(
        poly, scale_ratio=0.001
    )
    assert pytest.approx(area, rel=1e-3) == 20.0
    assert pytest.approx(perim, rel=1e-3) == 18.0


def test_acoustic_underlayment_evaluation_quantities():
    raw_data = [
        {
            "region_id": "AC-01",
            "boundary_polygon": [(0.0, 0.0), (5000.0, 0.0), (5000.0, 4000.0), (0.0, 4000.0)],
            "callout": "5mm RECYCLED RUBBER CRUMB ACOUSTIC UNDERLAYMENT W/ 100mm PERIMETER FLANKING STRIP IIC=62",
            "waste_allowance_percent": 10.0,
            "level_id": "L02",
        },
        {
            "region_id": "AC-02",
            "boundary_polygon": [(5000.0, 0.0), (10000.0, 0.0), (10000.0, 4000.0), (5000.0, 4000.0)],
            "callout": "8mm CROSSLINKED PE FOAM MEMBRANE NO FLANKING",
            "waste_allowance_percent": 5.0,
            "level_id": "L02",
        },
    ]

    result = SourceAcousticUnderlaymentMembraneShadowAuthority.evaluate_underlayments(raw_data)
    assert len(result.regions) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_regions_count == 2
    # Both regions are 20 m2 -> total net = 40 m2
    assert pytest.approx(q.total_net_area_m2, rel=1e-3) == 40.0

    # AC-01 gross (10% waste): 20 * 1.1 = 22 m2
    # AC-02 gross (5% waste): 20 * 1.05 = 21 m2
    # Total gross: 43 m2
    assert pytest.approx(q.total_gross_area_m2, rel=1e-3) == 43.0

    # AC-01 has flanking strip: perim = 18 m
    # AC-02 has NO flanking: 0 m
    # Total perimeter flanking: 18 m
    assert pytest.approx(q.total_perimeter_flanking_meters, rel=1e-3) == 18.0

    assert AcousticUnderlaymentType.RECYCLED_RUBBER_CRUMB.value in q.area_by_type
    assert AcousticUnderlaymentType.CROSSLINKED_PE_FOAM.value in q.area_by_type
