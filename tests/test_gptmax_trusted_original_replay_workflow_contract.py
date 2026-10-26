"""Security contract for manual, immutable MAX original-source validation."""
from pathlib import Path
import re
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
    "cache": "6a937ad7d44da2c63e2fae04492c332a03b3b623",
    "vertical": "d43de44b05b70944588c611b02da44a69b4aa533",
    "horizontal": "8dd491793d1624c8eb2aa6fbfd26d20b39f9f9e0",
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
    "cache": (
        ".github/workflows/gptmax-g17-source-receipt-integrity.yml",
        "docs/engineering/gptmax_g17_cached_source_integrity_20261020.md",
        "pb_physical_opening_authority.py",
        "tests/test_raster_opening_cached_source_integrity.py",
    ),
    "vertical": (
        "pb_gptmax_raster_tile_seam_shadow.py",
        "tests/test_gptmax_raster_tile_seam_source.py",
    ),
    "horizontal": (
        "pb_gptmax_horizontal_raster_tile_seam_shadow.py",
        "tests/test_gptmax_horizontal_raster_tile_seam_shadow.py",
    ),
}


class StrictLoader(yaml.SafeLoader):
    pass


# YAML 1.1 aliases "on", "yes", and "true" to one boolean mapping key.
# Use YAML-1.2-style bools and reject duplicate mapping keys.
StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in rules if tag != "tag:yaml.org,2002:bool"]
    for key, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}

StrictLoader.add_implicit_resolver("tag:yaml.org,2002:bool", re.compile(r"^(?:true|false|True|False|TRUE|FALSE)$"), list("tTfF"))


def _strict_mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=True)
        if not isinstance(key, str) or key in result:
            raise ValueError("Non-string or repeated YAML mapping key")
        result[key] = loader.construct_object(value_node, deep=True)
    return result


StrictLoader.add_constructor("tag:yaml.org,2002:map", _strict_mapping)


def _load():
    data = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=StrictLoader)
    if not isinstance(data, dict):
        raise ValueError("Workflow must be a mapping")
    return data


def test_manual_only_owner_main_context_never_pr_or_push():
    data = _load()
    assert data["on"] == {"workflow_dispatch": None}
    assert set(data) == {"name", "on", "permissions", "concurrency", "jobs"}
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
    guard_index = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Authenticate immutable"))
    provision_index = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Provision original"))
    assert guard_index < provision_index
    guard = steps[guard_index]["run"]
    assert f"approved_base={BASE}" in guard
    assert "git fetch --no-tags --depth=1 origin" in guard
    assert "git diff --name-only" in guard
    assert '[[ "$observed" != "$expected" ]]' in guard
    assert 'git checkout --detach "$approved_head"' not in guard
    assert 'git archive "$approved_head" | tar -x -C "$approved_tree"' in guard
    assert '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]' in guard
    assert 'echo "GPTMAX_APPROVED_TREE=$approved_tree" >> "$GITHUB_ENV"' in guard
    for name, head in HEADS.items():
        assert f"{name})" in guard
        assert f"approved_head={head}" in guard
        for path in PATHS[name]:
            assert path in guard
    assert "ORIGINAL_SOURCES_TOKEN" not in guard


def test_cache_target_has_distinct_immutable_base_and_no_dynamic_checkout():
    source = WORKFLOW.read_text(encoding="utf-8")
    guard = next(
        step["run"]
        for step in _load()["jobs"]["verify"]["steps"]
        if step.get("name", "").startswith("Authenticate immutable")
    )
    assert "cache)" in guard
    assert "approved_base=f480fc84d2e7486319e9b52a3a72790bb7435e69" in guard
    assert "approved_head=6a937ad7d44da2c63e2fae04492c332a03b3b623" in guard
    assert "focused_test=tests/test_raster_opening_cached_source_integrity.py" in guard
    assert 'git checkout --detach "$approved_head"' not in guard
    assert "github.event.pull_request" not in source
    assert "secrets.ORIGINAL_SOURCES_TOKEN" not in guard


