from __future__ import annotations

import inspect
import json

import pytest

import pb_combine_source_closed_runs as cli
from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import seal_source_closed_run


SHA_A = "a" * 64
SHA_B = "b" * 64


def quantity(quantity_id: str, entity_id: str, source_sha: str) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="room_area",
        semantic_key=f"room_area:{entity_id}",
        value=10.0,
        unit="m2",
        input_entity_ids=(entity_id,),
        formula="source_closed",
        formula_version="1",
        evidence_ids=(f"ev-{entity_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        metadata={
            "project_id": "project-a",
            "document_id": f"doc-{entity_id}",
            "source_sha256": source_sha,
            "revision_id": f"rev-{entity_id}",
        },
    )


def trace(entity_id: str, source_sha: str) -> CommercialTakeoffSourceTrace:
    return CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id="project-a",
        document_id=f"doc-{entity_id}",
        source_sha256=source_sha,
        source_page="p1",
        viewport_id=f"vp-{entity_id}",
        revision_id=f"rev-{entity_id}",
        current_revision_id=f"rev-{entity_id}",
        evidence_ids=(f"ev-{entity_id}",),
        canonical_entity_ids=(entity_id,),
    )


def test_cli_combines_verified_family_run_files(tmp_path) -> None:
    q1 = quantity("q1", "room-1", SHA_A)
    q2 = quantity("q2", "room-2", SHA_B)
    run1 = seal_source_closed_run(
        [q1],
        project_id="project-a",
        traces_by_quantity_id={"q1": trace("room-1", SHA_A)},
    )
    run2 = seal_source_closed_run(
        [q2],
        project_id="project-a",
        traces_by_quantity_id={"q2": trace("room-2", SHA_B)},
    )
    p1 = tmp_path / "room.json"
    p2 = tmp_path / "opening.json"
    out = tmp_path / "combined.json"
    p1.write_text(run1.to_json(), encoding="utf-8")
    p2.write_text(run2.to_json(), encoding="utf-8")

    assert cli.main([
        "--project-id", "project-a",
        "--input", str(p1),
        "--input", str(p2),
        "--output", str(out),
    ]) == 0

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["project_id"] == "project-a"
    assert [row["quantity_id"] for row in payload["quantities"]] == ["q1", "q2"]
    assert payload["source_sha256s"] == [SHA_A, SHA_B]
    loaded = cli.load_verified_sealed_run(out)
    assert loaded.fingerprint == payload["fingerprint"]


def test_cli_rejects_tampered_input_before_composition(tmp_path) -> None:
    q = quantity("q1", "room-1", SHA_A)
    run = seal_source_closed_run(
        [q],
        project_id="project-a",
        traces_by_quantity_id={"q1": trace("room-1", SHA_A)},
    )
    payload = json.loads(run.to_json())
    payload["quantities"][0]["value"] = 999.0
    path = tmp_path / "tampered.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(Exception, match="fingerprint mismatch"):
        cli.combine_sealed_run_files([path], project_id="project-a")


def test_cli_has_no_benchmark_truth_or_scoring_dependency() -> None:
    source = inspect.getsource(cli)
    for forbidden in (
        "reference_takeoff",
        "object_universe",
        "expected_quantity",
        "tolerance_fraction",
        "evaluate_project_v2",
    ):
        assert forbidden not in source
