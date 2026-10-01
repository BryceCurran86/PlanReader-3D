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


def test_canonical_opening_enrichment_and_provenance():
    """CanonicalOpening preserves stable physical opening identity, host wall, schedule mark, dimensions, and derived trade quantities."""
    from pb_production_3d_adapter import planreader_to_canonical_model

    payload = {
        "workspace_id": 99,
        "registered_walls": [
            {
                "wall_ref": "W_EXT_NORTH",
                "a": {"x": 0.0, "y": 0.0},
                "b": {"x": 10.0, "y": 0.0},
                "height_m": 2.7,
                "thickness_m": 0.24,
                "is_external": True,
                "level": {"id": "lvl_ground", "name": "Ground Floor", "level_index": 0},
                "openings": [
                    {
                        "opening_instance_id": "op_inst_W01_gnd",
                        "type_mark": "W01",
                        "opening_type": "WINDOW",
                        "opening_classification": "WINDOW",
                        "width_m": 1.8,
                        "height_m": 1.2,
                        "sill_height_m": 0.9,
                        "station_m": 2.5,
                        "schedule_ref": "SCHED_PAGE_04",
                        "detail_record_id": "DET_REC_W01",
                        "detail_semantic_identity_id": "SEM_ID_W01_ALUM",
                        "dimension_basis": "schedule_callout",
                        "dimension_source": "window_schedule_table",
                        "dimension_confidence": "high",
                        "plan_geometry_signature": "SIG_W01_GROUND_N",
                        "wall_ref": "W_EXT_NORTH",
                    },
                    {
                        "opening_instance_id": "op_inst_D01_gnd",
                        "type_mark": "D01",
                        "opening_type": "DOOR",
                        "opening_classification": "DOOR",
                        "width_m": 0.92,
                        "height_m": 2.1,
                        "sill_height_m": 0.0,
                        "offset_along_wall_m": 6.0,
                        "schedule_ref": "SCHED_PAGE_04",
                        "wall_ref": "W_EXT_NORTH",
                    },
                ],
            }
        ]
    }

    project, skipped = planreader_to_canonical_model(payload, is_validated_internal_workspace=True)
    project.recompute_relationships()

    walls = project.all_walls()
    assert len(walls) == 1
    wall = walls[0]

    openings = project.all_openings()
    assert len(openings) == 2

    # Verify bidirectional topological linkage
    assert wall.children_ids == ["op_inst_W01_gnd", "op_inst_D01_gnd"]

    w01 = next(op for op in openings if op.id == "op_inst_W01_gnd")
    assert w01.name == "W01"
    assert w01.mark == "W01"
    assert w01.opening_type == ObjectType.WINDOW
    assert w01.opening_classification == "WINDOW"
    assert w01.width_m == 1.8
    assert w01.height_m == 1.2
    assert w01.sill_height_m == 0.9
    assert w01.metadata["head_height_m"] == 2.1  # 0.9 + 1.2
    assert w01.offset_along_wall_m == 2.5
    assert w01.host_wall_id == wall.id
    assert w01.wall_id == wall.id
    assert w01.parent_id == wall.id

    # Verify schedule / detail provenance
    assert w01.metadata["schedule_ref"] == "SCHED_PAGE_04"
    assert w01.metadata["detail_record_id"] == "DET_REC_W01"
    assert w01.metadata["detail_semantic_identity_id"] == "SEM_ID_W01_ALUM"
    assert w01.metadata["dimension_basis"] == "schedule_callout"
    assert w01.metadata["dimension_source"] == "window_schedule_table"
    assert w01.metadata["dimension_confidence"] == "high"
    assert w01.metadata["plan_geometry_signature"] == "SIG_W01_GROUND_N"

    # Verify derived trade quantity binding (Windows No. 1.0)
    assert len(w01.derived_quantities) == 1
    binding = w01.derived_quantities[0]
    assert binding.trade_category == "windows"
    assert binding.item_code == "OPENING_W01"
    assert binding.quantity == 1.0
    assert binding.unit == "No."

    # Test dynamic costing via user rates without re-extracting geometry
    costs = project.recompute_quantities({"OPENING_W01": 650.0, "OPENING_D01": 1200.0})
    assert costs["items_costed"] == 2
    assert costs["total_cost"] == 1850.0
    assert costs["by_trade"]["windows"] == 650.0
    assert costs["by_trade"]["doors"] == 1200.0


