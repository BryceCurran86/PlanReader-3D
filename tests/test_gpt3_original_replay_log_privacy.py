"""Keep private original PlanReader score and producer receipts out of Actions logs.

Contract is source-neutral: it cannot prove actual original PDF availability,
authoritative quantities, commercial publication, or an accuracy promotion.
"""
from pathlib import Path

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {
    "maryborough": {
        "file": ".github/workflows/test-gpt3-maryborough-original-floor-score-input.yml",
        "job": "original-source",
        "producer": "tools.run_gpt3_maryborough_original_floor_score_input",
        "original": "Arch_Combined_Maryborough_Service_Station.pdf",
        "sha": "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
        "private_failure": "Original Maryborough producer FAILED (private details withheld)",
    },
    "lot16": {
        "file": ".github/workflows/test-gpt3-lot16-original-sealed-score-input.yml",
        "job": "original-lot16-real-seal",
        "producer": "tools.run_gpt3_lot16_original_sealed_score_input",
        "original": "1. Construction Plans - Lot 16 Power (REV E).pdf",
        "sha": "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844",
        "private_failure": "Original Lot16 producer FAILED (private details withheld)",
    },
}


class DuplicateRejectingLoader(yaml.BaseLoader):
    pass


def _unique_mapping(loader, node):
    result = {}
    for k_node, v_node in node.value:
        key = loader.construct_object(k_node)
        if key in result:
            raise yaml.constructor.ConstructorError(
                None, None, "duplicate YAML key", k_node.start_mark,
            )
        result[key] = loader.construct_object(v_node)
    return result


DuplicateRejectingLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping,
)


def _policy(text, name):
    expected = WORKFLOWS[name]
    try:
        cfg = yaml.load(text, Loader=DuplicateRejectingLoader)
        assert set(cfg["on"]) == {"pull_request", "workflow_dispatch"}
        job = cfg["jobs"][expected["job"]]
        assert job["if"] == (
            "${{ github.event_name == 'workflow_dispatch' && "
            "github.ref == 'refs/heads/main' && github.actor == 'BryceCurran86' && "
            "github.triggering_actor == 'BryceCurran86' }}"
        )
        steps = job["steps"]
        assert any(
            s.get("uses") == "./.github/actions/provision-original-sources"
            and s.get("with", {}).get("token") == "${{ secrets.ORIGINAL_SOURCES_TOKEN }}"
            and expected["original"] in s.get("with", {}).get("names", "")
            for s in steps
        )
        full = "\n".join(s.get("run", "") for s in steps)
        assert expected["original"] in full
        assert expected["sha"] in full
        assert "tools.gpt3_original_source_preflight" in full
        assert expected["producer"] in full
        assert "if ! /usr/bin/time -v timeout 3000s python -u -m " in full
        assert "--output-dir \"$OUT/production\" > \"$OUT/producer_console.log\" 2>&1; then" in full
        assert expected["private_failure"] in full
        assert "exit 1" in full
        assert '2>&1 | tee "$OUT/producer_console.log"' not in full
        assert 'cat "$OUT/producer_console.log"' not in full
        assert 'tail "$OUT/producer_console.log"' not in full
        assert 'print(json.dumps(d' not in full
        assert "sealed_run_fingerprint" not in full
        assert "sealed_run_integrity_verified" in full
        assert "verify_sealed_customer_output" in full
        assert "sealed_source_closed_run_from_dict" in full
        assert "benchmark_score_granted" in full
        assert "frozen_v2_reconciliation_complete" in full
        if name == "maryborough":
            assert 'assert sealed.fingerprint=="9f3ab9ac1497cae5c29f8873af9287a5d6e3b3a386937fdeb37f8b5989fd780d"' in full
            assert "MARYBOROUGH_CURRENT_SOURCE_EXACT24_VERIFIED_UNPUBLISHED" in full
            assert 'json.dumps(d,sort_keys=True)' not in full
        else:
            assert "Original sealed physical inventory VERIFIED; frozen match UNRESOLVED" in full
            assert "object_identity_map_supplied" in full
        assert any(
            s.get("name") == "Destroy private originals and unpublished source reports"
            and s.get("if") == "always()"
            and "rm -rf documents/sources artifacts" in s.get("run", "")
            for s in steps
        )
        assert "actions/upload-artifact" not in text
        assert "actions/download-artifact" not in text
        return True
    except (KeyError, TypeError, ValueError, AssertionError, yaml.YAMLError):
        return False


@pytest.mark.parametrize("name", sorted(WORKFLOWS))
def test_current_workflow_keeps_positive_checks_without_private_log_contents(name):
    original = (ROOT / WORKFLOWS[name]["file"]).read_text(encoding="utf-8")
    assert _policy(original, name)


