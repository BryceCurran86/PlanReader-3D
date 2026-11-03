"""Native sheet boundaries and sealed viewport addresses reach the real host reader.

These PDFs and contexts are source-neutral. Spatial ownership alone cannot
exclude a building outline, and a caller cannot reconstruct a sealed selector.
"""
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

import pb_physical_wall_candidate_authority as walls
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_binding_authority import (
    OpeningHostWallUniverseProducer,
    OpeningHostWallUniverseSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport,
    segment_page_viewports,
)


def _pdf(*, scale=1.0, dx=0.0, dy=0.0, cropped=False, metadata=True,
         title="GROUND FLOOR PLAN"):
    def point(x, y):
        return (x * scale + dx, y * scale + dy)

    with fitz.open() as document:
        page = document.new_page(width=1200 * scale + dx, height=842 * scale + dy)
        for a, b in (((24, 24), (1170, 24)), ((1170, 24), (1170, 770)),
                     ((1170, 770), (24, 770)), ((24, 770), (24, 24))):
            page.draw_line(point(*a), point(*b))
        for a, b in (((90, 120), (760, 120)), ((760, 120), (760, 600)),
                     ((760, 600), (90, 600)), ((90, 600), (90, 120))):
            page.draw_line(point(*a), point(*b), width=1.2 * scale)
        if cropped:
            page.draw_line(point(90, 200), point(24, 200), width=1.2 * scale)
        page.insert_text(point(180, 690), title, fontsize=11 * scale)
        for a, b in (((24, 774), (1170, 774)), ((1170, 774), (1170, 820)),
                     ((1170, 820), (24, 820)), ((24, 820), (24, 774))):
            page.draw_line(point(*a), point(*b))
        if metadata:
            for x, y, text in ((700, 788, "Drawing name:"), (700, 802, "Floor Plan"),
                               (900, 788, "Client"), (900, 802, "Example"),
                               (1040, 788, "REVISION"), (1120, 788, "Scale:")):
                page.insert_text(point(x, y), text, fontsize=6 * scale)
        return document.tobytes()


def _source(data):
    source = SourceVisibilityProducer(producer_method="sheet-frame-scope-test", producer_version="1")
    source.ingest_native_pdf_bytes(document_id="source-neutral-sheet", source_bytes=data,
                                   source_locator="memory://source.pdf")
    producer = walls.PhysicalWallCandidateProducer.from_authenticated_viewports(source, page_ids=("1",))
    assert len(producer._scopes) == 1
    scope = next(iter(producer._scopes.values()))
    authority = producer.authority()
    selector = OpeningHostWallUniverseSelector(
        document_id=scope.document_id, revision_id=scope.revision_id,
        source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id,
        page_id=scope.page_id, decision_scope_id=scope.decision_scope_id,
    )
    reader = OpeningHostWallUniverseProducer.from_physical_wall_candidate_authority(authority).authority()
    return source, authority, scope, selector, reader


@pytest.fixture(scope="module")
def genuine():
    return _source(_pdf())


@pytest.mark.parametrize("scale,dx,dy", ((1.0, 0.0, 0.0), (0.8, 13.0, 9.0), (1.3, 0.0, 0.0)))
def test_real_native_sheet_frame_reaches_complete_source_scope_and_host_universe(scale, dx, dy):
    data = _pdf(scale=scale, dx=dx, dy=dy)
    with fitz.open(stream=data, filetype="pdf") as document:
        viewport, = segment_page_viewports(document[0], page_number=1)
    assert is_authoritative_derived_viewport(viewport)
    assert viewport.provenance["partition_mode"] == "single_floor_plan_sheet_frame"
    source, _authority, scope, selector, reader = _source(data)
    before = repr(scope)
    result = reader.resolve_scope(selector)
    assert scope.scope_complete is True and scope.records
    assert result.status is Status.CORROBORATED and result.scope_complete is True
    assert result.records == scope.records
    assert repr(scope) == before
    assert source.published_snapshot_for_revision(scope.revision_id).snapshot.snapshot_id == scope.snapshot_id


@pytest.mark.parametrize("rotation", (90, 180, 270))
def test_unproven_rotated_sheet_frame_cannot_create_an_authenticated_scope(rotation):
    # F.07 does not authenticate this rotated source. Consumer-side frame
    # handling must not fill in that missing upstream ownership proof.
    with fitz.open(stream=_pdf(), filetype="pdf") as document:
        document[0].set_rotation(rotation)
        data = document.tobytes()
    source = SourceVisibilityProducer(producer_method="sheet-frame-rotation-test", producer_version="1")
    source.ingest_native_pdf_bytes(document_id="source-neutral-sheet", source_bytes=data,
                                   source_locator="memory://source.pdf")
    producer = walls.PhysicalWallCandidateProducer.from_authenticated_viewports(source, page_ids=("1",))
    assert not producer._scopes


@pytest.mark.parametrize("title,mode", (
    ("FLOOR FINISH PLAN", "single_floor_finish_plan_sheet_frame"),
    ("REFLECTED CEILING PLAN", "single_reflected_ceiling_sheet_frame"),
))
def test_other_original_spatial_sheet_frames_reach_the_same_host_reader(title, mode):
    data = _pdf(title=title)
    with fitz.open(stream=data, filetype="pdf") as document:
        viewport, = segment_page_viewports(document[0], page_number=1)
    assert viewport.provenance["partition_mode"] == mode
    _source_obj, _authority, scope, selector, reader = _source(data)
    assert scope.scope_complete is True
    assert reader.resolve_scope(selector).status is Status.CORROBORATED


