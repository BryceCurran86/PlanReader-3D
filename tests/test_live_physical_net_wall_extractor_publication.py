from __future__ import annotations

from types import SimpleNamespace

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _drawing_and_boq_pdf() -> bytes:
    doc = fitz.open()
    try:
        drawing = doc.new_page(width=760.0, height=650.0)
        drawing.insert_text(
            fitz.Point(40.0, 60.0),
            (
                "GROUND FLOOR PLAN SCALE 1:100 DRAWING TITLE ARCHITECTURAL PLAN "
                + "SOURCE DRAWING ANNOTATION " * 12
            ),
            fontsize=7.0,
        )
        boq = doc.new_page(width=760.0, height=650.0)
        boq.insert_text(
            fitz.Point(40.0, 60.0),
            (
                "BILL OF QUANTITIES RATE AMOUNT KSHS "
                + "MEASURED WORK ITEM DESCRIPTION RATE AMOUNT " * 10
            ),
            fontsize=7.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _disable_unrelated_late_live_paths(monkeypatch) -> None:
    monkeypatch.setattr(
        "pb_live_ceiling_lining_integration.collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=("test_no_ceiling",),
            claims=(),
        ),
    )


def test_extractor_scopes_physical_net_wall_to_drawing_pages_and_publishes_claim(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "drawing-plus-boq.pdf"
    path.write_bytes(_drawing_and_boq_pdf())
    seen: dict[str, object] = {}
    canonical_wall_payload = {
        "canonical_wall_id": "whole-wall-1",
        "physical_wall_id": "whole-wall-1",
        "page_id": "1",
        "wall_local_frame_id": "whole-wall-1",
        "length_m": 15.0,
        "height_m": 3.0,
        "gross_area_m2": 45.0,
        "net_area_m2": 42.5,
        "member_wall_candidate_ids": ["wall-candidate-1"],
        "plan_members": [
            {
                "wall_candidate_id": "wall-candidate-1",
                "centerline_pts": [[10.0, 20.0], [160.0, 20.0]],
                "level_id": "ground",
            }
        ],
        "opening_identity_ids": ["opening-1"],
        "opening_voids": [
            {
                "opening_identity_id": "opening-1",
                "u0": 4.0,
                "u1": 5.0,
                "z0": 0.0,
                "z1": 2.5,
            }
        ],
        "gross_geometry_record_id": "gross-1",
        "whole_wall_role_record_id": "role-1",
        "evidence_ids": ["gross-1", "void-1", "role-1"],
    }
    canonical_wall = SimpleNamespace(to_dict=lambda: canonical_wall_payload)
    canonical_opening_payload = {
        "canonical_opening_id": "opening-1",
        "physical_opening_id": "opening-1",
        "page_id": "1",
        "viewport_id": "floor-plan-1",
        "semantic_class": "opening",
        "opening_kind": "window",
        "type_mark": "W1",
        "structural_pattern": "jamb_bounded_two_face_interruption",
        "host_wall_id": "whole-wall-1",
        "wall_local_frame_id": "whole-wall-1",
        "u0": 4.0,
        "u1": 5.0,
        "z0": 0.0,
        "z1": 2.5,
        "width_m": 1.0,
        "height_m": 2.5,
        "area_m2": 2.5,
        "geometry_complete": True,
        "source_observation_ids": ["obs-a", "obs-b"],
        "source_geometries": [[10.0, 20.0, 20.0, 20.0]],
        "evidence_ids": ["opening-1", "void-1"],
    }
    canonical_opening = SimpleNamespace(
        to_dict=lambda: canonical_opening_payload
    )
    canonical_room_payload = {
        "canonical_room_id": "room-1",
        "physical_room_id": "room-1",
        "page_id": "1",
        "viewport_id": None,
        "polygon_pdf_pts": [[20.0, 20.0], [100.0, 20.0], [100.0, 80.0], [20.0, 80.0]],
        "bounding_wall_ids": ["whole-wall-1"],
        "coordinate_unit": "pdf_pt",
        "geometry_complete": True,
        "metric_geometry_complete": False,
    }
    canonical_room = SimpleNamespace(to_dict=lambda: canonical_room_payload)
    canonical_floor_payload = {
        "canonical_floor_id": "floor-room-1",
        "room_entity_id": "room-1",
        "page_id": "1",
        "polygon_pdf_pts": canonical_room_payload["polygon_pdf_pts"],
        "geometry_complete": True,
        "metric_geometry_complete": False,
        "metric_area_m2": None,
        "finish_descriptor": None,
        "commercial_quantity_authority": False,
    }
    canonical_floor = SimpleNamespace(to_dict=lambda: canonical_floor_payload)
    opening_area_quantity = QuantityEvidence(
        quantity_id="opening-area-q1",
        family="opening_area",
        semantic_key="window_area:opening-1",
        value=2.5,
        unit="m2",
        input_entity_ids=("opening-1",),
        evidence_ids=("opening-1", "figured-1"),
        authority="test_opening_area",
        status="corroborated",
        confidence=1.0,
    )
    opening_count_quantity = QuantityEvidence(
        quantity_id="opening-count-q1",
        family="opening_count",
        semantic_key="opening_count:window:W1",
        value=1.0,
        unit="ea",
        input_entity_ids=("opening-1",),
        evidence_ids=("opening-1", "schedule-row-1"),
        authority="test_opening_count",
        status="corroborated",
        confidence=1.0,
    )
    captured_coverage: dict[str, object] = {}

    def fake_physical_wall_claim(pdf_path, *, pages=None):
        seen["pdf_path"] = pdf_path
        seen["pages"] = list(pages or ())
        return SimpleNamespace(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=("test_physical_net_wall_resolved",),
            quantity_m2=42.5,
            source_pages=(1,),
            canonical_walls=(canonical_wall,),
            canonical_wall_status=EvidenceResolutionStatus.CORROBORATED,
            canonical_wall_reason_codes=("test_canonical_wall_resolved",),
            canonical_wall_source_pages=(1,),
            unresolved_wall_candidate_ids=(),
            canonical_openings=(canonical_opening,),
            canonical_rooms=(canonical_room,),
            canonical_floors=(canonical_floor,),
            canonical_floor_status=EvidenceResolutionStatus.CORROBORATED,
            canonical_floor_reason_codes=("test_canonical_floor_resolved",),
            canonical_floor_source_pages=(1,),
            canonical_room_status=EvidenceResolutionStatus.CORROBORATED,
            canonical_room_reason_codes=("test_canonical_room_resolved",),
            canonical_room_source_pages=(1,),
            external_wall_ids=("whole-wall-1",),
            evidence_ids=("gross-1", "void-1", "role-1"),
            quantity_id="physical-net-wall-q1",
            confidence=1.0,
            opening_quantity_evidence=(opening_area_quantity,),
            opening_count_quantity_evidence=(opening_count_quantity,),
        )

    monkeypatch.setattr(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        fake_physical_wall_claim,
    )

    def capture_coverage(*, objects, quantities, registry_run_scope, output_rows=None):
        captured_coverage["quantity_ids"] = tuple(q.quantity_id for q in quantities)
        return (), {}

    monkeypatch.setattr(
        "pb_live_canonical_coverage_registry.collect_live_canonical_coverage",
        capture_coverage,
    )
    _disable_unrelated_late_live_paths(monkeypatch)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        collect_item35_shadow=False,
    )

    assert seen["pages"] == [0]
    wall = next(pred for pred in predictions if pred.tag == "perimeter_walling")
    assert wall.quantity == 42.5
    assert wall.unit == "SM"
    assert wall.confidence == 1.0
    assert wall.source_page == 1
    assert wall.dimensions is None
    assert wall.metadata["derivation"] == "source_owned_physical_external_net_wall"
    assert wall.metadata["commercial_projection_allowed"] is True
    assert wall.metadata["raw_evidence_ref"] == "physical-net-wall-q1"
    assert wall.metadata["canonical_wall_ids"] == ["whole-wall-1"]
    assert wall.metadata["canonical_wall_objects"] == [canonical_wall_payload]
    assert extractor.physical_net_wall_live["status"] == "corroborated"
    assert extractor.physical_net_wall_live["canonical_walls"] == [
        canonical_wall_payload
    ]
    assert extractor.canonical_walls_live["status"] == "corroborated"
    assert extractor.canonical_walls_live["source_pages"] == [1]
    assert extractor.canonical_walls_live["unresolved_wall_candidate_ids"] == []
    assert extractor.canonical_walls_live["walls"] == [canonical_wall_payload]
    assert extractor.canonical_openings_live["status"] == "corroborated"
    assert extractor.canonical_openings_live["openings"] == [
        canonical_opening_payload
    ]
    assert extractor.canonical_rooms_live["status"] == "corroborated"
    assert extractor.canonical_rooms_live["source_pages"] == [1]
    assert extractor.canonical_rooms_live["rooms"] == [canonical_room_payload]
    assert extractor.canonical_building_live["status"] == "corroborated"
    assert extractor.canonical_building_live["building_id"]
    assert extractor.canonical_building_live["levels"] == []
    assert extractor.canonical_building_live["level_assignment_complete"] is False
    assert extractor.canonical_building_live["object_counts"]["walls"] == 1
    assert extractor.canonical_building_live["object_counts"]["openings"] == 1
    assert extractor.canonical_building_live["object_counts"]["rooms"] == 1
    assert extractor.canonical_building_live["object_counts"]["floors"] == 1
    assert wall.metadata["canonical_opening_ids"] == ["opening-1"]
    assert wall.metadata["canonical_opening_objects"] == [
        canonical_opening_payload
    ]
    assert extractor.extraction_status["physical_net_wall_live"] == "corroborated"
    assert "opening-area-q1" in captured_coverage["quantity_ids"]
    assert "opening-count-q1" in captured_coverage["quantity_ids"]


