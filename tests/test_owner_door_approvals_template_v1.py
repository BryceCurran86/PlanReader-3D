"""Owner door approvals template: a blank approvals file for the owner to fill in, default off, producing no value and no authority.

The library builder is exercised on synthetic compositions; the handoff wiring is exercised with the same stubbed core-family world as the
review lane.  The real chain is run separately against the original document.  Synthetic ids and numbers only; no project width, height,
area, name or door count is used anywhere in this file.
"""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
from dataclasses import replace
from types import SimpleNamespace

import pytest

import pb_owner_door_review_handoff as lib
from tests.test_live_opening_area_quantity_publication import SHA, _composition, _opening
from tests.test_owner_approved_door_review_promotion_v1 import _approval
from tests.test_owner_door_review_handoff_wiring_v1 import PROJECT, _normalised_summary, _tree, _World
from tools import run_source_closed_project_handoff as handoff

TEMPLATE_FILE = "owner_door_review/owner_door_height_approvals_template.json"
OWNER_FIELDS = ("height_mm", "approved_by", "approved_at")
STAMP = "2026-01-01T09:00:00+10:00"


def _door(canonical_id: str, *, page: str = "3", kind: str | None = "door", area_m2=None, sha: str = SHA):
    basis = None if area_m2 is None else "figured_opening_label"
    return replace(
        _opening(canonical_id=canonical_id, kind=kind, area_m2=area_m2, area_basis=basis,
                 figured_area_record_id=None if area_m2 is None else "figured-1"),
        page_id=page, source_sha256=sha)


def _claim(*openings):
    return SimpleNamespace(canonical_openings=tuple(openings))


def _build(openings, claim_openings=None, *, sha: str = SHA):
    openings = tuple(openings)
    return lib.build_owner_door_approvals_template(
        _composition(*openings), claim=_claim(*(openings if claim_openings is None else claim_openings)), source_sha256=sha)


def _write(path: pathlib.Path, document) -> pathlib.Path:
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _filled(document, **fields):
    values = {"height_mm": 2000.0, "approved_by": "Test Approver", "approved_at": STAMP, **fields}
    filled = copy.deepcopy(document)
    for entry in filled["approvals"]:
        entry.update(values)
    return filled


# ------------------------------------------------------------------ the document

def test_a_listed_door_is_an_approvals_entry_with_every_owner_field_blank():
    outcome = _build([_door("door-a")])
    assert outcome.gate == lib.GATE_TEMPLATE_READY and outcome.door_count == 1 and outcome.pages == (3,)
    assert outcome.document == {
        "schema_version": lib.OWNER_DOOR_HEIGHT_APPROVALS_SCHEMA_VERSION, "source_sha256": SHA,
        "approvals": [{"physical_opening_id": "door-a", "page": 3, "height_mm": None, "approved_by": None, "approved_at": None}],
    }


def test_entries_are_sorted_by_page_then_id_and_each_door_appears_once():
    doors = [_door("door-b", page="4"), _door("door-c", page="3"), _door("door-a", page="4")]
    outcome = _build(doors)
    assert [(e["page"], e["physical_opening_id"]) for e in outcome.document["approvals"]] == [(3, "door-c"), (4, "door-a"), (4, "door-b")]
    assert outcome.pages == (3, 4) and outcome.door_count == 3


def test_no_entry_carries_a_value_an_approver_or_a_date():
    outcome = _build([_door(f"door-{index}") for index in range(5)])
    for entry in outcome.document["approvals"]:
        assert set(entry) == {"physical_opening_id", "page", *OWNER_FIELDS}
        assert all(entry[field] is None for field in OWNER_FIELDS)
    assert set(outcome.document) == {"schema_version", "source_sha256", "approvals"}


# ------------------------------------------------------------------ the loader

def test_the_unfilled_template_is_refused_by_the_loader(tmp_path):
    path = _write(tmp_path / "t.json", _build([_door("door-a")]).document)
    with pytest.raises(lib.OwnerDoorHeightApprovalsError):
        lib.load_owner_door_height_approvals(path, source_sha256=SHA)


