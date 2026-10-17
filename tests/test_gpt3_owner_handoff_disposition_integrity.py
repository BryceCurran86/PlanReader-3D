"""A stopped original PDF owner process is not a successful source seal."""
from copy import deepcopy
import pytest
from tools.gpt3_120_target_input_fingerprint_ledger import _stable_owner_evidence

def run(state="COMPLETED", exit_code=0):
    return {
        "repo_head": "a"*40,
        "files": [],
        "project_handoffs": [{"project_id": "source-project", "status": state, "exit_code": exit_code}],
    }


def test_successful_owner_completion_is_a_valid_stable_disposition():
    assert _stable_owner_evidence(run())["handoff_results"] == [("source-project", "COMPLETED", 0)]


def test_original_memory_limit_with_no_os_exit_code_remains_blocked_not_missing():
    assert _stable_owner_evidence(run("MEMORY_LIMIT", None))["handoff_results"] == [
        ("source-project", "MEMORY_LIMIT", None)
    ]


@pytest.mark.parametrize("state,code", [
    ("COMPLETED", None), ("COMPLETED", True), ("COMPLETED", 1),
    ("MEMORY_LIMIT", 0), ("TIMEOUT", 0), ("FAILED", False),
    ("ERROR", "1"), ("FIRM_QUANTITIES_VERIFIED", 0), ("DONE", 0),
])
def test_owner_run_fingerprint_rejects_forged_completion_or_fake_success(state, code):
    with pytest.raises(ValueError, match="disposition|exit code"):
        _stable_owner_evidence(run(state, code))


def test_owner_machine_failed_process_nonzero_exit_preserved_as_failed():
    assert _stable_owner_evidence(run("FAILED", 17))["handoff_results"] == [
        ("source-project", "FAILED", 17)
    ]
