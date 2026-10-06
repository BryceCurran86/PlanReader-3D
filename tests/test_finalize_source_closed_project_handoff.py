from __future__ import annotations

import json

import pytest

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import SourceClosedRunConflictError, seal_source_closed_run
from tools import finalize_source_closed_project_handoff as finalizer


SHA = "a" * 64


def _run(quantity_id: str, entity_id: str, *, project_id: str = "project-a"):
    quantity = QuantityEvidence(
        quantity_id=quantity_id,
        family="floor_area",
        semantic_key=f"floor_area:{entity_id}",
        value=10.0,
        unit="m2",
        input_entity_ids=(entity_id,),
        formula="source_closed",
        formula_version="1",
        evidence_ids=(f"ev-{entity_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        metadata={},
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id=project_id,
        document_id="doc-1",
        source_sha256=SHA,
        source_page="1",
        viewport_id=f"vp-{entity_id}",
        revision_id="rev-1",
        current_revision_id="rev-1",
        evidence_ids=quantity.evidence_ids,
        canonical_entity_ids=quantity.input_entity_ids,
    )
    return seal_source_closed_run(
        (quantity,),
        project_id=project_id,
        traces_by_quantity_id={quantity_id: trace},
    )


def test_finalizer_combines_core_and_surfaces_into_scoreboard_shape(tmp_path) -> None:
    project_id = "project-a"
    _core = _run("q-core", "opening-1")
    _surfaces = _run("q-surface", "floor-1")
    (tmp_path / f"{project_id}.core.json").write_text(_core.to_json(), encoding="utf-8")
    (tmp_path / f"{project_id}.surfaces.json").write_text(_surfaces.to_json(), encoding="utf-8")

    summary = finalizer.finalize_split_project_handoff(
        project_id=project_id,
        input_dir=tmp_path,
    )

    assert summary["available_groups"] == ["core", "surfaces"]
    assert summary["missing_groups"] == []
    assert summary["complete_group_set"] is True
    assert summary["quantity_count"] == 2
    payload = json.loads((tmp_path / f"{project_id}.json").read_text(encoding="utf-8"))
    assert payload["project_id"] == project_id
    assert [row["quantity_id"] for row in payload["quantities"]] == ["q-core", "q-surface"]
    assert (tmp_path / f"{project_id}.handoff-summary.json").is_file()


def test_finalizer_reports_missing_group_without_inventing_it(tmp_path) -> None:
    project_id = "project-a"
    core = _run("q-core", "opening-1")
    (tmp_path / f"{project_id}.core.json").write_text(core.to_json(), encoding="utf-8")

    summary = finalizer.finalize_split_project_handoff(
        project_id=project_id,
        input_dir=tmp_path,
    )

    assert summary["available_groups"] == ["core"]
    assert summary["missing_groups"] == ["surfaces"]
    assert summary["complete_group_set"] is False
    assert summary["quantity_count"] == 1
    payload = json.loads((tmp_path / f"{project_id}.json").read_text(encoding="utf-8"))
    assert [row["quantity_id"] for row in payload["quantities"]] == ["q-core"]


def test_finalizer_rejects_cross_project_split_input(tmp_path) -> None:
    project_id = "project-a"
    core = _run("q-core", "opening-1", project_id=project_id)
    surfaces = _run("q-surface", "floor-1", project_id="project-b")
    (tmp_path / f"{project_id}.core.json").write_text(core.to_json(), encoding="utf-8")
    (tmp_path / f"{project_id}.surfaces.json").write_text(surfaces.to_json(), encoding="utf-8")

    with pytest.raises(SourceClosedRunConflictError, match="belongs to project"):
        finalizer.finalize_split_project_handoff(
            project_id=project_id,
            input_dir=tmp_path,
        )


def test_finalizer_requires_at_least_one_split_run(tmp_path) -> None:
    with pytest.raises(FileNotFoundError, match="no split sealed runs"):
        finalizer.finalize_split_project_handoff(
            project_id="project-a",
            input_dir=tmp_path,
        )
