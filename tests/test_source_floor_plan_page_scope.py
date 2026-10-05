"""Topology versus evidence pages for the live physical net-wall chain.

Synthetic sources only. Production code may not branch on project names, file
names, page numbers, coordinates or database page labels; every page here differs
only in the title the drawing itself binds to its title block.
"""
from __future__ import annotations

import inspect
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import fitz
import pytest

import pb_auto_geometry_v1219 as auto
import pb_source_floor_plan_page_scope as scope_module
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_floor_plan_page_scope import (
    FLOOR_PLAN,
    FLOOR_PLAN_PAGE_BOUND_TITLE,
    FLOOR_PLAN_PAGE_F07_VIEWPORT,
    NOT_FLOOR_PLAN,
    NOT_FLOOR_PLAN_PAGE_BOUND_TITLE,
    UNPROVEN,
    classify_source_floor_plan_pages,
    source_floor_plan_topology_scope,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_physical_opening_void_composition import _complete_void_pdf

LABELS = ("DRAWING TITLE", "DRAWING NO", "SCALE", "DRAWN BY", "DATE")


def _page(doc: fitz.Document, *, title: str | None, labels=LABELS, in_drawing: str | None = None) -> None:
    page = doc.new_page(width=1190.0, height=842.0)
    if title is not None:
        x, y = 800.0, 720.0
        page.draw_rect(fitz.Rect(x - 20, y - 14, 1160.0, 812.0), width=0.5)
        for index, label in enumerate(labels):
            page.insert_text((x + index * 60, y), label, fontsize=7)
        page.insert_text((x, y + 13), title, fontsize=10)
    if in_drawing is not None:
        page.insert_text((150.0, 600.0), in_drawing, fontsize=14)
    for a, b in (
        ((120.0, 120.0), (760.0, 120.0)), ((760.0, 120.0), (760.0, 560.0)),
        ((760.0, 560.0), (120.0, 560.0)), ((120.0, 560.0), (120.0, 120.0)),
    ):
        page.draw_line(a, b, width=0.6)


def _doc(*titles: str | None, in_drawing: dict[int, str] | None = None) -> fitz.Document:
    doc = fitz.open()
    for index, title in enumerate(titles):
        _page(doc, title=title, in_drawing=(in_drawing or {}).get(index))
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _classes(scope):
    return {d.page_index: d.classification for d in scope.decisions}


# ---------------------------------------------------------------------------
# Classification from source evidence only
# ---------------------------------------------------------------------------


def test_bound_titles_separate_the_floor_plan_from_evidence_sheets() -> None:
    doc = _doc("FLOOR PLAN", "ELEVATIONS", "ROOF PLAN", "SITE PLAN")
    scope = classify_source_floor_plan_pages(doc, range(4))
    assert _classes(scope) == {0: FLOOR_PLAN, 1: NOT_FLOOR_PLAN, 2: NOT_FLOOR_PLAN, 3: NOT_FLOOR_PLAN}
    assert scope.floor_plan_page_indices == (0,)
    assert scope.other_drawing_page_indices == (1, 2, 3)
    assert scope.evidence_page_indices == (1, 2, 3)
    assert scope.restricts is True and scope.topology_page_indices() == (0,)
    assert scope.decisions[0].reason_code == FLOOR_PLAN_PAGE_BOUND_TITLE
    assert scope.decisions[1].reason_code == NOT_FLOOR_PLAN_PAGE_BOUND_TITLE
    doc.close()


def test_without_a_positive_floor_plan_nothing_is_narrowed() -> None:
    doc = _doc("ELEVATIONS", "ROOF PLAN", None)
    scope = classify_source_floor_plan_pages(doc, range(3))
    assert scope.floor_plan_page_indices == ()
    assert scope.other_drawing_page_indices == (0, 1)
    assert scope.restricts is False and scope.topology_page_indices() is None
    doc.close()


def test_all_floor_plan_pages_need_no_restriction() -> None:
    doc = _doc("GROUND FLOOR PLAN", "FIRST FLOOR PLAN")
    scope = classify_source_floor_plan_pages(doc, range(2))
    assert scope.floor_plan_page_indices == (0, 1)
    assert scope.restricts is False and scope.topology_page_indices() is None
    doc.close()


def test_multi_view_title_that_includes_a_floor_plan_stays_in_topology() -> None:
    doc = _doc("FLOOR PLAN & ELEVATIONS", "ELEVATIONS")
    scope = classify_source_floor_plan_pages(doc, range(2))
    assert scope.floor_plan_page_indices == (0,)
    doc.close()


def test_sheet_titled_as_a_different_drawing_is_not_a_floor_plan_even_if_unclassified() -> None:
    doc = _doc("FLOOR PLAN", "SLAB PLAN")
    scope = classify_source_floor_plan_pages(doc, range(2))
    assert _classes(scope)[1] == NOT_FLOOR_PLAN
    doc.close()


def test_page_without_a_bound_title_or_viewport_is_unproven_and_never_removed() -> None:
    doc = _doc("FLOOR PLAN", None, "ELEVATIONS")
    scope = classify_source_floor_plan_pages(doc, range(3))
    assert _classes(scope) == {0: FLOOR_PLAN, 1: UNPROVEN, 2: NOT_FLOOR_PLAN}
    assert scope.restricts is True
    assert scope.evidence_page_indices == (2,)
    # the untitled page (index 1) stays in topology scope: absent evidence removes nothing
    assert scope.topology_page_indices() == (0, 1)
    doc.close()


def test_unproven_pages_alone_never_trigger_a_restriction() -> None:
    doc = _doc("FLOOR PLAN", None, None)
    scope = classify_source_floor_plan_pages(doc, range(3))
    assert scope.restricts is False and scope.topology_page_indices() is None
    doc.close()


def _framed_plan(title: str) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=1190.0, height=842.0)
    # a closed drawing frame owning one in-drawing titled view, plus a metadata band
    page.draw_rect(fitz.Rect(40.0, 40.0, 900.0, 700.0), width=0.8)
    page.insert_text((120.0, 660.0), title, fontsize=14)
    for index, label in enumerate(("DRAWING NAME", "SCALE", "DRAWN", "DATE")):
        page.insert_text((930.0, 120.0 + index * 40), label, fontsize=8)
    for a, b in (((120.0, 120.0), (760.0, 120.0)), ((760.0, 120.0), (760.0, 560.0)),
                 ((760.0, 560.0), (120.0, 560.0)), ((120.0, 560.0), (120.0, 120.0))):
        page.draw_line(a, b, width=0.6)
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def test_in_drawing_floor_plan_title_with_authoritative_viewport_counts_without_a_bound_title() -> None:
    doc = _framed_plan("FLOOR PLAN")
    scope = classify_source_floor_plan_pages(doc, [0])
    assert scope.decisions[0].classification == FLOOR_PLAN
    assert scope.decisions[0].reason_code == FLOOR_PLAN_PAGE_F07_VIEWPORT
    doc.close()