@pytest.mark.parametrize("blank", OWNER_FIELDS)
def test_leaving_any_one_owner_field_blank_is_still_refused(tmp_path, blank):
    document = _filled(_build([_door("door-a")]).document)
    document["approvals"][0][blank] = None
    with pytest.raises(lib.OwnerDoorHeightApprovalsError):
        lib.load_owner_door_height_approvals(_write(tmp_path / "t.json", document), source_sha256=SHA)


def test_a_filled_template_loads_as_one_approval_per_listed_door(tmp_path):
    template = _build([_door("door-b", page="4"), _door("door-a")]).document
    loaded = lib.load_owner_door_height_approvals(_write(tmp_path / "t.json", _filled(template, height_mm=1500.0)), source_sha256=SHA)
    assert [record.geometry_ref for record in loaded.records] == ["door-a", "door-b"]
    assert [record.page for record in loaded.records] == [3, 4] and loaded.pages == (3, 4)
    assert {record.value for record in loaded.records} == {1500.0}
    assert {record.approved_by for record in loaded.records} == {"Test Approver"}


def test_removing_an_entry_removes_that_door_from_the_approvals(tmp_path):
    template = _build([_door("door-a"), _door("door-b")]).document
    filled = _filled(template)
    del filled["approvals"][0]
    loaded = lib.load_owner_door_height_approvals(_write(tmp_path / "t.json", filled), source_sha256=SHA)
    assert [record.geometry_ref for record in loaded.records] == ["door-b"]


def test_the_template_is_bound_to_its_document(tmp_path):
    filled = _filled(_build([_door("door-a")]).document)
    with pytest.raises(lib.OwnerDoorHeightApprovalsError, match="different document"):
        lib.load_owner_door_height_approvals(_write(tmp_path / "t.json", filled), source_sha256="b" * 64)


# ------------------------------------------------------------------ what is listed

def test_only_doors_without_an_area_that_the_claim_also_holds_are_listed():
    listed = _door("door-listed")
    openings = [
        listed,
        _door("window-1", kind="window"),
        _door("untyped-1", kind=None),
        _door("door-with-area", area_m2=1.8),
        _door("door-outside-claim"),
    ]
    claim_openings = [opening for opening in openings if opening.canonical_opening_id != "door-outside-claim"]
    outcome = _build(openings, claim_openings)
    assert [e["physical_opening_id"] for e in outcome.document["approvals"]] == ["door-listed"]


def test_a_door_the_claim_does_not_hold_is_never_listed():
    outcome = _build([_door("door-a")], claim_openings=[])
    assert outcome.gate == lib.GATE_TEMPLATE_NO_DOORS and outcome.document is None
    assert outcome.door_count == 0 and outcome.pages == ()


@pytest.mark.parametrize("claim", [SimpleNamespace(), SimpleNamespace(canonical_openings=None), SimpleNamespace(canonical_openings="x"),
                                   SimpleNamespace(canonical_openings=(SimpleNamespace(canonical_opening_id=" door-a"),))])
def test_a_claim_without_usable_opening_ids_lists_nothing(claim):
    outcome = lib.build_owner_door_approvals_template(_composition(_door("door-a")), claim=claim, source_sha256=SHA)
    assert outcome.gate == lib.GATE_TEMPLATE_NO_DOORS and outcome.document is None


def test_an_empty_composition_lists_nothing():
    outcome = _build([])
    assert outcome.gate == lib.GATE_TEMPLATE_NO_DOORS and outcome.document is None


def test_the_listing_does_not_depend_on_input_order():
    doors = [_door("door-c", page="4"), _door("door-a"), _door("door-b")]
    forward = _build(doors).document
    assert _build(list(reversed(doors))).document == forward
    assert lib.build_owner_door_approvals_template(
        _composition(*doors), claim=_claim(*reversed(doors)), source_sha256=SHA).document == forward


