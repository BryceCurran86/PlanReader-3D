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
    "cache": "5ae6170f03b81c58df15423b997caacd9e778f87",
    "vertical": "f7e2872a56d920f28043af29474f82dfd5a401b4",
    "horizontal": "98deb79aa5d4f1c45b666d8b7a71a77f82a5c825",
    "antigravity": "0377a077d94552f4297e73ae1f1e0d0b44bcd53d",
}
BASES = {
    "host": BASE,
    "frame": BASE,
    "receipt": BASE,
    "cache": "86c0193c157cd1333a11470b45d50ab3f5cf44fc",
    "vertical": "5a3649001830efd119c28c9a40db795ce815f4c2",
    "horizontal": "fa7b2bd77adaa8ddf3c5af2e2ff80e755f44c512",
    "antigravity": "782b4e3ef4028e9463f39a4a64feb5c50b9332f6",
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
        "pb_physical_opening_authority.py",
        "tests/test_raster_opening_cached_source_integrity.py",
    ),
    "vertical": (
        "docs/engineering/gptmax_vertical_third_root_ownership_20261029.md",
        "pb_gptmax_raster_tile_seam_shadow.py",
        "tests/test_gptmax_raster_tile_seam_source.py",
    ),
    "horizontal": (
        "docs/engineering/gptmax_horizontal_third_root_ownership_20261029.md",
        "pb_gptmax_horizontal_raster_tile_seam_shadow.py",
        "tests/test_gptmax_horizontal_raster_tile_seam_shadow.py",
    ),
    "antigravity": (
        "pb_live_wall_opening_authority_composition.py",
        "pb_opening_host_frame_authority.py",
        ".github/workflows/test-gptmax-original-split-frame-shadow.yml",
        "tests/test_gptmax_alternate_raster_frame_source_edge_gate.py",
        "tests/test_gptmax_raster_split_frame_shadow.py",
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
    assert data["on"] == {"workflow_dispatch": {"inputs": {"target": {
        "description": "SHA-reviewed original-source target (all runs every gate)",
        "type": "choice", "required": True, "default": "cache",
        "options": list(HEADS) + ["all"],
    }}}}
    assert set(data) == {"name", "on", "permissions", "concurrency", "jobs"}
    assert data["permissions"] == {"contents": "read"}
    assert tuple(data["jobs"]) == ("verify",)
    job = data["jobs"]["verify"]
    assert "github.event_name == 'workflow_dispatch'" in job["if"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.actor == 'BryceCurran86'" in job["if"]
    assert "github.triggering_actor == 'BryceCurran86'" in job["if"]
    selector = job["strategy"]["matrix"]["target"]
    assert selector.startswith("${{ fromJSON(") and selector.endswith(") }}")
    assert "inputs.target == 'all'" in selector and '["unsupported"]' in selector
    for name in HEADS:
        assert f"inputs.target == '{name}'" in selector
        assert f'["{name}"]' in selector
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    assert job["strategy"]["fail-fast"] is False
    assert "github.event.inputs" not in WORKFLOW.read_text(encoding="utf-8")


def test_owner_rerun_guard_rejects_foreign_writer_and_non_manual_context():
    # github.actor is the ORIGINAL workflow initiator on a rerun; the
    # rerunning writer is github.triggering_actor. Both must be the owner.
    guard = _load()["jobs"]["verify"]["if"]
    assert guard == (
        "${{ github.event_name == 'workflow_dispatch' && "
        "github.ref == 'refs/heads/main' && "
        "github.actor == 'BryceCurran86' && "
        "github.triggering_actor == 'BryceCurran86' }}"
    )
    cases = (
        ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "BryceCurran86", True),
        ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "foreign-writer", False),
        ("workflow_dispatch", "refs/heads/main", "foreign-writer", "BryceCurran86", False),
        ("workflow_dispatch", "refs/heads/feature", "BryceCurran86", "BryceCurran86", False),
        ("pull_request", "refs/heads/main", "BryceCurran86", "BryceCurran86", False),
        ("push", "refs/heads/main", "BryceCurran86", "BryceCurran86", False),
    )
    for event, ref, original, rerunner, allowed in cases:
        assert all((
            event == "workflow_dispatch",
            ref == "refs/heads/main",
            original == "BryceCurran86",
            rerunner == "BryceCurran86",
        )) is allowed


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
        assert f"approved_base={BASES[name]}" in guard
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
    assert f"approved_base={BASES['cache']}" in guard
    assert f"approved_head={HEADS['cache']}" in guard
    assert "focused_test=tests/test_raster_opening_cached_source_integrity.py" in guard
    assert 'git checkout --detach "$approved_head"' not in guard
    assert "github.event.pull_request" not in source
    assert "secrets.ORIGINAL_SOURCES_TOKEN" not in guard


def test_vertical_original_source_target_cannot_be_satisfied_by_synthetic_passes():
    source = WORKFLOW.read_text(encoding="utf-8")
    steps = _load()["jobs"]["verify"]["steps"]
    guard = next(step["run"] for step in steps if step.get("name", "").startswith("Authenticate immutable"))
    assert "vertical)" in guard
    assert f"approved_base={BASES['vertical']}" in guard
    assert f"approved_head={HEADS['vertical']}" in guard
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
    assert f"approved_base={BASES['horizontal']}" in guard
    assert f"approved_head={HEADS['horizontal']}" in guard
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


