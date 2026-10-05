from __future__ import annotations

from dataclasses import replace
import inspect

import fitz
import pytest

import pb_live_room_area_customer_projection as customer_projection
import pb_live_room_area_source_closed_export as export
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffConflictError,
    existing_commercial_gate_results,
)


def _cross_view_room_area_pdf() -> bytes:
    doc = fitz.open()
    try:
        plan = doc.new_page(width=300.0, height=200.0)
        for first, second in (
            ((50.0, 50.0), (250.0, 50.0)),
            ((250.0, 50.0), (250.0, 150.0)),
            ((250.0, 150.0), (50.0, 150.0)),
            ((50.0, 150.0), (50.0, 50.0)),
            ((150.0, 50.0), (150.0, 150.0)),
        ):
            plan.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )
        plan.insert_text((78.0, 100.0), "OFFICE", fontsize=9.0)
        plan.insert_text((178.0, 100.0), "STUDY", fontsize=9.0)

        detail = doc.new_page(width=400.0, height=300.0)
        detail.insert_text((150.0, 150.0), "OFFICE", fontsize=10.0)

        detail.draw_line(
            (100.0, 80.0),
            (250.0, 80.0),
            color=(0, 0, 0),
            width=1.0,
        )
        detail.draw_line(
            (100.0, 68.0),
            (100.0, 92.0),
            color=(0, 0, 0),
            width=1.0,
        )
        detail.draw_line(
            (250.0, 68.0),
            (250.0, 92.0),
            color=(0, 0, 0),
            width=1.0,
        )
        detail.insert_text((164.0, 77.0), "3600", fontsize=9.0)

        # The vertical dimension shares a source witness junction with the
        # horizontal dimension at (250, 80).
        detail.draw_line(
            (280.0, 80.0),
            (280.0, 180.0),
            color=(0, 0, 0),
            width=1.0,
        )
        detail.draw_line(
            (250.0, 80.0),
            (292.0, 80.0),
            color=(0, 0, 0),
            width=1.0,
        )
        detail.draw_line(
            (268.0, 180.0),
            (292.0, 180.0),
            color=(0, 0, 0),
            width=1.0,
        )
        detail.insert_text(
            (277.0, 147.0),
            "2400",
            fontsize=9.0,
            rotate=90,
        )
        return doc.tobytes()
    finally:
        doc.close()


@pytest.fixture(scope="module")
def live_claim(tmp_path_factory):
    path = (
        tmp_path_factory.mktemp("live-room-area-source-closed")
        / "cross-view-room-area.pdf"
    )
    path.write_bytes(_cross_view_room_area_pdf())
    return collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        room_area_support_pages=(1,),
    )


def _firm_quantity(claim):
    firm = [
        quantity
        for quantity in claim.room_area_quantity_evidence
        if not quantity.abstained
    ]
    assert len(firm) == 1
    return firm[0]


def _resolved_floor(claim):
    floors = [
        floor
        for floor in claim.canonical_floors
        if floor.metric_area_quantity_id
    ]
    assert len(floors) == 1
    return floors[0]


def test_live_room_area_seals_with_source_and_canonical_floor_trace(
    live_claim,
) -> None:
    quantity = _firm_quantity(live_claim)
    floor = _resolved_floor(live_claim)
    assert quantity.value == pytest.approx(8.64)
    assert floor.metric_area_m2 == pytest.approx(8.64)
    assert floor.metric_area_quantity_id == quantity.quantity_id

    traces = export.build_live_room_area_source_traces(
        live_claim,
        workspace_id=7,
        project_id="source-project",
    )
    assert set(traces) == {quantity.quantity_id}
    trace = traces[quantity.quantity_id]
    assert set(quantity.input_entity_ids).issubset(trace.canonical_entity_ids)
    assert floor.canonical_floor_id in trace.canonical_entity_ids
    assert floor.physical_floor_surface_id in trace.canonical_entity_ids
    assert floor.source_room_face_record_id == trace.metadata[
        "source_room_face_record_id"
    ]
    assert set(quantity.evidence_ids).issubset(trace.evidence_ids)

    run = export.seal_live_room_area_run(
        live_claim,
        workspace_id=7,
        project_id="source-project",
    )
    assert run.project_id == "source-project"
    assert run.source_sha256s == (floor.source_sha256,)
    assert len(run.quantities) == 1

    row = run.quantities[0]
    assert row.quantity_id == quantity.quantity_id
    assert row.family == "room_area"
    assert row.value == pytest.approx(8.64)
    assert row.unit == "m2"
    assert row.lineage_ok is True
    assert row.abstained is False
    # Sealed production identity remains the quantity's real source-room
    # identity; canonical floor identity is additional trace provenance only.
    assert row.object_identity_refs == tuple(sorted(quantity.input_entity_ids))


def test_unavailable_room_areas_are_omitted_not_exported_as_zero(
    live_claim,
) -> None:
    assert any(
        quantity.abstained
        for quantity in live_claim.room_area_quantity_evidence
    )
    run = export.seal_live_room_area_run(
        live_claim,
        workspace_id=7,
        project_id="source-project",
    )
    assert len(run.quantities) == 1
    assert all(not row.abstained for row in run.quantities)
    assert all(row.value is not None and row.value > 0.0 for row in run.quantities)


