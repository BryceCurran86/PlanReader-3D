"""Rooms recovered from a drawing area name their walls in the whole-page canonical map (default off).

Synthetic only; no private source. Wall candidate IDs hash their scope, so a room from the viewport fallback never matched the
page-keyed canonical wall map. ``compose_live_canonical_rooms(..., viewport_wall_identity_links=True)`` links a drawing-area
candidate to the one page candidate with the identical traced path and source primitive IDs, one-to-one in both scopes; anything
else stays unlinked. A link resolves nothing: an unresolved page wall keeps the room's relationships incomplete.
"""
from __future__ import annotations

import random
from types import SimpleNamespace

import fitz
import pytest

import pb_live_canonical_room_composition as rooms_module
import pb_live_physical_net_wall_integration as integration
from pb_live_canonical_room_composition import ViewportWallIdentityLink, compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import PhysicalWallIdentity
from pb_source_visibility_authority import SourceVisibilityProducer

OK = EvidenceResolutionStatus.CORROBORATED
PATH = ((0.0, 0.0), (10.0, 0.0))


# ------------------------------------------------------------------------------------------------ the link rule

def _record(candidate_id, *, path=PATH, lines=("obs-1",), status=OK, identity_id="wall2_x", blocking=(), owner=None):
    identity = PhysicalWallIdentity(
        wall_candidate_id=candidate_id if owner is None else owner, viewport_id="scope", candidate_identity_id=identity_id,
        path_fingerprint=path, source_primitive_ids=tuple(lines), edge_ids=("e1",), status=status, blocking_reasons=blocking,
    )
    return SimpleNamespace(wall_candidate_id=candidate_id, physical_identity=identity)


def _scope(records, **overrides):
    fields = {"status": OK, "document_id": "doc", "revision_id": "rev", "source_sha256": "a" * 64, "page_id": "1",
              "records": tuple(records)}
    fields.update(overrides)
    return SimpleNamespace(**fields)


def _links(page_records, view_records, *, page=None, view=None):
    return rooms_module._viewport_to_page_wall_candidate_ids(
        _scope(page_records, **(page or {})), _scope(view_records, **(view or {})),
    )


def test_the_same_path_and_source_lines_link_one_to_one():
    page = [_record("p1"), _record("p2", lines=("obs-2",))]
    view = [_record("v2", lines=("obs-2",)), _record("v1")]
    assert _links(page, view) == {"v1": "p1", "v2": "p2"}


@pytest.mark.parametrize("view_kwargs", [
    {"lines": ("obs-9",)}, {"path": ((0.0, 0.0), (11.0, 0.0))}, {"lines": ("obs-1", "obs-9")}, {"lines": ()},
    {"status": EvidenceResolutionStatus.ABSTAINED}, {"identity_id": None}, {"blocking": ("blocked",)}, {"owner": "someone-else"},
])
def test_a_wall_that_differs_or_has_no_usable_identity_stays_unlinked(view_kwargs):
    assert _links([_record("p1")], [_record("v1", **view_kwargs)]) == {}


@pytest.mark.parametrize("page_kwargs", [{"lines": ()}, {"identity_id": None}, {"owner": "someone-else"}])
def test_an_unusable_page_identity_never_receives_a_link(page_kwargs):
    assert _links([_record("p1", **page_kwargs)], [_record("v1", **page_kwargs)]) == {}


def test_two_walls_with_one_signature_on_either_side_abstain_and_do_not_block_others():
    other_page, other_view = _record("p2", lines=("obs-2",)), _record("v2", lines=("obs-2",))
    assert _links([_record("p1"), _record("p1b"), other_page], [_record("v1"), other_view]) == {"v2": "p2"}
    assert _links([_record("p1"), other_page], [_record("v1"), _record("v1b"), other_view]) == {"v2": "p2"}


@pytest.mark.parametrize("override", [
    {"document_id": "other"}, {"revision_id": "other"}, {"source_sha256": "b" * 64}, {"page_id": "2"},
    {"status": EvidenceResolutionStatus.ABSTAINED},
])
def test_another_source_page_or_an_unresolved_scope_links_nothing(override):
    assert _links([_record("p1")], [_record("v1")], view=override) == {}
    assert _links([_record("p1")], [_record("v1")], page=override) == {}


def test_record_order_does_not_matter():
    page = [_record(f"p{i}", lines=(f"obs-{i}",)) for i in range(20)] + [_record("dup", lines=("obs-3",))]
    view = [_record(f"v{i}", lines=(f"obs-{i}",)) for i in range(20)]
    first = _links(page, view)
    random.Random(7).shuffle(page)
    random.Random(8).shuffle(view)
    assert _links(page, view) == first and len(first) == 19 and "v3" not in first


# ------------------------------------------------------------------------------------------------ through the room composer

