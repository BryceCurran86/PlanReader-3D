from __future__ import annotations

from copy import deepcopy
from dataclasses import replace

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceObject
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_floor_finish_area_source_closed_export import seal_live_floor_finish_area_run
from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from tools.prepare_gpt3_pending_floor_surface_identity_activation import (
    PROOF_READY,
    READY,
    build_floor_surface_activation,
)


SHA = "a" * 64


def _floor() -> LiveCanonicalFloorSurfaceObject:
    return LiveCanonicalFloorSurfaceObject(
        canonical_floor_id="floor-1",
        physical_floor_surface_id="physical-floor-1",
        room_entity_id="room-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        page_id="7",
        viewport_id="vp-floor",
        polygon_pdf_pts=((10.0, 10.0), (20.0, 10.0), (20.0, 20.0), (10.0, 20.0)),
        area_page_pts2=100.0,
        bounding_wall_ids=("w1", "w2", "w3", "w4"),
        canonical_bounding_wall_ids=(),
        source_room_face_record_id="face-1",
        evidence_ids=("ev-area", "ev-def", "ev-occ"),
        geometry_complete=True,
        metric_geometry_complete=False,
        metric_area_m2=8.64,
        metric_area_quantity_id="room-area-1",
        metric_area_authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        finish_descriptor="tile",
        structural_slab_id=None,
        physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=False,
    )


def _quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="floor-finish-q1",
        family="floor_finish_area",
        semantic_key="floor_finish_area:floor-1:FT3:tile",
        value=8.64,
        unit="m2",
        input_entity_ids=("floor-1",),
        formula="authenticated_documented_floor_finish",
        formula_version="1",
        evidence_ids=("ev-area", "ev-def", "ev-occ"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=("authenticated_cross_view_floor_finish_area",),
        metadata={
            "source_sha256": SHA,
            "revision_id": "rev-1",
            "page_no": "7",
            "viewport_id": "vp-floor",
            "canonical_floor_id": "floor-1",
            "physical_floor_surface_id": "physical-floor-1",
            "source_room_face_record_id": "face-1",
            "finish_code": "FT3",
            "semantic_finish": "tile",
            "support_snapshot_id": "semantic-snap-1",
            "support_page_id": "11",
            "support_viewport_id": "finish-vp",
            "finish_definition_record_id": "def-1",
            "finish_occurrence_record_id": "occ-1",
            "finish_occurrence_evidence_id": "ev-occ",
            "source_dimension_page_id": "11",
            "figured_dimension_ids": ("dim-h-source", "dim-v-source"),
        },
    )


def _publication() -> LiveExternalPhysicalNetWallPublication:
    return LiveExternalPhysicalNetWallPublication(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test",),
        quantity_evidence=None,
        canonical_walls=(),
        external_wall_ids=(),
        gross_geometry_record_ids=(),
        whole_wall_role_record_ids=(),
        physical_void_record_ids=(),
        opening_universe_record_ids=(),
    )


def _claim() -> LivePhysicalNetWallClaim:
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("test",),
        quantity_m2=None,
        source_pages=(),
        canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(_floor(),),
        canonical_floor_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_floor_reason_codes=(),
        canonical_floor_source_pages=(7,),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=_publication(),
        floor_finish_quantity_evidence=(_quantity(),),
    )


