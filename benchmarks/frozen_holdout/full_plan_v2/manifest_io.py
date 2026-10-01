"""Manifest loading for the full-plan takeoff reconciliation benchmark V2."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .evaluator import (
    ProducedTakeoffItemV2,
    ProjectBenchmarkManifestV2,
    SourceDocumentV2,
    VerifiedTakeoffItemV2,
)

SCHEMA_VERSION = "2.0"


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise TypeError(f"{path} must contain a JSON object")
    if str(data.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError(f"{path} has unsupported schema_version")
    return data


def _source_doc(raw: dict[str, Any]) -> SourceDocumentV2:
    return SourceDocumentV2(
        name=raw["name"],
        role=raw["role"],
        sha256=raw["sha256"],
        size_bytes=int(raw["size_bytes"]),
        page_count=int(raw["page_count"]),
    )
def _verified_item(raw: dict[str, Any], project_id: str) -> VerifiedTakeoffItemV2:
    return VerifiedTakeoffItemV2(
        item_id=raw["item_id"],
        project_id=project_id,
        description=raw["description"],
        unit=raw["unit"],
        expected_quantity=float(raw["expected_quantity"]),
        tolerance_fraction=float(raw["tolerance_fraction"]),
        expected_object_refs=tuple(raw.get("expected_object_refs") or ()),
        denominator_eligible=bool(raw.get("denominator_eligible", True)),
        verification_status=str(raw.get("verification_status") or "VERIFIED"),
    )


def load_project_manifest(path: Path) -> ProjectBenchmarkManifestV2:
    raw = _load_json(path)
    project_id = str(raw["project_id"])
    return ProjectBenchmarkManifestV2(
        project_id=project_id,
        status=str(raw["status"]),
        source_documents=tuple(_source_doc(value) for value in raw.get("source_documents", ())),
        reference_takeoff_documents=tuple(
            _source_doc(value) for value in raw.get("reference_takeoff_documents", ())
        ),
        verified_items=tuple(
            _verified_item(value, project_id) for value in raw.get("verified_takeoff_items", ())
        ),
        reason_codes=tuple(raw.get("reason_codes") or ()),
    )


def load_suite_manifests(root: Path) -> tuple[ProjectBenchmarkManifestV2, ...]:
    suite = _load_json(root / "manifest.json")
    project_ids = tuple(str(value) for value in suite.get("projects", ()))
    required = int(suite.get("required_project_count", 0))
    if required <= 0 or len(project_ids) != required:
        raise ValueError("suite project list must exactly equal required_project_count")
    if len(set(project_ids)) != len(project_ids):
        raise ValueError("suite project ids must be unique")
    manifests = []
    for project_id in project_ids:
        path = root / "projects" / project_id / "source_manifest.json"
        manifest = load_project_manifest(path)
        if manifest.project_id != project_id:
            raise ValueError(f"project manifest identity mismatch: {project_id}")
        manifests.append(manifest)
    return tuple(manifests)


def load_produced_items(path: Path) -> tuple[ProducedTakeoffItemV2, ...]:
    if not path.exists():
        return ()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise TypeError(f"{path} must contain a JSON list")
    return tuple(
        ProducedTakeoffItemV2(
            quantity_id=value["quantity_id"],
            value=None if value.get("value") is None else float(value["value"]),
            unit=value["unit"],
            object_refs=tuple(value.get("object_refs") or ()),
            lineage_ok=bool(value.get("lineage_ok", True)),
            abstained=bool(value.get("abstained", False)),
        )
        for value in raw
    )
