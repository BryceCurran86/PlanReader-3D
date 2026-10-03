from __future__ import annotations

import inspect

import fitz
import pytest

from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_physical_opening_void_composition import _complete_void_pdf




def _complete_void_floor_plan_pdf() -> bytes:
    doc = fitz.open(stream=_complete_void_pdf(), filetype="pdf")
    try:
        page = doc[0]
        page.insert_text(fitz.Point(20.0, 25.0), "GROUND FLOOR PLAN")
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_live_opening_counts_reuse_generic_count_authority(tmp_path) -> None:
    path = tmp_path / "physical-opening-count.pdf"
    path.write_bytes(_complete_void_floor_plan_pdf())

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert result.canonical_openings
    assert result.opening_count_quantity_evidence
    count = result.opening_count_quantity_evidence[0]
    assert count.family == "opening_count"
    assert count.value == 1.0
    assert count.unit == "ea"
    assert count.input_entity_ids == (
        result.canonical_openings[0].canonical_opening_id,
    )
    assert count.semantic_key.endswith(":window:W1")
    assert count.abstained is False


def test_live_opening_area_quantities_survive_even_when_wall_quantity_abstains(
    tmp_path,
) -> None:
    path = tmp_path / "physical-opening-area.pdf"
    path.write_bytes(_complete_void_pdf())

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert result.quantity_m2 is None
    assert result.canonical_openings
    assert result.opening_quantity_evidence
    area = result.opening_quantity_evidence[0]
    assert area.family == "opening_area"
    assert area.input_entity_ids == (
        result.canonical_openings[0].canonical_opening_id,
    )
    assert area.value is not None
    assert area.value > 0.0


def test_live_physical_net_wall_runs_real_source_chain_and_fails_closed_without_height(
    tmp_path,
) -> None:
    path = tmp_path / "physical-net-wall.pdf"
    path.write_bytes(_complete_void_pdf())

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    # This fixture deliberately has no independent wall-height authority.
    # The live seam must execute the source-owned chain without manufacturing
    # a default-height gross/net wall quantity.
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert result.quantity_m2 is None
    assert result.quantity_id is None

    # Semantic wall identity/geometry must survive independently from later
    # height/gross/net-wall quantity authority.
    assert result.canonical_wall_status is EvidenceResolutionStatus.CORROBORATED
    assert result.canonical_walls
    assert all(wall.geometry_complete for wall in result.canonical_walls)
    assert any(
        wall.physical_identity_resolved
        and wall.identity_status == "physical_resolved_by_opening_host_frame"
        for wall in result.canonical_walls
    )
    assert all(
        wall.metric_geometry_complete is False
        for wall in result.canonical_walls
    )

    assert result.canonical_openings
    assert all(
        opening.canonical_opening_id == opening.physical_opening_id
        for opening in result.canonical_openings
    )
    assert result.external_wall_ids == ()


def test_live_physical_net_wall_rejects_empty_or_out_of_range_page_scope(
    tmp_path,
) -> None:
    path = tmp_path / "physical-net-wall.pdf"
    path.write_bytes(_complete_void_pdf())

    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=())

    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=(999,))


def test_live_physical_net_wall_accepts_no_quantity_truth_inputs() -> None:
    parameters = set(
        inspect.signature(collect_live_physical_net_wall_claim).parameters
    )
    forbidden = {
        "wall_id",
        "wall_ids",
        "external_wall_ids",
        "gross_area_m2",
        "net_area_m2",
        "opening_area_m2",
        "opening_count",
        "quantity",
        "trade_scope_id",
        "deduction_rule",
        "expected",
        "benchmark",
    }
    assert not (parameters & forbidden)
