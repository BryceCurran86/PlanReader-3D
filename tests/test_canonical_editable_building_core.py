"""Tests for the Canonical Editable Building Model Core.

Verifies:
1. Canonical element hierarchy: House -> Storey -> Room -> Wall/Floor/Ceiling -> Opening.
2. Topological and structural relationship preservation (recompute_relationships).
3. WallFace finish assignments and net face areas.
4. One physical wall/slab object supporting multiple trades via QuantityFormulaBinding.
5. Dynamic costing without re-extracting plans (OBJECT -> FORMULA -> RATE -> COST).
6. Evidence-based constructability issues and clash detection.
7. Serialization, deserialization, and round-trip JSON fidelity.
"""
from __future__ import annotations

import json
import pytest

from pb_canonical_building import (
    CanonicalBuilding,
    CanonicalConstructabilityIssue,
    CanonicalFloor,
    CanonicalLevel,
    CanonicalOpening,
    CanonicalProject,
    CanonicalSpace,
    CanonicalWall,
    ObjectType,
    QuantityFormulaBinding,
    ReviewState,
    Vector2D,
    WallFace,
)


def test_wall_face_net_area_and_deductions():
    """Face A and Face B preserve independent finish assignments and deductions on ONE physical wall."""
    face_a = WallFace(
        face_id="A",
        finish="Plasterboard + Low-sheen Acrylic Paint",
        substrate="Timber Stud",
        area_gross_m2=24.4,
        opening_deductions_m2=4.2,
        area_net_m2=20.2,
    )
    face_b = WallFace(
        face_id="B",
        finish="Ceramic Wall Tiles (Full Height)",
        substrate="Villaboard",
        area_gross_m2=24.4,
        opening_deductions_m2=2.1,
        area_net_m2=22.3,
    )
    wall = CanonicalWall(
        id="W-101",
        name="Bed1 / Ensuite Partition",
        start_point=Vector2D(x=0.0, y=0.0),
        end_point=Vector2D(x=10.0, y=0.0),
        height_m=2.44,
        thickness_m=0.09,
        face_a=face_a,
        face_b=face_b,
    )
    assert wall.length_m() == 10.0
    assert wall.gross_area_m2() == 24.4
    assert wall.face_a.area_net_m2 == 20.2
    assert wall.face_b.area_net_m2 == 22.3


def test_one_physical_wall_multiple_trade_quantities():
    """ONE physical wall drives multiple trades through QuantityFormulaBinding without separate geometries."""
    wall = CanonicalWall(
        id="W-102",
        name="External Boundary Wall",
        start_point=Vector2D(x=0.0, y=0.0),
        end_point=Vector2D(x=12.0, y=0.0),
        height_m=2.5,
        thickness_m=0.24,
        is_external=True,
    )
    # Add an opening
    door = CanonicalOpening(
        id="D-01",
        name="Front Entry Door",
        opening_type="DOOR",
        width_m=1.0,
        height_m=2.1,
    )
    wall.openings.append(door)

    gross = wall.gross_area_m2()  # 12.0 * 2.5 = 30.0
    net = wall.net_area_m2()      # 30.0 - (1.0 * 2.1 = 2.1) = 27.9
    assert gross == 30.0
    assert net == 27.9

    # Trades consuming ONE wall object
    wall.derived_quantities = [
        QuantityFormulaBinding(trade_category="bricklaying", item_code="BRK_EXT", quantity=net, unit="m2", user_rate=145.0),
        QuantityFormulaBinding(trade_category="plastering", item_code="PLS_INT", quantity=net, unit="m2", user_rate=38.0),
        QuantityFormulaBinding(trade_category="painting", item_code="PNT_INT", quantity=net, unit="m2", user_rate=22.0),
        QuantityFormulaBinding(trade_category="skirting", item_code="CRX_SKT", quantity=wall.length_m() - door.width_m, unit="lm", user_rate=18.5),
    ]

    for qb in wall.derived_quantities:
        qb.calculate_cost()

    cost_brick = next(q.total_cost for q in wall.derived_quantities if q.trade_category == "bricklaying")
    cost_skirt = next(q.total_cost for q in wall.derived_quantities if q.trade_category == "skirting")

    assert cost_brick == round(27.9 * 145.0, 2)
    assert cost_skirt == round(11.0 * 18.5, 2)


