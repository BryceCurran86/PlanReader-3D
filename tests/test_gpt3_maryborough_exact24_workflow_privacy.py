"""Source-neutral privacy contract for the original-derived Maryborough 24 baseline.

This test does not authenticate a private PDF, signed customer row or frozen
score. It verifies that the existing source-positive checks still run while
only a bounded, non-authoritative receipt may leave the workflow runner.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/score-gpt3-maryborough-exact-24.yml"
)
PUBLIC_PATH = (
    "artifacts/maryborough-exact-24/public/"
    "reconciliation_integrity_receipt.json"
)
ALLOWED_KEYS = frozenset({
    "schema_version", "source_sha_verified", "reconciliation_complete",
    "denominator", "matched_within_tolerance", "matched_outside_tolerance",
    "missed", "partial", "unresolved", "unsupported_extra",
    "coverage_accuracy", "precision_adjusted_accuracy",
    "no_unsupported_ft3_material_binding",
    "four_project_publication_allowed",
})


def _scripts(raw: str):
    doc = yaml.safe_load(raw)
    assert isinstance(doc, dict)
    jobs = doc["jobs"]
    assert tuple(jobs) == ("exact-maryborough-24",)
    steps = jobs["exact-maryborough-24"]["steps"]
    named = {step.get("name"): step for step in steps if "name" in step}
    return steps, named


def _receipt_expr(raw: str):
    _, named = _scripts(raw)
    script = named["Run unchanged exact frozen 24-object reconciler"]["run"]
    code = script.split("python - <<'PY'\n", 1)[1].split("\nPY", 1)[0]
    tree = ast.parse(code)
    receipts = [
        node.value for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "receipt"
                for t in node.targets)
    ]
    assert len(receipts) == 1
    expr = receipts[0]
    assert isinstance(expr, ast.Dict)
    keys = [ast.literal_eval(key) for key in expr.keys]
    assert len(keys) == len(set(keys))
    assert frozenset(keys) == ALLOWED_KEYS
    values = dict(zip(keys, expr.values))
    assert isinstance(values["four_project_publication_allowed"], ast.Constant)
    assert values["four_project_publication_allowed"].value is False
    assert isinstance(values["no_unsupported_ft3_material_binding"], ast.Constant)
    assert values["no_unsupported_ft3_material_binding"].value is True
    assert isinstance(values["schema_version"], ast.Constant)
    assert values["schema_version"].value == "gpt3-maryborough-exact24-public-summary-v1"
    assert {n.id for n in ast.walk(expr) if isinstance(n, ast.Name)} <= {"d"}
    return expr


def _privacy_contract(raw: str) -> bool:
    try:
        steps, named = _scripts(raw)
        uploads = [s for s in steps if s.get("uses", "").startswith("actions/upload-artifact")]
        assert len(uploads) == 1
        upload = uploads[0]
        assert upload["uses"] == "actions/upload-artifact@v4"
        assert upload["if"] == "success()"
        assert upload["with"]["path"] == PUBLIC_PATH
        assert upload["with"]["if-no-files-found"] == "error"
        assert upload["with"]["name"] == "gpt3-maryborough-exact-24-public-summary"
        assert steps.index(upload) < steps.index(
            named["Destroy original-derived sealed/customer and score inputs"]
        )
        cleanup = named["Destroy original-derived sealed/customer and score inputs"]
        assert cleanup["if"] == "always()"
        assert cleanup["run"].strip() == "rm -rf artifacts/maryborough-exact-24"
        download = named["Download exact merged Maryborough source-sealed artifact"]["run"]
        assert "11754145628/zip" in download
        assert "3766aa3677ba25db98dca12d6ef7610f0c1cb4c9dd285c3e62bfd85b8bc600c7" in download
        assert "2eccc537d2ce04987bdcc70761ca56e4ad2ded0f" in download
        signed = named["Reverify sealed run and customer-row parity"]["run"]
        assert "verify_sealed_customer_output(sealed, rows)" in signed
        assert "assert len(sealed.quantities)==3" in signed
        assert "assert verified.customer_row_count==3" in signed
        assert "assert sealed.fingerprint==" in signed
        assert '"sealed_run_fingerprint": sealed.fingerprint' not in signed
        assert '"sealed_run_id": sealed.run_id' not in signed
        score = named["Run unchanged exact frozen 24-object reconciler"]["run"]
        assert "benchmarks/frozen_holdout/full_plan_v2/run_exact_project_reconciliation.py" in score
        assert '"bindings": []' in named["Write zero-binding exact-source identity map"]["run"]
        for required in (
            'assert d["denominator"]==24',
            'assert d["matched_within_tolerance"]==0',
            'assert d["missed"]==24',
            'assert d["unsupported_extra"]==3',
            'assert d["coverage_accuracy"]==0.0',
            'assert d["precision_adjusted_accuracy"]==0.0',
            'assert {item["quantity_id"] for item in produced}==expected_source_quantity_ids',
            '"four_project_publication_allowed":False',
            'public.mkdir(parents=True,exist_ok=True)',
        ):
            assert required in score
        assert "print(\"MARYBOROUGH_EXACT_24\",json.dumps(d" not in score
        assert "print(json.dumps(d" not in score
        assert "actions/upload-artifact" not in score
        assert "source/production" not in upload["with"]["path"]
        _receipt_expr(raw)
    except (AssertionError, KeyError, IndexError, TypeError, ValueError,
            SyntaxError, yaml.YAMLError):
        return False
    return True


def test_original_exact_24_replay_keeps_source_gates_but_only_public_summary():
    assert _privacy_contract(WORKFLOW.read_text(encoding="utf-8"))


def test_public_receipt_expression_cannot_carry_private_original_fields():
    expr = _receipt_expr(WORKFLOW.read_text(encoding="utf-8"))
    synthetic = {
        "denominator": 24, "matched_within_tolerance": 0,
        "matched_outside_tolerance": 0, "missed": 24, "partial": 0,
        "unresolved": 0, "unsupported_extra": 3,
        "coverage_accuracy": 0.0, "precision_adjusted_accuracy": 0.0,
        "produced_items": [{"quantity_id": "PRIVATE_CANARY"}],
        "source_sha256s": ["PRIVATE_SOURCE_CANARY"],
    }
    receipt = eval(compile(ast.Expression(body=expr), "<receipt>", "eval"),
                   {"__builtins__": {}}, {"d": synthetic})
    assert set(receipt) == ALLOWED_KEYS
    assert receipt["schema_version"] == "gpt3-maryborough-exact24-public-summary-v1"
    assert receipt["four_project_publication_allowed"] is False
    assert receipt["matched_within_tolerance"] == 0
    assert "PRIVATE_CANARY" not in repr(receipt)
    assert "PRIVATE_SOURCE_CANARY" not in repr(receipt)


@pytest.mark.parametrize(("old", "new"), [
    (PUBLIC_PATH, "artifacts/maryborough-exact-24"),
    (PUBLIC_PATH, "artifacts/maryborough-exact-24/source/production"),
    ("if: success()\n        with:\n          name: gpt3-maryborough",
     "if: always()\n        with:\n          name: gpt3-maryborough"),
    ("if-no-files-found: error", "if-no-files-found: ignore"),
    ("rm -rf artifacts/maryborough-exact-24", "echo retained"),
    ("assert d[\"matched_within_tolerance\"]==0",
     "assert d[\"matched_within_tolerance\"]>=0"),
    ('"four_project_publication_allowed":False',
     '"four_project_publication_allowed":True'),
    ('"sealed_run_fingerprint": sealed.fingerprint',
     '"sealed_run_fingerprint": sealed.fingerprint'),
])
def test_privacy_or_source_gate_regressions_are_detected(old, new):
    raw = WORKFLOW.read_text(encoding="utf-8")
    if old == new:
        # Explicitly add a private identity to the published log payload.
        modified = raw.replace('"sealed_quantity_count": 3,',
                               '"sealed_quantity_count": 3,\n'
                               '              "sealed_run_fingerprint": sealed.fingerprint,', 1)
    else:
        assert old in raw
        modified = raw.replace(old, new, 1)
    assert modified != raw
    assert not _privacy_contract(modified)