def _inputs():
    claim = _claim()
    sealed = seal_live_floor_finish_area_run(
        claim, workspace_id=1, project_id="project-1"
    )
    rows = list(project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1"
    ))
    pending = {
        "project_id": "project-1",
        "source_sha256": SHA,
        "pending_identities": [{
            "status": READY,
            "canonical_floor_id": "floor-1",
            "physical_floor_surface_id": "physical-floor-1",
            "benchmark_item_id": "item-1",
            "benchmark_object_ref": "object-1",
        }],
    }
    active = {
        "schema_version": "1.0.0",
        "project_id": "project-1",
        "source_sha256s": [SHA],
        "bindings": [],
    }
    manifest = {
        "project_id": "project-1",
        "source_documents": [{"sha256": SHA}],
        "verified_takeoff_items": [{
            "item_id": "item-1",
            "denominator_eligible": True,
            "expected_object_refs": ["object-1"],
            "unit": "m2",
        }],
    }
    universe = {
        "project_id": "project-1",
        "floor_surfaces": [{
            "object_ref": "object-1",
            "physical_kind": "floor_finish_surface",
            # Identity activation must never use expected quantity equality.
            "expected_area_m2": 999999.0,
            "verification": {"fully_source_closed": True},
            "provenance": {
                "source_evidence_refs": ["sheet:A", "sheet:B"],
            },
        }],
    }
    proof = {
        "source_sha256": SHA,
        "bindings": [{
            "proof_status": PROOF_READY,
            "production_family": "floor_finish_area",
            "canonical_floor_id": "floor-1",
            "physical_floor_surface_id": "physical-floor-1",
            "benchmark_item_id": "item-1",
            "benchmark_object_ref": "object-1",
            "required_trace_canonical_entity_ids": [
                "floor-1", "physical-floor-1",
            ],
            "required_trace_evidence_ids": ["ev-def", "ev-occ"],
            "frozen_source_evidence_refs": ["sheet:A", "sheet:B"],
        }],
    }
    return sealed.to_dict(), rows, pending, active, manifest, universe, proof


def _activate(**changes):
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    values = dict(
        pending_ledger=pending,
        sealed_run_payload=sealed,
        customer_rows=rows,
        active_identity_map_payload=active,
        source_manifest=manifest,
        source_identity_proof=proof,
        object_universe=universe,
    )
    values.update(changes)
    return build_floor_surface_activation(**values)


def test_floor_surface_activation_requires_source_proven_sealed_customer_row() -> None:
    identity_map, receipt = _activate()
    assert receipt["activated_count"] == 1
    assert receipt["benchmark_score_granted"] is False
    assert receipt["evaluator_invoked"] is False
    assert identity_map["bindings"] == [{
        "benchmark_item_id": "item-1",
        "production_family": "floor_finish_area",
        "production_object_identity_refs": ["floor-1"],
    }]


def test_floor_surface_activation_does_not_match_by_expected_area() -> None:
    # The frozen object deliberately carries a nonsensical expected area in
    # _inputs(); success proves identity is driven by pre-certified ancestry.
    identity_map, _ = _activate()
    assert identity_map["bindings"][0]["production_object_identity_refs"] == [
        "floor-1"
    ]


def test_floor_surface_activation_rejects_forged_source_evidence() -> None:
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    proof = deepcopy(proof)
    proof["bindings"][0]["required_trace_evidence_ids"] = [
        "ev-def", "forged-source-evidence",
    ]
    with pytest.raises(ValueError, match="source-proven evidence"):
        _activate(source_identity_proof=proof)


def test_floor_surface_activation_rejects_wrong_physical_floor() -> None:
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    pending = deepcopy(pending)
    pending["pending_identities"][0]["physical_floor_surface_id"] = "physical-other"
    with pytest.raises(ValueError, match="does not authorize"):
        _activate(pending_ledger=pending)


def test_floor_surface_activation_rejects_unverified_identity_proof() -> None:
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    proof = deepcopy(proof)
    proof["bindings"][0]["proof_status"] = "DIAGNOSTIC_ONLY"
    with pytest.raises(ValueError, match="not independently certified"):
        _activate(source_identity_proof=proof)


def test_floor_surface_activation_rejects_frozen_source_ancestry_drift() -> None:
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    universe = deepcopy(universe)
    universe["floor_surfaces"][0]["provenance"]["source_evidence_refs"] = [
        "sheet:A", "sheet:C",
    ]
    with pytest.raises(ValueError, match="source ancestry differs"):
        _activate(object_universe=universe)


def test_floor_surface_activation_rejects_duplicate_active_identity() -> None:
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    active = deepcopy(active)
    active["bindings"] = [{
        "benchmark_item_id": "item-1",
        "production_family": "floor_finish_area",
        "production_object_identity_refs": ["floor-1"],
    }]
    with pytest.raises(ValueError, match="already active"):
        _activate(active_identity_map_payload=active)


def test_floor_surface_activation_rejects_missing_customer_row() -> None:
    sealed, rows, pending, active, manifest, universe, proof = _inputs()
    with pytest.raises(Exception):
        _activate(customer_rows=[])
