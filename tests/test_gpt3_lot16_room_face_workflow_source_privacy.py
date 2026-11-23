from pathlib import Path

WORKFLOW = Path(__file__).resolve().parents[1] / ".github/workflows/diag-lot16-room-face-scope.yml"


def test_source_fixture_never_proves_positive_original_authority():
    # A static contract cannot prove that the private original existed or
    # that the diagnostic completed. No new customer/score evidence follows.
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "score" not in text.lower()
    assert "commercial_projection_allowed" not in text
