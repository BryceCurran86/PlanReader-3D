from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pytest

_FROZEN_ROOT = Path(__file__).resolve().parents[2] / "benchmarks" / "frozen_holdout"
sys.path.insert(0, str(_FROZEN_ROOT))

from full_plan_v2.manifest_io import load_project_manifest

ROOT = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "projects"
)
PROJECT_ID = "au_qld_3laurel"


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_3laurel_primary_ceiling_truth_is_atomic_and_source_closed():
    project = ROOT / PROJECT_ID
    manifest = load_project_manifest(project / "source_manifest.json")

    assert manifest.status == "INCOMPLETE"
    assert len(manifest.verified_items) == 30

    ceilings = [
        item for item in manifest.verified_items
        if item.trade_category == "ceilings"
    ]
    assert len(ceilings) == 7
    assert all(item.denominator_eligible for item in ceilings)
    assert all(item.unit == "m2" for item in ceilings)
    assert all(len(item.expected_object_refs) == 1 for item in ceilings)
    assert all(item.source_document_refs == ("reference_takeoff.json",) for item in ceilings)
    assert sum(item.expected_quantity for item in ceilings) == pytest.approx(297.5)

    universe = _json(project / "object_universe.json")
    planes = universe["primary_ceiling_planes"]
    assert len(planes) == 7
    assert {row["object_ref"] for row in planes} == {
        item.expected_object_refs[0] for item in ceilings
    }
    assert universe["primary_ceiling_plane_universe_complete"] is True

    ref = manifest.reference_takeoff_documents[0]
    ref_path = project / ref.name
    assert _sha256(ref_path) == ref.sha256
    assert ref_path.stat().st_size == ref.size_bytes


def test_3laurel_primary_ceiling_reconciliation_is_exact():
    project = ROOT / PROJECT_ID
    ref = _json(project / "reference_takeoff.json")
    closure = ref["primary_ceiling_reconciliation"]

    assert closure["closure_check_id"] == "3laurel:closure:primary_ceiling_planes"
    assert len(closure["component_object_refs"]) == 7
    assert closure["component_sum_m2"] == pytest.approx(297.5)
    assert closure["declared_reference_plan_area_m2"] == pytest.approx(297.5)
    assert closure["difference_m2"] == pytest.approx(0.0)
    assert closure["primary_ceiling_universe_complete"] is True


def test_3laurel_secondary_ceiling_faces_remain_fail_closed():
    project = ROOT / PROJECT_ID
    unresolved = _json(project / "unresolved_items.json")
    by_family = {row["family"]: row for row in unresolved["items"]}
    assert by_family["secondary_fc_soffit_and_beam_faces"]["status"] == "UNRESOLVED"

    report = _json(project / "verification_report.json")
    summary = report["primary_ceiling_closure_summary"]
    assert summary["verified_ceiling_plane_count"] == 7
    assert summary["verified_area_m2"] == pytest.approx(297.5)
    assert summary["primary_ceiling_universe_complete"] is True
    assert summary["secondary_fc_soffit_and_beam_faces_complete"] is False

    proofs = {row["proof"]: row for row in report["proofs"]}
    assert proofs["primary ceiling planes source-closed"]["status"] == "PASS"
    assert proofs["full project surface universe complete"]["status"] == "FAIL"
