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
    door_items = [
        item for item in manifest.verified_items
        if item.item_id.startswith("maryborough-door-")
    ]
    assert {item.item_id for item in door_items} == {
        "maryborough-door-ipf3-count",
        "maryborough-door-ipf3-leaf-area-one-face",
        "maryborough-door-laminex-partition-count",
        "maryborough-door-aluminium-glazed-count",
        "maryborough-door-coolroom-by-others-count",
        "maryborough-door-lessee-shelving-by-others-count",
    }

    eligible = [item for item in door_items if item.denominator_eligible]
    excluded = [item for item in door_items if not item.denominator_eligible]
    assert len(eligible) == 3
    assert len(excluded) == 3

    by_id = {item.item_id: item for item in door_items}
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
    assert universe["wc_shower_floor_surface_universe_complete"] is True
    floors = {row["object_ref"]: row for row in universe["verified_floor_surfaces"]}
    assert floors["maryborough:surface:floor:wc_shower_north"]["expected_area_m2"] == 4.7547
    assert floors["maryborough:surface:floor:wc_shower_middle"]["expected_area_m2"] == 4.7547
    assert floors["maryborough:surface:floor:wc_shower_south"]["expected_area_m2"] == 4.7547
    assert universe["wc_shower_ceiling_surface_universe_complete"] is True
    ceilings = {row["object_ref"]: row for row in universe["verified_ceiling_surfaces"]}
    assert ceilings["maryborough:surface:ceiling:wc_shower_north"]["expected_area_m2"] == 4.7547
    assert ceilings["maryborough:surface:ceiling:wc_shower_middle"]["expected_area_m2"] == 4.7547
    assert ceilings["maryborough:surface:ceiling:wc_shower_south"]["expected_area_m2"] == 4.7547
    assert floors["maryborough:surface:floor:pwd"]["expected_area_m2"] == 7.854
    assert ceilings["maryborough:surface:ceiling:pwd"]["expected_area_m2"] == 7.854
    assert floors["maryborough:surface:floor:airlock"]["expected_area_m2"] == 7.66688
    assert ceilings["maryborough:surface:ceiling:airlock"]["expected_area_m2"] == 7.66688
    assert floors["maryborough:surface:floor:laundry"]["expected_area_m2"] == 8.34782
    assert ceilings["maryborough:surface:ceiling:laundry"]["expected_area_m2"] == 8.34782
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


def test_maryborough_wc_shower_geometry_is_two_route_closed():
    ref = _json(ROOT / "au_qld_maryborough_service_station" / "reference_takeoff.json")
    checks = ref["wc_shower_floor_geometry_checks"]
    assert len(checks) == 3
    assert {row["entry_door_tag"] for row in checks} == {"D07", "D08", "D09"}
    for row in checks:
        assert row["a140_figured_mm"] == [2935, 1620]
        assert row["a140_area_m2"] == 4.7547
        assert row["agreement"] == "PASS_WITHIN_DRAWING_TOLERANCE"


def test_maryborough_wc_shower_ceiling_truth_is_closed():
    ref = _json(ROOT / "au_qld_maryborough_service_station" / "reference_takeoff.json")
    checks = ref["wc_shower_ceiling_geometry_checks"]
    assert len(checks) == 3
    for row in checks:
        assert row["a120_ceiling_finish"] == "WFPB"
        assert row["a120_ceiling_height_mm"] == 2400
        assert row["footprint_figured_mm"] == [2935, 1620]
        assert row["expected_area_m2"] == 4.7547
        assert row["agreement"] == "PASS"


def test_maryborough_pwd_floor_and_ceiling_truth_is_closed():
    ref = _json(ROOT / "au_qld_maryborough_service_station" / "reference_takeoff.json")
    check = ref["pwd_geometry_checks"]
    assert check["a502_figured_mm"] == [3570, 2200]
    assert check["area_m2"] == 7.854
    assert check["a140_floor_finish"] == "FT2"
    assert check["a120_ceiling_finish"] == "WFPB"
    assert check["a120_ceiling_height_mm"] == 2400
    assert check["agreement"] == "PASS"