def test_consolidated_opening_detail_definitions_across_sheets_no_double_deduction():
    """Opening detail bridge consolidates multi-sheet observations into physical opening instances with exact 1x area deduction."""
    from pb_opening_detail_definition_authority import OpeningDetailDefinitionRecord
    from pb_opening_detail_definition_bridge import (
        consolidate_opening_identities,
        enrich_openings_with_detail_definitions,
        apply_opening_deductions_to_walls,
    )

    # Observations of the same opening "W01" across plan, elevation, schedule, and detail sheets
    raw_observations = [
        {
            "opening_id": "op_W01_plan",
            "type_mark": "W01",
            "host_wall_id": "W-101",
            "width_m": 1.8,
            "height_m": 1.2,
            "plan_page_id": "P_02",
        },
        {
            "opening_id": "op_W01_plan",
            "type_mark": "W01",
            "host_wall_id": "W-101",
            "elevation_page_id": "P_05",
        },
        {
            "opening_id": "op_W01_plan",
            "type_mark": "W01",
            "host_wall_id": "W-101",
            "schedule_page_id": "P_08",
        },
    ]

    consolidated = consolidate_opening_identities(raw_observations)
    assert len(consolidated) == 1
    cop = consolidated[0]
    assert cop.opening_id == "op_W01_plan"
    assert cop.type_mark == "W01"
    assert cop.host_wall_id == "W-101"
    assert cop.width_m == 1.8
    assert cop.height_m == 1.2
    assert cop.area_m2 == 2.16
    assert cop.plan_page_id == "P_02"
    assert cop.elevation_page_id == "P_05"
    assert cop.schedule_page_id == "P_08"

    # Detail definition record
    import pb_opening_detail_definition_authority as openmod
    from pb_migration_contracts import EvidenceResolutionStatus
    detail_rec = OpeningDetailDefinitionRecord(
        record_id="det_W01",
        semantic_identity_id="SEM_W01",
        document_id="doc1",
        revision_id="rev1",
        source_sha256="a" * 64,
        snapshot_id="snap1",
        page_id="P_09",
        source_partition_id="part1",
        sequence_start=10,
        sequence_end=20,
        source_bbox=(100.0, 200.0, 300.0, 400.0),
        family="window",
        subtype="awning",
        material="aluminium",
        width_mm=1800,
        height_mm=1200,
        dimension_basis="detail_unspecified",
        source_observation_ids=("obs-1",),
        required_observation_ids=("obs-1",),
        word_evidence=(),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(openmod.OPENING_DETAIL_DEFINITION_RESOLVED,),
        _seal=openmod._RECORD_SEAL,
    )

    enriched = enrich_openings_with_detail_definitions(consolidated, [detail_rec], mark_to_semantic_identity={"W01": "SEM_W01"})
    assert len(enriched) == 1
    eop = enriched[0]
    assert eop.family == "window"
    assert eop.subtype == "awning"
    assert eop.material == "aluminium"
    assert eop.detail_record_id == "det_W01"

    # Apply deductions to host wall: 10m length * 2.7m height = 27.0 m2 gross
    # Opening area = 1.8 * 1.2 = 2.16 m2. Net = 24.84 m2. Deducted exactly ONCE.
    walls = [{"wall_ref": "W-101", "gross_m2": 27.0, "net_m2": 27.0}]
    updated_walls = apply_opening_deductions_to_walls(walls, enriched)
    assert len(updated_walls) == 1
    w = updated_walls[0]
    assert w["opening_deduction_m2"] == 2.16
    assert w["net_m2"] == 24.84
    assert w["consolidated_opening_ids"] == ["op_W01_plan"]


