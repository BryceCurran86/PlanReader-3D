"""Report-only plan-view wall scopes (#4764 7209088255): sheet furniture, non-plan sheets, green exclusions and wall ink.

Synthetic sheets only. The plan sheet is the repository's own source-owned plan-view fixture with walls, a green line and
sheet furniture drawn onto it; the other sheets are a register and a schedule.
"""
from __future__ import annotations

from types import SimpleNamespace

import fitz
import pytest

import pb_wall_plan_view_scope_report as report
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_physical_wall_candidate_viewport_scope_v1 import _draw_plan
from tests.test_source_owned_physical_plan_view import _sheet

BLACK, GREEN = (0.0, 0.0, 0.0), (0.0, 0.5, 0.0)


def _plan_sheet(*, furniture=True, green=True):
    with fitz.open(stream=_sheet(), filetype="pdf") as document:
        page = document[0]
        for rect in ((120, 130, 320, 136), (120, 320, 320, 326), (120, 136, 126, 320), (314, 136, 320, 320)):
            page.draw_rect(fitz.Rect(*rect), color=None, fill=BLACK)
        if green:
            page.draw_line((126, 228), (314, 228), color=GREEN, width=0.5)
        if furniture:
            for y in (440, 455, 470, 485):
                page.draw_line((420, y), (850, y), color=BLACK, width=0.5)  # register-like rows running to the sheet edge
            for x in (420, 520, 620, 720):
                page.draw_line((x, 440), (x, 485), color=BLACK, width=0.5)
        return document.tobytes()


def _register_sheet():
    document = fitz.open()
    page = document.new_page(width=850, height=500)
    page.insert_text((60, 40), "DRAWING TRANSMITTAL", fontsize=12)
    for y in range(60, 300, 20):
        page.draw_line((40, y), (850, y), color=BLACK, width=0.5)
    for x in range(40, 850, 90):
        page.draw_line((x, 60), (x, 280), color=BLACK, width=0.5)
    data = document.tobytes()
    document.close()
    return data


def _report(data):
    source = SourceVisibilityProducer(producer_method="wall-plan-view-report-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="report-test", source_bytes=data,
                                               source_locator="memory://report.pdf", page_ids=("1",))
    return report.wall_plan_view_scope_report(source, revision_id=published.revision.revision_id, page_ids=("1",))


def _page(data):
    (page,) = _report(data)["pages"]
    return page


def test_sheet_furniture_stays_out_of_the_plan_view_and_the_page_scope_is_untouched():
    page = _page(_plan_sheet())
    plain = _page(_plan_sheet(furniture=False))
    assert page["page_scope"]["candidates"] > plain["page_scope"]["candidates"]
    (view,) = page["proven_plan_views"]
    (plain_view,) = plain["proven_plan_views"]
    assert view["candidates"] == plain_view["candidates"] > 0 and view["boundary_tainted"] == 0


def test_green_paint_leaves_only_the_wall_ink_variant():
    page = _page(_plan_sheet(furniture=False))
    without_green = _page(_plan_sheet(furniture=False, green=False))
    (ink,), (view,) = page["proven_plan_views_wall_ink"], page["proven_plan_views"]
    (clean,) = without_green["proven_plan_views_wall_ink"]
    assert ink == clean and ink["candidates"] < view["candidates"]


@pytest.mark.parametrize("data", [_register_sheet(), _sheet(role="DOOR SCHEDULE"), _sheet(role="FRONT ELEVATION")],
                         ids=["register", "schedule", "elevation"])
def test_a_sheet_without_an_authenticated_plan_view_says_so(data):
    page = _page(data)
    assert all(page[name] == report.NO_PLAN_VIEW for name in report.VIEW_VARIANTS)


def test_the_report_is_repeatable_and_resolves_nothing_in_an_incomplete_scope():
    data = _plan_sheet()
    first, second = _report(data), _report(data)
    assert first == second
    (page,) = first["pages"]
    for scope in [page["page_scope"], *(s for name in report.VIEW_VARIANTS if page[name] != report.NO_PLAN_VIEW for s in page[name])]:
        if not scope["scope_complete"]:
            assert scope["resolved_walls"] == 0 and scope["room_faces_with_all_walls_resolved"] == 0


def test_resolved_walls_follow_the_live_composition_rule():
    equivalence = SimpleNamespace(representative_wall_ids=("a", "c"), equivalence_groups=(("a", "b"),))
    complete = SimpleNamespace(status=EvidenceResolutionStatus.CORROBORATED, scope_complete=True, equivalence=equivalence)
    assert report.resolved_wall_ids(complete) == {"a", "b", "c"}
    for change in ({"scope_complete": False}, {"status": EvidenceResolutionStatus.ABSTAINED}, {"equivalence": None}):
        assert report.resolved_wall_ids(SimpleNamespace(**{**vars(complete), **change})) == set()


def _framed_plan(tmp_path, *, green=False, crossing=False):
    path = tmp_path / f"plan-{green}-{crossing}.pdf"
    _draw_plan(path, crossing=crossing)
    if green:
        with fitz.open(path) as document:
            document[0].draw_line((90, 150), (210, 150), color=GREEN, width=0.5)
            document.saveIncr()
    return path.read_bytes()


def test_a_framed_titled_plan_is_an_authenticated_view_without_being_a_proven_one(tmp_path):
    page = _page(_framed_plan(tmp_path))
    (view,) = page["authenticated_plan_views"]
    assert view["view_type"] == "floor_plan" and view["candidates"] > 0 and view["scope_complete"]
    assert page["proven_plan_views"] == report.NO_PLAN_VIEW


def test_green_paint_and_crossing_lines_show_up_in_the_authenticated_view(tmp_path):
    plain = _page(_framed_plan(tmp_path))
    green = _page(_framed_plan(tmp_path, green=True))
    (view,), (ink,) = green["authenticated_plan_views"], green["authenticated_plan_views_wall_ink"]
    assert ink["candidates"] < view["candidates"] and ink == plain["authenticated_plan_views_wall_ink"][0]
    (crossed,) = _page(_framed_plan(tmp_path, crossing=True))["authenticated_plan_views"]
    assert not crossed["scope_complete"] and crossed["primitives_crossing_boundary"] >= 1


def test_only_a_source_producer_is_accepted():
    with pytest.raises(TypeError):
        report.wall_plan_view_scope_report(object(), revision_id="r", page_ids=("1",))
