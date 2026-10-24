"""Retention-harness contracts; fake child execution is not source validation."""
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.run_gptmax_original_retention_check as audit


@pytest.fixture
def setup(tmp_path, monkeypatch):
    pdf = tmp_path/"source.pdf"
    pdf.write_bytes(b"test source bytes, not a real drawing")
    archived = tmp_path/"archive"
    archived.mkdir()
    for name in audit.SIGNED_FILES: (archived/name).write_text('{"test":"retained"}\n')
    state = dict(head="a"*40,dirty="")
    def git(repo,*args):
        if args == ("rev-parse","HEAD"):return state["head"]
        if args == ("rev-parse","HEAD^{tree}"):return "b"*40
        return state["dirty"]
    monkeypatch.setattr(audit,"_git",git)
    monkeypatch.setattr(audit,"_environment",lambda _: {"unit_test_environment":True})
    args = dict(project="lot16",pdf=pdf,expected_source_sha256=sha256(pdf.read_bytes()).hexdigest(),
                archived=archived,output=tmp_path/"output",expected_head="a"*40)
    return args,state


@pytest.mark.parametrize("failure", ["head","dirty","source","output","archive","archive-output"])
def test_failed_preflight_never_runs_a_source_producer(setup, monkeypatch, failure):
    args,state = setup
    if failure == "head":state["head"]="c"*40
    elif failure == "dirty":state["dirty"]=" M pb_uncommitted.py"
    elif failure == "source":args["pdf"].write_bytes(b"changed")
    elif failure == "output":args["output"].mkdir()
    elif failure == "archive":(args["archived"]/audit.SIGNED_FILES[0]).unlink()
    elif failure == "archive-output":args["output"]=args["archived"]/"new-replay"
    def forbidden(*args,**kwargs):raise AssertionError("invalid preflight executed producer")
    monkeypatch.setattr(audit.subprocess,"run",forbidden)
    with pytest.raises((ValueError,FileExistsError)):
        audit.run_retention_check(**args)


@pytest.mark.parametrize("damage", ["different-output","missing-output","source-changed",
                                    "archive-changed","head-changed","failed-child",None])
def test_receipt_distinguishes_execution_retention_and_mutation(setup, monkeypatch, damage):
    args,state = setup
    def child(command,**kwargs):
        production = Path(command[-1]);production.mkdir(parents=True)
        if damage != "missing-output":
            for name in audit.SIGNED_FILES:
                (production/name).write_bytes((args["archived"]/name).read_bytes())
        if damage == "different-output":(production/audit.SIGNED_FILES[0]).write_text("changed")
        if damage == "source-changed":args["pdf"].write_bytes(b"changed source")
        if damage == "archive-changed":(args["archived"]/audit.SIGNED_FILES[0]).write_text("changed archive")
        if damage == "head-changed":state["head"]="c"*40
        return SimpleNamespace(returncode=1 if damage == "failed-child" else 0)
    monkeypatch.setattr(audit.subprocess,"run",child)
    receipt = audit.run_retention_check(**args)
    assert receipt["retention_verified"] is (damage is None)
    assert receipt["source_replay_completed"] is (damage != "failed-child")
    assert receipt["benchmark_score_granted"] is False
    assert receipt["commercial_promotion_granted"] is False
    assert json.loads((args["output"]/"retention_receipt.json").read_text()) == receipt


def test_file_comparison_does_not_claim_execution(tmp_path):
    produced, archived = tmp_path/"new",tmp_path/"old"
    produced.mkdir();archived.mkdir()
    for name in audit.SIGNED_FILES:
        (produced/name).write_bytes(b"retained");(archived/name).write_bytes(b"retained")
    evidence = audit.compare_retained_source_files(produced,archived)
    assert all(e["byte_identical"] for e in evidence)
    assert all("source_replay_completed" not in e for e in evidence)
