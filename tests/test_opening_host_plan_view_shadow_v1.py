"""Report-only floor-plan view ownership of opening host bindings (#4764 7211359981, geometry task C01).

Synthetic geometry and synthetic sheets only.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest

import pb_opening_host_plan_view_shadow as shadow
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_binding_authority import OpeningHostBindingProducer
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_wall_opening_authority_composition import _host_fixture_pdf, _ingest
from tests.test_physical_wall_candidate_viewport_scope_v1 import _draw_plan
from tests.test_source_owned_physical_plan_view import _sheet

VIEW = ("v1", (0.0, 0.0, 100.0, 100.0))
OPENING = [(40.0, 49.0), (50.0, 49.0), (50.0, 51.0), (40.0, 51.0)]
MEMBERS = [[(10.0, 50.0), (40.0, 50.0)], [(50.0, 50.0), (90.0, 50.0)]]


def _outcome(opening=OPENING, members=MEMBERS, views=(VIEW,)):
    result = shadow.plan_view_ownership(opening, members, views)
    return result.status, result.reason_codes[-1], result.view_id


def test_one_view_containing_the_opening_and_every_wall_owns_the_binding():
    assert _outcome() == (Status.CORROBORATED, shadow.OWNED, "v1")
    other = ("v2", (200.0, 200.0, 300.0, 300.0))
    assert _outcome(views=(other, VIEW)) == (Status.CORROBORATED, shadow.OWNED, "v1")
    on_edge = [[(0.0, 50.0), (40.0, 50.0)], [(50.0, 50.0), (100.0, 50.0)]]
    assert _outcome(members=on_edge)[:2] == (Status.CORROBORATED, shadow.OWNED)


@pytest.mark.parametrize("kwargs, status, reason", [
    ({"views": ()}, Status.ABSTAINED, shadow.NO_PLAN_VIEW),
    ({"views": (("v", (200.0, 200.0, 300.0, 300.0)),)}, Status.ABSTAINED, shadow.OUTSIDE),
    ({"views": (("v", (0.0, 0.0, 0.0, 100.0)),)}, Status.ABSTAINED, shadow.NO_PLAN_VIEW),  # a degenerate box is no view
    ({"members": [[(10.0, 50.0), (40.0, 50.0)], [(50.0, 50.0), (100.01, 50.0)]]}, Status.ABSTAINED, shadow.SPLIT),
    ({"views": (VIEW, ("v2", (0.0, 0.0, 200.0, 200.0)))}, Status.CONFLICT, shadow.AMBIGUOUS),
    ({"opening": []}, Status.ABSTAINED, shadow.UNAVAILABLE),
    ({"members": []}, Status.ABSTAINED, shadow.UNAVAILABLE),
    ({"members": [[(10.0, 50.0), (40.0, 50.0)], []]}, Status.ABSTAINED, shadow.UNAVAILABLE),
    ({"members": [[(10.0, float("nan")), (40.0, 50.0)]]}, Status.ABSTAINED, shadow.UNAVAILABLE),
])
def test_everything_else_abstains_or_conflicts_with_a_typed_reason(kwargs, status, reason):
    got_status, got_reason, view_id = _outcome(**kwargs)
    assert (got_status, got_reason, view_id) == (status, reason, None)


def _moved(transform):
    box = [transform((VIEW[1][0], VIEW[1][1])), transform((VIEW[1][2], VIEW[1][3]))]
    xs, ys = sorted(p[0] for p in box), sorted(p[1] for p in box)
    return {"opening": [transform(p) for p in OPENING], "members": [[transform(p) for p in m] for m in MEMBERS],
            "views": (("v1", (xs[0], ys[0], xs[1], ys[1])),)}


@pytest.mark.parametrize("transform", [
    lambda p: (p[0] + 731.5, p[1] - 12.25), lambda p: (p[0] * 3.7, p[1] * 3.7), lambda p: (p[1], p[0]),
    lambda p: (100.0 - p[0], 100.0 - p[1])], ids=["translate", "scale", "transpose", "rotate180"])
def test_ownership_is_invariant_to_moving_the_whole_drawing(transform):
    assert _outcome(**_moved(transform)) == (Status.CORROBORATED, shadow.OWNED, "v1")


def test_input_order_and_wall_splitting_do_not_change_the_outcome():
    split = [[(10.0, 50.0), (25.0, 50.0)], [(25.0, 50.0), (40.0, 50.0)], [(50.0, 50.0), (90.0, 50.0)]]
    other = ("v0", (200.0, 200.0, 300.0, 300.0))
    first = _outcome(members=split, views=(other, VIEW, VIEW))
    second = _outcome(opening=list(reversed(OPENING)), members=list(reversed(split)), views=(VIEW, other))
    assert first == second == _outcome()


def _published(data):
    source = SourceVisibilityProducer(producer_method="host-plan-view-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="host-plan-view", source_bytes=data,
                                               source_locator="memory://plan.pdf", page_ids=("1",))
    return source, published


def _walls(source):
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=("1",)).authority()
    return authority


def _trace(identity, *, members, status=Status.CORROBORATED, host="group-1"):
    return SimpleNamespace(opening_identity_id=identity, representative_observation_id=f"obs-{identity}", page_id="1",
                           status=status, reason_codes=("opening_host_binding_resolved",), record_id=None,
                           host_wall_id=host, member_wall_candidate_ids=tuple(members))


def _composition(published, walls, traces, apertures):
    def prove_existence(selector):
        identity = selector.observation_id.removeprefix("obs-")
        record = SimpleNamespace(record_id=identity, page_id="1", aperture_bbox_pt=apertures[identity])
        return SimpleNamespace(existence_record=record)

    return SimpleNamespace(revision_id=published.revision.revision_id, page_ids=("1",), opening_bindings=tuple(traces),
                           physical_opening_authority=SimpleNamespace(prove_existence=prove_existence),
                           physical_wall_candidate_authority=walls, supplemental_physical_wall_candidate_authority=None)


def _plan_report(tmp_path):
    path = tmp_path / "plan.pdf"
    _draw_plan(path)
    source, published = _published(path.read_bytes())
    walls = _walls(source)
    scope = walls.resolve_scope(shadow.PhysicalWallCandidateSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id, page_id="1",
        decision_scope_id=shadow._decision_scope_id("1")))
    wall = sorted(record.wall_candidate_id for record in scope.records  # an interior wall, not the sheet frame
                  if all(60 < x < 400 and 40 < y < 320 for x, y in record.wall_candidate.centerline_pts))[0]
    traces = [
        _trace("inside", members=[wall]),
        _trace("outside", members=[wall]),
        _trace("unknown-wall", members=["wall_missing"]),
        _trace("not-bound", members=[], status=Status.ABSTAINED, host=None),
    ]
    apertures = {"inside": (150.0, 78.0, 170.0, 82.0), "outside": (450.0, 360.0, 470.0, 364.0),
                 "unknown-wall": (150.0, 78.0, 170.0, 82.0), "not-bound": None}
    composition = _composition(published, walls, traces, apertures)
    return source, composition, traces


def test_the_report_finds_the_authenticated_plan_view_that_owns_a_binding(tmp_path):
    source, composition, traces = _plan_report(tmp_path)
    before = [vars(t).copy() for t in traces]
    first = shadow.opening_host_plan_view_report(composition, source)
    second = shadow.opening_host_plan_view_report(composition, source)
    assert first == second and [vars(t) for t in traces] == before
    (page,) = first["pages"]
    assert page["plan_views"] == {"authenticated": 1, "proven": 0}
    assert page["host_bindings"] == 3 and page["other_opening_traces"] == 1
    by_id = {row["opening_identity_id"]: row for row in page["rows"]}
    assert by_id["inside"]["authenticated"]["reason_codes"] == [shadow.OWNED]
    assert by_id["inside"]["authenticated"]["status"] == Status.CORROBORATED.value
    assert by_id["inside"]["proven"]["reason_codes"][-1] == shadow.NO_PLAN_VIEW
    assert by_id["outside"]["authenticated"]["reason_codes"][-1] == shadow.SPLIT  # wall inside, opening outside
    assert by_id["unknown-wall"]["authenticated"]["reason_codes"][-1] == shadow.UNAVAILABLE
    assert by_id["inside"]["combined"] == by_id["inside"]["authenticated"]
    assert page["ownership"]["combined"][shadow.OWNED] == 1


def test_a_schedule_sheet_owns_no_binding():
    source, published = _published(_sheet(role="DOOR SCHEDULE"))
    walls = _walls(source)
    composition = _composition(published, walls, [_trace("door", members=["wall_x"])],
                               {"door": (150.0, 150.0, 170.0, 154.0)})
    (page,) = shadow.opening_host_plan_view_report(composition, source)["pages"]
    assert page["plan_views"] == {"authenticated": 0, "proven": 0}
    assert page["rows"][0]["authenticated"]["status"] == Status.ABSTAINED.value


def test_a_proven_plan_view_alone_owns_a_binding():
    source, published = _published(_sheet())  # the stricter source-owned view only; the F.07 builder authenticates none
    wall = SimpleNamespace(wall_candidate_id="w", wall_candidate=SimpleNamespace(
        centerline_pts=((100.0, 200.0), (300.0, 200.0)), curve_control_pts=None))
    walls = SimpleNamespace(selectors_for_authenticated_viewports=lambda **_: (),
                            resolve_scope=lambda _: SimpleNamespace(records=(wall,)))
    composition = _composition(published, walls, [_trace("door", members=["w"])], {"door": (150.0, 198.0, 170.0, 202.0)})
    (page,) = shadow.opening_host_plan_view_report(composition, source)["pages"]
    assert page["plan_views"] == {"authenticated": 0, "proven": 1}
    (row,) = page["rows"]
    assert row["authenticated"]["reason_codes"][-1] == shadow.NO_PLAN_VIEW
    assert row["proven"]["reason_codes"] == row["combined"]["reason_codes"] == [shadow.OWNED]


def _framed(tmp_path, title):
    path = tmp_path / "framed.pdf"
    _draw_plan(path)
    with fitz.open(path) as document:
        page = document[0]
        page.add_redact_annot(fitz.Rect(70, 295, 300, 320), fill=(1, 1, 1))
        page.apply_redactions(graphics=fitz.PDF_REDACT_LINE_ART_NONE)
        page.insert_text((80, 310), title, fontsize=11)
        return document.tobytes()


def test_only_floor_plan_views_can_own_a_binding(tmp_path):
    source, published = _published(_framed(tmp_path, "NORTH ELEVATION"))
    scopes = shadow._build_authenticated_viewport_scope_results(
        source_producer=source, published=published, source_bytes=source._producer._store.source_bytes_by_revision[
            published.revision.revision_id], page_id="1")
    assert [scope.viewport_view_type for scope in scopes] == ["elevation"]  # authenticated, but not a plan
    composition = _composition(published, _walls(source), [_trace("w", members=["wall_x"])],
                               {"w": (150.0, 78.0, 170.0, 82.0)})
    (page,) = shadow.opening_host_plan_view_report(composition, source)["pages"]
    assert page["plan_views"]["authenticated"] == 0


def test_disagreeing_wall_geometry_or_another_opening_record_is_unavailable(tmp_path):
    source, composition, traces = _plan_report(tmp_path)
    wall = traces[0].member_wall_candidate_ids[0]
    moved = SimpleNamespace(wall_candidate_id=wall, wall_candidate=SimpleNamespace(
        centerline_pts=((100.0, 100.0), (101.0, 100.0)), curve_control_pts=None))
    composition.supplemental_physical_wall_candidate_authority = SimpleNamespace(
        selectors_for_authenticated_viewports=lambda **_: (), resolve_scope=lambda _: SimpleNamespace(records=(moved,)))
    (page,) = shadow.opening_host_plan_view_report(composition, source)["pages"]
    row = next(row for row in page["rows"] if row["opening_identity_id"] == "inside")
    assert row["authenticated"]["reason_codes"][-1] == shadow.UNAVAILABLE

    composition.supplemental_physical_wall_candidate_authority = None
    real = composition.physical_opening_authority.prove_existence
    for change in ({"record_id": "someone-else"}, {"page_id": "2"}):
        composition.physical_opening_authority = SimpleNamespace(prove_existence=lambda selector, change=change:
            SimpleNamespace(existence_record=SimpleNamespace(**{**vars(real(selector).existence_record), **change})))
        (page,) = shadow.opening_host_plan_view_report(composition, source)["pages"]
        assert {row["authenticated"]["reason_codes"][-1] for row in page["rows"]} == {shadow.UNAVAILABLE}


def test_only_a_source_producer_is_accepted():
    with pytest.raises(TypeError):
        shadow.opening_host_plan_view_report(SimpleNamespace(revision_id="r"), object())


def test_only_the_flag_guarded_composition_imports_the_module():
    root = Path(__file__).resolve().parents[1]
    importers = [path.relative_to(root).as_posix() for path in root.rglob("*.py")
                 if not {"tests", "tools"} & set(path.relative_to(root).parts[:1])
                 and path.name != "pb_opening_host_plan_view_shadow.py"
                 and "pb_opening_host_plan_view_shadow" in path.read_text(encoding="utf-8", errors="ignore")]
    assert importers == ["pb_live_wall_opening_authority_composition.py"]
    script = ("import sys\n"
              "from tests.test_live_wall_opening_authority_composition import _host_fixture_pdf, _ingest\n"
              "from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority as compose\n"
              "source, published = _ingest(_host_fixture_pdf(), 'default-off')\n"
              "compose(source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=('1',))\n"
              "sys.exit(int('pb_opening_host_plan_view_shadow' in sys.modules))\n")
    assert subprocess.run([sys.executable, "-c", script], cwd=root).returncode == 0


@pytest.mark.parametrize("authenticated, proven, expected", [
    ("v", None, shadow.OWNED), (None, "p", shadow.OWNED), ("v", "p", shadow.OWNED),
    (None, None, shadow.NO_PLAN_VIEW)])
def test_either_view_builder_may_own_a_binding(authenticated, proven, expected):
    def result(view):
        if view is None:
            return shadow.PlanViewOwnership(Status.ABSTAINED, (shadow.UNPROVEN, shadow.NO_PLAN_VIEW))
        return shadow.PlanViewOwnership(Status.CORROBORATED, (shadow.OWNED,), view)

    combined = shadow.combine_ownership(result(authenticated), result(proven))
    assert combined.reason_codes[-1] == expected


def test_a_conflict_or_a_measured_outside_beats_a_missing_view():
    owned = shadow.PlanViewOwnership(Status.CORROBORATED, (shadow.OWNED,), "v")
    conflict = shadow.PlanViewOwnership(Status.CONFLICT, (shadow.UNPROVEN, shadow.AMBIGUOUS))
    missing = shadow.PlanViewOwnership(Status.ABSTAINED, (shadow.UNPROVEN, shadow.NO_PLAN_VIEW))
    outside = shadow.PlanViewOwnership(Status.ABSTAINED, (shadow.UNPROVEN, shadow.OUTSIDE))
    assert shadow.combine_ownership(owned, conflict) is conflict
    assert shadow.combine_ownership(conflict, owned) is conflict
    assert shadow.combine_ownership(outside, missing) is outside
    assert shadow.combine_ownership(missing, outside) is outside


def _framed_host_fixture():
    with fitz.open(stream=_host_fixture_pdf(), filetype="pdf") as document:
        page = document[0]
        page.draw_rect(fitz.Rect(8, 30, 312, 220), color=(0, 0, 0), width=1)
        page.insert_text((100, 200), "GROUND FLOOR PLAN", fontsize=11)
        return document.tobytes()


def _compose(data, **kwargs):
    source, published = _ingest(data, "plan-view-gate")
    return compose_live_wall_opening_authority(source_visibility_producer=source,
                                               revision_id=published.revision.revision_id, page_ids=("1",), **kwargs)


def test_the_opt_in_gate_withholds_a_host_on_a_sheet_without_a_floor_plan():
    data = _host_fixture_pdf()  # one byte string: opening identities follow the source bytes
    plain, gated = _compose(data), _compose(data, require_plan_view_host_ownership_shadow=True)
    assert plain.opening_bindings and all(t.status is Status.CORROBORATED for t in plain.opening_bindings)
    assert [t.opening_identity_id for t in gated.opening_bindings] == [t.opening_identity_id for t in plain.opening_bindings]
    for trace in gated.opening_bindings:
        assert trace.status is Status.ABSTAINED and trace.host_wall_id is None and not trace.member_wall_candidate_ids
        assert trace.reason_codes == (shadow.UNPROVEN, shadow.NO_PLAN_VIEW)
        assert gated.opening_host_binding_authority.resolve(
            gated.binding_selectors[trace.opening_identity_id]).record is None
    assert all(frame.status is not Status.CORROBORATED for frame in gated.host_frames)


def test_the_opt_in_gate_keeps_every_host_a_floor_plan_view_owns():
    data = _framed_host_fixture()
    plain, gated = _compose(data), _compose(data, require_plan_view_host_ownership_shadow=True)
    assert plain.opening_bindings and gated.opening_bindings == plain.opening_bindings
    assert gated.host_frames == plain.host_frames


def test_the_gate_flag_must_be_an_explicit_boolean():
    with pytest.raises(TypeError):
        _compose(_host_fixture_pdf(), require_plan_view_host_ownership_shadow="yes")


def test_withholding_only_demotes_published_hosts():
    gated = _compose(_framed_host_fixture())
    producer = OpeningHostBindingProducer.__new__(OpeningHostBindingProducer)
    owned = gated.opening_bindings[0].opening_identity_id
    record = gated.opening_host_binding_authority.resolve(gated.binding_selectors[owned])
    empty = type(record)(status=Status.ABSTAINED, reason_codes=("other_reason",), record=None)
    producer._results = {("d", "r", "s", "n", "1", "scope", owned): record, ("d", "r", "s", "n", "1", "scope", "x"): empty}
    producer._source_fragment_roles_shadow = False
    producer.withhold_published_hosts({owned: ("why",), "x": ("why",), "unknown": ("why",)})
    results = producer.published_results()
    assert results[("d", "r", "s", "n", "1", "scope", owned)].record is None
    assert results[("d", "r", "s", "n", "1", "scope", owned)].reason_codes == ("why",)
    assert results[("d", "r", "s", "n", "1", "scope", "x")] is empty and len(results) == 2
