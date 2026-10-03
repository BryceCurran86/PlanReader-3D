from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import fitz

import pb_auto_geometry_v1219 as auto
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _floor_plan_with_schedule_quantity(
    *,
    tag: str = "W1",
    quantity: int | None,
) -> bytes:
    payload = _complete_void_pdf(tag=tag)
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        page = doc[0]
        # View classification is source-owned; make the synthetic source an
        # explicit floor plan rather than relying on a viewport-name heuristic.
        page.insert_text(fitz.Point(20.0, 24.0), "FLOOR PLAN")
        if quantity is not None:
            # Extend the existing synthetic opening schedule with a real
            # explicit quantity column. The historical default count=1 is not
            # sufficient for the positive commercial path.
            page.insert_text(fitz.Point(680.0, 500.0), "QTY")
            page.insert_text(fitz.Point(680.0, 530.0), str(int(quantity)))
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_explicit_schedule_quantity_reaches_live_opening_count_quantity_and_registry(
    tmp_path,
) -> None:
    path = tmp_path / "counted-opening.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert len(claim.canonical_openings) == 1
    opening = claim.canonical_openings[0]
    assert opening.opening_kind == "window"
    assert opening.type_mark == "W1"

    assert len(claim.opening_count_quantity_evidence) == 1
    quantity = claim.opening_count_quantity_evidence[0]
    assert quantity.family == "opening_count"
    assert quantity.semantic_key == "opening_count:W1"
    assert quantity.value == 1.0
    assert quantity.unit == "ea"
    assert quantity.input_entity_ids == (opening.canonical_opening_id,)
    assert quantity.metadata["schedule_corroborated"] is True
    assert quantity.metadata["opening_mark"] == "W1"

    summaries, gaps = collect_live_canonical_coverage(
        objects=claim.canonical_openings,
        quantities=claim.opening_count_quantity_evidence,
        registry_run_scope="live-opening-count-regression",
    )
    assert gaps == {}
    assert summaries
    records = [
        record
        for summary in summaries
        for record in summary.object_records
        if record.object_id == opening.canonical_opening_id
    ]
    assert len(records) == 1
    assert quantity.quantity_id in records[0].quantity_ids

    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    opening_family = report["family_reports"]["opening"]
    assert opening_family["stage_counts"]["QUANTIFIED"] == 1
    assert "explicit_quantity_link_unavailable" not in opening_family["reason_codes"]


def test_explicit_schedule_count_reaches_customer_runtime_row_even_without_wall_quantity(
    tmp_path,
) -> None:
    path = tmp_path / "counted-opening-customer.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert claim.opening_count_quantity_evidence
    count_quantity = claim.opening_count_quantity_evidence[0]

    app = SimpleNamespace(
        lquery=lambda *_args, **_kwargs: [{"id": 1, "path": str(path)}]
    )
    with patch(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        return_value=claim,
    ):
        wall_rows = auto._try_physical_net_wall_rows(
            app,
            1,
            [{
                "document_id": 1,
                "page_no": 1,
                "selected": 1,
                "page_type": "floor plan",
            }],
            [],
        )

    # The wall fixture has no independent wall-height authority; opening
    # commercial output must not be gated on a successful net-wall row.
    assert wall_rows is None
    opening_rows = app._live_opening_takeoff_rows_by_workspace[1]
    count_rows = [
        dict(zip(auto.TAKEOFF_ROW_FIELDS, row))
        for row in opening_rows
        if count_quantity.quantity_id in str(
            dict(zip(auto.TAKEOFF_ROW_FIELDS, row))["source_reference"]
        )
    ]
    assert len(count_rows) == 1
    row = count_rows[0]
    assert row["section"] == "Openings"
    assert row["element"] == "Window count"
    assert row["location"] == "W1"
    assert row["quantity"] == 1.0
    assert row["unit"] == "ea"
    assert row["quantity_status"] == "Measured"
    assert row["inclusion_status"] == "PROVISIONAL"


def test_implicit_schedule_default_never_becomes_live_commercial_count(
    tmp_path,
) -> None:
    path = tmp_path / "implicit-count-opening.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=None))

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert claim.canonical_openings
    assert claim.opening_count_quantity_evidence == ()