def _fallback_pdf() -> bytes:
    """Two rooms inside a framed floor plan, with a legend line elsewhere so the whole-page room scope cannot publish."""
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)
    page.draw_rect(fitz.Rect(30.0, 30.0, 300.0, 270.0), color=(0, 0, 0), width=1.0)
    page.insert_text((80.0, 60.0), "GROUND FLOOR PLAN", fontsize=10.0)
    page.insert_text((325.0, 70.0), "LEGEND", fontsize=10.0)
    page.draw_line(fitz.Point(325.0, 150.0), fitz.Point(385.0, 150.0), color=(0, 0, 0), width=1.0)
    for first, second in (
        ((70.0, 90.0), (270.0, 90.0)), ((270.0, 90.0), (270.0, 240.0)), ((270.0, 240.0), (70.0, 240.0)),
        ((70.0, 240.0), (70.0, 90.0)), ((170.0, 90.0), (170.0, 240.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1.0)
    data = doc.tobytes()
    doc.close()
    return data


@pytest.fixture(scope="module")
def fallback():
    source = SourceVisibilityProducer(producer_method="viewport-link-test", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id="viewport-link-doc", source_bytes=_fallback_pdf(), source_locator="memory://viewport-link.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=("1",),
    )
    walls = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening)
    return source, wall_opening, walls


def _compose(fallback, **kwargs):
    source, wall_opening, walls = fallback
    kwargs.setdefault("canonical_wall_ids_by_candidate", walls.candidate_to_canonical_wall_id)
    kwargs.setdefault("unresolved_wall_candidate_ids", walls.unresolved_wall_candidate_ids)
    return compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=wall_opening, **kwargs)


def _public(composition):
    return [room.to_dict() for room in composition.rooms]


def test_off_by_default_the_rooms_have_no_canonical_walls_and_no_links(fallback):
    result = _compose(fallback)
    assert len(result.rooms) == 2 and all(room.viewport_id for room in result.rooms)
    assert all(room.canonical_bounding_wall_ids == () for room in result.rooms)
    assert result.viewport_wall_identity_links == ()
    assert _public(_compose(fallback, viewport_wall_identity_links=False)) == _public(result)


def test_on_each_room_names_its_page_walls_and_nothing_else_changes(fallback):
    off, on = _compose(fallback), _compose(fallback, viewport_wall_identity_links=True)
    walls = fallback[2]
    canonical = {wall.canonical_wall_id for wall in walls.walls}
    assert (on.status, on.reason_codes, on.source_pages) == (off.status, off.reason_codes, off.source_pages)
    for before, after in zip(off.rooms, on.rooms):
        assert after.canonical_bounding_wall_ids and set(after.canonical_bounding_wall_ids) <= canonical
        assert after.wall_relationships_complete is False  # the page walls are unresolved candidates
        expected = {**before.to_dict(), "canonical_bounding_wall_ids": list(after.canonical_bounding_wall_ids)}
        assert after.to_dict() == expected
        assert on.room_face_authority_binding_for(after) is not None


def test_the_receipt_lists_exactly_the_links_the_rooms_used(fallback):
    result = _compose(fallback, viewport_wall_identity_links=True)
    walls = fallback[2]
    links = result.viewport_wall_identity_links
    assert links and list(links) == sorted(set(links)) and all(type(link) is ViewportWallIdentityLink for link in links)
    used = {wall_id for room in result.rooms for wall_id in room.bounding_wall_ids}
    assert {link.viewport_wall_candidate_id for link in links} == used
    for room in result.rooms:
        by_view = {link.viewport_wall_candidate_id: link.page_wall_candidate_id for link in links}
        assert room.canonical_bounding_wall_ids == tuple(dict.fromkeys(
            walls.candidate_to_canonical_wall_id[by_view[wall_id]] for wall_id in room.bounding_wall_ids
        ))
        assert {link.viewport_decision_scope_id for link in links} == {room.decision_scope_id}
    again = _compose(fallback, viewport_wall_identity_links=True)
    assert again.viewport_wall_identity_links == links and _public(again) == _public(result)


def test_the_link_follows_the_page_walls_resolution_and_never_adds_one(fallback):
    walls = fallback[2]
    resolved = _compose(fallback, viewport_wall_identity_links=True, unresolved_wall_candidate_ids=())
    assert all(room.wall_relationships_complete for room in resolved.rooms)
    links = {link.viewport_wall_candidate_id: link.page_wall_candidate_id for link in resolved.viewport_wall_identity_links}
    first, second = resolved.rooms
    only_first = sorted({links[w] for w in first.bounding_wall_ids} - {links[w] for w in second.bounding_wall_ids})
    partly = _compose(fallback, viewport_wall_identity_links=True, unresolved_wall_candidate_ids=only_first[:1])
    assert [room.wall_relationships_complete for room in partly.rooms] == [False, True]
    assert walls.unresolved_wall_candidate_ids  # the fixture's real page walls are all unresolved