def test_end_to_end_customer_upload_parity_with_canonical_model():
    """End-to-end customer plan upload: auto geometry persists canonical model and customer takeoff rows match net quantities."""
    import tempfile
    from pathlib import Path
    from unittest.mock import patch
    import pb_planreader_3d_app as app_mod
    import pb_auto_geometry_v1219 as auto
    from pb_canonical_persistence import load_workspace_canonical_model

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "planreader_test.db"
        with patch.object(app_mod, "DB_PATH", db_path):
            setattr(app_mod, "_pb_local_db_initialized_v1215", False)
            app_mod.init_local_db()

            # Create workspace, document, and pages
            app_mod.lexecute("INSERT INTO workspaces(id, job_name, created_at, updated_at) VALUES(1, 'Parity Test', 'x', 'x')")
            app_mod.lexecute("INSERT INTO documents(id, workspace_id, file_name, path, sha256, page_count) VALUES(1, 1, 'plans.pdf', 'plans.pdf', 'sha', 1)")
            app_mod.lexecute(
                """INSERT INTO pages(id, document_id, workspace_id, page_no, page_label, page_type, scale_text, px_per_m, render_zoom, extracted_text, selected)
                   VALUES(1, 1, 1, 1, 'Elevation North', 'Elevation', '1:100', 28.35, 1.0, 'ELEVATION', 1)"""
            )

            # Mock registered walls: wall with 1 window (1.8m x 1.2m = 2.16m2) on a 10m x 2.7m wall (gross 27.0m2, net 24.84m2)
            reg_wall = {
                "wall_ref": "W_NORTH_PARITY",
                "side": "North",
                "substrate": "Brick veneer",
                "height_m": 2.7,
                "height_status": "confirmed",
                "height_confidence": "Verified",
                "gross_m2": 27.0,
                "opening_deduction_m2": 2.16,
                "net_m2": 24.84,
                "is_external": True,
                "thickness_m": 0.24,
                "a": {"x": 0.0, "y": 0.0},
                "b": {"x": 10.0, "y": 0.0},
                "level": {"id": "lvl_ground", "name": "Ground Floor", "level_index": 0},
                "openings": [
                    {
                        "opening_instance_id": "op_W01_parity",
                        "type_mark": "W01",
                        "opening_type": "WINDOW",
                        "width_m": 1.8,
                        "height_m": 1.2,
                        "sill_height_m": 0.9,
                        "station_m": 3.0,
                        "wall_ref": "W_NORTH_PARITY",
                    }
                ],
            }

            app_mod.build_registered_walls_v139 = lambda ws_id: [reg_wall]

            # Run automatic plan geometry
            report = auto.analyse_workspace(app_mod, 1)

            assert report is not None
            assert report["canonical_model_id"] == "ws_1_canonical"
            assert report["canonical_wall_count"] == 1
            assert report["canonical_opening_count"] == 1

            # Verify canonical model persistence
            ok, project, msg, payload = load_workspace_canonical_model(app_mod, 1)
            assert ok is True
            assert project is not None
            assert project.id == "ws_1_canonical"

            c_wall = project.all_walls()[0]
            assert c_wall.id == "wall_W_NORTH_PARITY"
            assert c_wall.length_m() == 10.0
            assert c_wall.height_m == 2.7
            assert c_wall.gross_area_m2() == 27.0
            assert round(c_wall.net_area_m2(), 2) == 24.84
            assert len(c_wall.openings) == 1

            c_op = c_wall.openings[0]
            assert c_op.mark == "W01"
            assert c_op.width_m == 1.8
            assert c_op.height_m == 1.2
            assert c_op.host_wall_id == c_wall.id

            # Verify customer takeoff rows directly in SQLite
            rows = app_mod.lquery("SELECT section, element, location, substrate, quantity, unit, notes FROM takeoff_rows WHERE workspace_id=1")
            assert len(rows) >= 1
            wall_row = next(r for r in rows if "W_NORTH_PARITY" in str(r.get("notes") or "") or "W_NORTH_PARITY" in str(r.get("location") or "") or "W_NORTH_PARITY" in str(r.get("element") or ""))
            assert wall_row["quantity"] == 24.84
            assert wall_row["unit"] == "m²"
            assert "Gross 27.00 m²" in wall_row["notes"]
            assert "authenticated opening deductions 2.16 m²" in wall_row["notes"]