def test_cropped_real_wall_is_not_laundered_through_the_sheet_frame():
    _source_obj, _authority, scope, selector, reader = _source(_pdf(cropped=True))
    assert scope.scope_complete is False
    result = reader.resolve_scope(selector)
    assert result.status is not Status.CORROBORATED and result.scope_complete is False


def test_frame_exclusion_requires_the_complete_original_sheet_edge():
    with fitz.open(stream=_pdf(), filetype="pdf") as document:
        viewport, = segment_page_viewports(document[0], page_number=1)
    full = {"x1": 24.0, "y1": 24.0, "x2": 1170.0, "y2": 24.0}
    assert walls._segment_is_authenticated_vector_frame_edge(full, viewport=viewport)
    assert not walls._segment_is_authenticated_vector_frame_edge(
        {**full, "x2": 500.0}, viewport=viewport,
    )


def test_declared_derived_sheet_frame_without_source_product_is_not_excluded():
    viewport = SimpleNamespace(
        status="derived", boundary_source="title_partition", bounding_box=(24, 24, 1170, 770),
        provenance={"partition_mode": "single_floor_plan_sheet_frame", "single_view_validated": True,
                    "metadata_label_count": 3, "drawing_vector_primitive_count": 4,
                    "sheet_frame_bbox": (24, 24, 1170, 770)},
    )
    assert is_authoritative_derived_viewport(viewport)
    assert not walls._segment_is_authenticated_vector_frame_edge(
        {"x1": 24, "y1": 24, "x2": 1170, "y2": 24}, viewport=viewport,
    )


def test_modifying_the_original_frame_geometry_invalidates_its_source_product():
    with fitz.open(stream=_pdf(), filetype="pdf") as document:
        viewport, = segment_page_viewports(document[0], page_number=1)
    assert walls._has_authenticated_derived_sheet_frame(viewport)
    viewport.provenance["sheet_frame_bbox"] = (24, 24, 1171, 770)
    assert not walls._segment_is_authenticated_vector_frame_edge(
        {"x1": 24, "y1": 24, "x2": 1170, "y2": 24}, viewport=viewport,
    )


@pytest.mark.parametrize("mode", ("single_floor_plan_printable_area", "source_owned_physical_plan_component"))
def test_other_authenticated_derived_bounds_do_not_erase_a_physical_outer_wall(monkeypatch, mode):
    # Even a trusted spatial scope is not necessarily a drawn annotation frame.
    monkeypatch.setattr(walls, "is_segment_page_viewports_product", lambda _v: True)
    monkeypatch.setattr(walls, "is_authoritative_derived_viewport", lambda _v: True)
    viewport = SimpleNamespace(
        status="derived", boundary_source="title_partition", bounding_box=(24, 24, 1170, 770),
        provenance={"partition_mode": mode, "sheet_frame_bbox": (24, 24, 1170, 770)},
    )
    assert not walls._segment_is_authenticated_vector_frame_edge(
        {"x1": 24, "y1": 24, "x2": 1170, "y2": 24}, viewport=viewport,
    )


@pytest.mark.parametrize("field,value", (
    ("document_id", "other-document"), ("revision_id", "other-revision"),
    ("source_sha256", "f" * 64), ("snapshot_id", "other-snapshot"),
    ("page_id", "2"), ("decision_scope_id", "other-scope"),
))
def test_caller_cannot_resolve_a_foreign_or_invented_host_scope(genuine, field, value):
    _source_obj, _authority, _scope, selector, reader = genuine
    result = reader.resolve_scope(replace(selector, **{field: value}))
    assert result.status is not Status.CORROBORATED and result.scope_complete is False


def test_source_owned_selector_is_used_whole_without_parsing_its_address(genuine, monkeypatch):
    _source_obj, authority, scope, selector, reader = genuine
    source_selector, = authority.selectors_for_authenticated_viewports(
        document_id=scope.document_id, revision_id=scope.revision_id,
        source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id, page_id=scope.page_id,
    )
    owned = replace(source_selector, decision_scope_id="opaque:source:address:with:colons")
    expected = replace(scope, decision_scope_id=owned.decision_scope_id, scope_complete=True)
    monkeypatch.setattr(authority, "selectors_for_authenticated_viewports", lambda **_kwargs: (owned,))
    received = []

    def resolve(actual):
        received.append(actual)
        return expected if actual is owned else replace(scope, scope_complete=False)

    monkeypatch.setattr(authority, "resolve_scope", resolve)
    result = reader.resolve_scope(replace(selector, decision_scope_id=owned.decision_scope_id))
    assert result.status is Status.CORROBORATED
    assert received == [owned]


def test_duplicate_source_owned_scope_addresses_never_elect_first(genuine, monkeypatch):
    _source_obj, authority, scope, selector, reader = genuine
    source_selector, = authority.selectors_for_authenticated_viewports(
        document_id=scope.document_id, revision_id=scope.revision_id,
        source_sha256=scope.source_sha256, snapshot_id=scope.snapshot_id, page_id=scope.page_id,
    )
    monkeypatch.setattr(authority, "selectors_for_authenticated_viewports", lambda **_kwargs: (
        source_selector, replace(source_selector),
    ))
    result = reader.resolve_scope(selector)
    assert result.status is not Status.CORROBORATED and result.scope_complete is False
