"""Real source producer -> FIRM issuer -> source seal -> workspace customer row.

Source-neutral synthetic PDF fixture only. This proves call-path interoperability,
not an original Maryborough FT3 match, W4/D15 door threshold or frozen score.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pb_auto_geometry_v1219 as auto
from pb_cross_view_floor_finish_authority import (
    CrossViewFloorFinishProducer, enrich_live_canonical_floor_finishes,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_finish_area_source_closed_export import (
    seal_live_floor_finish_area_run,
)
from pb_live_floor_finish_customer_projection import (
    project_live_floor_finish_customer_rows,
)
from pb_migration_contracts import EvidenceResolutionStatus as Status
from tests.test_cross_view_floor_finish_authority_v1 import (
    _payload, _patch_material_viewports, _source_room_area_and_floor,
)
from tests.test_live_floor_finish_area_source_closed_export import (
    _claim as _empty_customer_claim,
)


def _real_issuer_fixture(monkeypatch, *, area_metadata_mutation=None):
    _patch_material_viewports(monkeypatch)
    pdf = _payload()
    source, room_areas, floors = _source_room_area_and_floor(pdf)
    if area_metadata_mutation is not None:
        original = room_areas.records[0]
        area = replace(
            original.area_evidence,
            metadata={
                **dict(original.area_evidence.metadata),
                **area_metadata_mutation,
            },
        )
        room_areas = replace(
            room_areas, records=(replace(original, area_evidence=area),),
        )
    finishes = CrossViewFloorFinishProducer.from_source(
        source=source, room_areas=room_areas, floors=floors,
    ).publish()
    enriched = enrich_live_canonical_floor_finishes(floors, finishes)
    claim = replace(
        _empty_customer_claim(),
        canonical_floors=enriched.floors,
        floor_finish_quantity_evidence=finishes.quantities,
    )
    return pdf, finishes, claim


def test_native_figured_source_to_actual_workspace_floor_finish(
    monkeypatch, tmp_path,
):
    pdf, finishes, claim = _real_issuer_fixture(monkeypatch)
    assert finishes.status is Status.CORROBORATED
    assert len(finishes.quantities) == 1
    issued = finishes.quantities[0]
    assert issued.status == "firm"
    assert issued.value == 8.64
    assert issued.semantic_key.endswith(":FT1:tile")

    sealed = seal_live_floor_finish_area_run(
        claim, workspace_id=1, project_id="customer-workspace:1",
    )
    rows = project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="customer-workspace:1",
    )
    assert len(sealed.quantities) == len(rows) == 1
    assert sealed.quantities[0].quantity_id == issued.quantity_id
    assert sealed.quantities[0].value == issued.value
    assert verify_sealed_customer_output(
        sealed, rows,
    ).verified_quantity_ids == (issued.quantity_id,)
    assert rows[0]["element"] == "Floor finish area (FT1)"
    assert rows[0]["finish_system"] == "tile"
    assert rows[0]["quantity"] == 8.64

    # The real workspace application consumes the already producer-issued
    # claim; do not replace the issuer, source traces or customer projector.
    pdf_path = tmp_path / "source-neutral-dimension-floor.pdf"
    pdf_path.write_bytes(pdf)
    app = SimpleNamespace(lquery=lambda *_: [{"id": 1, "path": str(pdf_path)}])
    with patch(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        return_value=claim,
    ):
        auto._try_physical_net_wall_rows(
            app, 1, [{"document_id": 1, "page_no": 1}], [],
        )
    output = app._live_floor_finish_takeoff_rows_by_workspace[1]
    assert len(output) == 1, repr(
        app._ag09_family_coverage_by_workspace[1]["family_gaps"]
    )
    actual = dict(zip(auto.TAKEOFF_ROW_FIELDS, output[0]))
    assert actual["element"] == rows[0]["element"] == "Floor finish area (FT1)"
    assert actual["finish_system"] == "tile"
    assert actual["quantity"] == issued.value
    assert actual["quantity_status"] == "To review"
    assert actual["inclusion_status"] == "INCLUSION"
    assert issued.quantity_id in actual["notes"]


def test_foreign_original_axis_cannot_reach_firm_seal_or_workspace(
    monkeypatch, tmp_path,
):
    pdf, finishes, claim = _real_issuer_fixture(
        monkeypatch,
        area_metadata_mutation={
            "figured_dimension_ids": ("forged-dimension-h", "forged-dimension-v"),
        },
    )
    assert finishes.quantities == ()
    assert claim.floor_finish_quantity_evidence == ()
    assert project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="customer-workspace:1",
    ) == ()
    source = tmp_path / "synthetic-forged-axis.pdf"
    source.write_bytes(pdf)
    app = SimpleNamespace(lquery=lambda *_: [{"id": 1, "path": str(source)}])
    with patch(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        return_value=claim,
    ):
        auto._try_physical_net_wall_rows(
            app, 1, [{"document_id": 1, "page_no": 1}], [],
        )
    assert app._live_floor_finish_takeoff_rows_by_workspace[1] == []


def test_same_original_revision_distinct_semantic_snapshot_seals_exact_ft_code(
    monkeypatch,
):
    """A separate schedule/finish snapshot is valid; room geometry stays owned."""
    from pb_source_visibility_authority import SourceVisibilityProducer

    _patch_material_viewports(monkeypatch)
    payload = _payload()
    geometry_source, room_areas, floors = _source_room_area_and_floor(
        payload, page_ids=("1", "2"),
    )
    geometry_revision = room_areas.records[0].area_evidence.metadata[
        "room_revision_id"
    ]
    original = geometry_source.published_snapshot_for_revision(geometry_revision)
    assert original is not None
    semantic = SourceVisibilityProducer(
        producer_method="gpt1-source-neutral-finish-separate-snapshot",
        producer_version="1.0",
    )
    material = semantic.ingest_native_pdf_bytes(
        document_id=original.revision.document_id,
        source_bytes=payload,
        source_locator="memory://synthetic-independent-material.pdf",
        page_ids=("2", "3"),
    )
    assert material.revision.revision_id == original.revision.revision_id
    assert material.snapshot.snapshot_id != original.snapshot.snapshot_id

    finishes = CrossViewFloorFinishProducer.from_source(
        source=semantic, room_areas=room_areas, floors=floors,
    ).publish()
    assert finishes.status is Status.CORROBORATED
    assert len(finishes.quantities) == 1
    claim = replace(
        _empty_customer_claim(),
        canonical_floors=enrich_live_canonical_floor_finishes(
            floors, finishes,
        ).floors,
        floor_finish_quantity_evidence=finishes.quantities,
    )
    sealed = seal_live_floor_finish_area_run(
        claim, workspace_id=1, project_id="project-1",
    )
    rows = project_live_floor_finish_customer_rows(
        claim, workspace_id=1, project_id="project-1",
    )
    assert len(rows) == 1
    assert rows[0]["element"] == "Floor finish area (FT1)"
    assert rows[0]["quantity"] == 8.64
    assert finishes.quantities[0].metadata["support_snapshot_id"] == (
        material.snapshot.snapshot_id
    )
    assert tuple(
        finishes.quantities[0].metadata["figured_dimension_ids"]
    ) == tuple(sorted(
        room_areas.records[0].area_evidence.metadata["figured_dimension_ids"]
    ))
    assert verify_sealed_customer_output(
        sealed, rows,
    ).verified_quantity_ids == (finishes.quantities[0].quantity_id,)


def test_foreign_revision_semantic_snapshot_cannot_sign_floor_finish(
    monkeypatch,
):
    """The same numeric dimensions and FT1 cannot join different PDF roots."""
    from pb_source_visibility_authority import SourceVisibilityProducer

    _patch_material_viewports(monkeypatch)
    payload = _payload()
    _, room_areas, floors = _source_room_area_and_floor(
        payload, page_ids=("1", "2"),
    )
    foreign_source = SourceVisibilityProducer(
        producer_method="gpt1-source-neutral-foreign-revision",
        producer_version="1.0",
    )
    foreign_source.ingest_native_pdf_bytes(
        document_id="unrelated-original-source-root",
        source_bytes=payload,
        source_locator="memory://foreign-finish.pdf",
        page_ids=("2", "3"),
    )
    disputed = CrossViewFloorFinishProducer.from_source(
        source=foreign_source, room_areas=room_areas, floors=floors,
    ).publish()
    assert disputed.status is Status.CONFLICT
    assert disputed.quantities == ()
    assert disputed.records == ()


def test_source_signed_room_area_and_ft_material_reach_real_workspace_as_separate_rows(
    tmp_path,
):
    """Actual workspace adapter must not discard a source-closed floor for blank UI fields."""
    from tests.test_live_floor_family_customer_output import (
        _production_shaped_source_area_and_finish_claim,
    )

    claim = _production_shaped_source_area_and_finish_claim()
    source_area = claim.room_area_quantity_evidence[0]
    assert not source_area.metadata.get("location")
    assert not source_area.metadata.get("section")
    assert not source_area.metadata.get("substrate")

    pdf_file = tmp_path / "gpt1-source-neutral-area-workspace.pdf"
    pdf_file.write_bytes(_payload())
    app = SimpleNamespace(lquery=lambda *_: [
        {"id": 1, "path": str(pdf_file)},
    ])
    with patch(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        return_value=claim,
    ):
        auto._try_physical_net_wall_rows(
            app, 1, [{"document_id": 1, "page_no": 1}], [],
        )

    floor_rows = app._live_room_area_takeoff_rows_by_workspace[1]
    finish_rows = app._live_floor_finish_takeoff_rows_by_workspace[1]
    gaps = app._ag09_family_coverage_by_workspace[1]["family_gaps"]
    assert len(floor_rows) == len(finish_rows) == 1, repr(gaps)
    floor = dict(zip(auto.TAKEOFF_ROW_FIELDS, floor_rows[0]))
    finish = dict(zip(auto.TAKEOFF_ROW_FIELDS, finish_rows[0]))
    assert floor["section"] == "Internal"
    assert floor["element"] == "Floor area"
    assert floor["location"] == "room-1"
    assert floor["substrate"] == "Floor"
    # The workspace persistence boundary replaces an unassigned material with
    # its honest unresolved display value; it must not copy FT1/tile.
    assert floor["finish_system"] == "To be confirmed"
    assert floor["quantity"] == 8.64
    assert floor["quantity_status"] == "To review"
    assert source_area.quantity_id in floor["source_reference"]
    assert finish["element"] == "Floor finish area (FT1)"
    assert finish["finish_system"] == "tile"
    assert finish["quantity"] == floor["quantity"]
    assert finish["quantity_status"] == "To review"
    assert finish["notes"] != floor["notes"]


def test_real_workspace_cannot_reclassify_revoked_room_area_or_retain_its_ft(
    tmp_path,
):
    """Both workspace family paths fail closed when original area is EXCLUDED."""
    from tests.test_live_floor_family_customer_output import (
        _production_shaped_source_area_and_finish_claim,
    )

    claim = _production_shaped_source_area_and_finish_claim()
    original = claim.room_area_quantity_evidence[0]
    excluded = replace(
        original,
        metadata={**original.metadata, "inclusion_status": "EXCLUSION"},
    )
    claim = replace(claim, room_area_quantity_evidence=(excluded,))
    pdf_file = tmp_path / "gpt1-source-neutral-excluded-workspace.pdf"
    pdf_file.write_bytes(_payload())
    app = SimpleNamespace(lquery=lambda *_: [
        {"id": 1, "path": str(pdf_file)},
    ])
    with patch(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        return_value=claim,
    ):
        auto._try_physical_net_wall_rows(
            app, 1, [{"document_id": 1, "page_no": 1}], [],
        )

    assert app._live_room_area_takeoff_rows_by_workspace[1] == []
    assert app._live_floor_finish_takeoff_rows_by_workspace[1] == []
    gaps = app._ag09_family_coverage_by_workspace[1]["family_gaps"]
    assert any(
        "live_room_area_customer_projection_failed:ValueError" in reason
        for reason in gaps.get("floor", ())
    ), repr(gaps)
    assert any(
        "live_floor_finish_customer_projection_failed:SourceClosedRunConflictError"
        in reason
        for reason in gaps.get("floor_finish", ())
    ), repr(gaps)
    assert excluded.value == 8.64
    assert claim.floor_finish_quantity_evidence[0].value == 8.64