def test_vertical_original_source_target_cannot_be_satisfied_by_synthetic_passes():
    source = WORKFLOW.read_text(encoding="utf-8")
    steps = _load()["jobs"]["verify"]["steps"]
    guard = next(step["run"] for step in steps if step.get("name", "").startswith("Authenticate immutable"))
    assert "vertical)" in guard
    assert "approved_base=198dc337c06968f97ab1b6e66d55ede8a7c5a9ed" in guard
    assert "approved_head=d43de44b05b70944588c611b02da44a69b4aa533" in guard
    assert "focused_test=tests/test_gptmax_raster_tile_seam_source.py" in guard
    assert 'echo "GPTMAX_TARGET=$TARGET" >> "$GITHUB_ENV"' in guard
    focused = next(step for step in steps if step.get("name", "").startswith("Verify original-provisioned"))
    assert focused["env"]["LOT16_ARCH_ORIGINAL"].endswith("1. Construction Plans - Lot 16 Power (REV E).pdf")
    script = focused["run"]
    assert '[[ "$GPTMAX_TARGET" == "vertical" ]]' in script
    assert "test_original_lot16_2124_corner_rail_has_two_independent_vertical_tile_roots" in script
    assert "1 passed" in script
    assert "source ink test skipped or missing" in script
    assert "github.event.pull_request" not in source


def test_horizontal_original_source_gap_guard_cannot_be_satisfied_by_synthetic_passes():
    source = WORKFLOW.read_text(encoding="utf-8")
    steps = _load()["jobs"]["verify"]["steps"]
    guard = next(
        step["run"] for step in steps
        if step.get("name", "").startswith("Authenticate immutable")
    )
    assert "horizontal)" in guard
    assert "approved_base=96d6c737167c8dcc94e006488c86f47bf573274a" in guard
    assert "approved_head=8dd491793d1624c8eb2aa6fbfd26d20b39f9f9e0" in guard
    assert "focused_test=tests/test_gptmax_horizontal_raster_tile_seam_shadow.py" in guard
    assert "git diff --name-only" in guard
    focused = next(
        step for step in steps
        if step.get("name", "").startswith("Verify original-provisioned")
    )
    assert focused["env"]["PLANREADER_LOT16_ORIGINAL_PDF"].endswith(
        "1. Construction Plans - Lot 16 Power (REV E).pdf"
    )
    script = focused["run"]
    assert '[[ "$GPTMAX_TARGET" == "horizontal" ]]' in script
    assert "test_original_elevation_panel_rail_is_continuous_across_horizontal_source_tiles" in script
    assert "1 passed" in script
    assert "Original p5 horizontal rail test skipped or missing" in script
    assert "github.event.pull_request" not in source


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
    source = next(step for step in steps if step.get("name", "").startswith("Verify real original"))
    script = source["run"]
    assert "test_original_source_appends_one_area_and_preserves_all_eight_signed_customer_bodies" in script
    assert "PLANREADER_LOT16_ORIGINAL_PDF" in source["env"]
    assert "grep -Eq" in script and " passed" in script
    assert "source-positive replay skipped" in script
    other = next(step for step in steps if step.get("name", "").startswith("Verify original-provisioned"))
    assert 'python -m pytest -q --tb=no --disable-warnings "$GPTMAX_FOCUSED_TEST"' in other["run"]
    assert "grep -Eq" in other["run"]
    cleanup = steps[-1]
    assert cleanup["if"] == "always()"
    assert 'rm -rf "$RUNNER_TEMP/gptmax-approved-target" "$RUNNER_TEMP/gptmax-approved-deps" documents/sources' in cleanup["run"]
    assert "rm -f" in cleanup["run"]


def test_trigger_aliases_and_duplicates_cannot_bypass_manual_only_gate():
    import pytest

    source = WORKFLOW.read_text(encoding="utf-8")
    for replacement in (
        "on:\n  workflow_dispatch:\n  pull_request:",
        "on:\n  workflow_dispatch:\non:\n  pull_request:",
        "on:\n  pull_request:\ntrue:\n  workflow_dispatch:",
        "yes:\n  workflow_dispatch:",
        "on:\n  workflow_dispatch:\n  workflow_dispatch:",
        "on:\n  workflow_dispatch:\n1: ignored",
        "on:\n  workflow_dispatch:\nunreviewed: ignored",
    ):
        mutated = source.replace("on:\n  workflow_dispatch:", replacement, 1)
        with pytest.raises((ValueError, KeyError, AssertionError, yaml.YAMLError)):
            data = yaml.load(mutated, Loader=StrictLoader)
            assert data["on"] == {"workflow_dispatch": None}
            assert set(data) == {"name", "on", "permissions", "concurrency", "jobs"}


