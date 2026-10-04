import threading

from pb_diagnostic_utilities import _DIAGNOSTIC_MAX_ENTRIES, _diag_record


def test_diagnostics_records() -> None:
    class FakeOwner:
        pass

    owner = FakeOwner()
    key = ("doc", "rev", "sha", "snap", "page", "scope", "candidate")
    record = {
        "stage": "physical_wall_candidate_scope",
        "authority": "PhysicalWallCandidateAuthority",
        "function": "_assemble_scope_result",
        "document_id": "doc",
        "revision_id": "rev",
        "snapshot_id": "snap",
        "decision_scope_id": "scope",
        "candidate_id": "candidate",
    }

    _diag_record(owner, key, record)
    assert key in owner._diag_first_failure
    assert owner._diag_first_failure[key]["stage"] == "physical_wall_candidate_scope"


def test_diag_eviction_policy() -> None:
    class FakeOwner:
        pass

    original_limit = _DIAGNOSTIC_MAX_ENTRIES
    try:
        import pb_diagnostic_utilities as utils

        utils._DIAGNOSTIC_MAX_ENTRIES = 2
        owner = FakeOwner()
        for i in range(5):
            key = (f"k{i}",)
            _diag_record(owner, key, {"stage": f"stage-{i}", "index": i})
        assert len(owner._diag_first_failure) <= 2
        assert list(owner._diag_first_failure.keys())[-1] == ("k4",)
    finally:
        utils._DIAGNOSTIC_MAX_ENTRIES = original_limit


def test_diagnostics_are_thread_safe() -> None:
    class FakeOwner:
        pass

    owner = FakeOwner()
    barrier = threading.Barrier(2)

    def worker(idx: int) -> None:
        barrier.wait()
        _diag_record(owner, (f"thread-{idx}",), {"stage": "t", "idx": idx})

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(owner._diag_first_failure) == 2


if __name__ == "__main__":
    test_diagnostics_records()
    test_diag_eviction_policy()
    test_diagnostics_are_thread_safe()
    print("diagnostics tests passed")
