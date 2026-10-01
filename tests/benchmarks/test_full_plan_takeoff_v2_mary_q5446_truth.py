from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

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


def _json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_reference_hash(project_id: str):
    project = ROOT / project_id
    manifest = _json(project / "source_manifest.json")
    ref = manifest["reference_takeoff_documents"][0]
    path = project / ref["name"]
    assert _sha256(path) == ref["sha256"]
    assert path.stat().st_size == ref["size_bytes"]


def test_maryborough_verified_door_core_is_exact_and_project_stays_incomplete():
    project = ROOT / "au_qld_maryborough_service_station"
    manifest = load_project_manifest(project / "source_manifest.json")
    assert manifest.status == "INCOMPLETE"
    assert len(manifest.reference_takeoff_documents) == 1
    assert len(manifest.verified_items) == 7

    eligible = [item for item in manifest.verified_items if item.denominator_eligible]
    excluded = [item for item in manifest.verified_items if not item.denominator_eligible]
    assert len(eligible) == 4
    assert len(excluded) == 3

    by_id = {item.item_id: item for item in manifest.verified_items}
    assert by_id["maryborough-door-ipf3-count"].expected_quantity == 11
    assert by_id["maryborough-door-ipf3-leaf-area-one-face"].expected_quantity == 20.2368
    assert not by_id["maryborough-door-ipf3-leaf-area-one-face"].denominator_eligible
    assert by_id["maryborough-door-laminex-partition-count"].expected_quantity == 3
    assert by_id["maryborough-door-aluminium-glazed-count"].expected_quantity == 2
    assert by_id["maryborough-door-coolroom-by-others-count"].expected_quantity == 2
    assert (
        by_id["maryborough-door-lessee-shelving-by-others-count"].expected_quantity
        == 10
    )

    universe = _json(project / "object_universe.json")
    doors = universe["doors"]
    assert len(doors) == 28
    assert {door["source_tag"] for door in doors} == {
        f"D{i:02d}" for i in range(1, 29)
    }

    class_counts = {}
    for door in doors:
        class_counts[door["door_class"]] = (
            class_counts.get(door["door_class"], 0) + 1
        )
    assert class_counts == {
        "aluminium_glazed": 2,
        "by_others_coolroom": 2,
        "by_others_lessee_shelving": 10,
        "laminex_partition": 3,
        "painted_ipf3": 11,
    }
    assert sum(class_counts.values()) == 28
    assert universe["window_identity_universe_complete"] is True
    assert universe["window_area_universe_complete"] is False
    assert {row["source_tag"] for row in universe["windows"]} == {"W01", "W02", "W03", "W04", "W05", "W06"}
    _assert_reference_hash("au_qld_maryborough_service_station")


def test_q5446_only_independently_closed_alfresco_enters_verified_core():
    project = ROOT / "au_qld_q5446_armstrong32_harlequin"
    manifest = load_project_manifest(project / "source_manifest.json")
    assert manifest.status == "INCOMPLETE"
    assert len(manifest.reference_takeoff_documents) == 1
    assert len(manifest.verified_items) == 5

    item = manifest.verified_items[0]
    assert item.item_id == "q5446-alfresco-floor-area"
    assert item.expected_quantity == 12.0
    assert item.unit == "m2"
    assert item.expected_object_refs == ("q5446:surface:floor:alfresco",)

    by_id = {row.item_id: row for row in manifest.verified_items}
    assert by_id["q5446-ground-ensuite-floor-tiling-area"].expected_quantity == 4.2224
    assert by_id["q5446-first-ensuite-floor-tiling-area"].expected_quantity == 5.9572
    assert by_id["q5446-first-bath-floor-tiling-area"].expected_quantity == 5.8446
    assert by_id["q5446-ground-laundry-floor-tiling-area"].expected_quantity == 4.1864

    ref = _json(project / "reference_takeoff.json")
    controls = {
        row["name"]: row for row in ref["declared_area_controls_not_truth"]
    }
    assert set(controls) == {
        "ground_floor",
        "first_floor",
        "porch",
        "garage",
        "total",
    }
    assert controls["garage"]["quantity_m2"] == 36.40
    assert controls["total"]["quantity_m2"] == 298.19
    assert len(ref["independent_geometry_checks"]) == 4
    _assert_reference_hash("au_qld_q5446_armstrong32_harlequin")


def test_verified_items_have_exact_refs_reference_doc_and_lineage():
    for project_id in (
        "au_qld_maryborough_service_station",
        "au_qld_q5446_armstrong32_harlequin",
    ):
        project = ROOT / project_id
        manifest = load_project_manifest(project / "source_manifest.json")
        assert manifest.status == "INCOMPLETE"
        for item in manifest.verified_items:
            assert item.verification_status == "VERIFIED"
            assert item.expected_object_refs
            assert item.source_document_refs == ("reference_takeoff.json",)
            assert item.source_location_refs
            assert item.tolerance_policy_id == "relative-tolerance-v1"
            assert item.tolerance_fraction == 0.05


def test_verification_reports_fail_closed_on_full_project_completeness():
    for project_id in (
        "au_qld_maryborough_service_station",
        "au_qld_q5446_armstrong32_harlequin",
    ):
        report = _json(ROOT / project_id / "verification_report.json")
        assert report["project_status"] == "INCOMPLETE"
        assert report["source_hash_verification"]["status"] == "PASS"
        proof = {row["proof"]: row for row in report["proofs"]}
        assert proof["PlanReader output not used as benchmark truth"]["status"] == "PASS"
        assert proof["full project surface universe complete"]["status"] == "FAIL"


def test_q5446_area_closure_audit_stays_fail_closed():
    report = _json(ROOT / "au_qld_q5446_armstrong32_harlequin" / "verification_report.json")
    checks = {row["object_ref"]: row for row in report["measurement_closure_checks"]}
    assert checks["q5446:surface:floor:alfresco"]["status"] == "PASS"
    assert checks["q5446:surface:floor:ground_laundry"]["status"] == "PASS"
    assert checks["q5446:candidate:garage"]["status"] == "UNRESOLVED"
    assert checks["q5446:candidate:porch"]["status"] == "UNRESOLVED"
    assert checks["q5446:candidate:ground_floor"]["status"] == "UNRESOLVED"
    assert checks["q5446:candidate:first_floor"]["status"] == "UNRESOLVED"
