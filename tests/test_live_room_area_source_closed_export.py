from __future__ import annotations

from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_live_room_area_source_closed_export import (
    build_live_room_area_source_traces,
    seal_live_room_area_run,
)
from pb_portable_raster_ocr_authority import MockOCRBackend
from tests.test_live_physical_net_wall_integration import _two_room_cross_view_area_pdf


def _claim(tmp_path, monkeypatch):
    import pb_cross_view_room_area_authority as area_module
    from pb_raster_plan_dimension_authority import RasterPlanDimensionProducer

    monkeypatch.setattr(
        area_module.RasterPlanDimensionProducer,
        "create",
        staticmethod(
            lambda *, source_visibility: RasterPlanDimensionProducer.create_for_tests(
                source_visibility=source_visibility,
                backend=MockOCRBackend(()),
            )
        ),
    )
    path = tmp_path / "room-area-source-closed.pdf"
    path.write_bytes(_two_room_cross_view_area_pdf())
    return collect_live_physical_net_wall_claim(
        path,
        pages=(0,),
        topology_pages=(0,),
        room_area_support_pages=(1,),
    )


def test_room_area_trace_preserves_source_and_physical_identities(
    tmp_path,
    monkeypatch,
) -> None:
    claim = _claim(tmp_path, monkeypatch)
    positive = [
        quantity
        for quantity in claim.room_area_quantity_evidence
        if not quantity.abstained
    ]
    assert len(positive) == 1
    quantity = positive[0]

    traces = build_live_room_area_source_traces(
        claim,
        workspace_id=7,
        project_id="synthetic-project",
    )
    assert tuple(traces) == (quantity.quantity_id,)
    trace = traces[quantity.quantity_id]

    assert set(quantity.input_entity_ids).issubset(set(trace.canonical_entity_ids))
    assert set(quantity.evidence_ids).issubset(set(trace.evidence_ids))
    assert trace.document_id
    assert trace.source_sha256
    assert trace.revision_id == trace.current_revision_id
    assert trace.source_page == "1"
    assert trace.viewport_id

    metadata = dict(trace.metadata)
    assert metadata["source_room_identity"] == quantity.input_entity_ids[0]
    assert metadata["physical_room_id"] in trace.canonical_entity_ids
    assert metadata["physical_floor_surface_id"] in trace.canonical_entity_ids
    assert metadata["source_room_face_record_id"] in trace.evidence_ids


def test_room_area_source_closed_run_seals_firm_area_and_omits_blocked_sibling(
    tmp_path,
    monkeypatch,
) -> None:
    claim = _claim(tmp_path, monkeypatch)
    all_quantities = tuple(claim.room_area_quantity_evidence)
    assert any(quantity.abstained for quantity in all_quantities)
    assert any(not quantity.abstained for quantity in all_quantities)

    sealed = seal_live_room_area_run(
        claim,
        workspace_id=11,
        project_id="synthetic-project",
    )

    assert len(sealed.quantities) == 1
    row = sealed.quantities[0]
    assert row.abstained is False
    assert row.value == 8.64
    assert row.unit == "m2"
    assert row.family == "room_area"
    assert row.lineage_ok is True
    assert row.lineage_reason_codes == ()
    assert len(row.object_identity_refs) == 1
    assert set(row.object_identity_refs).issubset(
        set(row.trace_canonical_entity_ids)
    )

    # The unresolved sibling is absence, not a fabricated zero quantity.
    assert not any(
        sealed_row.value == 0.0
        for sealed_row in sealed.quantities
    )


def test_room_area_source_closed_run_is_deterministic(
    tmp_path,
    monkeypatch,
) -> None:
    claim = _claim(tmp_path, monkeypatch)
    first = seal_live_room_area_run(
        claim,
        workspace_id=17,
        project_id="synthetic-project",
    )
    second = seal_live_room_area_run(
        claim,
        workspace_id=17,
        project_id="synthetic-project",
    )

    assert first.to_dict() == second.to_dict()
    assert first.fingerprint == second.fingerprint