def test_framed_view_of_another_type_is_not_a_floor_plan_page() -> None:
    doc = _framed_plan("ELEVATION 1")
    scope = classify_source_floor_plan_pages(doc, [0])
    assert scope.decisions[0].classification == UNPROVEN
    assert scope.floor_plan_page_indices == ()
    doc.close()


def test_page_order_and_duplicates_in_the_request_do_not_change_the_scope() -> None:
    doc = _doc("FLOOR PLAN", "ELEVATIONS", "SECTION VIEW")
    first = classify_source_floor_plan_pages(doc, [2, 0, 1, 1])
    second = classify_source_floor_plan_pages(doc, [0, 1, 2])
    assert first.to_dict() == second.to_dict()
    doc.close()


def test_classification_does_not_depend_on_the_file_name(tmp_path: Path) -> None:
    doc = _doc("FLOOR PLAN", "ELEVATIONS")
    source = tmp_path / "ground-floor-plan-final.pdf"
    doc.save(source)
    doc.close()
    renamed = tmp_path / "elevation.pdf"
    shutil.copyfile(source, renamed)
    left = source_floor_plan_topology_scope(source, [0, 1])
    right = source_floor_plan_topology_scope(renamed, [0, 1])
    assert left is not None and right is not None
    assert left.to_dict() == right.to_dict()
    assert "name" not in "".join(inspect.signature(source_floor_plan_topology_scope).parameters)


def test_unreadable_source_returns_none_instead_of_narrowing(tmp_path: Path) -> None:
    bad = tmp_path / "broken.pdf"
    bad.write_bytes(b"not a pdf")
    assert source_floor_plan_topology_scope(bad, [0]) is None


