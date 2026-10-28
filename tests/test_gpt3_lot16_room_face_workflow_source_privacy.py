"""Private original Lot16 room geometry never leaves the source diagnostic job.

This validates release privacy; it does NOT grant original-source, quantity,
commercial, or frozen V2 benchmark authority.
"""
from pathlib import Path
import re

import pytest
import yaml


WORKFLOW = (
    Path(__file__).resolve().parents[1]
    / ".github/workflows/diag-lot16-room-face-scope.yml"
)
LOT16_SHA256 = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
OWNER_GUARD = (
    "${{ github.event_name == 'workflow_dispatch' && "
    "github.ref == 'refs/heads/main' && github.actor == 'BryceCurran86' && "
    "github.repository == 'BryceCurran86/PlanReader-3D' && "
    "github.triggering_actor == 'BryceCurran86' }}"
)
PUBLIC_TEST_COMMAND = (
    "python -m pytest -q tests/test_source_room_label_authority_v1.py "
    "tests/test_gpt3_lot16_room_face_workflow_source_privacy.py"
)


class StrictLoader(yaml.BaseLoader):
    """Do not allow a duplicate YAML key to override a privacy requirement."""


def _unique_mapping(loader, node):
    output = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in output:
            raise yaml.constructor.ConstructorError(
                None, None, "duplicate YAML mapping key", key_node.start_mark,
            )
        output[key] = loader.construct_object(value_node)
    return output


StrictLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping,
)


def _contract(source):
    """Strictly validate the CI source-disclosure boundary and fail-closed gate."""
    try:
        doc = yaml.load(source, Loader=StrictLoader)
        assert isinstance(doc, dict)
        triggers = doc["on"]
        assert set(triggers) == {"workflow_dispatch", "pull_request"}
        assert doc["permissions"] == {"contents": "read"}
        assert doc["jobs"].keys() == {"source-neutral", "source-room-face"}
        public = doc["jobs"]["source-neutral"]
        assert set(public) == {"runs-on", "timeout-minutes", "steps"}
        public_steps = public["steps"]
        assert public["runs-on"] == "ubuntu-latest"
        assert len(public_steps) == 4
        assert public_steps[0] == {
            "uses": "actions/checkout@v4",
            "with": {"persist-credentials": "false"},
        }
        assert public_steps[1]["uses"] == "actions/setup-python@v5"
        assert public_steps[1]["with"]["python-version"] == "3.13"
        assert public_steps[2]["run"] == "pip install -r requirements.txt -r requirements-ci-v1228.txt"
        assert public_steps[3]["run"] == PUBLIC_TEST_COMMAND
        assert public_steps[3]["env"] == {"PYTHONPATH": "."}
        for forbidden in (
            "secrets", "ORIGINAL_SOURCES", "documents/sources",
            "tools/diag_lot16_room_face_scope.py", "provision-original-sources",
        ):
            assert forbidden not in str(public)
        job = doc["jobs"]["source-room-face"]
        assert set(job) == {"if", "runs-on", "timeout-minutes", "steps"}
        assert job["if"] == OWNER_GUARD
        assert job["runs-on"] == "ubuntu-latest"
        steps = job["steps"]
        assert len(steps) == 7
        assert steps[0] == {
            "uses": "actions/checkout@v4",
            "with": {"ref": "${{ github.sha }}", "persist-credentials": "false"},
        }
        assert steps[1]["uses"] == "actions/setup-python@v5"
        assert steps[2]["name"] == "Install pinned dependencies"
        assert steps[3]["env"] == {"EXPECTED_SHA": "${{ github.sha }}"}
        assert steps[3]["run"] == 'test "$(git rev-parse HEAD)" = "$EXPECTED_SHA"'
        assert steps[4]["uses"] == "./.github/actions/provision-original-sources"
        assert steps[4]["with"] == {
            "token": "${{ secrets.ORIGINAL_SOURCES_TOKEN }}",
            "repository": "${{ vars.ORIGINAL_SOURCES_REPOSITORY }}",
            "ref": "${{ vars.ORIGINAL_SOURCES_REF }}",
            "names": "1. Construction Plans - Lot 16 Power (REV E).pdf",
            "allow-missing": "false",
        }
        assert steps[5]["name"] == "Run original Lot16 source page-3 diagnostic"
        assert steps[6]["if"] == "always()"
        assert steps[6]["run"] == "rm -rf documents/sources"
        assert all("if" not in step for step in (*public_steps, *steps[:6]))
        assert "continue-on-error" not in source
        assert all("upload-artifact" not in str(step) for step in steps)
        assert all("download-artifact" not in str(step) for step in steps)
        assert "actions/upload-artifact" not in source
        assert source.count("${{ secrets.ORIGINAL_SOURCES_TOKEN }}") == 1
        assert "github.event.pull_request.head.sha" not in str(job)
        assert "tee " not in source
        assert "cat lot16-room-face" not in source
        assert "retention-days:" not in source
        script = steps[5]["run"]
        assert f'expected = "{LOT16_SHA256}"' in script
        assert 'Path("documents/sources").glob("*.pdf")' in script
        assert "hashlib.sha256(path.read_bytes()).hexdigest() == expected" in script
        assert "if len(matched) != 1:" in script
        assert '"tools/diag_lot16_room_face_scope.py"' in script
        assert '"--pdf", str(matched[0]), "--page-index", "2"' in script
        assert '"--output", str(Path(temporary) / "lot16-room-face-scope.json")' in script
        assert 'with TemporaryDirectory(prefix="gpt3-lot16-private-source-") as temporary:' in script
        assert "stdout=subprocess.DEVNULL" in script
        assert "stderr=subprocess.DEVNULL" in script
        assert "check=False" in script
        assert "if completed.returncode != 0:" in script
        assert "raise SystemExit(" in script
        assert "(private source details withheld)" in script
        assert "private report unpublished" in script
        assert "print(json.dumps(" not in script
        assert "print(completed." not in script
        assert "capture_output=True" not in script
        assert "shell=True" not in script
        assert "subprocess.run(" in script
        assert re.search(r"\n\s+python - <<'PY'\n", source)
        return True
    except (AssertionError, ValueError, TypeError, KeyError, yaml.YAMLError):
        return False