def test_a_page_wall_missing_from_the_canonical_map_leaves_its_rooms_unmapped(fallback):
    walls = fallback[2]
    full = _compose(fallback, viewport_wall_identity_links=True)
    links = {link.viewport_wall_candidate_id: link.page_wall_candidate_id for link in full.viewport_wall_identity_links}
    first = full.rooms[0]
    second_walls = {links[w] for w in full.rooms[1].bounding_wall_ids}
    gone = next(links[w] for w in first.bounding_wall_ids if links[w] not in second_walls)
    mapping = {k: v for k, v in walls.candidate_to_canonical_wall_id.items() if k != gone}
    partial = _compose(fallback, viewport_wall_identity_links=True, canonical_wall_ids_by_candidate=mapping)
    assert partial.rooms[0].canonical_bounding_wall_ids == () and partial.rooms[1].canonical_bounding_wall_ids
    assert all(link.page_wall_candidate_id != gone for link in partial.viewport_wall_identity_links)
    assert {link.viewport_wall_candidate_id for link in partial.viewport_wall_identity_links} == set(partial.rooms[1].bounding_wall_ids)


def test_when_no_room_can_be_mapped_the_receipt_is_empty(fallback):
    walls = fallback[2]
    full = _compose(fallback, viewport_wall_identity_links=True)
    links = {link.viewport_wall_candidate_id: link.page_wall_candidate_id for link in full.viewport_wall_identity_links}
    shared = set(full.rooms[0].bounding_wall_ids) & set(full.rooms[1].bounding_wall_ids)
    gone = {links[wall_id] for wall_id in shared}
    assert gone
    mapping = {k: v for k, v in walls.candidate_to_canonical_wall_id.items() if k not in gone}
    none = _compose(fallback, viewport_wall_identity_links=True, canonical_wall_ids_by_candidate=mapping)
    assert all(room.canonical_bounding_wall_ids == () for room in none.rooms) and none.viewport_wall_identity_links == ()


def test_without_a_canonical_map_the_switch_changes_nothing(fallback):
    off = _compose(fallback, canonical_wall_ids_by_candidate=None, unresolved_wall_candidate_ids=None)
    on = _compose(fallback, canonical_wall_ids_by_candidate=None, unresolved_wall_candidate_ids=None,
                  viewport_wall_identity_links=True)
    assert _public(on) == _public(off) and on.viewport_wall_identity_links == ()


def test_page_scope_rooms_are_untouched_by_the_switch():
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    for first, second in (
        ((50.0, 50.0), (250.0, 50.0)), ((250.0, 50.0), (250.0, 150.0)), ((250.0, 150.0), (50.0, 150.0)),
        ((50.0, 150.0), (50.0, 50.0)), ((150.0, 50.0), (150.0, 150.0)),
    ):
        page.draw_line(fitz.Point(*first), fitz.Point(*second), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    source = SourceVisibilityProducer(producer_method="viewport-link-page-test", producer_version="1.0")
    published = source.ingest_native_pdf_bytes(
        document_id="viewport-link-page-doc", source_bytes=payload, source_locator="memory://viewport-link-page.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=("1",),
    )
    fixture = (source, wall_opening,
               compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening))
    off, on = _compose(fixture), _compose(fixture, viewport_wall_identity_links=True)
    assert _public(on) == _public(off) and on == off and all(room.canonical_bounding_wall_ids for room in on.rooms)


@pytest.mark.parametrize("bad", [1, 0, None, "yes"])
def test_the_switch_must_be_a_real_boolean(bad, fallback):
    with pytest.raises(ValueError, match="viewport_wall_identity_links"):
        _compose(fallback, viewport_wall_identity_links=bad)
    for call in (integration.collect_live_physical_net_wall_claim, integration._collect_live_physical_net_wall_claim):
        with pytest.raises(ValueError, match="viewport wall identity links"):
            call("does-not-exist.pdf", viewport_wall_identity_links=bad)


def test_the_collector_passes_the_switch_to_the_room_composer_only_when_named(tmp_path, monkeypatch):
    seen: list[dict] = []
    original = integration.compose_live_canonical_rooms

    def spy(*args, **kwargs):
        seen.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(integration, "compose_live_canonical_rooms", spy)
    path = tmp_path / "fallback.pdf"
    path.write_bytes(_fallback_pdf())
    kwargs = {"pages": (0,), "topology_pages": (0,), "include_surface_finishes": False}
    off = integration.collect_live_physical_net_wall_claim(path, **kwargs)
    assert "viewport_wall_identity_links" not in seen[-1]
    on = integration.collect_live_physical_net_wall_claim(path, viewport_wall_identity_links=True, **kwargs)
    assert seen[-1]["viewport_wall_identity_links"] is True
    assert [r.canonical_room_id for r in on.canonical_rooms] == [r.canonical_room_id for r in off.canonical_rooms]
    assert all(r.canonical_bounding_wall_ids == () for r in off.canonical_rooms)
    assert off.canonical_rooms and all(r.canonical_bounding_wall_ids for r in on.canonical_rooms)
    assert on.quantity_m2 == off.quantity_m2 and on.reason_codes == off.reason_codes