def test_internal_partition_derived_quantities_and_faces():
    """Internal partition walls automatically compute carpentry lm, link bounding room faces, and apply opening deductions to both faces."""
    from pb_production_3d_adapter import planreader_to_canonical_model

    payload = {
        "workspace_id": 105,
        "registered_walls": [
            {
                "wall_ref": "PART_BED1_HALL",
                "a": {"x": 0.0, "y": 0.0},
                "b": {"x": 5.0, "y": 0.0},
                "height_m": 2.7,
                "thickness_m": 0.09,
                "is_external": False,
                "substrate": "Timber stud",
                "takeoff_eligible": True,
                "face_a": {"face_id": "A", "finish": "Acrylic paint low sheen", "substrate": "Plasterboard"},
                "face_b": {"face_id": "B", "finish": "Acrylic paint low sheen", "substrate": "Villaboard"},
                "level": {"id": "lvl_gnd", "name": "Ground Floor", "level_index": 0},
                "openings": [
                    {
                        "opening_instance_id": "op_D02_bed1",
                        "type_mark": "D02",
                        "opening_type": "DOOR",
                        "width_m": 0.82,
                        "height_m": 2.04,
                        "offset_along_wall_m": 1.5,
                        "wall_ref": "PART_BED1_HALL",
                    }
                ],
            }
        ],
        "spaces": [
            {
                "id": "SP_BED1",
                "name": "Bed 1",
                "area_m2": 15.0,
                "bounding_wall_ids": ["wall_PART_BED1_HALL"],
            },
            {
                "id": "SP_HALL",
                "name": "Hallway",
                "area_m2": 8.0,
                "bounding_wall_ids": ["wall_PART_BED1_HALL"],
            }
        ],
    }

    project, skipped = planreader_to_canonical_model(payload, is_validated_internal_workspace=True)
    project.recompute_relationships()

    walls = project.all_walls()
    assert len(walls) == 1
    w = walls[0]

    assert w.is_external is False
    assert w.length_m() == 5.0
    assert w.height_m == 2.7
    assert w.gross_area_m2() == 13.5
    # Door area = 0.82 * 2.04 = 1.6728 m2. Net = 13.5 - 1.6728 = 11.8272 m2
    assert round(w.net_area_m2(), 4) == 11.8272

    # Carpentry partition quantity in lm
    assert len(w.derived_quantities) >= 1
    carpentry = next(q for q in w.derived_quantities if q.trade_category == "carpentry")
    assert carpentry.unit == "lm"
    assert carpentry.quantity == 5.0
    assert "PARTITION" in carpentry.item_code

    # Verify Face A and Face B area and space linkage
    assert w.face_a is not None
    assert w.face_b is not None
    assert w.face_a.area_gross_m2 == 13.5
    assert w.face_b.area_gross_m2 == 13.5
    assert round(w.face_a.opening_deductions_m2, 4) == 1.6728
    assert round(w.face_b.opening_deductions_m2, 4) == 1.6728
    assert round(w.face_a.area_net_m2, 4) == 11.8272
    assert round(w.face_b.area_net_m2, 4) == 11.8272

    # Verify bounded room assignments
    assert w.face_a.bounded_space_id == "SP_BED1"
    assert w.face_b.bounded_space_id == "SP_HALL"

    # Dynamic costing
    cost_summary = project.recompute_quantities({
        carpentry.item_code: 48.0,  # $48/lm framing
        "OPENING_D02": 320.0,       # $320 door unit
    })
    assert cost_summary["items_costed"] == 2
    assert cost_summary["by_trade"]["carpentry"] == 240.0  # 5.0 lm * $48
    assert cost_summary["by_trade"]["doors"] == 320.0      # 1 door * $320
    assert cost_summary["total_cost"] == 560.0


def test_bound_wall_finish_schedule_authority_on_wall_faces():
    """Wall faces maintain independent finish codes and area bounds without duplicate geometry."""
    from pb_production_3d_adapter import planreader_to_canonical_model

    payload = {
        "workspace_id": 106,
        "registered_walls": [
            {
                "wall_ref": "W_EXT_FACADE",
                "a": {"x": 0.0, "y": 0.0},
                "b": {"x": 8.0, "y": 0.0},
                "height_m": 3.0,
                "thickness_m": 0.25,
                "is_external": True,
                "substrate": "Clay brick",
                "takeoff_eligible": True,
                "face_a": {
                    "face_id": "EXTERNAL",
                    "finish": "Face brickwork natural mortar",
                    "substrate": "Clay brick",
                    "finish_code": "BRK-01",
                },
                "face_b": {
                    "face_id": "INTERNAL",
                    "finish": "Acrylic wash & wear low sheen",
                    "substrate": "Plasterboard",
                    "finish_code": "PNT-02",
                },
                "level": {"id": "lvl_gnd", "name": "Ground Floor", "level_index": 0},
                "openings": [
                    {
                        "opening_instance_id": "op_W02_ext",
                        "type_mark": "W02",
                        "opening_type": "WINDOW",
                        "width_m": 2.0,
                        "height_m": 1.5,
                        "sill_height_m": 0.8,
                        "wall_ref": "W_EXT_FACADE",
                    }
                ],
            }
        ],
    }

    project, skipped = planreader_to_canonical_model(payload, is_validated_internal_workspace=True)
    project.recompute_relationships()

    walls = project.all_walls()
    assert len(walls) == 1
    w = walls[0]

    # Gross area: 8m * 3m = 24.0 m2. Window area: 2.0m * 1.5m = 3.0 m2. Net = 21.0 m2.
    assert w.gross_area_m2() == 24.0
    assert w.net_area_m2() == 21.0

    # Face A (External) and Face B (Internal)
    assert w.face_a.finish_code == "BRK-01"
    assert w.face_a.area_gross_m2 == 24.0
    assert w.face_a.opening_deductions_m2 == 3.0
    assert w.face_a.area_net_m2 == 21.0

    assert w.face_b.finish_code == "PNT-02"
    assert w.face_b.area_gross_m2 == 24.0
    assert w.face_b.opening_deductions_m2 == 3.0
    assert w.face_b.area_net_m2 == 21.0