def test_private_test_token_only_in_trusted_staging_and_manifest_provisioner():
    steps = _load()["jobs"]["verify"]["steps"]
    matches = [step for step in steps if "ORIGINAL_SOURCES_TOKEN" in str(step)]
    assert len(matches) == 2
    stage, provision = matches
    assert stage["name"].startswith("Stage immutable private")
    assert stage["if"] == "${{ matrix.target == 'antigravity' }}"
    assert stage["env"]["SOURCE_TEST_TOKEN"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert stage["env"]["SOURCE_TEST_REPOSITORY"] == "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}"
    assert "python -m pytest" not in stage["run"]
    assert "git checkout" not in stage["run"]
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
    assert 'rm -rf "$RUNNER_TEMP/gptmax-approved-target" "$RUNNER_TEMP/gptmax-approved-deps" "$RUNNER_TEMP/gptmax-private-tests" documents/sources' in cleanup["run"]
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
    focused_script = steps[focused_index]["run"]
    # The owner-selected Antigravity target adds one more *isolated* original
    # south-wall test, never a shell/host-side private-source test.
    assert focused_script.count("run_isolated python -m pytest") == 4
    assert '[[ "$GPTMAX_TARGET" == "antigravity" ]]' in focused_script
    assert "for side in north south; do" in focused_script
    assert "/private-tests/test_antigravity_lot16_${side}_wall_frame.py" in focused_script
    assert "Pinned private original wall-frame test skipped or missing" in focused_script
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
    assert 'rm -rf "$RUNNER_TEMP/gptmax-approved-target" "$RUNNER_TEMP/gptmax-approved-deps" "$RUNNER_TEMP/gptmax-private-tests" documents/sources' in cleanup["run"]


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


def test_owner_selective_original_targets_reject_any_unreviewed_source_path():
    data=_load()
    target=data["on"]["workflow_dispatch"]["inputs"]["target"]
    assert target["type"] == "choice" and target["required"] is True
    assert target["default"] == "cache"
    assert target["options"] == list(HEADS) + ["all"]
    selector=data["jobs"]["verify"]["strategy"]["matrix"]["target"]
    assert "inputs.target == 'all'" in selector
    assert '["unsupported"]' in selector
    for name in HEADS:
        assert f"inputs.target == '{name}'" in selector
    guard=next(s["run"] for s in data["jobs"]["verify"]["steps"] if s.get("name","").startswith("Authenticate immutable"))
    assert "case \"$TARGET\" in" in guard
    assert "ORIGINAL_SOURCES_TOKEN" not in guard
    assert "github.event.pull_request" not in WORKFLOW.read_text(encoding="utf-8")


def test_antigravity_original_both_walls_sha_pinned_before_private_source_provision():
    steps=_load()["jobs"]["verify"]["steps"]
    source=next(s["run"] for s in steps if s.get("name","").startswith("Authenticate immutable"))
    assert "antigravity)" in source
    assert f"approved_base={BASES['antigravity']}" in source
    assert f"approved_head={HEADS['antigravity']}" in source
    assert "focused_test=tests/test_gptmax_alternate_raster_frame_source_edge_gate.py" in source
    for path in PATHS["antigravity"]:
        assert path in source
    execute=next(s["run"] for s in steps if s.get("name","").startswith("Verify original-provisioned"))
    assert '[[ "$GPTMAX_TARGET" == "antigravity" ]]' in execute
    assert "for side in north south; do" in execute
    assert "/private-tests/test_antigravity_lot16_${side}_wall_frame.py" in execute
    assert "Pinned private original wall-frame test skipped or missing" in execute
    assert "--network none --read-only --cap-drop ALL" in execute

def test_private_original_tests_are_content_pinned_and_inert_until_offline_execution():
    steps = _load()["jobs"]["verify"]["steps"]
    names = [s.get("name", "") for s in steps]
    auth = next(i for i, n in enumerate(names) if n.startswith("Authenticate immutable"))
    build = next(i for i, n in enumerate(names) if n.startswith("Build no-network"))
    stage = next(i for i, n in enumerate(names) if n.startswith("Stage immutable private"))
    provision = next(i for i, n in enumerate(names) if n.startswith("Provision original"))
    focused = next(i for i, n in enumerate(names) if n.startswith("Verify original-provisioned"))
    assert auth < build < stage < provision < focused
    script = steps[stage]["run"]
    for sha in ("1a1de74e07776727f01ce3af7aa02f8ade817ff7",
                "ad02703c837e683ac2ddbba06bfa347e1e333c72"):
        assert sha in script
    assert "/git/blobs/{sha}" in script
    assert "hashlib.sha1" in script and "observed != sha" in script
    assert 'b"b.opening_identity_id == key" not in data' in script
    assert 'b"key in b.opening_identity_id" in data' in script
    assert 'b"pytest.skip(" in data' in script
    assert 'data.count(b"def test_") != 1' in script
    assert "os.O_EXCL" in script and "0o400" in script
    assert "python -m pytest" not in script
    assert "upload-artifact" not in WORKFLOW.read_text(encoding="utf-8")
    assert "SOURCE_TEST_TOKEN" not in steps[focused]["run"]
    focused_script = steps[focused]["run"]
    assert '--mount "type=bind,src=$GPTMAX_PRIVATE_TESTS,dst=/private-tests,readonly"' in focused_script
    assert "for side in north south; do" in focused_script
    assert "Pinned private original wall-frame test skipped or missing" in focused_script
    assert '"$RUNNER_TEMP/gptmax-private-tests"' in steps[-1]["run"]
