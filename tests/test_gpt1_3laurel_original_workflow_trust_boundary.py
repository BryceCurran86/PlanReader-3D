"""3Laurel original source-positive replay must be trusted-main only."""
from pathlib import Path


WORKFLOW = Path(__file__).resolve().parents[1] / (
    ".github/workflows/gpt1-3laurel-source-positive-opening.yml"
)


def _workflow():
    text = WORKFLOW.read_text(encoding="utf-8")
    return text, text.split("\n  original-opening-production:\n", 1)[1]


def test_pr_uses_only_source_neutral_opening_publisher_checks():
    text, original = _workflow()
    assert "  source-neutral:" in text
    assert 'python-version: ["3.13", "3.14"]' in text
    assert "tests/test_live_opening_area_quantity_publication.py" in text
    assert "github.event_name == 'workflow_dispatch'" in original
    assert "github.ref == 'refs/heads/main'" in original
    assert "github.actor == 'BryceCurran86'" in original
    assert "github.repository == 'BryceCurran86/PlanReader-3D'" in original
    assert "ref: ${{ github.sha }}" in original
    assert "github.event.pull_request.head.sha" not in original
    assert "persist-credentials: false" in original


def test_original_is_pinned_private_and_no_report_is_publicly_uploaded():
    text, original = _workflow()
    assert "uses: ./.github/actions/provision-original-sources" in original
    assert "token: ${{ secrets.ORIGINAL_SOURCES_TOKEN }}" in original
    # Main's exact manifest filename selector supersedes the older project
    # selector; do not broaden provisioning during branch integration.
    assert "names: 3LAUREL - Construction Plan Set Rev3 08.05.26.pdf" in original
    assert 'allow-missing: "false"' in original
    assert "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e" in original
    assert "verify_sealed_customer_output(run,rows)" in original
    assert "actions/upload-artifact" not in text
    assert "rm -rf documents/sources artifacts" in original
    cleanup = original.split("- name: Destroy private originals", 1)[1]
    assert "laurel-source-positive-core" in cleanup
    assert 'rm -f "$RUNNER_TEMP"/guarded-original-*.sh' in cleanup
