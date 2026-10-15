"""Import safety and parser parity for the strict persisted-evidence JSON reader.

Synthetic inputs only; nothing here authenticates original bytes, quantities or benchmark identities.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from pb_strict_evidence_json import MAX_JSON_NESTING_DEPTH, parse_strict_evidence_json
from scripts.report_full_plan_v2_readiness import _parse_evidence_json as readiness_parser

REPO = Path(__file__).resolve().parents[1]

CORPUS = [
    "{}", "[]", "0", "null", '"text"', "true",
    '{"a":1,"b":[1,2,{"c":null}],"d":"[not nesting] {x} \\"q\\""}',
    '{"x":12345678901234567890,"y":1.25,"z":0.00000001,"w":-0.0}',
    "NaN", "Infinity", "-Infinity", '{"a":NaN}', '{"a":Infinity}', '{"a":-Infinity}',
    "1e10000", "-1e10000", '{"a":1e309}', '{"a":1e308}', '{"a":-1e308}',
    "9" * 400, "-" + "9" * 400, "1" + "0" * 308, "1" + "0" * 309,
    '{"a":1,"a":2}', '{"o":{"p":{"k":1,"k":2}}}', '[{"k":1,"k":1}]',
    '{"a":"bad\\q"}', '{"a":', '{"a":1}}', "", " ", "{'a':1}", '{"a":1,}', '[1 2]',
    "[" * MAX_JSON_NESTING_DEPTH + "0" + "]" * MAX_JSON_NESTING_DEPTH,
    "[" * (MAX_JSON_NESTING_DEPTH + 1) + "0" + "]" * (MAX_JSON_NESTING_DEPTH + 1),
    '{"a":' * (MAX_JSON_NESTING_DEPTH + 1) + "0" + "}" * (MAX_JSON_NESTING_DEPTH + 1),
    '{"s":"' + "[" * 5000 + '"}',  # brackets inside a string are not nesting
    '{"s":"\\"' + "[" * 5000 + '"}',
]


def _outcome(parser, payload):
    try:
        return ("ok", parser(payload))
    except ValueError as exc:  # json.JSONDecodeError is a ValueError
        return ("error", type(exc).__name__, str(exc))


@pytest.mark.parametrize("payload", CORPUS, ids=[f"case{i}" for i in range(len(CORPUS))])
def test_import_safe_reader_is_identical_to_the_readiness_parser(payload):
    assert _outcome(parse_strict_evidence_json, payload) == _outcome(readiness_parser, payload)


def test_expected_accept_reject_semantics_are_pinned():
    assert parse_strict_evidence_json('{"n":12345678901234567890}') == {"n": 12345678901234567890}
    for bad in ("NaN", "Infinity", "-Infinity", "1e10000", "9" * 400, '{"a":1,"a":2}', "[" * 513 + "0" + "]" * 513):
        with pytest.raises(ValueError):
            parse_strict_evidence_json(bad)


_BLOCK_SCRIPTS_CODE = textwrap.dedent(
    """
    import sys
    repo = sys.argv[1]
    sys.path.insert(0, repo)

    class _BlockScripts:
        # Simulates a deployment that ships the pb_* modules without the repository scripts/ directory.
        def find_spec(self, name, path=None, target=None):
            if name == "scripts" or name.startswith("scripts."):
                raise ImportError("scripts/ is not importable in this layout: " + name)
            return None

    sys.meta_path.insert(0, _BlockScripts())
    from pb_customer_output_verification import CustomerOutputVerificationError, _strict_customer_notes

    assert _strict_customer_notes('{"adapter":"commercial_takeoff","quantity":{"quantity_id":"q"}}')["adapter"] == "commercial_takeoff"
    for bad in ('{"a":NaN}', '{"a":1e10000}', '{"a":1,"a":2}', "[" * 513 + "0" + "]" * 513, "not json"):
        try:
            _strict_customer_notes(bad)
        except CustomerOutputVerificationError:
            continue
        raise SystemExit("accepted malformed notes: " + bad[:20])
    assert "scripts" not in sys.modules and not any(m.startswith("scripts.") for m in sys.modules)
    print("IMPORT_SAFE_OK")
    """
)


def test_customer_notes_parser_works_when_scripts_is_not_importable_from_another_cwd(tmp_path):
    result = subprocess.run(
        [sys.executable, "-c", _BLOCK_SCRIPTS_CODE, str(REPO)],
        cwd=tmp_path, capture_output=True, text=True, timeout=300,
    )
    assert result.returncode == 0, result.stderr[-2000:]
    assert "IMPORT_SAFE_OK" in result.stdout


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            found.add(node.module.split(".")[0])
    return found


def test_no_production_module_imports_the_scripts_namespace():
    offenders = [p.name for p in sorted(REPO.glob("pb_*.py")) if "scripts" in _imported_modules(p)]
    assert offenders == []


def test_strict_reader_is_stdlib_only():
    assert _imported_modules(REPO / "pb_strict_evidence_json.py") <= {"__future__", "json", "math"}
