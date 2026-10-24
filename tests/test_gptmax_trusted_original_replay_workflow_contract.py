"""Security contract for manual, immutable MAX original-source validation."""
from pathlib import Path
import yaml

WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/gptmax-trusted-original-opening-replay-manual.yml"
)
BASE = "041ea388fc0501e20594d110f46992fe8a6c7042"
HEADS = {
    "host": "b58d435efa65e003ba55754c2bdc152df5c91e8b",
    "frame": "fd33915001c32c0b715013e72a6823fbddc1eb89",
    "receipt": "cef7e07d1df950c654fe8d8bd25d93184d3733c3",
}
PATHS = {
    "host": (
        "pb_opening_host_binding_authority.py",
        "tests/test_gptmax_host_equivalence_conflict_monotonic.py",
    ),
    "frame": (
        "pb_opening_host_frame_authority.py",
        "tests/test_gptmax_independent_axes_figured_pair_handoff.py",
        "tests/test_gptmax_opening_frame_equivalence_conflict_monotonic.py",
        "tools/diag_gptmax_producer_owned_g17_wall_shadow.py",
    ),
    "receipt": (
        "docs/engineering/gptmax_g17_source_receipt_registration_20261020.md",
        "pb_source_visibility_authority.py",
        "tests/test_raster_opening_receipt_registration.py",
    ),
}


def _load():
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_manual_only_owner_main_context_never_pr_or_push():
    data = _load()
    assert data.get(True, data.get("on")) == {"workflow_dispatch": None}
    assert data["permissions"] == {"contents": "read"}
    assert tuple(data["jobs"]) == ("verify",)
    job = data["jobs"]["verify"]
    assert "github.event_name == 'workflow_dispatch'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.actor == 'BryceCurran86'" in job["if"]
    assert job["strategy"]["matrix"]["target"] == list(HEADS)
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    assert job["strategy"]["fail-fast"] is False
    assert "github.event.inputs" not in WORKFLOW.read_text(encoding="utf-8")


def test_exact_head_code_diff_and_parent_tree_veto_precede_original_download():
    steps = _load()["jobs"]["verify"]["steps"]
    guard_index = next(i for i, s in enumerate(steps) if s["name"].startswith("Authenticate immutable"))
    provision_index = next(i for i, s in enumerate(steps) if s["name"].startswith("Provision original"))
    assert guard_index < provision_index
    guard = steps[guard_index]["run"]
    assert f"approved_base={BASE}" in guard
    assert "git fetch --no-tags --depth=1 origin" in guard
    assert "git diff --name-only" in guard
    assert '[[ "$observed" != "$expected" ]]' in guard
    assert 'git checkout --detach "$approved_head"' in guard
    assert '[[ "$(git rev-parse HEAD)" == "$approved_head" ]]' in guard
    for name, head in HEADS.items():
        assert f"{name})" in guard
        assert f"approved_head={head}" in guard
        for path in PATHS[name]:
            assert path in guard
    assert "ORIGINAL_SOURCES_TOKEN" not in guard


def test_secret_only_in_manifest_authenticated_source_provisioner():
    steps = _load()["jobs"]["verify"]["steps"]
    matches = [step for step in steps if "ORIGINAL_SOURCES_TOKEN" in str(step)]
    assert len(matches) == 1
    provision = matches[0]
    assert provision["uses"] == "./.github/actions/provision-original-sources"
    assert provision["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert provision["with"]["repository"] == "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}"
    assert provision["with"]["ref"] == "${{ vars.ORIGINAL_SOURCES_REF }}"
    assert provision["with"]["allow-missing"] == "false"
    assert provision["with"]["names"].strip() == (
        "1. Construction Plans - Lot 16 Power (REV E).pdf"
    )
    source = WORKFLOW.read_text(encoding="utf-8")
    assert "actions/upload-artifact" not in source
    assert "actions/download-artifact" not in source
    assert "curl " not in source
    assert "wget " not in source
    assert "github.event.pull_request" not in source


def test_real_original_requires_pass_and_archived_customer_parity():
    steps = _load()["jobs"]["verify"]["steps"]
    source = next(step for step in steps if step["name"].startswith("Verify real original"))
    script = source["run"]
    assert "test_original_source_appends_one_area_and_preserves_all_eight_signed_customer_bodies" in script
    assert "PLANREADER_LOT16_ORIGINAL_PDF" in source["env"]
    assert "grep -Eq" in script and " passed" in script
    assert "source-positive replay skipped" in script
    other = next(step for step in steps if step["name"].startswith("Verify original-provisioned"))
    assert 'python -m pytest -q --tb=no --disable-warnings "$GPTMAX_FOCUSED_TEST"' in other["run"]
    assert "grep -Eq" in other["run"]
    cleanup = steps[-1]
    assert cleanup["if"] == "always()"
    assert "rm -rf documents/sources" in cleanup["run"]
    assert "rm -f" in cleanup["run"]
