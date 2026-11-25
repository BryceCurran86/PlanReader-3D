"""Tests for manifest-driven external source-PDF and identity-map bundle inventory."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz
import pytest

import pb_source_bundle_inventory as sbi
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _make_pdf(path: Path, *, pages: int = 1, text: str = "SHEET") -> tuple[str, int]:
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = fitz.open()
    for idx in range(pages):
        page = doc.new_page(width=200, height=200)
        page.insert_text((20, 40), f"{text} {idx + 1}")
    data = doc.tobytes()
    doc.close()
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest(), len(data)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _build_synthetic_suite(
    tmp_path: Path,
    *,
    layout: str = "flat",
    map_refs_override: list[dict] | None = None,
) -> tuple[Path, Path, Path, dict[str, str]]:
    suite_root = tmp_path / "suite"
    source_dir = tmp_path / "private_secret_sources"
    map_dir = tmp_path / "private_secret_maps"
    source_dir.mkdir(parents=True, exist_ok=True)
    map_dir.mkdir(parents=True, exist_ok=True)

    pdf_a_name = "secret_alpha_arch_plan.pdf"
    pdf_b1_name = "secret_beta_floor_plan.pdf"
    pdf_b2_name = "secret_beta_schedule.pdf"

    if layout == "flat":
        sha_a, size_a = _make_pdf(source_dir / pdf_a_name, pages=2, text="ALPHA")
        sha_b1, size_b1 = _make_pdf(source_dir / pdf_b1_name, pages=1, text="BETA1")
        sha_b2, size_b2 = _make_pdf(source_dir / pdf_b2_name, pages=3, text="BETA2")
    elif layout == "project_scoped":
        sha_a, size_a = _make_pdf(source_dir / "proj_alpha" / pdf_a_name, pages=2, text="ALPHA")
        sha_b1, size_b1 = _make_pdf(source_dir / "proj_beta" / pdf_b1_name, pages=1, text="BETA1")
        sha_b2, size_b2 = _make_pdf(source_dir / "proj_beta" / pdf_b2_name, pages=3, text="BETA2")
    elif layout == "both_identical":
        sha_a, size_a = _make_pdf(source_dir / pdf_a_name, pages=2, text="ALPHA")
        (source_dir / "proj_alpha").mkdir(parents=True, exist_ok=True)
        (source_dir / "proj_alpha" / pdf_a_name).write_bytes((source_dir / pdf_a_name).read_bytes())
        sha_b1, size_b1 = _make_pdf(source_dir / pdf_b1_name, pages=1, text="BETA1")
        sha_b2, size_b2 = _make_pdf(source_dir / pdf_b2_name, pages=3, text="BETA2")
    else:
        raise AssertionError(layout)

    _write_json(
        suite_root / "manifest.json",
        {
            "schema_version": "2.0",
            "benchmark_id": "synthetic_suite_v2",
            "required_project_count": 2,
            "projects": ["proj_alpha", "proj_beta"],
        },
    )
    _write_json(
        suite_root / "projects" / "proj_alpha" / "source_manifest.json",
        {
            "schema_version": "2.0",
            "project_id": "proj_alpha",
            "status": "VERIFIED",
            "source_package_complete": True,
            "source_documents": [
                {
                    "name": pdf_a_name,
                    "role": "architectural_plans",
                    "sha256": sha_a,
                    "size_bytes": size_a,
                    "page_count": 2,
                }
            ],
            "reference_takeoff_documents": [
                {
                    "name": "alpha_ref_boq.pdf",
                    "role": "reference_takeoff",
                    "sha256": "a" * 64,
                    "size_bytes": 100,
                    "page_count": 1,
                }
            ],
            "verified_takeoff_items": [
                {
                    "item_id": "alpha-floor-01",
                    "description": "Main room floor area",
                    "trade_category": "floor_area",
                    "unit": "m2",
                    "expected_quantity": 25.0,
                    "tolerance_policy_id": "area_2pct",
                    "tolerance_fraction": 0.02,
                    "expected_object_refs": ["room:alpha:main"],
                    "source_document_refs": ["alpha_ref_boq.pdf"],
                    "source_location_refs": ["page-1"],
                    "denominator_eligible": True,
                },
                {
                    "item_id": "alpha-non-denom-02",
                    "description": "Informational note",
                    "trade_category": "floor_area",
                    "unit": "m2",
                    "expected_quantity": 5.0,
                    "tolerance_policy_id": "area_2pct",
                    "tolerance_fraction": 0.02,
                    "expected_object_refs": [],
                    "denominator_eligible": False,
                },
            ],
        },
    )
    _write_json(
        suite_root / "projects" / "proj_beta" / "source_manifest.json",
        {
            "schema_version": "2.0",
            "project_id": "proj_beta",
            "status": "VERIFIED",
            "source_package_complete": True,
            "source_documents": [
                {
                    "name": pdf_b1_name,
                    "role": "architectural_plans",
                    "sha256": sha_b1,
                    "size_bytes": size_b1,
                    "page_count": 1,
                },
                {
                    "name": pdf_b2_name,
                    "role": "door_schedule",
                    "sha256": sha_b2,
                    "size_bytes": size_b2,
                    "page_count": 3,
                },
            ],
            "reference_takeoff_documents": [
                {
                    "name": "beta_ref_boq.pdf",
                    "role": "reference_takeoff",
                    "sha256": "b" * 64,
                    "size_bytes": 100,
                    "page_count": 1,
                }
            ],
            "verified_takeoff_items": [
                {
                    "item_id": "beta-door-01",
                    "description": "Entry door area",
                    "trade_category": "opening_area",
                    "unit": "m2",
                    "expected_quantity": 2.1,
                    "tolerance_policy_id": "opening_2pct",
                    "tolerance_fraction": 0.02,
                    "expected_object_refs": ["opening:beta:d1"],
                    "source_document_refs": ["beta_ref_boq.pdf"],
                    "source_location_refs": ["page-1"],
                    "denominator_eligible": True,
                },
                {
                    "item_id": "beta-ceil-01",
                    "description": "Main ceiling area",
                    "trade_category": "ceiling_lining",
                    "unit": "m2",
                    "expected_quantity": 25.0,
                    "tolerance_policy_id": "area_2pct",
                    "tolerance_fraction": 0.02,
                    "expected_object_refs": ["ceiling:beta:main"],
                    "source_document_refs": ["beta_ref_boq.pdf"],
                    "source_location_refs": ["page-1"],
                    "denominator_eligible": True,
                },
            ],
        },
    )

    _write_json(
        map_dir / "proj_alpha.identity_map.json",
        {
            "schema_version": "1.0.0",
            "project_id": "proj_alpha",
            "source_sha256s": [sha_a],
            "bindings": map_refs_override
            if map_refs_override is not None
            else [
                {
                    "benchmark_item_id": "alpha-floor-01",
                    "production_family": "floor_area",
                    "production_object_identity_refs": ["secret_private_entity_alpha_001"],
                }
            ],
        },
    )
    _write_json(
        map_dir / "proj_beta.identity_map.json",
        {
            "schema_version": "1.0.0",
            "project_id": "proj_beta",
            "source_sha256s": [sha_b1, sha_b2],
            "bindings": [
                {
                    "benchmark_item_id": "beta-door-01",
                    "production_family": "opening_area",
                    "production_object_identity_refs": ["secret_private_entity_beta_001"],
                },
                {
                    "benchmark_item_id": "beta-ceil-01",
                    "production_family": "ceiling_lining",
                    "production_object_identity_refs": ["secret_private_entity_beta_002"],
                },
            ],
        },
    )
    return suite_root, source_dir, map_dir, {
        "sha_a": sha_a,
        "sha_b1": sha_b1,
        "sha_b2": sha_b2,
        "pdf_a_name": pdf_a_name,
        "pdf_b1_name": pdf_b1_name,
        "pdf_b2_name": pdf_b2_name,
    }


@pytest.mark.parametrize("layout", ["flat", "project_scoped", "both_identical"])
def test_verify_complete_bundle_and_public_safe_receipt(tmp_path: Path, layout: str) -> None:
    suite_root, source_dir, map_dir, meta = _build_synthetic_suite(tmp_path, layout=layout)

    first = sbi.verify_benchmark_input_bundle(
        suite_root=suite_root,
        source_dir=source_dir,
        identity_map_dir=map_dir,
    )
    second = sbi.verify_benchmark_input_bundle(
        suite_root=suite_root,
        source_dir=source_dir,
        identity_map_dir=map_dir,
    )

    assert first.status == "READY"
    assert first.is_score_or_replay_result is False
    assert first.reason_codes == ()
    assert first.receipt_sha256 == second.receipt_sha256
    assert first.source_inventory.status == "COMPLETE_VERIFIED"
    assert first.source_inventory.verified_project_count == 2
    assert first.source_inventory.verified_document_count == 3
    assert first.source_inventory.unexpected_pdf_count == 0
    assert first.identity_maps.status == "ALL_MAPS_VALID"
    assert first.identity_maps.valid_project_count == 2
    assert first.identity_maps.total_denominator_items == 3
    assert first.identity_maps.total_bound_items == 3
    assert first.source_inventory.documents[0].matched_layout == layout

    # Public-safe serialization must never leak private paths, PDF names, or raw entity refs.
    safe_blob = json.dumps(first.to_safe_dict(), sort_keys=True)
    assert str(source_dir) not in safe_blob
    assert str(map_dir) not in safe_blob
    assert "private_secret_sources" not in safe_blob
    assert "private_secret_maps" not in safe_blob
    assert meta["pdf_a_name"] not in safe_blob
    assert meta["pdf_b1_name"] not in safe_blob
    assert "secret_private_entity_" not in safe_blob


def test_source_bundle_detects_missing_size_sha_page_and_corrupt_mismatches(tmp_path: Path) -> None:
    suite_root, source_dir, _, meta = _build_synthetic_suite(tmp_path, layout="flat")

    # 1. Missing PDF
    pdf_a = source_dir / meta["pdf_a_name"]
    original_a_bytes = pdf_a.read_bytes()
    pdf_a.unlink()
    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "MISSING"
    assert "source_document_missing" in receipt.reason_codes

    # 2. Size mismatch
    pdf_a.write_bytes(original_a_bytes + b"extra")
    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "SIZE_MISMATCH"
    assert "source_document_size_mismatch" in receipt.reason_codes

    # 3. Same size, different SHA-256
    flipped = bytearray(original_a_bytes)
    flipped[-1] ^= 0xFF
    pdf_a.write_bytes(bytes(flipped))
    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "SHA256_MISMATCH"
    assert "source_document_sha256_mismatch" in receipt.reason_codes

    # 4. Page-count mismatch when manifest expects 99 pages
    pdf_a.write_bytes(original_a_bytes)
    manifest_a = suite_root / "projects" / "proj_alpha" / "source_manifest.json"
    raw = json.loads(manifest_a.read_text(encoding="utf-8"))
    raw["source_documents"][0]["page_count"] = 99
    _write_json(manifest_a, raw)
    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "PAGE_COUNT_MISMATCH"
    assert receipt.documents[0].actual_page_count == 2

    # 5. Unreadable non-PDF bytes matching manifest size+sha when page check is enabled
    corrupt = b"NOT_A_REAL_PDF_FILE_BYTES"
    pdf_a.write_bytes(corrupt)
    raw["source_documents"][0]["size_bytes"] = len(corrupt)
    raw["source_documents"][0]["sha256"] = hashlib.sha256(corrupt).hexdigest()
    raw["source_documents"][0]["page_count"] = 1
    _write_json(manifest_a, raw)
    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "UNREADABLE"


def test_source_bundle_rejects_conflicting_flat_and_scoped_copies(tmp_path: Path) -> None:
    suite_root, source_dir, _, meta = _build_synthetic_suite(tmp_path, layout="flat")
    scoped = source_dir / "proj_alpha" / meta["pdf_a_name"]
    _make_pdf(scoped, pages=2, text="DIFFERENT")

    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "CONFLICTING_DUPLICATE"
    assert "conflicting_flat_and_project_scoped_source_copies" in receipt.reason_codes


def test_source_bundle_counts_and_strictly_rejects_unexpected_pdfs(tmp_path: Path) -> None:
    suite_root, source_dir, _, _ = _build_synthetic_suite(tmp_path, layout="flat")
    _make_pdf(source_dir / "stray_extra_plan.pdf", pages=1, text="EXTRA")

    permissive = sbi.verify_source_bundle_inventory(
        suite_root=suite_root,
        source_dir=source_dir,
        strict_no_unexpected_pdfs=False,
    )
    assert permissive.status == "COMPLETE_VERIFIED"
    assert permissive.unexpected_pdf_count == 1
    assert "stray_extra_plan.pdf" not in json.dumps(permissive.to_safe_dict())

    strict = sbi.verify_source_bundle_inventory(
        suite_root=suite_root,
        source_dir=source_dir,
        strict_no_unexpected_pdfs=True,
    )
    assert strict.status == "INCOMPLETE_OR_FAILED"
    assert "unexpected_pdf_files_present" in strict.reason_codes


def test_symlink_rejection_for_directories_and_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    suite_root, source_dir, map_dir, meta = _build_synthetic_suite(tmp_path, layout="flat")
    pdf_a = source_dir / meta["pdf_a_name"]
    map_a = map_dir / "proj_alpha.identity_map.json"

    real_is_symlink = Path.is_symlink

    monkeypatch.setattr(Path, "is_symlink", lambda self: self == source_dir or real_is_symlink(self))
    with pytest.raises(ValueError, match="source_dir_symlink_rejected"):
        sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)

    monkeypatch.setattr(Path, "is_symlink", lambda self: self == pdf_a or real_is_symlink(self))
    receipt = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert receipt.status == "INCOMPLETE_OR_FAILED"
    assert receipt.documents[0].status == "SYMLINK_REJECTED"

    monkeypatch.setattr(Path, "is_symlink", lambda self: self == map_a or real_is_symlink(self))
    map_receipt = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert map_receipt.status == "INCOMPLETE_OR_INVALID"
    assert map_receipt.projects[0].status == "SYMLINK_REJECTED"


def test_identity_map_audit_detects_missing_unknown_partial_hash_and_shared_atoms(
    tmp_path: Path,
) -> None:
    suite_root, _, map_dir, meta = _build_synthetic_suite(tmp_path, layout="flat")

    # 1. Missing map
    map_a = map_dir / "proj_alpha.identity_map.json"
    saved_a = map_a.read_bytes()
    map_a.unlink()
    res = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert res.status == "INCOMPLETE_OR_INVALID"
    assert res.projects[0].status == "MISSING"

    # 2. Invalid JSON with NaN
    map_a.write_text('{"schema_version": "1.0.0", "x": NaN}', encoding="utf-8")
    res = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert res.projects[0].status == "INVALID_JSON"

    # 3. Binding to a non-denominator item fails closed
    _write_json(
        map_a,
        {
            "schema_version": "1.0.0",
            "project_id": "proj_alpha",
            "source_sha256s": [meta["sha_a"]],
            "bindings": [
                {
                    "benchmark_item_id": "alpha-non-denom-02",
                    "production_family": "floor_area",
                    "production_object_identity_refs": ["ref_non_denom"],
                }
            ],
        },
    )
    res = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert res.status == "INCOMPLETE_OR_INVALID"
    assert "identity_map_unknown_denominator_item" in res.projects[0].reason_codes

    # 4. Partial source hash coverage fails when require_all_source_hashes=True, passes when False
    map_a.write_bytes(saved_a)
    map_b = map_dir / "proj_beta.identity_map.json"
    raw_b = json.loads(map_b.read_text(encoding="utf-8"))
    raw_b["source_sha256s"] = [meta["sha_b1"]]
    _write_json(map_b, raw_b)
    res_strict = sbi.verify_identity_map_bundle(
        suite_root=suite_root, identity_map_dir=map_dir, require_all_source_hashes=True,
    )
    assert res_strict.status == "INCOMPLETE_OR_INVALID"
    assert "identity_map_incomplete_source_sha256_coverage" in res_strict.projects[1].reason_codes

    res_subset = sbi.verify_identity_map_bundle(
        suite_root=suite_root, identity_map_dir=map_dir, require_all_source_hashes=False,
    )
    assert res_subset.status == "ALL_MAPS_VALID"
    assert res_subset.projects[1].covered_source_hash_count == 1
    assert res_subset.projects[1].expected_source_hash_count == 2

    # 5. Shared production ref atom across two different families detected & optionally rejected
    raw_b["source_sha256s"] = [meta["sha_b1"], meta["sha_b2"]]
    raw_b["bindings"][1]["production_object_identity_refs"] = ["secret_private_entity_beta_001"]
    _write_json(map_b, raw_b)
    res_report = sbi.verify_identity_map_bundle(
        suite_root=suite_root, identity_map_dir=map_dir, reject_shared_ref_atoms=False,
    )
    assert res_report.status == "ALL_MAPS_VALID"
    assert res_report.projects[1].shared_ref_tuple_count == 1
    assert res_report.projects[1].shared_ref_atom_count == 1

    res_reject = sbi.verify_identity_map_bundle(
        suite_root=suite_root, identity_map_dir=map_dir, reject_shared_ref_atoms=True,
    )
    assert res_reject.status == "INCOMPLETE_OR_INVALID"
    assert "identity_map_shared_production_ref_atom" in res_reject.projects[1].reason_codes


def test_resolve_bundle_directories_precedence_and_fail_closed(tmp_path: Path) -> None:
    cfg = tmp_path / "bundle.json"
    _write_json(
        cfg,
        {
            "source_dir": str(tmp_path / "cfg_src"),
            "identity_map_dir": str(tmp_path / "cfg_maps"),
        },
    )
    env = {
        sbi.ENV_SOURCE_DIR: str(tmp_path / "env_src"),
        sbi.ENV_IDENTITY_MAP_DIR: str(tmp_path / "env_maps"),
    }

    # Explicit overrides config and env
    src, maps = sbi.resolve_bundle_directories(
        source_dir=tmp_path / "arg_src",
        identity_map_dir=tmp_path / "arg_maps",
        config_path=cfg,
        env=env,
    )
    assert src == tmp_path / "arg_src"
    assert maps == tmp_path / "arg_maps"

    # Config overrides env
    src, maps = sbi.resolve_bundle_directories(config_path=cfg, env=env)
    assert src == tmp_path / "cfg_src"
    assert maps == tmp_path / "cfg_maps"

    # Env works when config omitted
    src, maps = sbi.resolve_bundle_directories(env=env)
    assert src == tmp_path / "env_src"
    assert maps == tmp_path / "env_maps"

    # Missing identity_map_dir fails closed even if default_source_dir is given
    with pytest.raises(ValueError, match="identity_map_dir_not_configured"):
        sbi.resolve_bundle_directories(env={}, default_source_dir=tmp_path / "fallback_src")

    # Unknown config key fails closed
    bad_cfg = tmp_path / "bad.json"
    _write_json(bad_cfg, {"source_dir": "a", "identity_map_dir": "b", "unexpected": "c"})
    with pytest.raises(ValueError, match="bundle_config_unknown_key"):
        sbi.resolve_bundle_directories(config_path=bad_cfg, env={})


def test_identity_map_project_mismatch_unknown_hash_and_duplicate_item(tmp_path: Path) -> None:
    suite_root, _, map_dir, meta = _build_synthetic_suite(tmp_path, layout="flat")
    map_a = map_dir / "proj_alpha.identity_map.json"

    # Wrong project_id
    _write_json(
        map_a,
        {
            "schema_version": "1.0.0",
            "project_id": "proj_beta",
            "source_sha256s": [meta["sha_a"]],
            "bindings": [
                {
                    "benchmark_item_id": "alpha-floor-01",
                    "production_family": "floor_area",
                    "production_object_identity_refs": ["ref_a"],
                }
            ],
        },
    )
    res = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert res.status == "INCOMPLETE_OR_INVALID"
    assert "identity_map_project_id_mismatch" in res.projects[0].reason_codes

    # Unknown source hash
    _write_json(
        map_a,
        {
            "schema_version": "1.0.0",
            "project_id": "proj_alpha",
            "source_sha256s": ["f" * 64],
            "bindings": [
                {
                    "benchmark_item_id": "alpha-floor-01",
                    "production_family": "floor_area",
                    "production_object_identity_refs": ["ref_a"],
                }
            ],
        },
    )
    res = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert res.status == "INCOMPLETE_OR_INVALID"
    assert "identity_map_unknown_source_sha256" in res.projects[0].reason_codes

    # Duplicate benchmark_item_id fails closed inside V2ProductionIdentityMap schema validation
    _write_json(
        map_a,
        {
            "schema_version": "1.0.0",
            "project_id": "proj_alpha",
            "source_sha256s": [meta["sha_a"]],
            "bindings": [
                {
                    "benchmark_item_id": "alpha-floor-01",
                    "production_family": "floor_area",
                    "production_object_identity_refs": ["ref_a1"],
                },
                {
                    "benchmark_item_id": "alpha-floor-01",
                    "production_family": "floor_area",
                    "production_object_identity_refs": ["ref_a2"],
                },
            ],
        },
    )
    res = sbi.verify_identity_map_bundle(suite_root=suite_root, identity_map_dir=map_dir)
    assert res.status == "INCOMPLETE_OR_INVALID"
    assert "identity_map_schema_error" in res.projects[0].reason_codes


def test_unsafe_manifest_pdf_name_and_no_input_mutation(tmp_path: Path) -> None:
    suite_root, source_dir, map_dir, meta = _build_synthetic_suite(tmp_path, layout="flat")
    before_hashes = {
        p.relative_to(tmp_path): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(tmp_path.rglob("*"))
        if p.is_file()
    }
    receipt = sbi.verify_benchmark_input_bundle(
        suite_root=suite_root, source_dir=source_dir, identity_map_dir=map_dir,
    )
    assert receipt.status == "READY"
    after_hashes = {
        p.relative_to(tmp_path): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(tmp_path.rglob("*"))
        if p.is_file()
    }
    assert before_hashes == after_hashes

    # Manifest with path traversal in source document name fails closed as UNSAFE_NAME
    manifest_a = suite_root / "projects" / "proj_alpha" / "source_manifest.json"
    raw = json.loads(manifest_a.read_text(encoding="utf-8"))
    raw["source_documents"][0]["name"] = "../escape.pdf"
    _write_json(manifest_a, raw)
    bad = sbi.verify_source_bundle_inventory(suite_root=suite_root, source_dir=source_dir)
    assert bad.status == "INCOMPLETE_OR_FAILED"
    assert bad.documents[0].status == "UNSAFE_NAME"
    assert "unsafe_manifest_pdf_name" in bad.reason_codes


def test_module_has_zero_hardcoded_project_or_sha_literals() -> None:
    module_path = Path(sbi.__file__)
    findings = audit_shared_source(
        module_path.read_text(encoding="utf-8"),
        filename=module_path.name,
    )
    assert findings == ()