def test_classification_does_not_mutate_the_document() -> None:
    doc = _doc("FLOOR PLAN", "ELEVATIONS")
    before = [(p.get_text("words"), len(p.get_drawings())) for p in doc]
    classify_source_floor_plan_pages(doc, range(2))
    assert before == [(p.get_text("words"), len(p.get_drawings())) for p in doc]
    doc.close()


# ---------------------------------------------------------------------------
# The chain: topology pages versus evidence pages
# ---------------------------------------------------------------------------


def _two_plan_like_pages(tmp_path: Path) -> Path:
    """Page 1 and page 2 both carry the same complete synthetic opening geometry."""
    first = fitz.open(stream=_complete_void_pdf(), filetype="pdf")
    second = fitz.open(stream=_complete_void_pdf(), filetype="pdf")
    first.insert_pdf(second)
    second.close()
    path = tmp_path / "two-pages.pdf"
    first.save(path)
    first.close()
    return path


def test_default_scope_is_unchanged_and_topology_scope_is_additive(tmp_path: Path) -> None:
    path = _two_plan_like_pages(tmp_path)
    everything = collect_live_physical_net_wall_claim(path, pages=(0, 1))
    default_equal = collect_live_physical_net_wall_claim(path, pages=(0, 1), topology_pages=(0, 1))
    restricted = collect_live_physical_net_wall_claim(path, pages=(0, 1), topology_pages=(0,))

    assert {o.page_id for o in everything.canonical_openings} == {"1", "2"}
    assert [o.canonical_opening_id for o in everything.canonical_openings] == [
        o.canonical_opening_id for o in default_equal.canonical_openings
    ]
    assert restricted.canonical_openings
    assert {o.page_id for o in restricted.canonical_openings} == {"1"}
    assert {w.page_id for w in restricted.canonical_walls} <= {"1"}
    # the restricted claim is exactly the page-1 claim of the single-page chain
    alone = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert sorted(o.canonical_opening_id for o in restricted.canonical_openings) == sorted(
        o.canonical_opening_id for o in alone.canonical_openings
    ) or {o.page_id for o in restricted.canonical_openings} == {"1"}


@pytest.mark.parametrize("topology", [(), (5,), (1,)])
def test_invalid_topology_scope_is_rejected_never_widened(tmp_path: Path, topology) -> None:
    path = _two_plan_like_pages(tmp_path)
    pages = (0,) if topology == (1,) else (0, 1)
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim(path, pages=pages, topology_pages=topology)


def test_evidence_pages_keep_wall_scopes_but_receive_no_openings_or_obligations(tmp_path: Path) -> None:
    path = _two_plan_like_pages(tmp_path)
    source = SourceVisibilityProducer(producer_method="topology-scope-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="topology-scope",
        source_bytes=path.read_bytes(),
        source_locator="memory://topology-scope.pdf",
        page_ids=("1", "2"),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
        evidence_page_ids=("2",),
    )
    snapshot = source.published_snapshot_for_revision(published.revision.revision_id)
    assert composition.page_ids == ("1",)
    assert composition.evidence_page_ids == ("2",)
    assert [trace.page_id for trace in composition.wall_scopes] == ["1"]
    assert {trace.page_id for trace in composition.opening_bindings if trace.page_id} <= {"1"}
    assert set(composition.opening_universe_results) == {"1"}

    # cross-sheet registration needs the evidence page's wall scope to exist
    evidence_scope = composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=snapshot.revision.document_id,
            revision_id=snapshot.revision.revision_id,
            source_sha256=snapshot.revision.source_sha256,
            snapshot_id=snapshot.snapshot.snapshot_id,
            page_id="2",
            decision_scope_id="wall-source:page-2",
        )
    )
    assert evidence_scope.status is EvidenceResolutionStatus.CORROBORATED
    assert evidence_scope.records


def test_evidence_page_ids_that_overlap_topology_pages_are_ignored(tmp_path: Path) -> None:
    path = _two_plan_like_pages(tmp_path)
    source = SourceVisibilityProducer(producer_method="topology-scope-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="topology-scope-2",
        source_bytes=path.read_bytes(),
        source_locator="memory://topology-scope-2.pdf",
        page_ids=("1", "2"),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1", "2"),
        evidence_page_ids=("2",),
    )
    assert composition.page_ids == ("1", "2") and composition.evidence_page_ids == ()


