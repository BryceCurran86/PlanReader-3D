"""
test_source_raf_airflow_grille_grommet_shadow.py

Unit tests for SourceRAFAirflowGrilleGrommetShadowAuthority.
"""

import pytest
from pb_source_raf_airflow_grille_grommet_shadow import (
    SourceRAFAirflowGrilleGrommetShadowAuthority,
    RAFAppurtenanceType,
    DamperControlMechanism,
    RAFAppurtenanceSpec,
    RAFAppurtenanceExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_raf_appurtenance_callout_parsing():
    parsed1 = SourceRAFAirflowGrilleGrommetShadowAuthority.parse_callout(
        "600x600 56% OPEN PERFORATED AIRFLOW PANEL W/ OPPOSING BLADE DAMPER 1200 CFM"
    )
    assert parsed1["appurtenance_type"] == RAFAppurtenanceType.INTEGRATED_DAMPER_PANEL
    assert parsed1["open_area_percent"] == 56.0
    assert parsed1["airflow_capacity_cfm"] == 1200.0
    assert parsed1["damper_mechanism"] == DamperControlMechanism.OPPOSING_BLADE_DAMPER
    assert parsed1["panel_width_mm"] == 600.0
    assert parsed1["panel_length_mm"] == 600.0

    parsed2 = SourceRAFAirflowGrilleGrommetShadowAuthority.parse_callout(
        "68% DIRECTIONAL HIGH CFM AIRFLOW GRILLE 1500 CFM"
    )
    assert parsed2["appurtenance_type"] == RAFAppurtenanceType.HIGH_CFM_DIRECTIONAL_GRILLE
    assert parsed2["open_area_percent"] == 68.0
    assert parsed2["airflow_capacity_cfm"] == 1500.0

    parsed3 = SourceRAFAirflowGrilleGrommetShadowAuthority.parse_callout(
        "200mm DIA SPLIT BRUSH CABLE GROMMET"
    )
    assert parsed3["appurtenance_type"] == RAFAppurtenanceType.BRUSH_SEAL_CABLE_GROMMET
    assert parsed3["open_area_percent"] == 0.0

    parsed4 = SourceRAFAirflowGrilleGrommetShadowAuthority.parse_callout(
        "INTEGRAL 4-GANG POWER/DATA FLOOR BOX"
    )
    assert parsed4["appurtenance_type"] == RAFAppurtenanceType.INTEGRAL_FLOOR_BOX


def test_raf_appurtenance_point_snapping():
    pt = (602.4, 1203.8)
    snapped = SourceRAFAirflowGrilleGrommetShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (602.5, 1205.0)


def test_raf_appurtenance_evaluation_quantities():
    raw_data = [
        {
            "item_id": "RAF-01",
            "location_point": (600.0, 600.0),
            "callout": "600x600 56% OPEN PERFORATED AIRFLOW PANEL W/ OPPOSING BLADE DAMPER 1200 CFM",
            "level_id": "L01",
            "room_id": "SERVER-01",
        },
        {
            "item_id": "RAF-02",
            "location_point": (600.0, 1200.0),
            "callout": "68% DIRECTIONAL HIGH CFM AIRFLOW GRILLE 1500 CFM",
            "level_id": "L01",
            "room_id": "SERVER-01",
        },
        {
            "item_id": "RAF-03",
            "location_point": (1200.0, 600.0),
            "callout": "200mm DIA SPLIT BRUSH CABLE GROMMET",
            "level_id": "L01",
            "room_id": "SERVER-01",
        },
    ]

    result = SourceRAFAirflowGrilleGrommetShadowAuthority.evaluate_appurtenances(raw_data)
    assert len(result.items) == 3
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_items_count == 3
    assert q.total_airflow_panels_count == 2
    # 1200 + 1500 = 2700 CFM
    assert q.total_airflow_capacity_cfm == 2700.0
    assert q.total_cable_grommets_count == 1
    assert q.total_floor_boxes_count == 0

    assert q.count_by_type[RAFAppurtenanceType.INTEGRATED_DAMPER_PANEL.value] == 1
    assert q.count_by_type[RAFAppurtenanceType.HIGH_CFM_DIRECTIONAL_GRILLE.value] == 1
    assert q.count_by_type[RAFAppurtenanceType.BRUSH_SEAL_CABLE_GROMMET.value] == 1

    assert q.count_by_damper[DamperControlMechanism.OPPOSING_BLADE_DAMPER.value] == 1
    assert q.count_by_damper[DamperControlMechanism.NO_DAMPER.value] == 2