def test_building_does_not_change_the_composition_or_the_claim():
    doors = [_door("door-a"), _door("door-b", kind="window")]
    composition, claim = _composition(*doors), _claim(*doors)
    openings_before = composition.canonical_openings
    before = (repr(composition), repr(claim))
    lib.build_owner_door_approvals_template(composition, claim=claim, source_sha256=SHA)
    assert (repr(composition), repr(claim)) == before
    assert composition.canonical_openings is openings_before and claim.canonical_openings == tuple(doors)


def test_two_builds_are_identical():
    doors = [_door("door-a"), _door("door-b", page="2")]
    assert _build(doors) == _build(doors)


# ------------------------------------------------------------------ refusals

def test_a_door_from_a_different_document_is_refused():
    with pytest.raises(RuntimeError, match="different document"):
        _build([_door("door-a", sha="c" * 64)])


def test_a_repeated_canonical_id_is_refused():
    with pytest.raises(RuntimeError, match="repeat"):
        _build([_door("door-a"), _door("door-a")])


@pytest.mark.parametrize("page", ["", "0", "03", "-1", "x", "²", "3.0", None, 3])
def test_a_page_id_that_is_not_a_plain_positive_page_number_is_refused(page):
    with pytest.raises(RuntimeError, match="page"):
        _build([_door("door-a", page=page)])


def test_a_foreign_window_or_a_door_with_an_area_is_not_judged():
    outcome = _build([_door("door-a"), _door("window-x", kind="window", sha="c" * 64), _door("door-y", area_m2=1.0, sha="c" * 64, page="x")])
    assert [e["physical_opening_id"] for e in outcome.document["approvals"]] == ["door-a"]


def test_inputs_are_type_checked():
    with pytest.raises(TypeError):
        lib.build_owner_door_approvals_template(object(), claim=_claim(), source_sha256=SHA)
    with pytest.raises(ValueError):
        lib.build_owner_door_approvals_template(_composition(), claim=_claim(), source_sha256="ABC")


# ------------------------------------------------------------------ the source step

def test_the_step_composes_with_no_approvals_and_the_claims_scope_and_options(tmp_path, monkeypatch):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"source-bytes")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    door = _door("door-a", sha=sha)
    seen = {}

    def compose(pdf_bytes, **kwargs):
        seen.update(kwargs, pdf_bytes=pdf_bytes)
        return _composition(door)

    monkeypatch.setattr(lib, "compose_owner_approved_opening_voids", compose)
    outcome = lib.run_owner_door_approvals_template_step(
        pdf, claim=_claim(door), source_sha256=sha, page_count=5, pages=(1, 2), topology_pages=(1,),
        room_area_support_pages=(3,), native_text_kwargs={"source_glyph_ledger_text_trust": True})
    decoded, topology, evidence = lib.claim_page_scope(5, (1, 2), (1,), (3,))
    assert seen["approvals"] == () and seen["pdf_bytes"] == b"source-bytes" and seen["source_sha256"] == sha
    assert (seen["decoded_page_ids"], seen["topology_page_ids"], seen["evidence_page_ids"]) == (decoded, topology, evidence)
    assert seen["native_text_kwargs"] == {"source_glyph_ledger_text_trust": True}
    assert outcome.gate == lib.GATE_TEMPLATE_READY and outcome.door_count == 1


def test_the_step_and_the_review_step_compose_the_same_scope(tmp_path, monkeypatch):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"source-bytes")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    door = _door("door-a", sha=sha)
    calls = []
    monkeypatch.setattr(lib, "compose_owner_approved_opening_voids",
                        lambda pdf_bytes, **kwargs: calls.append(kwargs) or _composition(door))
    scope = dict(page_count=4, pages=(0, 1, 2), topology_pages=(1,), room_area_support_pages=None,
                 native_text_kwargs={"source_native_finish_text_shadow": True})
    lib.run_owner_door_approvals_template_step(pdf, claim=_claim(door), source_sha256=sha, **scope)
    approvals = lib.OwnerDoorHeightApprovals(records=(_approval(geometry_ref="door-a", page=2),), pages=(2,), file_sha256="d" * 64)
    lib.run_owner_door_review_step(pdf, approvals=approvals, claim=_claim(door), workspace_id=1, project_id="p",
                                   source_sha256=sha, **scope)
    keys = ("decoded_page_ids", "topology_page_ids", "evidence_page_ids", "native_text_kwargs", "source_sha256")
    assert {key: calls[0][key] for key in keys} == {key: calls[1][key] for key in keys}


