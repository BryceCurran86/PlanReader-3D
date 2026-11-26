import pytest
from scripts.ci_compare_worker_runs import compare, junit_receipt


def test_compare_rejects_missing_or_changed_outcomes(tmp_path):
    path = tmp_path / "result.xml"
    path.write_text('<testsuites><testsuite time="10"><testcase classname="a" name="x"/><testcase classname="a" name="y"><skipped type="pytest.xfail"/></testcase></testsuite></testsuites>')
    rows = [junit_receipt(path, w) for w in (0, 2, 4, 8)]
    assert "| 8 | 2 | 10.00 | 1.00x |" in compare(rows)
    with pytest.raises(ValueError, match="missing"):
        compare(rows[:-1])
    changed = [*rows[:-1], {**rows[-1], "outcomes_sha256": "changed"}]
    with pytest.raises(ValueError, match="outcome mismatch"):
        compare(changed)
    path.write_text('<testsuite time="10"><testcase classname="a" name="x"><failure/></testcase></testsuite>')
    with pytest.raises(ValueError, match="failed"):
        junit_receipt(path, 2)
    path.write_text('<testsuite time="10"><testcase classname="a" name="x"/><testcase classname="a" name="x"/></testsuite>')
    with pytest.raises(ValueError, match="duplicate"):
        junit_receipt(path, 2)