def test_strict_loader_does_not_mutate_global_safe_loader():
    assert yaml.safe_load("on: true") == {True: True}


def test_private_original_never_enters_networked_pr_head_execution_or_raw_logs():
    """Immutable SHA/path pinning alone is not a sandbox for executable PR-head tests."""
    steps = _load()["jobs"]["verify"]["steps"]
    names = [step.get("name", "") for step in steps]
    build_index = next(i for i, name in enumerate(names) if name.startswith("Build no-network"))
    provision_index = next(i for i, name in enumerate(names) if name.startswith("Provision original"))
    replay_index = next(i for i, name in enumerate(names) if name.startswith("Verify real original"))
    focused_index = next(i for i, name in enumerate(names) if name.startswith("Verify original-provisioned"))
    assert build_index < provision_index < replay_index < focused_index
    build = steps[build_index]["run"]
    assert "docker build" in build
    assert "COPY requirements.txt requirements-ci-v1228.txt /deps/" in build
    assert "documents/sources" not in build
    for index in (replay_index, focused_index):
        script = steps[index]["run"]
        assert "docker run --rm --network none --read-only --cap-drop ALL" in script
        assert "--security-opt no-new-privileges" in script
        assert '--mount "type=bind,src=$GPTMAX_APPROVED_TREE,dst=/repo,readonly"' in script
        assert '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/repo/documents/sources,readonly"' in script
        assert "--tmpfs /tmp:" in script
        assert '--env PYTHONPATH=/repo' in script
        assert "run_isolated python -m pytest" in script
        assert "grep -E '^(FAILED |ERROR )'" not in script
        assert "curl " not in script and "wget " not in script
        assert "--volume /var/run/docker.sock" not in script
        assert "--network host" not in script
        assert "secrets.ORIGINAL_SOURCES_TOKEN" not in script
    assert steps[focused_index]["run"].count("run_isolated python -m pytest") == 3
    assert steps[replay_index]["run"].count("run_isolated python -m pytest") == 1


def test_token_bearing_provisioner_uses_trusted_main_not_reviewed_pr_checkout():
    """Immutable PR test code is inert until executed in the offline container."""
    steps = _load()["jobs"]["verify"]["steps"]
    guard_index = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Authenticate immutable"))
    provision_index = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Provision original"))
    build_index = next(i for i, s in enumerate(steps) if s.get("name", "").startswith("Build no-network"))
    assert guard_index < build_index < provision_index
    guard = steps[guard_index]["run"]
    assert 'git checkout --detach "$approved_head"' not in guard
    assert 'git archive "$approved_head" | tar -x -C "$approved_tree"' in guard
    assert 'mkdir -p "$approved_tree/documents/sources"' in guard
    assert '[[ "$(git rev-parse HEAD)" == "$GITHUB_SHA" ]]' in guard
    assert '[[ -z "$(git status --porcelain)" ]]' in guard
    assert '[[ -f "$approved_tree/$focused_test" ]]' in guard
    assert steps[provision_index]["uses"] == "./.github/actions/provision-original-sources"
    for step in steps[provision_index + 1:]:
        script = step.get("run", "")
        assert "git checkout" not in script
        assert "python -m pytest" not in script.replace("run_isolated python -m pytest", "")
        assert "--network host" not in script
    for step in steps:
        if step.get("name", "").startswith(("Verify real original", "Verify original-provisioned")):
            script = step["run"]
            assert '--mount "type=bind,src=$GPTMAX_APPROVED_TREE,dst=/repo,readonly"' in script
            assert '--mount "type=bind,src=$GITHUB_WORKSPACE/documents/sources,dst=/repo/documents/sources,readonly"' in script
            assert "docker run --rm --network none --read-only --cap-drop ALL" in script
    cleanup = steps[-1]
    assert 'rm -rf "$RUNNER_TEMP/gptmax-approved-target" "$RUNNER_TEMP/gptmax-approved-deps" documents/sources' in cleanup["run"]