def test_extractor_does_not_promote_abstained_physical_net_wall_claim(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "drawing.pdf"
    path.write_bytes(_drawing_and_boq_pdf())
    canonical_opening_payload = {
        "canonical_opening_id": "opening-1",
        "physical_opening_id": "opening-1",
        "host_wall_id": "whole-wall-1",
        "geometry_complete": False,
    }
    canonical_opening = SimpleNamespace(
        to_dict=lambda: canonical_opening_payload
    )
    canonical_room_payload = {
        "canonical_room_id": "room-1",
        "physical_room_id": "room-1",
        "page_id": "1",
        "viewport_id": None,
        "polygon_pdf_pts": [[20.0, 20.0], [100.0, 20.0], [100.0, 80.0], [20.0, 80.0]],
        "bounding_wall_ids": ["whole-wall-1"],
        "coordinate_unit": "pdf_pt",
        "geometry_complete": True,
        "metric_geometry_complete": False,
    }
    canonical_room = SimpleNamespace(to_dict=lambda: canonical_room_payload)
    canonical_floor_payload = {
        "canonical_floor_id": "floor-room-1",
        "room_entity_id": "room-1",
        "page_id": "1",
        "polygon_pdf_pts": canonical_room_payload["polygon_pdf_pts"],
        "geometry_complete": True,
        "metric_geometry_complete": False,
        "metric_area_m2": None,
        "finish_descriptor": None,
        "commercial_quantity_authority": False,
    }
    canonical_floor = SimpleNamespace(to_dict=lambda: canonical_floor_payload)
    canonical_wall_payload = {
        "canonical_wall_id": "wall2-candidate-1",
        "physical_wall_id": None,
        "identity_status": "candidate_physical_equivalence_unresolved",
        "physical_identity_resolved": False,
        "geometry_complete": True,
        "metric_geometry_complete": False,
        "quantity_complete": False,
    }
    canonical_wall = SimpleNamespace(to_dict=lambda: canonical_wall_payload)

    monkeypatch.setattr(
        GenericPlanReaderExtractor,
        "_detect_outer_envelope",
        staticmethod(lambda *args, **kwargs: (10.0, 8.0)),
    )
    monkeypatch.setattr(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: SimpleNamespace(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=("test_physical_net_wall_unavailable",),
            quantity_m2=None,
            source_pages=(),
            canonical_walls=(canonical_wall,),
            canonical_wall_status=EvidenceResolutionStatus.CANDIDATE,
            canonical_wall_reason_codes=("test_canonical_wall_candidate",),
            canonical_wall_source_pages=(1,),
            unresolved_wall_candidate_ids=("wall-candidate-1",),
            canonical_openings=(canonical_opening,),
            canonical_rooms=(canonical_room,),
            canonical_floors=(canonical_floor,),
            canonical_floor_status=EvidenceResolutionStatus.CORROBORATED,
            canonical_floor_reason_codes=("test_canonical_floor_resolved",),
            canonical_floor_source_pages=(1,),
            canonical_room_status=EvidenceResolutionStatus.CORROBORATED,
            canonical_room_reason_codes=("test_canonical_room_resolved",),
            canonical_room_source_pages=(1,),
            external_wall_ids=(),
            evidence_ids=(),
            quantity_id=None,
            confidence=0.0,
        ),
    )
    _disable_unrelated_late_live_paths(monkeypatch)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        collect_item35_shadow=False,
    )

    assert extractor.physical_net_wall_live["status"] == "abstained"
    assert extractor.canonical_walls_live["status"] == "candidate"
    assert extractor.canonical_walls_live["walls"] == [canonical_wall_payload]
    assert extractor.canonical_walls_live["unresolved_wall_candidate_ids"] == [
        "wall-candidate-1"
    ]
    assert extractor.canonical_openings_live["status"] == "corroborated"
    assert extractor.canonical_openings_live["openings"] == [
        canonical_opening_payload
    ]
    assert extractor.canonical_rooms_live["status"] == "corroborated"
    assert extractor.canonical_rooms_live["rooms"] == [canonical_room_payload]
    assert extractor.canonical_building_live["status"] == "corroborated"
    assert extractor.canonical_building_live["building_id"]
    assert extractor.canonical_building_live["levels"] == []
    physical_promotions = [
        pred
        for pred in predictions
        if (pred.metadata or {}).get("derivation")
        == "source_owned_physical_external_net_wall"
    ]
    assert physical_promotions == []