def test_room_area_export_fails_closed_without_unique_enriched_floor(
    live_claim,
) -> None:
    floor = _resolved_floor(live_claim)
    missing = replace(
        floor,
        metric_area_m2=None,
        metric_area_quantity_id=None,
        metric_area_authority=None,
    )
    claim_without_mapping = replace(
        live_claim,
        canonical_floors=tuple(
            missing if item.canonical_floor_id == floor.canonical_floor_id else item
            for item in live_claim.canonical_floors
        ),
    )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="does not map to exactly one canonical floor",
    ):
        export.build_live_room_area_source_traces(
            claim_without_mapping,
            workspace_id=7,
            project_id="source-project",
        )

    duplicate = replace(
        floor,
        canonical_floor_id=f"{floor.canonical_floor_id}-duplicate",
        physical_floor_surface_id=(
            f"{floor.physical_floor_surface_id}-duplicate"
        ),
    )
    claim_with_duplicate = replace(
        live_claim,
        canonical_floors=(*live_claim.canonical_floors, duplicate),
    )
    with pytest.raises(
        SourceClosedRunConflictError,
        match="does not map to exactly one canonical floor",
    ):
        export.build_live_room_area_source_traces(
            claim_with_duplicate,
            workspace_id=7,
            project_id="source-project",
        )


def test_live_room_area_export_has_no_truth_or_scoring_dependency() -> None:
    source = inspect.getsource(export)
    forbidden = (
        "benchmarks.",
        "full_plan_v2",
        "reference_takeoff",
        "expected_quantity",
        "golden",
    )
    for value in forbidden:
        assert value not in source


def test_live_room_area_figured_quantity_projects_to_unreviewed_customer_row(
    live_claim,
) -> None:
    quantity = _firm_quantity(live_claim)
    figured_ids = tuple(quantity.metadata.get("figured_dimension_ids") or ())
    assert figured_ids

    rows = customer_projection.project_live_room_area_customer_rows(
        live_claim,
        workspace_id=7,
        project_id="source-project",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["quantity_id"] == quantity.quantity_id
    assert row["quantity"] == pytest.approx(8.64)
    assert row["unit"] == "m2"
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"
    assert row["row_role"] == "floor_area"
    assert row["inclusion_status"] == "INCLUSION"
    assert row["measurement_method"] == "figured_dimension"
    assert set(row["figured_dimension_ids"]) == set(figured_ids)
    assert row["source_sha256"] == _resolved_floor(live_claim).source_sha256

    gates = existing_commercial_gate_results(row)
    assert all(result[0] is False for result in gates.values())


def _scaled_room_area_claim(
    live_claim,
    *,
    resolved_scale_id: str | None,
    scale_status: str = "resolved",
    scale_conflicts: tuple[str, ...] = (),
):
    quantity = _firm_quantity(live_claim)
    metadata = dict(quantity.metadata or {})
    metadata["figured_dimension_ids"] = []
    metadata["resolved_scale_id"] = resolved_scale_id
    metadata["scale_status"] = scale_status
    metadata["scale_conflicts"] = list(scale_conflicts)
    scaled = replace(
        quantity,
        authority="pdf_scaled",
        formula="shoelace_polygon_area / trusted_px_per_m^2",
        metadata=metadata,
    )
    floor = _resolved_floor(live_claim)
    scaled_floor = replace(
        floor,
        metric_area_authority="pdf_scaled",
    )
    return replace(
        live_claim,
        room_area_quantity_evidence=tuple(
            scaled if item.quantity_id == quantity.quantity_id else item
            for item in live_claim.room_area_quantity_evidence
        ),
        canonical_floors=tuple(
            scaled_floor if item.canonical_floor_id == floor.canonical_floor_id else item
            for item in live_claim.canonical_floors
        ),
    )


def test_live_room_area_scaled_quantity_projects_only_with_explicit_scale_authority(
    live_claim,
) -> None:
    claim = _scaled_room_area_claim(
        live_claim,
        resolved_scale_id="scale:room-area:1",
        scale_status="resolved",
    )

    rows = customer_projection.project_live_room_area_customer_rows(
        claim,
        workspace_id=7,
        project_id="source-project",
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["quantity"] == pytest.approx(8.64)
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"
    assert row["measurement_method"] == "scaled_geometry"
    assert row["resolved_scale_id"] == "scale:room-area:1"
    assert row["scale_status"] == "resolved"
    assert row["scale_conflicts"] == []
    assert row["row_role"] == "floor_area"

    gates = existing_commercial_gate_results(row)
    assert all(result[0] is False for result in gates.values())


def test_scaled_room_area_without_resolved_scale_id_remains_unprojected(
    live_claim,
) -> None:
    claim = _scaled_room_area_claim(
        live_claim,
        resolved_scale_id=None,
        scale_status="resolved",
    )

    rows = customer_projection.project_live_room_area_customer_rows(
        claim,
        workspace_id=7,
        project_id="source-project",
    )

    assert rows == ()


def test_scaled_room_area_with_scale_conflict_fails_closed(
    live_claim,
) -> None:
    claim = _scaled_room_area_claim(
        live_claim,
        resolved_scale_id="scale:room-area:1",
        scale_status="resolved",
        scale_conflicts=("scale_conflict",),
    )

    with pytest.raises(CommercialTakeoffConflictError, match="scale conflicts"):
        customer_projection.project_live_room_area_customer_rows(
            claim,
            workspace_id=7,
            project_id="source-project",
        )


def test_room_area_customer_projection_omits_abstention_instead_of_zero(
    live_claim,
) -> None:
    abstained = tuple(
        quantity
        for quantity in live_claim.room_area_quantity_evidence
        if quantity.abstained
    )
    assert abstained
    claim = replace(live_claim, room_area_quantity_evidence=abstained)

    rows = customer_projection.project_live_room_area_customer_rows(
        claim,
        workspace_id=7,
        project_id="source-project",
    )

    assert rows == ()


def test_live_room_area_customer_projection_has_no_truth_or_scoring_dependency() -> None:
    source = inspect.getsource(customer_projection)
    forbidden = (
        "benchmarks.",
        "full_plan_v2",
        "reference_takeoff",
        "expected_quantity",
        "golden",
    )
    for value in forbidden:
        assert value not in source
