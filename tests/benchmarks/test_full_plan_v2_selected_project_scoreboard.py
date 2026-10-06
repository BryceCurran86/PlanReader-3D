from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys

import pytest

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import seal_source_closed_run

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "run_selected_project_scoreboard.py"
)
_SPEC = importlib.util.spec_from_file_location(
    "full_plan_v2_selected_project_scoreboard",
    _MODULE_PATH,
)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = _MODULE
_SPEC.loader.exec_module(_MODULE)

score_selected_projects = _MODULE.score_selected_projects


def _sha(project_id: str) -> str:
    return (project_id.encode("utf-8").hex() * 64)[:64].ljust(64, "a")


def _write_manifest(root: Path, project_id: str, expected: float) -> None:
    sha = _sha(project_id)
    project_dir = root / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "2.0",
        "project_id": project_id,
        "status": "VERIFIED",
        "source_package_complete": True,
        "source_documents": [{
            "name": f"{project_id}.pdf",
            "role": "architectural_drawings",
            "sha256": sha,
            "size_bytes": 100,
            "page_count": 1,
        }],
        "reference_takeoff_documents": [{
            "name": f"{project_id}-reference.json",
            "role": "independent_verified_reference_takeoff",
            "sha256": sha,
            "size_bytes": 100,
            "page_count": 1,
        }],
        "reason_codes": ["synthetic_truth_expansion_in_progress"],
        "verified_takeoff_items": [{
            "item_id": f"{project_id}-floor",
            "description": "Verified floor area",
            "trade_category": "tiling",
            "unit": "m2",
            "expected_quantity": expected,
            "tolerance_policy_id": "relative-tolerance-v1",
            "tolerance_fraction": 0.0,
            "expected_object_refs": [f"{project_id}:floor"],
            "source_document_refs": [f"{project_id}-reference.json"],
            "source_location_refs": ["sheet:A100:room"],
            "denominator_eligible": True,
            "verification_status": "VERIFIED",
        }],
    }
    (project_dir / "source_manifest.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _write_sealed(
    sealed_dir: Path,
    *,
    project_id: str,
    value: float,
) -> None:
    sha = _sha(project_id)
    entity_id = f"canonical-floor-{project_id}"
    quantity = QuantityEvidence(
        quantity_id=f"qty-{project_id}",
        family="room_area",
        semantic_key=f"room_area:{entity_id}",
        value=value,
        unit="m2",
        input_entity_ids=(entity_id,),
        formula="figured",
        formula_version="1",
        evidence_ids=(f"ev-{project_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        metadata={
            "document_id": f"doc-{project_id}",
            "source_sha256": sha,
            "revision_id": f"rev-{project_id}",
        },
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id=project_id,
        document_id=f"doc-{project_id}",
        source_sha256=sha,
        source_page="1",
        viewport_id=f"vp-{project_id}",
        revision_id=f"rev-{project_id}",
        current_revision_id=f"rev-{project_id}",
        evidence_ids=quantity.evidence_ids,
        canonical_entity_ids=quantity.input_entity_ids,
    )
    run = seal_source_closed_run(
        (quantity,),
        project_id=project_id,
        traces_by_quantity_id={quantity.quantity_id: trace},
    )
    sealed_dir.mkdir(parents=True, exist_ok=True)
    (sealed_dir / f"{project_id}.json").write_text(
        run.to_json(),
        encoding="utf-8",
    )


def _write_identity_map(identity_dir: Path, project_id: str) -> None:
    identity_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "1.0.0",
        "project_id": project_id,
        "source_sha256s": [_sha(project_id)],
        "bindings": [{
            "benchmark_item_id": f"{project_id}-floor",
            "production_object_identity_refs": [
                f"canonical-floor-{project_id}"
            ],
            "production_family": "room_area",
        }],
    }
    (identity_dir / f"{project_id}.identity_map.json").write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _fixture(tmp_path: Path):
    root = tmp_path / "full_plan_v2"
    sealed = tmp_path / "sealed"
    identities = tmp_path / "identities"
    for project_id, value in (("p1", 10.0), ("p2", 20.0)):
        _write_manifest(root, project_id, value)
        _write_sealed(sealed, project_id=project_id, value=value)
        _write_identity_map(identities, project_id)
    return root, sealed, identities


def test_selected_project_scoreboard_reports_complete_two_project_score(
    tmp_path,
) -> None:
    root, sealed, identities = _fixture(tmp_path)

    score, ledger = score_selected_projects(
        root=root,
        project_ids=("p1", "p2"),
        sealed_dir=sealed,
        identity_map_dir=identities,
    )

    assert score.status == "COMPLETE_CURRENT_TRUTH_SET"
    assert score.configured_projects == 2
    assert score.executed_projects == 2
    assert score.source_closed_truth_items == 2
    assert score.executed_denominator == 2
    assert score.matched_within_tolerance == 2
    assert score.matched_outside_tolerance == 0
    assert score.missed == 0
    assert score.partial == 0
    assert score.unresolved == 0
    assert score.hallucinations == 0
    assert score.development_accuracy == pytest.approx(1.0)
    assert score.precision_adjusted_accuracy == pytest.approx(1.0)
    assert ledger.failure_items == ()
    assert ledger.unsupported_outputs == ()
    assert ledger.missing_execution_project_ids == ()


def test_selected_project_scoreboard_requires_every_selected_sealed_run(
    tmp_path,
) -> None:
    root, sealed, identities = _fixture(tmp_path)
    (sealed / "p2.json").unlink()

    with pytest.raises(
        FileNotFoundError,
        match="selected project sealed run is missing",
    ):
        score_selected_projects(
            root=root,
            project_ids=("p1", "p2"),
            sealed_dir=sealed,
            identity_map_dir=identities,
        )


def test_selected_project_scoreboard_rejects_duplicate_project_ids(
    tmp_path,
) -> None:
    root, sealed, identities = _fixture(tmp_path)

    with pytest.raises(ValueError, match="project_ids must be unique"):
        score_selected_projects(
            root=root,
            project_ids=("p1", "p1"),
            sealed_dir=sealed,
            identity_map_dir=identities,
        )


def test_selected_project_scoreboard_cli_writes_score_and_failure_ledger(
    tmp_path,
) -> None:
    root, sealed, identities = _fixture(tmp_path)
    output = tmp_path / "score.json"
    ledger = tmp_path / "ledger.json"

    assert _MODULE.main([
        "--root", str(root),
        "--project-id", "p1",
        "--project-id", "p2",
        "--sealed-dir", str(sealed),
        "--identity-map-dir", str(identities),
        "--output", str(output),
        "--failure-ledger-output", str(ledger),
    ]) == 0

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["configured_projects"] == 2
    assert payload["source_closed_truth_items"] == 2
    assert payload["matched_within_tolerance"] == 2
    assert payload["development_accuracy"] == pytest.approx(1.0)
    assert payload["precision_adjusted_accuracy"] == pytest.approx(1.0)

    failure_payload = json.loads(ledger.read_text(encoding="utf-8"))
    assert failure_payload["failure_items"] == []
    assert failure_payload["unsupported_outputs"] == []
    assert failure_payload["missing_execution_project_ids"] == []
