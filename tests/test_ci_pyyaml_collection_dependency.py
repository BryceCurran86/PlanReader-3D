"""CI must provision the YAML parser used by original-source workflow tests.

The production Render install intentionally does not need PyYAML. This test
prevents another green preflight followed by a pytest collection crash.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_ci_only_dependencies_include_yaml_parser_required_at_collection():
    lines = (ROOT / "requirements-ci-v1228.txt").read_text().splitlines()
    requirements = [
        line.strip().lower()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert any(
        value.startswith("pyyaml>=") and ",<7" in value
        for value in requirements
    )
    assert any(value.startswith("pytest") for value in requirements)
    # The public CI full suite installs this exact manifest.
    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "pip install -r requirements.txt -r requirements-ci-v1228.txt" in workflow