def _assert_approved_dependency_context(build):
    """Fail closed if moving main or a broad checkout enters Docker context."""
    assert 'approved_deps="$RUNNER_TEMP/gptmax-approved-deps"' in build
    assert 'mkdir -p "$approved_deps"' in build
    assert 'for dep in requirements.txt requirements-ci-v1228.txt; do' in build
    assert '[[ -f "$GPTMAX_APPROVED_TREE/$dep" && ! -L "$GPTMAX_APPROVED_TREE/$dep" ]]' in build
    assert 'cp -- "$GPTMAX_APPROVED_TREE/$dep" "$approved_deps/$dep"' in build
    assert '-f - "$approved_deps" <<' in build
    assert '-f - . <<' not in build
    assert 'cp -- "$GITHUB_WORKSPACE/$dep"' not in build


def test_dependency_image_uses_only_immutable_sha_approved_requirements():
    steps = _load()["jobs"]["verify"]["steps"]
    build = next(step["run"] for step in steps if step.get("name", "").startswith("Build no-network"))
    _assert_approved_dependency_context(build)
    cleanup = steps[-1]
    assert cleanup["if"] == "always()"
    assert '"$RUNNER_TEMP/gptmax-approved-deps"' in cleanup["run"]


def test_dependency_context_static_tampering_is_rejected():
    import pytest

    steps = _load()["jobs"]["verify"]["steps"]
    build = next(step["run"] for step in steps if step.get("name", "").startswith("Build no-network"))
    tampered = (
        build.replace('cp -- "$GPTMAX_APPROVED_TREE/$dep"', 'cp -- "$GITHUB_WORKSPACE/$dep"'),
        build.replace('-f - "$approved_deps" <<', '-f - . <<'),
        build.replace('mkdir -p "$approved_deps"', 'mkdir -p "$GITHUB_WORKSPACE"'),
        build.replace('[[ -f "$GPTMAX_APPROVED_TREE/$dep" && ! -L "$GPTMAX_APPROVED_TREE/$dep" ]]', ':'),
    )
    for mutated in tampered:
        assert mutated != build
        with pytest.raises(AssertionError):
            _assert_approved_dependency_context(mutated)


def test_dependency_copy_shell_ignores_moving_main_and_private_sentinel(tmp_path):
    """Execute actual pre-build copy, without Docker, network or originals."""
    import os
    import subprocess

    steps = _load()["jobs"]["verify"]["steps"]
    build = next(step["run"] for step in steps if step.get("name", "").startswith("Build no-network"))
    copy_script = build.split("docker build --pull", 1)[0]
    approved = tmp_path / "approved"
    moving_main = tmp_path / "moving-main"
    approved.mkdir()
    moving_main.mkdir()
    for name in ("requirements.txt", "requirements-ci-v1228.txt"):
        (approved / name).write_text("PINNED-" + name, encoding="utf-8")
        (moving_main / name).write_text("MOVING-MAIN-" + name, encoding="utf-8")
    (moving_main / "private-original.pdf").write_bytes(b"private-sentinel")
    env = dict(os.environ, RUNNER_TEMP=str(tmp_path), GPTMAX_APPROVED_TREE=str(approved),
               GITHUB_WORKSPACE=str(moving_main))
    subprocess.run(["bash", "-euo", "pipefail", "-c", copy_script], cwd=moving_main,
                   env=env, check=True, capture_output=True, text=True)
    context = tmp_path / "gptmax-approved-deps"
    assert sorted(p.name for p in context.iterdir()) == [
        "requirements-ci-v1228.txt", "requirements.txt"
    ]
    for name in ("requirements.txt", "requirements-ci-v1228.txt"):
        assert (context / name).read_text(encoding="utf-8") == "PINNED-" + name
    assert not (context / "private-original.pdf").exists()