def test_recompute_relationships_enforces_bi_directional_linkages():
    """recompute_relationships builds House -> Storey -> Room -> Wall -> Opening linkages."""
    project = CanonicalProject(id="PRJ-01", name="Harlequin 32")
    building = CanonicalBuilding(id="BLD-01", name="Main Residence")
    level = CanonicalLevel(id="LVL-01", name="Ground Floor", level_index=0, elevation_m=0.0)

    wall1 = CanonicalWall(id="W-01", name="Wall 1", start_point=Vector2D(0, 0), end_point=Vector2D(5, 0), height_m=2.44)
    opening1 = CanonicalOpening(id="OP-01", name="Window W01", opening_type="WINDOW", width_m=1.2, height_m=1.2)
    wall1.openings.append(opening1)

    space1 = CanonicalSpace(id="SP-01", name="Living Room", bounding_wall_ids=["W-01"])

    level.walls.append(wall1)
    level.spaces.append(space1)
    building.levels.append(level)
    project.buildings.append(building)

    # Before recompute
    assert opening1.wall_id is None
    assert "SP-01" not in wall1.bounded_space_ids

    # Execute relationship recomputation
    project.recompute_relationships()

    assert opening1.wall_id == "W-01"
    assert opening1.host_wall_id == "W-01"
    assert opening1.level_id == "LVL-01"
    assert "OP-01" in wall1.children_ids
    assert "SP-01" in wall1.bounded_space_ids
    assert space1.level_id == "LVL-01"


def test_recompute_quantities_with_dynamic_rates():
    """OBJECT -> FORMULA -> RATE -> COST allows instant commercial price updates."""
    project = CanonicalProject(id="PRJ-02")
    building = CanonicalBuilding(id="BLD-02")
    level = CanonicalLevel(id="LVL-02")
    wall = CanonicalWall(id="W-02", start_point=Vector2D(0, 0), end_point=Vector2D(10, 0), height_m=2.5)
    wall.derived_quantities.append(
        QuantityFormulaBinding(trade_category="bricklaying", item_code="BRK_COMM", quantity=25.0, unit="m2")
    )
    level.walls.append(wall)
    building.levels.append(level)
    project.buildings.append(building)

    # Initial cost with empty rates
    summary1 = project.recompute_quantities({})
    assert summary1["total_cost"] == 0.0
    assert summary1["items_costed"] == 0

    # User updates trade rate map without re-running plan extraction
    rates = {"BRK_COMM": 150.0}
    summary2 = project.recompute_quantities(rates)
    assert summary2["total_cost"] == 3750.0  # 25.0 * 150.0
    assert summary2["items_costed"] == 1
    assert summary2["by_trade"]["bricklaying"] == 3750.0


def test_constructability_checks_detect_oversized_openings():
    """Detects geometric constructability issues such as opening exceeding host wall dimensions."""
    project = CanonicalProject(id="PRJ-03")
    building = CanonicalBuilding(id="BLD-03")
    level = CanonicalLevel(id="LVL-03", elevation_m=0.0)
    # 3m wall with a 4m sliding door
    wall = CanonicalWall(id="W-SHORT", start_point=Vector2D(0, 0), end_point=Vector2D(3, 0), height_m=2.4)
    door = CanonicalOpening(id="D-OVERSIZED", mark="SD01", width_m=4.0, height_m=2.1)
    wall.openings.append(door)

    level.walls.append(wall)
    building.levels.append(level)
    project.buildings.append(building)

    issues = project.check_constructability()
    assert len(issues) >= 1
    oversized = next((i for i in issues if i.category == "opening_width_exceeds_wall"), None)
    assert oversized is not None
    assert oversized.severity == "ERROR"
    assert "W-SHORT" in oversized.affected_element_ids
    assert "D-OVERSIZED" in oversized.affected_element_ids


def test_canonical_project_json_roundtrip():
    """Verifies complete serialization and deserialization fidelity for all new semantic fields."""
    project = CanonicalProject(id="PRJ-ROUNDTRIP", name="Roundtrip Test Project")
    building = CanonicalBuilding(id="BLD-RT", name="Building A")
    level = CanonicalLevel(id="LVL-RT", name="Ground Floor", elevation_m=10.5)

    wall = CanonicalWall(
        id="W-RT",
        name="Master Bedroom East Wall",
        start_point=Vector2D(1.0, 2.0),
        end_point=Vector2D(7.0, 2.0),
        height_m=2.7,
        thickness_m=0.09,
        bounded_space_ids=["SP-BED1"],
        face_a=WallFace(face_id="A", finish="Paint", area_net_m2=15.0),
        derived_quantities=[
            QuantityFormulaBinding(trade_category="carpentry", item_code="FRM-90", quantity=6.0, unit="lm", user_rate=45.0, total_cost=270.0)
        ],
        is_user_edited=True,
        revision_id="rev_002",
    )
    level.walls.append(wall)
    building.levels.append(level)
    project.buildings.append(building)
    project.constructability_issues.append(
        CanonicalConstructabilityIssue(category="test_issue", description="Sample check issue")
    )

    json_str = project.to_json()
    reconstructed = CanonicalProject.from_json(json_str)

    assert reconstructed.id == "PRJ-ROUNDTRIP"
    assert len(reconstructed.buildings) == 1
    assert len(reconstructed.buildings[0].levels) == 1
    rec_wall = reconstructed.buildings[0].levels[0].walls[0]
    assert rec_wall.id == "W-RT"
    assert rec_wall.is_user_edited is True
    assert rec_wall.revision_id == "rev_002"
    assert rec_wall.bounded_space_ids == ["SP-BED1"]
    assert rec_wall.face_a.finish == "Paint"
    assert rec_wall.face_a.area_net_m2 == 15.0
    assert len(rec_wall.derived_quantities) == 1
    assert rec_wall.derived_quantities[0].total_cost == 270.0
    assert len(reconstructed.constructability_issues) == 1
    assert reconstructed.constructability_issues[0].category == "test_issue"


