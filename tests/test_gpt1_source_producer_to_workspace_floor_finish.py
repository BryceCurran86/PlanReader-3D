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
