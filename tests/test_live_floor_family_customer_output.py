from __future__ import annotations

from types import SimpleNamespace

import pytest

import pb_live_floor_family_customer_output as module
from pb_live_external_physical_net_wall_publication import (
    LiveExternalPhysicalNetWallPublication,
)
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_closed_run_export import SourceClosedRunConflictError


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
        canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_floor_reason_codes=(),
        canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED,
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=0.0,
        publication=_publication(),
    )


def _fake_run(*quantity_ids: str):
    return SimpleNamespace(
        quantities=tuple(
            SimpleNamespace(quantity_id=quantity_id)
            for quantity_id in quantity_ids
        )
    )


def test_combines_floor_area_and_floor_finish_without_supersedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    floor_run = _fake_run("floor-area-q")
    finish_run = _fake_run("floor-finish-q")
    combined = _fake_run("floor-area-q", "floor-finish-q")
    calls = {}

    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: ({"quantity_id": "floor-area-q"},),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: ({"quantity_id": "floor-finish-q"},),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: floor_run,
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: finish_run,
    )

    def combine(runs, *, project_id):
        calls["runs"] = tuple(runs)
        calls["project_id"] = project_id
        return combined

    def verify(run, rows):
        calls["verify_run"] = run
        calls["verify_rows"] = tuple(rows)

    monkeypatch.setattr(module, "combine_source_closed_runs", combine)
    monkeypatch.setattr(module, "verify_sealed_customer_output", verify)

    actual_run, rows = module.project_live_floor_family_customer_output(
        _claim(),
        workspace_id=1,
        project_id="project-1",
    )

    assert actual_run is combined
    assert calls["runs"] == (floor_run, finish_run)
    assert calls["project_id"] == "project-1"
    assert rows == (
        {"quantity_id": "floor-area-q"},
        {"quantity_id": "floor-finish-q"},
    )
    assert calls["verify_run"] is combined
    assert calls["verify_rows"] == rows


def test_preserves_existing_floor_area_when_finish_family_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    floor_run = _fake_run("floor-area-q")
    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: ({"quantity_id": "floor-area-q"},),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: floor_run,
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError()),
    )
    monkeypatch.setattr(
        module,
        "combine_source_closed_runs",
        lambda runs, *, project_id: floor_run,
    )
    monkeypatch.setattr(
        module,
        "verify_sealed_customer_output",
        lambda *args, **kwargs: None,
    )

    run, rows = module.project_live_floor_family_customer_output(
        _claim(),
        workspace_id=1,
        project_id="project-1",
    )
    assert run is floor_run
    assert rows == ({"quantity_id": "floor-area-q"},)


def test_rejects_duplicate_quantity_id_across_floor_families(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    duplicate = {"quantity_id": "same-q"}
    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: (duplicate,),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: (dict(duplicate),),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: _fake_run("same-q"),
    )
    monkeypatch.setattr(
        module,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: _fake_run("same-q"),
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="quantity IDs are not unique",
    ):
        module.project_live_floor_family_customer_output(
            _claim(),
            workspace_id=1,
            project_id="project-1",
        )


def test_rejects_empty_floor_family_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        module,
        "project_live_floor_area_customer_rows",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        module,
        "project_live_floor_finish_customer_rows",
        lambda *args, **kwargs: (),
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="no source-closed floor-family",
    ):
        module.project_live_floor_family_customer_output(
            _claim(),
            workspace_id=1,
            project_id="project-1",
        )


@pytest.mark.parametrize(
    ("workspace_id", "project_id"),
    [(True, "project-1"), (0, "project-1"), (1, ""), (1, " project-1")],
)
def test_rejects_malformed_project_scope(
    workspace_id,
    project_id,
) -> None:
    with pytest.raises((TypeError, ValueError)):
        module.project_live_floor_family_customer_output(
            _claim(),
            workspace_id=workspace_id,
            project_id=project_id,
        )