def test_original_source_diagnostic_hides_report_and_still_fails_closed():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _contract(raw)
    assert raw.count("Original Lot16 room-face validation PASS") == 1
    assert raw.count("Original Lot16 room-face validation FAILED") == 1


@pytest.mark.parametrize(("old", "new"), [
    ("stdout=subprocess.DEVNULL", "stdout=subprocess.PIPE"),
    ("stderr=subprocess.DEVNULL", "stderr=subprocess.PIPE"),
    ("stdout=subprocess.DEVNULL", "stdout=None"),
    ("stderr=subprocess.DEVNULL", "stderr=None"),
    ("check=False", "check=True"),
    ("if completed.returncode != 0:", "if completed.returncode == 0:"),
    ('"gpt3-lot16-private-source-"', '"other"'),
    ("TemporaryDirectory(prefix=", "Path(prefix="),
    ('str(Path(temporary) / "lot16-room-face-scope.json")',
     '"lot16-room-face-scope.json"'),
    ('expected = "' + LOT16_SHA256 + '"', 'expected = "' + "f" * 64 + '"'),
    ('if len(matched) != 1:', 'if not matched:'),
    ('hashlib.sha256(path.read_bytes()).hexdigest() == expected', 'True'),
    ('"--page-index", "2"', '"--page-index", "3"'),
    ('"--pdf", str(matched[0])', '"--pdf", str(candidates[0])'),
    ("(private source details withheld)", "(full source report in logs)"),
    ("private report unpublished", "private report uploaded"),
])
def test_privacy_and_original_authority_mutations_are_rejected(old, new):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert old in raw
    assert _contract(raw)
    assert not _contract(raw.replace(old, new, 1))


@pytest.mark.parametrize("appended", [
    "\n      - uses: actions/upload-artifact@v4\n        with:\n"
    "          path: lot16-room-face-scope.json\n",
    "\n      - uses: actions/download-artifact@v4\n",
    "\n      - name: expose report\n"
    "        run: cat lot16-room-face-scope.json\n",
    "\n      - name: echo private token\n"
    "        run: echo ${{ secrets.ORIGINAL_SOURCES_TOKEN }}\n",
])
def test_extra_artifact_or_source_disclosure_steps_are_rejected(appended):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _contract(raw)
    assert not _contract(raw + appended)


def test_duplicate_workflow_yaml_keys_are_rejected():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _contract(raw)
    assert not _contract(raw + "\non:\n  push:\n")


@pytest.mark.parametrize(("old", "new"), [
    ("github.event_name == 'workflow_dispatch'", "github.event_name == 'pull_request'"),
    ("github.ref == 'refs/heads/main'", "github.ref == 'refs/heads/feature'"),
    ("github.actor == 'BryceCurran86'", "github.actor == 'foreign-writer'"),
    ("github.triggering_actor == 'BryceCurran86'", "github.triggering_actor == 'foreign-writer'"),
    ("github.repository == 'BryceCurran86/PlanReader-3D'", "true"),
    (" && github.triggering_actor", " || github.triggering_actor"),
    ("ref: ${{ github.sha }}", "ref: ${{ github.event.pull_request.head.sha }}"),
    ("persist-credentials: false", "persist-credentials: true"),
    ("contents: read", "contents: write"),
    ('allow-missing: "false"', 'allow-missing: "true"'),
    ("names: 1. Construction Plans - Lot 16 Power (REV E).pdf", "names: another-original.pdf"),
    ("if: always()", "if: success()"),
    ("run: rm -rf documents/sources", "run: echo retained-original"),
    (PUBLIC_TEST_COMMAND, "echo source-free-tests-passed"),
    (PUBLIC_TEST_COMMAND, PUBLIC_TEST_COMMAND + " && python tools/diag_lot16_room_face_scope.py"),
    ("  source-neutral:\n", "  source-neutral:\n    if: false\n"),
    ("      - name: Run original Lot16 source page-3 diagnostic\n",
     "      - name: Run original Lot16 source page-3 diagnostic\n        if: false\n"),
    ("    timeout-minutes: 55\n", "    timeout-minutes: 55\n    continue-on-error: true\n"),
])
def test_public_and_original_execution_boundary_mutations_are_rejected(old, new):
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _contract(raw)
    assert old in raw
    assert not _contract(raw.replace(old, new, 1))


def test_public_job_cannot_consume_private_source_token_or_add_a_source_step():
    raw = WORKFLOW.read_text(encoding="utf-8")
    assert _contract(raw)
    public_header = "      - name: Source-free room-label and workflow privacy checks"
    for inserted in (
        "      - run: echo ${{ secrets.ORIGINAL_SOURCES_TOKEN }}\n",
        "      - uses: ./.github/actions/provision-original-sources\n",
        "      - run: python tools/diag_lot16_room_face_scope.py\n",
    ):
        assert not _contract(raw.replace(public_header, inserted + public_header, 1))


def test_source_fixture_never_proves_positive_original_authority():
    # A static contract cannot prove that the private original existed or
    # that the diagnostic completed. No new customer/score evidence follows.
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "score" not in text.lower()
    assert "commercial_projection_allowed" not in text