def test_the_step_refuses_a_changed_source(tmp_path, monkeypatch):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"source-bytes")
    monkeypatch.setattr(lib, "compose_owner_approved_opening_voids", lambda *a, **k: pytest.fail("must not compose"))
    with pytest.raises(RuntimeError, match="changed"):
        lib.run_owner_door_approvals_template_step(
            pdf, claim=_claim(), source_sha256="e" * 64, page_count=1, pages=None, topology_pages=None,
            room_area_support_pages=None, native_text_kwargs={})


@pytest.mark.parametrize("options", [{"unknown_option": True}, {"source_glyph_ledger_text_trust": False}, {"source_glyph_ledger_text_trust": 1}])
def test_the_step_accepts_only_the_collectors_explicit_text_options(tmp_path, options):
    pdf = tmp_path / "s.pdf"
    pdf.write_bytes(b"source-bytes")
    with pytest.raises(ValueError, match="text options"):
        lib.run_owner_door_approvals_template_step(
            pdf, claim=_claim(), source_sha256="e" * 64, page_count=1, pages=None, topology_pages=None,
            room_area_support_pages=None, native_text_kwargs=options)


# ------------------------------------------------------------------ the handoff wiring

def _ready_outcome(sha: str):
    door = _door("opening-1", page="2", sha=sha)
    return lib.build_owner_door_approvals_template(_composition(door), claim=_claim(door), source_sha256=sha)


def _stub(world, monkeypatch, outcome=None, error=None):
    def step(pdf_path, **kwargs):
        world.steps.append((pdf_path, kwargs))
        if error is not None:
            raise error
        return outcome if outcome is not None else _ready_outcome(world.sha)

    monkeypatch.setattr(lib, "run_owner_door_approvals_template_step", step)


