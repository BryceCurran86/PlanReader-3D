from __future__ import annotations

import inspect

import pytest

from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


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



def test_live_chain_reuses_one_source_owned_physical_scale_producer(
    tmp_path,
    monkeypatch,
) -> None:
    from pb_physical_scale_authority import PhysicalScaleProducer

    path = tmp_path / "physical-net-wall-scale-reuse.pdf"
    path.write_bytes(_complete_void_pdf())

    original_init = PhysicalScaleProducer.__init__
    construction_count = 0

    def counted_init(self, *args, **kwargs):
        nonlocal construction_count
        construction_count += 1
        return original_init(self, *args, **kwargs)

    monkeypatch.setattr(PhysicalScaleProducer, "__init__", counted_init)

    result = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert construction_count == 1
    assert result.canonical_walls
    assert result.canonical_openings