def test_adapter_preserves_wall_external_and_faces():
    """planreader_to_canonical_model preserves is_external, face_a, and face_b on walls."""
    from pb_production_3d_adapter import planreader_to_canonical_model

    payload = {
        "walls": [
            {
                "wall_ref": "W-INT-01",
                "a": {"x": 0.0, "y": 0.0},
                "b": {"x": 5.0, "y": 0.0},
                "height_m": 2.7,
                "thickness_m": 0.09,
                "is_external": False,
                "face_a": {"face_id": "A", "finish": "Plasterboard", "area_net_m2": 13.5},
                "face_b": {"face_id": "B", "finish": "Tiles", "area_net_m2": 13.5},
                "openings": [
                    {
                        "id": "D-01",
                        "mark": "D01",
                        "width_m": 0.82,
                        "height_m": 2.04,
                        "offset_along_wall_m": 1.0,
                        "sill_height_m": 0.0,
                        "opening_classification": "DOOR",
                    }
                ],
            }
        ]
    }
    project, skipped = planreader_to_canonical_model(payload, is_validated_internal_workspace=True)
    assert not skipped
    walls = project.all_walls()
    assert len(walls) == 1
    wall = walls[0]
    assert wall.id == "wall_W-INT-01"
    assert wall.is_external is False
    assert wall.thickness_m == 0.09
    assert wall.face_a is not None
    assert wall.face_a.finish == "Plasterboard"
    assert wall.face_b is not None
    assert wall.face_b.finish == "Tiles"
    assert len(wall.openings) == 1
    op = wall.openings[0]
    assert op.host_wall_id == "wall_W-INT-01"
    assert op.mark == "D01"
    assert op.opening_classification == "DOOR"


def test_adapter_converts_spaces_and_links_to_bounding_walls():
    """planreader_to_canonical_model converts spaces/rooms and recompute_relationships links them to walls."""
    from pb_production_3d_adapter import planreader_to_canonical_model

    payload = {
        "walls": [
            {
                "wall_ref": "W-BOUND-1",
                "a": {"x": 0.0, "y": 0.0},
                "b": {"x": 4.0, "y": 0.0},
                "height_m": 2.7,
                "is_external": True,
            },
            {
                "wall_ref": "W-BOUND-2",
                "a": {"x": 4.0, "y": 0.0},
                "b": {"x": 4.0, "y": 3.0},
                "height_m": 2.7,
                "is_external": False,
            },
        ],
        "spaces": [
            {
                "id": "SP-BED1",
                "name": "Bedroom 1",
                "area_m2": 12.0,
                "bounding_wall_ids": ["wall_W-BOUND-1", "wall_W-BOUND-2"],
                "polygon": [{"x": 0, "y": 0}, {"x": 4, "y": 0}, {"x": 4, "y": 3}, {"x": 0, "y": 3}],
            }
        ],
    }
    project, skipped = planreader_to_canonical_model(payload, is_validated_internal_workspace=True)
    project.recompute_relationships()

    spaces = project.all_spaces()
    assert len(spaces) == 1
    sp = spaces[0]
    assert sp.id == "SP-BED1"
    assert sp.name == "Bedroom 1"
    assert sp.specified_floor_area_m2 == 12.0
    assert len(sp.bounding_wall_ids) == 2

    walls = {w.id: w for w in project.all_walls()}
    assert "SP-BED1" in walls["wall_W-BOUND-1"].bounded_space_ids
    assert "SP-BED1" in walls["wall_W-BOUND-2"].bounded_space_ids


def test_collect_workspace_evidence_captures_auto_geometry_partitions_and_finishes():
    """collect_workspace_3d_evidence ingests partition and finish observations from auto_geometry_v1219."""
    from pb_production_3d_adapter import collect_workspace_3d_evidence
    import json

    class MockApp:
        def lquery(self, sql, params=()):
            return []

        def workspace_setting(self, wid, key, default=None):
            if key == "auto_geometry_v1219":
                return json.dumps({
                    "version": "1.2.19",
                    "partitions": [
                        {"page_id": 1, "page_label": "A101", "total_length_m": 14.5, "wall_thickness_m": 0.09, "reason": "3 partition segments found"}
                    ],
                    "finishes": [
                        {"record_id": "fin_01", "trade_scope_id": "internal_paint", "finish_material": "Low sheen acrylic", "quantity_m2": 45.2, "physical_wall_ids": ["W1", "W2"]}
                    ],
                })
            return default

    snapshot = collect_workspace_3d_evidence(MockApp(), 42)
    obs_kinds = {obs["kind"] for obs in snapshot.get("evidence_observations", [])}
    assert "internal_partition_evidence" in obs_kinds
    assert "bound_wall_finish_evidence" in obs_kinds