def test_default_run_never_enters_the_template_lane(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(lib, "run_owner_door_approvals_template_step", lambda *a, **k: pytest.fail("template step must not run by default"))
    output, summary = world.run("out")
    assert "owner_door_approvals_template" not in summary and not (output / "owner_door_review").exists()
    assert "owner_door_approvals_template" not in json.loads((output / "production_summary.json").read_text(encoding="utf-8"))


def test_an_explicit_false_is_the_default(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    first = _tree(world.run("a")[0])
    second = _tree(world.run("b", owner_door_approvals_template=False)[0])
    assert set(first) == set(second)


def test_with_the_flag_the_only_additions_are_the_template_file_and_one_summary_key(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, base_summary = world.run("base")
    _stub(world, monkeypatch)
    on_out, on_summary = world.run("on", owner_door_approvals_template=True)
    base_tree, on_tree = _tree(base_out), _tree(on_out)
    assert set(on_tree) - set(base_tree) == {TEMPLATE_FILE} and set(base_tree) <= set(on_tree)
    for name in set(base_tree) - {"production_summary.json"}:
        assert on_tree[name] == base_tree[name], name
    normalised = _normalised_summary(on_out, base_out)
    lane = normalised.pop("owner_door_approvals_template")
    assert lane == {
        "enabled": True, "first_gate": lib.GATE_TEMPLATE_READY, "door_count": 1, "pages": [2],
        "template_file": str(base_out / TEMPLATE_FILE),
        "template_file_sha256": hashlib.sha256((on_out / TEMPLATE_FILE).read_bytes()).hexdigest(),
        "authority_granted": False, "included_in_combined_run": False, "benchmark_score_granted": False,
    }
    assert on_summary["status"] == base_summary["status"] == "sealed"
    assert normalised == _normalised_summary(base_out, base_out)


def test_the_summary_block_describes_the_file_it_wrote(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    _stub(world, monkeypatch)
    output, summary = world.run("on", owner_door_approvals_template=True)
    lane = summary["owner_door_approvals_template"]
    written = output / TEMPLATE_FILE
    assert lane["template_file"] == str(written) and lane["template_file_sha256"] == hashlib.sha256(written.read_bytes()).hexdigest()
    assert lane["first_gate"] == lib.GATE_TEMPLATE_READY and lane["door_count"] == 1 and lane["pages"] == [2]
    assert lane["authority_granted"] is False and lane["included_in_combined_run"] is False and lane["benchmark_score_granted"] is False
    assert json.loads(written.read_text(encoding="utf-8")) == _ready_outcome(world.sha).document


def test_the_written_file_is_blank_and_the_loader_refuses_it_until_filled(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    _stub(world, monkeypatch)
    output, _ = world.run("on", owner_door_approvals_template=True)
    written = output / TEMPLATE_FILE
    document = json.loads(written.read_text(encoding="utf-8"))
    assert all(entry[field] is None for entry in document["approvals"] for field in OWNER_FIELDS)
    with pytest.raises(lib.OwnerDoorHeightApprovalsError):
        lib.load_owner_door_height_approvals(written, source_sha256=world.sha)
    filled = _write(tmp_path / "filled.json", _filled(document))
    loaded = lib.load_owner_door_height_approvals(filled, source_sha256=world.sha)
    assert [record.geometry_ref for record in loaded.records] == ["opening-1"]


def test_a_filled_template_drives_the_review_lane_of_a_later_run(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    _stub(world, monkeypatch)
    output, _ = world.run("first", owner_door_approvals_template=True)
    filled = _write(tmp_path / "filled.json", _filled(json.loads((output / TEMPLATE_FILE).read_text(encoding="utf-8"))))
    seen = {}

    def review(pdf_path, **kwargs):
        seen.update(kwargs)
        return lib.OwnerDoorReviewOutcome(lib.GATE_NO_CANDIDATES, None, (), 0, {}, 0)

    monkeypatch.setattr(lib, "run_owner_door_review_step", review)
    _, summary = world.run("second", owner_door_height_approvals_file=filled)
    assert [record.geometry_ref for record in seen["approvals"].records] == ["opening-1"]
    assert "owner_door_approvals_template" not in summary and summary["owner_door_review"]["approval_count"] == 1


def test_the_template_never_enters_the_combined_run_or_the_family_runs(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    _stub(world, monkeypatch)
    output, _ = world.run("on", owner_door_approvals_template=True)
    tree = _tree(output)
    for name, payload in tree.items():
        if name != TEMPLATE_FILE and name != "production_summary.json":
            assert b"owner_door_height_approvals_template" not in payload, name
            assert b"approved_by" not in payload, name


def test_no_listed_door_writes_no_file_and_says_why(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, _ = world.run("base")
    _stub(world, monkeypatch, outcome=lib.OwnerDoorApprovalsTemplateOutcome(lib.GATE_TEMPLATE_NO_DOORS, None, 0, ()))
    out, summary = world.run("on", owner_door_approvals_template=True)
    assert set(_tree(out)) == set(_tree(base_out)) and not (out / "owner_door_review").exists()
    lane = summary["owner_door_approvals_template"]
    assert lane["first_gate"] == lib.GATE_TEMPLATE_NO_DOORS and lane["template_file"] is None and lane["door_count"] == 0


def test_the_step_sees_exactly_the_scope_and_options_the_claim_collector_saw(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    _stub(world, monkeypatch)
    world.run("on", owner_door_approvals_template=True, source_glyph_ledger_text_trust=True)
    (pdf_path, kwargs), = world.steps
    assert pdf_path == world.pdf and kwargs["claim"] is world.claim
    assert kwargs["pages"] == world.seen["pages"] == (1,)
    assert kwargs["topology_pages"] == world.seen["topology_pages"] == (1,)
    assert kwargs["room_area_support_pages"] is world.seen["room_area_support_pages"] is None
    assert kwargs["page_count"] == 3 and kwargs["source_sha256"] == world.sha
    assert kwargs["native_text_kwargs"] == {"source_glyph_ledger_text_trust": True}
    assert set(kwargs) == {"claim", "source_sha256", "page_count", "pages", "topology_pages", "room_area_support_pages", "native_text_kwargs"}


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
    _stub(world, monkeypatch, outcome=lib.OwnerDoorApprovalsTemplateOutcome(lib.GATE_TEMPLATE_NO_DOORS, None, 0, ()))
    summary = handoff.generate_project_handoff(
        pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=tmp_path / "out", owner_door_approvals_template=True)
    (_, kwargs), = world.steps
    assert kwargs["pages"] == world.seen["pages"] == (0, 1, 2, 3, 4)
    assert kwargs["topology_pages"] == world.seen["topology_pages"] == (0,)
    assert kwargs["room_area_support_pages"] == world.seen["room_area_support_pages"] == (2,)
    assert summary["owner_door_approvals_template"]["first_gate"] == lib.GATE_TEMPLATE_NO_DOORS


def test_two_runs_write_the_identical_template(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    _stub(world, monkeypatch)
    first = (world.run("a", owner_door_approvals_template=True)[0] / TEMPLATE_FILE).read_bytes()
    second = (world.run("b", owner_door_approvals_template=True)[0] / TEMPLATE_FILE).read_bytes()
    assert first == second


# ------------------------------------------------------------------ failure isolation

def test_a_failing_step_changes_nothing_else_and_writes_no_template(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, base_summary = world.run("base")
    _stub(world, monkeypatch, error=RuntimeError("boom"))
    out, summary = world.run("on", owner_door_approvals_template=True)
    assert set(_tree(out)) == set(_tree(base_out)) and not (out / "owner_door_review").exists()
    assert summary["status"] == base_summary["status"] == "sealed"
    lane = summary["owner_door_approvals_template"]
    assert lane["first_gate"] == "OWNER_DOOR_APPROVALS_TEMPLATE_UNVERIFIED:RuntimeError"
    assert lane["template_file"] is None and lane["template_file_sha256"] is None and lane["door_count"] == 0
    for name in set(_tree(base_out)) - {"production_summary.json"}:
        assert _tree(out)[name] == _tree(base_out)[name]


def test_a_write_failure_leaves_no_template_behind(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    base_out, _ = world.run("base")
    _stub(world, monkeypatch)
    real = handoff._write_text_atomic

    def flaky(path, payload):
        if pathlib.Path(path).name == lib.TEMPLATE_FILENAME:
            real(path, payload)
            raise OSError("disk full")
        return real(path, payload)

    monkeypatch.setattr(handoff, "_write_text_atomic", flaky)
    out, summary = world.run("on", owner_door_approvals_template=True)
    assert not (out / TEMPLATE_FILE).exists() and not (out / "owner_door_review").exists()
    assert set(_tree(out)) == set(_tree(base_out))
    lane = summary["owner_door_approvals_template"]
    assert lane["first_gate"] == "OWNER_DOOR_APPROVALS_TEMPLATE_UNVERIFIED:OSError" and lane["template_file"] is None
    assert summary["status"] == "sealed"


def test_a_killed_runner_leaves_the_template_lane_marked_not_run(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)

    def die(*args, **kwargs):
        raise RuntimeError("source producer unavailable")

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", die)
    output = tmp_path / "on"
    with pytest.raises(RuntimeError, match="source producer unavailable"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
            owner_door_approvals_template=True)
    persisted = json.loads((output / "production_summary.json").read_text(encoding="utf-8"))["owner_door_approvals_template"]
    assert persisted["first_gate"] == lib.GATE_TEMPLATE_NOT_RUN and persisted["template_file"] is None
    assert persisted["authority_granted"] is False and persisted["included_in_combined_run"] is False


# ------------------------------------------------------------------ refused before anything is written

def test_the_flag_excludes_the_approvals_file_option(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("refuse before source scope"))
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="mutually exclusive"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
            owner_door_approvals_template=True, owner_door_height_approvals_file=world.approvals_file())
    assert not output.exists()


@pytest.mark.parametrize("group", ["surfaces", "floor_area"])
def test_families_without_openings_refuse_the_flag_before_any_output(tmp_path, monkeypatch, group):
    world = _World(tmp_path, monkeypatch)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("refuse before source scope"))
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="family_group all or core"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group=group,
            owner_door_approvals_template=True)
    assert not output.exists()


@pytest.mark.parametrize("flag", [1, "yes", None])
def test_the_flag_must_be_an_explicit_boolean(tmp_path, monkeypatch, flag):
    world = _World(tmp_path, monkeypatch)
    output = tmp_path / "out"
    with pytest.raises(ValueError, match="explicit boolean"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
            owner_door_approvals_template=flag)
    assert not output.exists()


def test_a_reused_directory_holding_a_template_is_refused(tmp_path, monkeypatch):
    world = _World(tmp_path, monkeypatch)
    output = tmp_path / "reuse"
    (output / "owner_door_review").mkdir(parents=True)
    (output / TEMPLATE_FILE).write_text("{}", encoding="utf-8")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda *_: pytest.fail("old template must be rejected first"))
    with pytest.raises(FileExistsError, match="existing sealed handoff artifact"):
        handoff.generate_project_handoff(
            pdf_path=world.pdf, project_id=PROJECT, workspace_id=1, output_dir=output, family_group="core",
            owner_door_approvals_template=True)
    assert (output / TEMPLATE_FILE).read_text(encoding="utf-8") == "{}"


# ------------------------------------------------------------------ command line

def test_the_flag_is_off_by_default_on_the_command_line():
    args = handoff._parser().parse_args(["--pdf", "a.pdf", "--project-id", "p", "--output-dir", "o"])
    assert args.write_owner_door_approvals_template is False


def test_the_command_line_passes_the_flag_through(monkeypatch):
    captured = {}
    monkeypatch.setattr(handoff, "generate_project_handoff", lambda **kwargs: captured.update(kwargs) or {})
    monkeypatch.setattr("sys.argv", ["run", "--pdf", "a.pdf", "--project-id", "p", "--output-dir", "o",
                                     "--write-owner-door-approvals-template"])
    handoff.main()
    assert captured["owner_door_approvals_template"] is True


def test_the_command_line_passes_nothing_when_the_flag_is_absent(monkeypatch):
    captured = {}
    monkeypatch.setattr(handoff, "generate_project_handoff", lambda **kwargs: captured.update(kwargs) or {})
    monkeypatch.setattr("sys.argv", ["run", "--pdf", "a.pdf", "--project-id", "p", "--output-dir", "o"])
    handoff.main()
    assert "owner_door_approvals_template" not in captured


# ------------------------------------------------------------------ repository

def test_only_the_handoff_tool_imports_the_library_and_only_lazily():
    root = pathlib.Path(lib.__file__).resolve().parent
    importers = []
    for path in sorted(root.glob("*.py")) + sorted((root / "tools").glob("*.py")):
        if path.name in {"pb_owner_door_review_handoff.py"}:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if "pb_owner_door_review_handoff" in text:
            importers.append(path.name)
    assert importers == ["run_source_closed_project_handoff.py"]
    tool = (root / "tools" / "run_source_closed_project_handoff.py").read_text(encoding="utf-8")
    top_level = [line for line in tool.splitlines() if line.startswith(("import ", "from ")) and "pb_owner_door_review_handoff" in line]
    assert top_level == []
