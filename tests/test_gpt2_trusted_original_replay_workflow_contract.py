"""Safety contract for owner-initiated, SHA-pinned private source replays."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / ".github/workflows/gpt2-trusted-original-source-replay-manual.yml"
SOURCE = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
HEADS = {
    "a600": "9552e19b9adac0160256168a5b6c95bf4a0ea140",
    "freezer": "d7662c9f2c442051ed02dc513f4c3b096610dd2c",
    "d15": "49e3914e3da581d9cf8ac4a7d1d5186cbc4f67d1",
    "rcp": "753415e2e0aedde27dc4e8d0acd1bc3c22a73af8",
}


def _load():
    return yaml.safe_load(FILE.read_text(encoding="utf8"))


def test_owner_only_manual_source_triggers():
    document = _load()
    assert document.get(True, document.get("on")) == {"workflow_dispatch": None}
    assert document["permissions"] == {"contents": "read"}
    assert tuple(document["jobs"]) == ("original",)
    job = document["jobs"]["original"]
    assert "github.ref == 'refs/heads/main'" in job["if"]
    assert "github.actor == 'BryceCurran86'" in job["if"]
    assert job["strategy"]["fail-fast"] is False
    assert job["strategy"]["matrix"]["target"] == list(HEADS)
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]


def test_pinned_sha_allowlist_and_no_arbitrary_input():
    steps = _load()["jobs"]["original"]["steps"]
    guard = next(s for s in steps if s["name"].startswith("Validate immutable"))
    script = guard["run"]
    assert "ce322d69bbc9f47b5b2aed001684e01cbe04f48b" in script
    for target, sha in HEADS.items():
        assert target + ")" in script
        assert "approved_head=" + sha in script
    assert "git diff --name-only" in script
    assert "git checkout --detach" in script
    assert "expected_paths=" in script
    assert "github.event.inputs" not in FILE.read_text(encoding="utf8")


def test_token_only_present_in_frozen_manifest_provision_step():
    steps = _load()["jobs"]["original"]["steps"]
    matches = [s for s in steps if "ORIGINAL_SOURCES_TOKEN" in str(s)]
    assert len(matches) == 1
    source = matches[0]
    assert source["uses"] == "./.github/actions/provision-original-sources"
    assert source["with"]["token"] == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
    assert source["with"]["repository"] == "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}"
    assert source["with"]["ref"] == "${{ vars.ORIGINAL_SOURCES_REF }}"
    assert source["with"]["allow-missing"] == "false"
    assert source["with"]["names"].strip() == "Arch_Combined_Maryborough_Service_Station.pdf"
    text = FILE.read_text(encoding="utf8")
    assert SOURCE in text
    assert "actions/upload-artifact" not in text
    assert "\n  pull_request:" not in text
    assert "\n  pull_request_target:" not in text


def test_positive_source_test_required_and_private_outputs_removed():
    steps = _load()["jobs"]["original"]["steps"]
    positive = next(s for s in steps if s["name"].startswith("Require source-positive"))
    module = next(s for s in steps if s["name"].startswith("Run complete GPT2"))
    assert "Original case was skipped" in positive["run"]
    assert "grep -Eq" in positive["run"]
    assert "if ! python -m pytest" in positive["run"]
    assert "if ! python -m pytest" in module["run"]
    assert SOURCE == positive["env"]["PLANREADER_MARYBOROUGH_SOURCE_SHA256"]
    assert SOURCE == module["env"]["PLANREADER_MARYBOROUGH_SOURCE_SHA256"]
    assert "No FIRM quantity or benchmark score granted." in module["run"]
    assert steps[-1]["if"] == "always()"
    assert "rm -rf documents/sources" in steps[-1]["run"]
