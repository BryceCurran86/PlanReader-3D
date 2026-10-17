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
    ("MEMORY_LIMIT", 0), ("TIMEOUT", 0), ("PROCESS_FAILED", False),
    ("PROCESS_FAILED", None), ("PROCESS_FAILED", 0),
    ("PRIMARY_SOURCE_UNAVAILABLE", 0), ("SYSTEM_MEMORY_GUARD", 1),
    ("MEMORY_LIMIT", 17), ("TIMEOUT", 19),
    ("FAILED", 17), ("ERROR", "1"), ("FIRM_QUANTITIES_VERIFIED", 0), ("DONE", 0),
    ([], 0), ({}, 0), (None, 0),
])
def test_owner_run_fingerprint_rejects_forged_completion_or_fake_success(state, code):
    with pytest.raises(ValueError, match="disposition|exit code"):
        _stable_owner_evidence(run(state, code))


def test_owner_machine_failed_process_nonzero_exit_preserved_as_failed():
    assert _stable_owner_evidence(run("PROCESS_FAILED", 17))["handoff_results"] == [
        ("source-project", "PROCESS_FAILED", 17)
    ]

@pytest.mark.parametrize("status", [
    "TIMEOUT", "MEMORY_LIMIT", "SYSTEM_MEMORY_GUARD",
    "PRIMARY_SOURCE_UNAVAILABLE",
])
def test_actual_launcher_blocked_statuses_keep_null_exit_code(status):
    assert _stable_owner_evidence(run(status, None))["handoff_results"] == [
        ("source-project", status, None)
    ]


def test_actual_launcher_process_failed_is_negative_not_completed():
    assert _stable_owner_evidence(run("PROCESS_FAILED", -9))["handoff_results"] == [
        ("source-project", "PROCESS_FAILED", -9)
    ]