@pytest.mark.parametrize("name", sorted(WORKFLOWS))
@pytest.mark.parametrize(("old", "new"), [
    ('> "$OUT/producer_console.log" 2>&1; then',
     '2>&1 | tee "$OUT/producer_console.log"; then'),
    ('> "$OUT/producer_console.log" 2>&1; then',
     '> "$OUT/producer_console.log"; then'),
    ("if ! /usr/bin/time -v timeout 3000s python -u -m ",
     "/usr/bin/time -v timeout 3000s python -u -m "),
    ('echo "::error::', 'cat "$OUT/producer_console.log"; echo "::error::'),
    ('exit 1', 'exit 0'),
    ('"sealed_run_integrity_verified"', '"sealed_run_fingerprint"'),
    ("github.actor == 'BryceCurran86'", "github.actor == 'anyone'"),
    ("github.triggering_actor == 'BryceCurran86'",
     "github.triggering_actor == 'foreign-rerunner'"),
    ("github.triggering_actor == 'BryceCurran86'",
     "github.triggering_actor == 'BryceCurran86' || true"),
    ("&& github.triggering_actor == 'BryceCurran86'",
     "|| github.triggering_actor == 'BryceCurran86'"),
    ("github.event_name == 'workflow_dispatch'",
     "github.event_name == 'pull_request'"),
    ("github.ref == 'refs/heads/main'", "github.ref != 'refs/heads/main'"),
    ('rm -rf documents/sources artifacts', 'echo retained originals'),
])
def test_producer_log_and_source_trust_mutations_fail_closed(name, old, new):
    raw = (ROOT / WORKFLOWS[name]["file"]).read_text(encoding="utf-8")
    assert _policy(raw, name)
    assert old in raw
    assert not _policy(raw.replace(old, new, 1), name)


@pytest.mark.parametrize("name", sorted(WORKFLOWS))
def test_original_SHA_or_producer_changes_are_rejected(name):
    meta = WORKFLOWS[name]
    raw = (ROOT / meta["file"]).read_text(encoding="utf-8")
    assert _policy(raw, name)
    assert not _policy(raw.replace(meta["sha"], "0" * 64), name)
    assert not _policy(raw.replace(meta["producer"], "fake.producer"), name)


@pytest.mark.parametrize("name", sorted(WORKFLOWS))
def test_original_run_cannot_gain_upload_or_duplicate_trigger(name):
    raw = (ROOT / WORKFLOWS[name]["file"]).read_text(encoding="utf-8")
    assert not _policy(raw + "\non:\n  push:\n", name)
    assert not _policy(
        raw + "\n      - uses: actions/upload-artifact@v4\n        with:\n"
        "          path: artifacts\n",
        name,
    )


def test_score_payload_is_accepted_only_as_internal_assertion():
    text = (ROOT / WORKFLOWS["maryborough"]["file"]).read_text(encoding="utf-8")
    assert _policy(text, "maryborough")
    assert "assert d[\"denominator\"]==24" in text
    assert "assert d[\"coverage_accuracy\"]==0.0" in text
    assert 'print("MARYBOROUGH_CURRENT_SOURCE_EXACT24_VERIFIED_UNPUBLISHED")' in text
    assert 'print("MARYBOROUGH_CURRENT_SOURCE_EXACT24",json.dumps(d,sort_keys=True))' not in text


@pytest.mark.parametrize("name", sorted(WORKFLOWS))
def test_original_cleanup_cannot_be_conditioned_on_success(name):
    raw = (ROOT / WORKFLOWS[name]["file"]).read_text(encoding="utf-8")
    assert _policy(raw, name)
    original = (
        "      - name: Destroy private originals and unpublished source reports\n"
        "        if: always()"
    )
    assert original in raw
    assert not _policy(
        raw.replace(original, original.replace("always()", "success()"), 1),
        name,
    )


@pytest.mark.parametrize("name", sorted(WORKFLOWS))
@pytest.mark.parametrize(("event", "ref", "dispatcher", "rerunner", "permitted"), [
    ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "BryceCurran86", True),
    ("workflow_dispatch", "refs/heads/main", "BryceCurran86", "foreign-writer", False),
    ("workflow_dispatch", "refs/heads/main", "foreign-writer", "BryceCurran86", False),
    ("workflow_dispatch", "refs/heads/feature", "BryceCurran86", "BryceCurran86", False),
    ("pull_request", "refs/heads/main", "BryceCurran86", "BryceCurran86", False),
    ("push", "refs/heads/main", "BryceCurran86", "BryceCurran86", False),
])
def test_owner_rerun_release_gate_context(name, event, ref, dispatcher, rerunner, permitted):
    # The exact workflow guard is checked by _policy; this independently
    # exercises the four required predicates, including GitHub's distinct
    # original actor and rerun initiator identities. No secrets are used.
    raw = (ROOT / WORKFLOWS[name]["file"]).read_text(encoding="utf-8")
    assert _policy(raw, name)
    assert all((
        event == "workflow_dispatch",
        ref == "refs/heads/main",
        dispatcher == "BryceCurran86",
        rerunner == "BryceCurran86",
    )) is permitted
