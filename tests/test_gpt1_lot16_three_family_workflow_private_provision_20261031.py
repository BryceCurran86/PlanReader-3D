"""Security regression for original Lot16 three-family source-first workflow.

The original SHA/predicate tests may run only as a trusted owner/manual main
workflow. Untrusted PR code can run source-free, never private-original code.
"""
from pathlib import Path


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/gpt1-lot16-original-three-family-first-failure.yml"
)


def _jobs():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "jobs:\n  source-neutral:\n" in text
    source_neutral = text.split("\n  source-neutral:\n", 1)[1].split(
        "\n  original-source:\n", 1
    )[0]
    original = text.split("\n  original-source:\n", 1)[1]
    return text, source_neutral, original


def test_pr_runs_only_source_neutral_pinned_test_and_integrity_paths():
    text, neutral, original = _jobs()
    assert "on:\n  pull_request:" in text
    assert 'persist-credentials: false' in neutral
    assert "tests/test_gpt1_figured_dimension_scale_consistency_shadow.py" in neutral
    assert "tests/test_gpt1_source_figured_plan_plane_shadow.py" in neutral
    assert "tests/test_gpt1_source_owned_figured_plan_bridge.py" in neutral
    assert "tests/test_gpt1_lot16_three_family_workflow_private_provision_20261031.py" in neutral
    assert "scripts/check_full_plan_v2_integrity.py" in neutral
    for forbidden in (
        "provision-original-sources",
        "ORIGINAL_SOURCES_TOKEN",
        "documents/sources/",
        "diag_lot16_room_face_scope.py",
        "upload-artifact",
        "source-owned-plan-view",
    ):
        assert forbidden not in neutral
    assert "\n  workflow_dispatch:\n" in text
    assert "original-source:" in text


def test_original_replay_requires_exact_owner_main_manual_and_rerun_ownership():
    _, neutral, original = _jobs()
    first_line = original.splitlines()[0].strip()
    assert first_line.startswith("if: ${{ ") and first_line.endswith(" }}")
    for trusted_scope in (
        "github.event_name == 'workflow_dispatch'",
        "github.ref == 'refs/heads/main'",
        "github.repository == 'BryceCurran86/PlanReader-3D'",
        "github.actor == 'BryceCurran86'",
        "github.triggering_actor == 'BryceCurran86'",
    ):
        assert trusted_scope in first_line
    assert "&&" in first_line
    assert "||" not in first_line
    assert "github.event.pull_request.head.sha" not in original
    assert "persist-credentials: false" in original
    assert "ref: ${{ github.sha }}" in original
    assert "EXPECTED_SHA: ${{ github.sha }}" in original
    assert 'git rev-parse HEAD' in original
    assert "ORIGINAL_SOURCES_TOKEN" not in neutral


def test_trusted_original_sha_provision_and_first_failure_nonpromotion_are_preserved():
    _, _, original = _jobs()
    assert "uses: ./.github/actions/provision-original-sources" in original
    for check in (
        "secrets.ORIGINAL_SOURCES_TOKEN",
        "vars.ORIGINAL_SOURCES_REPOSITORY",
        "vars.ORIGINAL_SOURCES_REF",
        "names: 1. Construction Plans - Lot 16 Power (REV E).pdf",
        'allow-missing: "false"',
        "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
        "sha256sum --check",
        "--page-index 2",
        "--source-owned-plan-view",
        "--diagnostic-label BED",
        "source_figured_scale_shadow_consistent_not_authority",
        "source_plan_view_proof_mode",
        "source_proven_floor_plan_viewports",
        "source_area_units_inferred_from_pdf_points",
        "first_failure_frequency",
        "source_room_to_dimension_owner_proven",
        "physical_scale_authority_granted",
        "commercial_projection_allowed",
        "room_metric_area_authority_granted",
        "new_customer_quantity_created_by_this_workflow",
        "benchmark_score_granted",
    ):
        assert check in original


def test_no_private_diagnostic_in_public_logs_artifacts_or_working_tree():
    text, neutral, original = _jobs()
    assert "actions/upload-artifact@" not in text
    assert "artifacts/gpt1-original-lot16-first-failure" not in text
    assert "print(json.dumps({k:fields[k]" not in text
    assert "ORIGINAL_LOT16_SOURCE_FIRST_FAILURES" not in text
    assert 'out=Path(os.environ["RUNNER_TEMP"])' in original
    assert 'private_dir="$RUNNER_TEMP/gpt1-original-lot16-first-failure"' in original
    assert '> "$private_dir/private.log" 2>&1' in original
    assert "private details withheld" in original
    assert "if: always()" in original
    assert 'rm -rf documents/sources "$RUNNER_TEMP/gpt1-original-lot16-first-failure"' in original
    assert "original.json" not in neutral
    assert "stage_summary.json" not in neutral
    assert "raise SystemExit(1)" in original
    assert "raise SystemExit(0)" not in original


def test_source_first_status_does_not_mint_new_measurement_authority():
    _, _, original = _jobs()
    for forbidden_promotion in (
        '"diagnostic_only":True',
        '"new_customer_quantity_created_by_this_workflow":False',
        '"benchmark_score_granted":False',
        '"room_metric_area_authority_granted") is False',
        '"physical_scale_authority_granted") is False',
        '"commercial_projection_allowed") is False',
        '"published_quantities")==[]',
    ):
        assert forbidden_promotion in original
