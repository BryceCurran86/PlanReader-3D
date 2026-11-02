"""Public GPT2 page-9 RCP CI must not execute or upload private source."""
from pathlib import Path

import pytest
import yaml


WORKFLOW = Path(".github/workflows/diag-gpt2-page9-original-rcp-firstgate.yml")


def _privacy_failures(text: str) -> tuple[str, ...]:
    lower = text.lower()
    forbidden = (
        "source-proof:", "actions/upload-artifact@", "actions/download-artifact@",
        "documents/sources/", "original_sources_token", "secrets.",
        "provision-original-sources", "pull_request_target:",
        "contents: write", "id-token: write", "pdf.read_bytes()",
    )
    missing = (
        "pull_request:", "push:", "workflow_dispatch:",
        'python-version: ["3.13", "3.14"]',
        "permissions:\n  contents: read", "persist-credentials: false",
        "tests/test_gpt2_page9_original_rcp_firstgate.py",
        "tests/test_gpt2_page9_rcp_workflow_privacy.py",
        "check_full_plan_v2_integrity.py",
        "check_provider_gold_isolation.py",
    )
    return tuple(
        [f"forbidden {token}" for token in forbidden if token in lower]
        + [f"missing {token}" for token in missing if token not in text]
    )


def test_public_rcp_workflow_is_only_source_free_and_valid_yaml():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _privacy_failures(text) == ()
    workflow = yaml.safe_load(text)
    assert workflow["permissions"] == {"contents": "read"}
    assert set(workflow["jobs"]) == {"source-free"}
    job = workflow["jobs"]["source-free"]
    assert job["strategy"]["matrix"]["python-version"] == ["3.13", "3.14"]
    steps = job["steps"]
    assert any(step.get("name") == "Explicitly label source-free scope" for step in steps)
    assert all("actions/upload-artifact@" not in str(step) for step in steps)


@pytest.mark.parametrize("injected", (
    "  source-proof:\n    runs-on: ubuntu-latest\n",
    "      - uses: actions/upload-artifact@v4\n",
    "      - uses: actions/download-artifact@v4\n",
    "      - run: cat documents/sources/private.pdf\n",
    "      - run: echo ${{ secrets.ORIGINAL_SOURCES_TOKEN }}\n",
    "      - uses: ./.github/actions/provision-original-sources\n",
    "  pull_request_target:\n",
    "  contents: write\n",
    "  id-token: write\n",
    "      - run: python -c 'PDF.read_bytes()'\n",
))
def test_public_rcp_source_bearing_mutations_abstain(injected):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert _privacy_failures(text + injected)


@pytest.mark.parametrize("removed", (
    'python-version: ["3.13", "3.14"]',
    "permissions:\n  contents: read",
    "persist-credentials: false",
    "tests/test_gpt2_page9_original_rcp_firstgate.py",
    "tests/test_gpt2_page9_rcp_workflow_privacy.py",
    "check_full_plan_v2_integrity.py",
    "check_provider_gold_isolation.py",
))
def test_public_rcp_missing_safety_gates_abstain(removed):
    text = WORKFLOW.read_text(encoding="utf-8")
    assert removed in text
    assert _privacy_failures(text.replace(removed, ""))