def test_maryborough_airlock_laundry_truth_is_closed():
    ref = _json(ROOT / "au_qld_maryborough_service_station" / "reference_takeoff.json")
    checks = {row["room"]: row for row in ref["airlock_laundry_geometry_checks"]}
    assert checks["AIRLOCK"]["a501_figured_mm"] == [1520, 5044]
    assert checks["AIRLOCK"]["area_m2"] == 7.66688
    assert checks["LAUNDRY"]["a501_figured_mm"] == [1655, 5044]
    assert checks["LAUNDRY"]["area_m2"] == 8.34782
    for row in checks.values():
        assert row["a501_floor_finish"] == "FT2"
        assert row["a120_ceiling_finish"] == "WFPB"
        assert row["a120_ceiling_height_mm"] == 2400
        assert row["agreement"] == "PASS"


def test_maryborough_food_prep_office_family_is_scoped_and_source_closed():
    project = ROOT / "au_qld_maryborough_service_station"
    manifest = load_project_manifest(project / "source_manifest.json")
    universe = _json(project / "object_universe.json")
    manifest_json = _json(project / "source_manifest.json")

    expected_refs = {
        "maryborough:surface:floor:food_prep",
        "maryborough:surface:ceiling:food_prep",
        "maryborough:surface:floor:office",
        "maryborough:surface:ceiling:office",
    }
    expected_ids = {
        "maryborough-food-prep-ft3-floor-area",
        "maryborough-food-prep-fpb-ceiling-area",
        "maryborough-office-ft3-floor-area",
        "maryborough-office-grid-ceiling-area",
    }

    family_items = [
        item
        for item in manifest.verified_items
        if len(item.expected_object_refs) == 1
        and item.expected_object_refs[0] in expected_refs
    ]
    assert {item.item_id for item in family_items} == expected_ids
    assert {item.expected_object_refs[0] for item in family_items} == expected_refs
    assert all(item.denominator_eligible for item in family_items)
    assert all(item.unit == "m2" for item in family_items)
    assert {item.trade_category for item in family_items} == {"tiling", "ceilings"}

    objects = {
        row["object_ref"]: row
        for row in (
            universe["verified_floor_surfaces"]
            + universe["verified_ceiling_surfaces"]
        )
        if row["object_ref"] in expected_refs
    }
    assert set(objects) == expected_refs

    source_docs = {row["name"] for row in manifest_json["source_documents"]}
    for obj in objects.values():
        verification = obj["verification"]
        assert verification["object_exists"] is True
        assert verification["object_identified"] is True
        assert verification["geometry_verified"] is True
        assert verification["quantity_verified"] is True
        assert verification["fully_source_closed"] is True

        provenance = obj["provenance"]
        assert provenance["document_ref"] == (
            "Arch_Combined_Maryborough_Service_Station.pdf"
        )
        assert provenance["document_ref"] in source_docs
        assert set(provenance["source_evidence_refs"]) == set(
            obj["source_locations"]
        )
        assert all(
            any(
                evidence.startswith(sheet + ":")
                for sheet in provenance["sheet_page_refs"]
            )
            for evidence in provenance["source_evidence_refs"]
        )

    report = _json(project / "verification_report.json")
    summary = report["food_prep_office_surface_closure_summary"]
    assert set(summary["object_refs"]) == expected_refs
    assert summary["source_closed_object_count"] == 4
    assert summary["object_identity_available"] is True
    assert summary["geometry_verified"] is True
    assert summary["quantity_verified"] is True
    assert summary["provenance_chain_complete"] is True
    assert summary["project_surface_universe_complete"] is False


def test_maryborough_food_prep_truth_is_closed():
    ref = _json(ROOT / "au_qld_maryborough_service_station" / "reference_takeoff.json")
    check = ref["food_prep_geometry_check"]
    assert check["a140_figured_mm"] == [4025, 3297]
    assert check["area_m2"] == 13.270425
    assert check["a140_floor_finish"] == "FT3"
    assert check["a110_geometry_status"] == "MATCHING_PHYSICAL_ROOM"
    assert check["a120_ceiling_finish"] == "FPB"
    assert check["a120_ceiling_height_mm"] == 3000
    assert check["agreement"] == "PASS"


def test_maryborough_office_truth_is_closed():
    ref = _json(ROOT / "au_qld_maryborough_service_station" / "reference_takeoff.json")
    check = ref["office_geometry_check"]
    assert check["a140_figured_mm"] == [3570, 2536]
    assert check["area_m2"] == 9.05352
    assert check["a140_floor_finish"] == "FT3"
    assert check["a110_geometry_status"] == "MATCHING_PHYSICAL_ROOM"
    assert check["a120_ceiling_finish"] == "GRID"
    assert check["a120_ceiling_height_mm"] == 2400
    assert check["agreement"] == "PASS"