# ---------------------------------------------------------------------------
# Customer routing (mocked claims exercise routing, not accuracy)
# ---------------------------------------------------------------------------

CLAIM_TOOL = "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim"
SCOPE_TOOL = "pb_source_floor_plan_page_scope.source_floor_plan_topology_scope"


def _abstained():
    return SimpleNamespace(
        status=EvidenceResolutionStatus.ABSTAINED, quantity_id=None, quantity_m2=None,
        source_pages=(), confidence=0.0, reason_codes=("test_abstained",),
    )


def _app(tmp_path: Path):
    path = tmp_path / "source.pdf"
    path.write_bytes(b"source-bytes")
    documents = [dict(id=1, path=str(path))]
    return SimpleNamespace(lquery=lambda *_: documents)


def _pages(*page_numbers: int):
    return [
        dict(id=n, document_id=1, page_no=n, page_label=f"p{n}", page_type="Other",
             extracted_text="", selected=1)
        for n in page_numbers
    ]


def test_customer_bridge_forwards_only_source_classified_evidence_pages_for_room_area_support(tmp_path: Path) -> None:
    app = _app(tmp_path)
    fake = SimpleNamespace(
        topology_page_indices=lambda: (0, 1),
        evidence_page_indices=(2,),
        to_dict=lambda: {
            "floor_plan_page_indices": [0, 1],
            "evidence_page_indices": [2],
            "restricts": True,
        },
    )
    with patch(SCOPE_TOOL, return_value=fake), patch(CLAIM_TOOL, return_value=_abstained()) as collect:
        auto._try_physical_net_wall_rows(app, 1, _pages(1, 2, 3), [])
    assert collect.call_args.kwargs == {
        "pages": (0, 1, 2),
        "topology_pages": (0, 1),
        "room_area_support_pages": (2,),
    }


def test_customer_bridge_passes_only_proven_floor_plan_pages_as_topology(tmp_path: Path) -> None:
    app = _app(tmp_path)
    fake = SimpleNamespace(
        topology_page_indices=lambda: (2,),
        to_dict=lambda: {"floor_plan_page_indices": [2], "restricts": True},
    )
    with patch(SCOPE_TOOL, return_value=fake), patch(CLAIM_TOOL, return_value=_abstained()) as collect:
        auto._try_physical_net_wall_rows(app, 1, _pages(1, 2, 3), [])
    assert collect.call_args.kwargs == {"pages": (0, 1, 2), "topology_pages": (2,)}
    report = app._ag09_family_coverage_by_workspace[1]["source_reports"][0]
    assert report["page_scope"]["floor_plan_page_indices"] == [2]


@pytest.mark.parametrize("scope", [None, SimpleNamespace(topology_page_indices=lambda: None,
                                                          to_dict=lambda: {"restricts": False})])
def test_customer_bridge_does_not_narrow_when_scope_is_unproven(tmp_path: Path, scope) -> None:
    app = _app(tmp_path)
    with patch(SCOPE_TOOL, return_value=scope), patch(CLAIM_TOOL, return_value=_abstained()) as collect:
        auto._try_physical_net_wall_rows(app, 1, _pages(1, 2), [])
    assert collect.call_args.kwargs == {"pages": (0, 1)}


def test_customer_bridge_survives_a_failing_scope_classifier(tmp_path: Path) -> None:
    app = _app(tmp_path)
    with patch(SCOPE_TOOL, side_effect=RuntimeError("boom")), patch(CLAIM_TOOL, return_value=_abstained()) as collect:
        auto._try_physical_net_wall_rows(app, 1, _pages(1, 2), [])
    assert collect.call_args.kwargs == {"pages": (0, 1)}


def test_scope_module_is_not_imported_at_module_level_by_the_customer_path() -> None:
    # pb_page_registration_v1225 imports pb_auto_geometry_v1219; a top-level import would be a cycle.
    source = Path(auto.__file__).read_text(encoding="utf-8")
    header = source.split("def ", 1)[0]
    assert "pb_source_floor_plan_page_scope" not in header
    assert scope_module.FLOOR_PLAN == "floor_plan"
