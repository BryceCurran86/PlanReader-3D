"""Fail closed if the public GPT2 room-handoff PR workflow accesses private originals.

This is a static, source-neutral CI boundary. Private original-positive checks
must run separately from pull_request code under the owner/main/manual offline
replay contract; this test never reads an original PDF.
"""

from pathlib import Path

import pytest
import yaml


WORKFLOW = Path(".github/workflows/test-gpt2-source-room-handoff-integrity.yml")


def _unsafe_public_workflow_reasons(workflow: str) -> tuple[str, ...]:
    """Reject source-bearing steps or privileges in a PR-controlled workflow."""
    reasons = []
    lower = workflow.lower()
    forbidden = (
        ("source-proof:", "PR source-proof job"),
        ("actions/upload-artifact@", "PR artifact upload"),
        ("actions/download-artifact@", "PR artifact download"),
        ("documents/sources/", "private source path"),
        ("original_sources_token", "private source token"),
        ("secrets.", "secret reference"),
        ("provision-original-sources", "source provisioning"),
        ("pull_request_target:", "privileged PR trigger"),
        ("workflow_run:", "untrusted workflow trigger"),
        ("contents: write", "write permission"),
        ("id-token: write", "OIDC write permission"),
    )
    for token, reason in forbidden:
        if token in lower:
            reasons.append(reason)
    required = (
        ("pull_request:", "public PR trigger"),
        ('python-version: ["3.13","3.14"]', "dual-Python matrix"),
        ("permissions:\n  contents: read", "read-only token"),
        ("persist-credentials: false", "checkout credential isolation"),
        ("tests/test_gpt2_source_room_handoff_integrity.py", "source-free regression"),
        ("tests/test_gpt2_source_room_handoff_workflow_privacy.py", "privacy regression"),
        ("check_full_plan_v2_integrity.py", "frozen truth integrity"),
        ("check_provider_gold_isolation.py", "provider/gold separation"),
    )
    for token, reason in required:
        if token not in workflow:
            reasons.append(f"missing {reason}")
    return tuple(reasons)


def test_public_room_handoff_never_runs_private_original_source_or_uploads():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _unsafe_public_workflow_reasons(text) == ()
    assert text.count("    runs-on: ubuntu-latest") == 1
    assert "  focused:" in text
    assert "source-free" in text.lower()
    # Parse the actual workflow, not just substrings: a swallowed YAML step
    # must never silently turn a required safety check into shell text.
    parsed = yaml.safe_load(text)
    assert set(parsed["jobs"]) == {"focused"}
    assert parsed["permissions"] == {"contents": "read"}
    assert parsed["jobs"]["focused"]["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    steps = parsed["jobs"]["focused"]["steps"]
    assert any(step.get("name") == "Explicitly label source-free PR scope" for step in steps)


@pytest.mark.parametrize("injected", (
    "  source-proof:\n    runs-on: ubuntu-latest\n",
    "      - uses: actions/upload-artifact@v4\n",
    "      - uses: actions/download-artifact@v4\n",
    "      - run: cat documents/sources/private.pdf\n",
    "      - run: echo ${{ secrets.ORIGINAL_SOURCES_TOKEN }}\n",
    "      - uses: ./.github/actions/provision-original-sources\n",
    "  pull_request_target:\n",
    "  workflow_run:\n",
    "  contents: write\n",
    "  id-token: write\n",
))
def test_source_bearing_public_workflow_mutations_are_rejected(injected):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _unsafe_public_workflow_reasons(text + injected)


@pytest.mark.parametrize("removed", (
    'python-version: ["3.13","3.14"]',
    "permissions:\n  contents: read",
    "persist-credentials: false",
    "tests/test_gpt2_source_room_handoff_integrity.py",
    "check_full_plan_v2_integrity.py",
    "check_provider_gold_isolation.py",
))
def test_missing_source_free_and_security_gates_are_rejected(removed):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert removed in text
    assert _unsafe_public_workflow_reasons(text.replace(removed, ""))
