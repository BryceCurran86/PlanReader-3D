"""Owner-approved door review wired into the project handoff tool: default off, additive only, isolated from every existing output.

Source production and the sealing of the standard families are stubbed exactly as in the other handoff tests; the review step itself is
stubbed or run on a synthetic composition.  The real chain is run separately against the original document.
Synthetic numbers only; no project width, height, area or name is used anywhere in this file.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_owner_door_review_handoff as lib
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tests.symlink_test_support import symlink_or_skip
from tests.test_live_opening_area_quantity_publication import _composition
from tests.test_owner_approved_door_review_promotion_v1 import STAMP, _approval, _owner_opening
from tests.test_source_closed_project_handoff import _quantity, _run
from tools import run_source_closed_project_handoff as handoff

PROJECT = "project-core"
REVIEW_FILES = {
    "owner_door_review/owner_door_review.sealed.json",
    "owner_door_review/verified_owner_door_review_rows.json",
}


def _verified_outcome(sha: str, project_id: str = PROJECT):
    approval = _approval(geometry_ref="opening-1", metadata={**_approval().metadata, "source_sha256": sha})
    opening = replace(_owner_opening(approval, canonical_id="opening-1"), source_sha256=sha)
    return lib.assess_owner_door_review(
        _composition(opening), approvals=(approval,), claim=SimpleNamespace(canonical_openings=(opening,)),
        workspace_id=1, project_id=project_id, source_sha256=sha)


def _empty_outcome():
    return lib.OwnerDoorReviewOutcome(lib.GATE_NO_CANDIDATES, None, (), 0, {"opening_not_in_standard_claim": 1}, 0)


class _World:
    """One stubbed core-family handoff world (same stubs as the existing core test)."""

    def __init__(self, tmp_path, monkeypatch):
        self.tmp_path = tmp_path
        self.pdf = tmp_path / "source.pdf"
        self.pdf.write_bytes(b"source-bytes")
        self.sha = hashlib.sha256(self.pdf.read_bytes()).hexdigest()
        self.seen: dict = {}
        self.steps: list = []
        self.claim = SimpleNamespace(
            status=SimpleNamespace(value="corroborated"), reason_codes=("core-resolved",), canonical_walls=(1,),
            canonical_openings=(1,), canonical_rooms=(), canonical_floors=(), canonical_spaces=(),
            room_area_quantity_evidence=(), opening_quantity_evidence=(_quantity("q-opening", "opening_area"),),
            opening_count_quantity_evidence=(_quantity("q-count", "opening_count"),))
        monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((1,), (0, 2), 3))

        def collect(*args, **kwargs):
            self.seen.update(kwargs)
            return self.claim

        monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", collect)
        for name in ("publish_live_floor_area_quantities", "collect_live_ceiling_lining_claims", "publish_live_ceiling_area_quantities"):
            monkeypatch.setattr(handoff, name, self._forbidden)
        for seal, family, qid in (("seal_live_opening_area_claim_run", "opening_area", "q-opening"),
                                  ("seal_live_opening_count_run", "opening_count", "q-count")):
            monkeypatch.setattr(handoff, seal, lambda *a, _f=family, _q=qid, **k: _run(
                project_id=PROJECT, source_sha256=self.sha, family=_f, quantity_id=_q))

    @staticmethod
    def _forbidden(*args, **kwargs):
        raise AssertionError("core handoff must not invoke surface publication")

    def approvals_file(self, entries=None, *, sha=None, name="approvals.json") -> pathlib.Path:
        entries = [{"physical_opening_id": "opening-1", "page": 2, "height_mm": 2000.0, "approved_by": "Test Approver",
                    "approved_at": STAMP}] if entries is None else entries
        path = self.tmp_path / name
        path.write_text(json.dumps({"schema_version": "1.0.0", "source_sha256": sha or self.sha, "approvals": entries}), encoding="utf-8")
        return path

    def stub_step(self, monkeypatch, outcome=None, error=None):
        def step(pdf_path, **kwargs):
            self.steps.append((pdf_path, kwargs))
            if error is not None:
                raise error
            return outcome if outcome is not None else _verified_outcome(self.sha)

        monkeypatch.setattr(lib, "run_owner_door_review_step", step)

    def run(self, name, **kwargs):
        output = self.tmp_path / name
        summary = handoff.generate_project_handoff(
            pdf_path=self.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core", **kwargs)
        return output, summary


def _tree(root: pathlib.Path) -> dict[str, bytes]:
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in sorted(root.rglob("*")) if path.is_file()}


def _normalised_summary(output: pathlib.Path, as_if: pathlib.Path) -> dict:
    text = (output / "production_summary.json").read_text(encoding="utf-8").replace(
        json.dumps(str(output))[1:-1], json.dumps(str(as_if))[1:-1])
    return json.loads(text)


# ------------------------------------------------------------------ default off

def test_default_run_never_enters_the_review_lane(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(lib, "run_owner_door_review_step", lambda *a, **k: pytest.fail("review step must not run by default"))
    output, summary = world.run("out")
    assert "owner_door_review" not in summary and summary["status"] == "sealed"
    assert not (output / "owner_door_review").exists()
    assert "owner_door_review" not in json.loads((output / "production_summary.json").read_text(encoding="utf-8"))


def test_an_explicit_none_is_the_default(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    first = _tree(world.run("a")[0])
    second = _tree(world.run("b", owner_door_height_approvals_file=None)[0])
    assert set(first) == set(second)


# ------------------------------------------------------------------ on: additive only

def test_with_approvals_the_only_additions_are_the_review_files_and_one_summary_key(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, base_summary = world.run("base")
    world.stub_step(monkeypatch)
    on_out, on_summary = world.run("on", owner_door_height_approvals_file=world.approvals_file())
    base_tree, on_tree = _tree(base_out), _tree(on_out)
    assert set(on_tree) - set(base_tree) == REVIEW_FILES and set(base_tree) - set(on_tree) == set()
    for name in set(base_tree) - {"production_summary.json"}:
        assert on_tree[name] == base_tree[name], name
    on_json = _normalised_summary(on_out, base_out)
    review = on_json.pop("owner_door_review")
    assert on_json == _normalised_summary(base_out, base_out)
    assert on_summary["status"] == base_summary["status"] == "sealed"
    assert on_summary["combined_quantity_count"] == base_summary["combined_quantity_count"]
    assert on_summary["family_run_files"].keys() == base_summary["family_run_files"].keys()
    assert review["enabled"] is True and review["first_gate"] == "OWNER_DOOR_REVIEW_VERIFIED"
    assert review["included_in_combined_run"] is False and review["benchmark_score_granted"] is False
    assert review["candidate_count"] == 1 and review["review_row_count"] == 1 and review["approval_count"] == 1
    assert review["approvals_file_sha256"] == hashlib.sha256(world.approvals_file().read_bytes()).hexdigest()


def test_the_review_files_are_a_valid_sealed_run_and_its_verified_rows(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    world.stub_step(monkeypatch)
    output, summary = world.run("on", owner_door_height_approvals_file=world.approvals_file())
    run = sealed_source_closed_run_from_dict(json.loads((output / "owner_door_review" / "owner_door_review.sealed.json").read_text(encoding="utf-8")))
    rows = json.loads((output / "owner_door_review" / "verified_owner_door_review_rows.json").read_text(encoding="utf-8"))
    assert run.run_id == summary["owner_door_review"]["review_run_id"] and set(run.source_sha256s) == {world.sha}
    assert {q.status for q in run.quantities} == {"review_required"}
    assert verify_sealed_customer_output(run, rows).customer_row_count == len(rows) == 1
    assert all(row["origin"] == "AI" and row["quantity_status"] == "To review" for row in rows)
    assert summary["owner_door_review"]["review_run_file"] == str(output / "owner_door_review" / "owner_door_review.sealed.json")
    assert summary["owner_door_review"]["review_rows_file"] == str(output / "owner_door_review" / "verified_owner_door_review_rows.json")


def test_review_rows_never_enter_the_combined_run_or_the_family_runs(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    world.stub_step(monkeypatch)
    output, summary = world.run("on", owner_door_height_approvals_file=world.approvals_file())
    combined = json.loads((output / f"{PROJECT}.core.json").read_text(encoding="utf-8"))
    review_ids = {q.quantity_id for q in _verified_outcome(world.sha).run.quantities}
    assert not (review_ids & {q["quantity_id"] for q in combined["quantities"]})
    assert sorted(p.name for p in (output / "family_runs").glob("*")) == ["opening_area.sealed.json", "opening_count.sealed.json"]
    assert summary["combined_quantity_count"] == 2
    assert not (output / "verified_customer_rows.json").exists()


def test_two_runs_write_identical_review_files(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    world.stub_step(monkeypatch)
    first = _tree(world.run("a", owner_door_height_approvals_file=world.approvals_file())[0])
    second = _tree(world.run("b", owner_door_height_approvals_file=world.approvals_file())[0])
    for name in REVIEW_FILES:
        assert first[name] == second[name]


def test_no_candidates_writes_no_review_files_and_says_why(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, _ = world.run("base")
    world.stub_step(monkeypatch, _empty_outcome())
    out, summary = world.run("on", owner_door_height_approvals_file=world.approvals_file())
    assert set(_tree(out)) == set(_tree(base_out)) and not (out / "owner_door_review").exists()
    review = summary["owner_door_review"]
    assert review["first_gate"] == "NO_REVIEW_CANDIDATES" and review["candidate_count"] == 0
    assert review["withheld_counts"] == {"opening_not_in_standard_claim": 1} and review["review_run_file"] is None
    assert review["review_rows_file"] is None and review["review_run_id"] is None and review["review_row_count"] == 0


def test_the_step_sees_exactly_the_scope_and_options_the_claim_collector_saw(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    world.stub_step(monkeypatch)
    world.run("on", owner_door_height_approvals_file=world.approvals_file(),
              source_glyph_ledger_text_trust=True)
    (pdf_path, kwargs), = world.steps
    assert pdf_path == world.pdf and kwargs["claim"] is world.claim
    assert kwargs["pages"] == world.seen["pages"] == (1,)
    assert kwargs["topology_pages"] == world.seen["topology_pages"] == (1,)
    assert kwargs["room_area_support_pages"] is world.seen["room_area_support_pages"] is None
    assert kwargs["page_count"] == 3 and kwargs["source_sha256"] == world.sha
    assert kwargs["workspace_id"] == 1 and kwargs["project_id"] == PROJECT
    assert kwargs["native_text_kwargs"] == {"source_glyph_ledger_text_trust": True}
    assert world.seen["source_glyph_ledger_text_trust"] is True
    # the lane re-derives the composition, so it must run with the option the claim collector ran with
    assert kwargs["single_width_uniform_page_door_height_shadow"] is world.seen["single_width_uniform_page_door_height_shadow"] is False


def test_the_step_gets_no_text_options_unless_the_run_has_them(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    world.stub_step(monkeypatch)
    world.run("on", owner_door_height_approvals_file=world.approvals_file())
    assert world.steps[0][1]["native_text_kwargs"] == {}


def test_the_approvals_reach_the_step_as_the_loaded_records(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    world.stub_step(monkeypatch)
    world.run("on", owner_door_height_approvals_file=world.approvals_file())
    approvals = world.steps[0][1]["approvals"]
    assert type(approvals) is lib.OwnerDoorHeightApprovals and [r.geometry_ref for r in approvals.records] == ["opening-1"]


# ------------------------------------------------------------------ failure isolation

def test_a_failing_step_changes_nothing_else_and_never_reports_rows(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, base_summary = world.run("base")
    world.stub_step(monkeypatch, error=RuntimeError("boom"))
    out, summary = world.run("on", owner_door_height_approvals_file=world.approvals_file())
    assert set(_tree(out)) == set(_tree(base_out)) and not (out / "owner_door_review").exists()
    assert summary["status"] == base_summary["status"] == "sealed"
    assert summary["owner_door_review"]["first_gate"] == "OWNER_DOOR_REVIEW_UNVERIFIED:RuntimeError"
    assert summary["owner_door_review"]["review_rows_file"] is None and summary["owner_door_review"]["review_row_count"] == 0
    assert summary["claim_reason_codes"] == base_summary["claim_reason_codes"]
    for name in set(_tree(base_out)) - {"production_summary.json"}:
        assert _tree(out)[name] == _tree(base_out)[name]


def test_a_killed_runner_leaves_the_review_lane_marked_not_run(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)

    def die(*args, **kwargs):
        raise RuntimeError("source producer unavailable")

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", die)
    output = tmp_path / "on"
    with pytest.raises(RuntimeError, match="source producer unavailable"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
            owner_door_height_approvals_file=world.approvals_file())
    persisted = json.loads((output / "production_summary.json").read_text(encoding="utf-8"))
    assert persisted["owner_door_review"]["first_gate"] == "OWNER_DOOR_REVIEW_NOT_RUN"
    assert persisted["owner_door_review"]["review_rows_file"] is None and persisted["owner_door_review"]["included_in_combined_run"] is False


def test_a_write_failure_after_the_run_file_leaves_no_review_file_behind(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, _ = world.run("base")
    world.stub_step(monkeypatch)
    real = handoff._write_json

    def flaky(path, payload):
        if pathlib.Path(path).name == "verified_owner_door_review_rows.json":
            raise OSError("disk full")
        return real(path, payload)

    monkeypatch.setattr(handoff, "_write_json", flaky)
    out, summary = world.run("on", owner_door_height_approvals_file=world.approvals_file())
    assert set(_tree(out)) == set(_tree(base_out)) and not (out / "owner_door_review").exists()
    review = summary["owner_door_review"]
    assert review["first_gate"] == "OWNER_DOOR_REVIEW_UNVERIFIED:OSError"
    assert review["review_run_id"] is None and review["review_run_file"] is None and review["review_rows_file"] is None
    assert review["review_row_count"] == 0 and summary["status"] == "sealed"


# ------------------------------------------------------------------ refused before anything is written

@pytest.mark.parametrize("group", ["surfaces", "floor_area"])
def test_families_without_openings_refuse_an_approvals_file_before_any_output(tmp_path, monkeypatch, group):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("refuse before source scope"))
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="family"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group=group,
            owner_door_height_approvals_file=world.approvals_file())
    assert not output.exists()


@pytest.mark.parametrize("make", ["wrong_document", "malformed", "missing", "directory"])
def test_a_bad_approvals_file_is_refused_before_any_output(tmp_path, monkeypatch, make):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("refuse before source scope"))
    if make == "wrong_document":
        path = world.approvals_file(sha="b" * 64)
    elif make == "malformed":
        path = world.approvals_file()
        path.write_text("{", encoding="utf-8")
    elif make == "missing":
        path = tmp_path / "absent.json"
    else:
        path = tmp_path
    output = tmp_path / "out"
    with pytest.raises(lib.OwnerDoorHeightApprovalsError):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
            owner_door_height_approvals_file=path)
    assert not output.exists()


def test_a_reused_directory_holding_review_files_is_refused_with_or_without_the_option(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    for option in (None, world.approvals_file()):
        output = tmp_path / f"reuse-{option is not None}"
        (output / "owner_door_review").mkdir(parents=True)
        (output / "owner_door_review" / "owner_door_review.sealed.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("old review output must be rejected first"))
        with pytest.raises(FileExistsError, match="existing sealed handoff artifact"):
            handoff.generate_project_handoff(
                pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
                **({} if option is None else {"owner_door_height_approvals_file": option}))
        assert (output / "owner_door_review" / "owner_door_review.sealed.json").read_text(encoding="utf-8") == "{}"


def test_an_empty_review_directory_is_not_an_existing_seal(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    output = tmp_path / "out"
    (output / "owner_door_review").mkdir(parents=True)
    summary = handoff.generate_project_handoff(
        pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core")
    assert summary["status"] == "sealed"


def test_a_symlinked_review_directory_is_refused(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    output = tmp_path / "out"
    output.mkdir()
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    symlink_or_skip(output / "owner_door_review", elsewhere, target_is_directory=True)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("symlinked review directory must be rejected first"))
    with pytest.raises(FileExistsError, match="symlink"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core")


def test_a_symlinked_review_directory_is_refused_even_where_the_os_cannot_create_one(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    output = tmp_path / "out"
    (output / "owner_door_review").mkdir(parents=True)
    real = pathlib.Path.is_symlink
    monkeypatch.setattr(pathlib.Path, "is_symlink", lambda self: True if self.name == "owner_door_review" else real(self))
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("symlinked review directory must be rejected first"))
    with pytest.raises(FileExistsError, match="symlink"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core")


def test_the_complete_handoff_forwards_the_same_support_pages_to_the_step_as_to_the_collector(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0,), (2,), 5))
    world.claim = SimpleNamespace(
        status=SimpleNamespace(value="abstained"), reason_codes=("resolved-scope",), canonical_walls=(), canonical_openings=(),
        canonical_rooms=(), canonical_floors=(), canonical_spaces=(), room_area_quantity_evidence=(), opening_quantity_evidence=(),
        opening_count_quantity_evidence=())
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", lambda *a, **k: world.seen.update(k) or world.claim)
    monkeypatch.setattr(handoff, "collect_live_ceiling_lining_claims", lambda *a, **k: SimpleNamespace())
    monkeypatch.setattr(handoff, "publish_live_ceiling_area_quantities", lambda result: ())
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda claim: ())
    world.stub_step(monkeypatch, _empty_outcome())
    output = tmp_path / "out"
    summary = handoff.generate_project_handoff(
        pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output,
        owner_door_height_approvals_file=world.approvals_file())
    (_, kwargs), = world.steps
    assert kwargs["pages"] == world.seen["pages"] == (0, 1, 2, 3, 4)
    assert kwargs["topology_pages"] == world.seen["topology_pages"] == (0,)
    assert kwargs["room_area_support_pages"] == world.seen["room_area_support_pages"] == (2,)
    assert kwargs["page_count"] == 5
    assert summary["owner_door_review"]["first_gate"] == "NO_REVIEW_CANDIDATES"


# ------------------------------------------------------------------ command line

def test_the_option_is_off_by_default_on_the_command_line():
    args = handoff._parser().parse_args(["--pdf", "a.pdf", "--project-id", "p", "--output-dir", "o"])
    assert args.owner_door_height_approvals is None


def test_the_command_line_passes_the_path_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(handoff, "generate_project_handoff", lambda **kwargs: captured.update(kwargs) or {})
    monkeypatch.setattr("sys.argv", ["run", "--pdf", "a.pdf", "--project-id", "p", "--output-dir", "o",
                                     "--owner-door-height-approvals", "approvals.json"])
    handoff.main()
    assert captured["owner_door_height_approvals_file"] == pathlib.Path("approvals.json")


def test_the_command_line_passes_nothing_when_the_option_is_absent(monkeypatch):
    captured = {}
    monkeypatch.setattr(handoff, "generate_project_handoff", lambda **kwargs: captured.update(kwargs) or {})
    monkeypatch.setattr("sys.argv", ["run", "--pdf", "a.pdf", "--project-id", "p", "--output-dir", "o"])
    handoff.main()
    assert "owner_door_height_approvals_file" not in captured
