from __future__ import annotations

import pytest

from scripts.check_v2_truth_separation import (
    check_paths,
    find_separation_violation,
    is_production_code_file,
    is_v2_truth_file,
)


def test_all_active_v2_truth_files_are_protected() -> None:
    base = "benchmarks/frozen_holdout/full_plan_v2/projects/example"
    for filename in (
        "source_manifest.json",
        "reference_takeoff.json",
        "object_universe.json",
        "verification_report.json",
        "unresolved_items.json",
    ):
        assert is_v2_truth_file(f"{base}/{filename}")
    assert is_v2_truth_file("benchmarks/frozen_holdout/full_plan_v2/manifest.json")


def test_legacy_benchmark_files_no_longer_define_active_truth() -> None:
    assert not is_v2_truth_file(
        "benchmarks/public_tenders/example/expected_boq_summary.json"
    )
    assert not is_v2_truth_file("benchmarks/plans/example/expected_quantities.json")
    assert not is_v2_truth_file(
        "benchmarks/frozen_holdout/legacy_project/.holdout_lock.json"
    )


def test_mixed_v2_truth_and_production_is_rejected() -> None:
    with pytest.raises(
        SystemExit, match="Full Plan V2 truth / production separation gate failed"
    ):
        check_paths(
            [
                "benchmarks/frozen_holdout/full_plan_v2/projects/example/reference_takeoff.json",
                "pb_planreader_pdf_extractor.py",
            ]
        )


def test_truth_only_and_production_only_changes_are_allowed() -> None:
    check_paths(
        [
            "benchmarks/frozen_holdout/full_plan_v2/projects/example/reference_takeoff.json",
            "tests/test_v2_truth.py",
            "docs/v2_truth.md",
        ]
    )
    check_paths(["pb_planreader_pdf_extractor.py", "tests/test_extractor.py"])


def test_windows_paths_are_normalized() -> None:
    with pytest.raises(SystemExit):
        check_paths(
            [
                r"benchmarks\frozen_holdout\full_plan_v2\projects\example\object_universe.json",
                r"pb_planreader_pdf_extractor.py",
            ]
        )


def test_production_classifier_excludes_tests_docs_and_benchmarks() -> None:
    assert is_production_code_file("pb_planreader_pdf_extractor.py")
    assert is_production_code_file("planreader_takeoff_studio/frontend/studio.js")
    assert not is_production_code_file("tests/test_example.py")
    assert not is_production_code_file("docs/example.py")
    assert not is_production_code_file(
        "benchmarks/frozen_holdout/full_plan_v2/run_baseline.py"
    )


def test_violation_reports_exact_files() -> None:
    truth, production = find_separation_violation(
        [
            "benchmarks/frozen_holdout/full_plan_v2/projects/example/source_manifest.json",
            "pb_planreader_pdf_extractor.py",
        ]
    )
    assert truth == [
        "benchmarks/frozen_holdout/full_plan_v2/projects/example/source_manifest.json"
    ]
    assert production == ["pb_planreader_pdf_extractor.py"]
