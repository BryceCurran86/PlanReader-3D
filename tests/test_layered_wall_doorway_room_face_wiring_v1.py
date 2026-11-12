"""Wiring tests: doorway-closed rings through the unchanged room, area and floor chain (default-off)."""
from __future__ import annotations

import hashlib

import fitz
import pytest
from shapely.geometry import Polygon

from types import SimpleNamespace

import pb_layered_wall_doorway_room_face_scope_shadow as scope_module
import pb_same_view_room_area_authority as same_view_module
from pb_layered_wall_doorway_room_face_scope_shadow import (
    LAYERED_RING_SCOPE_REASON,
    RING_FIGURED_BOX_TOLERANCE_PT,
    RING_NOT_A_RECTANGLE_PREFIX,
    figured_box_pair_count,
    layered_ring_room_face_scope,
    layered_ring_scope_overrides,
    ring_face_bounding_box,
)
from pb_layered_wall_doorway_room_ring_shadow import build_from_pdf_bytes, build_layered_wall_doorway_room_rings
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_floor_area_customer_projection import project_live_floor_area_customer_rows
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_same_view_room_area_authority import SameViewRoomAreaProducer
from pb_source_room_face_authority import (
    SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED,
    SOURCE_ROOM_FACE_UNIVERSE_PARTIAL,
    SourceRoomFaceSelector,
    build_source_room_face_authority,
)
from pb_source_visibility_authority import SourceVisibilityProducer

K = 0.5522847498


def layered_room_pdf(*, vertical_pairs: str = "both", door: bool = True, wall_layer: str = "Enclosure_WallInternal",
                     swing: bool = True, label: str = "BED 2", stub: bool = False, robe: bool = False,
                     stub_depth: float = 28.0) -> bytes:
    """Room inner box (100, 80)-(250, 180) on a 400 x 300 page; figured 3600 x 2400 (24 mm per pt).

    vertical_pairs: "both" adds a second, independent figured pair 3600 x 1440 whose box is smaller
    than the room; "short_only" keeps ONLY that smaller pair; "full_only" keeps only the room pair.
    """
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)
    oc = doc.add_ocg(wall_layer, on=True)

    def rect(x0, y0, x1, y1):
        page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=None, fill=(0, 0, 0), oc=oc)

    rect(96, 76, 254, 80)
    rect(96, 180, 254, 184)
    rect(96, 80, 100, 180)
    if stub:
        rect(120, 80, 122, 80 + stub_depth)  # a wall return hanging into the room from the top wall
    if robe:
        # a wardrobe: a wall return from the top wall plus a front on the band y 108..110 whose opening
        # (x 144.4..246) is closed only by two frame boxes and two overlapping sliding leaves
        rect(140, 80, 142, 110)
        rect(140, 108, 144.4, 110)
        rect(246, 108, 250, 110)
        for fx0, fx1 in ((144.4, 145.5), (244.9, 246.0)):
            page.draw_rect(fitz.Rect(fx0, 107.72, fx1, 110.28), color=None, fill=(1, 1, 1), oc=oc)
        page.draw_line(fitz.Point(145.5, 108.0), fitz.Point(195.0, 108.0), color=(0, 0, 0), width=0.34, oc=oc)
        page.draw_line(fitz.Point(190.0, 110.2), fitz.Point(244.9, 110.2), color=(0, 0, 0), width=0.34, oc=oc)
        page.insert_text((180.0, 98.0), "ROBE", fontsize=9.0)
    door_top = 130 if robe else 110  # keep the door's leaf line off the wardrobe front's line
    if door:
        rect(250, 80, 254, door_top)
        rect(250, door_top + 24, 254, 180)
        if swing:
            c, o, t = (250, door_top), (226, door_top), (250, door_top + 24)
            p2 = (o[0] + K * (t[0] - c[0]), o[1] + K * (t[1] - c[1]))
            p3 = (t[0] + K * (o[0] - c[0]), t[1] + K * (o[1] - c[1]))
            page.draw_bezier(fitz.Point(*o), fitz.Point(*p2), fitz.Point(*p3), fitz.Point(*t),
                             color=(0, 0, 0), width=0.34, oc=oc)
            page.draw_line(fitz.Point(*c), fitz.Point(*o), color=(0, 0, 0), width=0.34, oc=oc)
    else:
        rect(250, 80, 254, 180)
    tick_end = 170.0 if vertical_pairs == "both" else 92.0
    page.draw_line((100.0, 70.0), (250.0, 70.0), color=(0, 0, 0), width=1.0)
    page.draw_line((100.0, 62.0), (100.0, tick_end), color=(0, 0, 0), width=1.0)
    page.draw_line((250.0, 62.0), (250.0, tick_end), color=(0, 0, 0), width=1.0)
    page.insert_text((164.0, 67.0), "3600", fontsize=9.0)
    if vertical_pairs in ("both", "full_only"):
        page.draw_line((290.0, 80.0), (290.0, 180.0), color=(0, 0, 0), width=1.0)
        page.draw_line((250.0, 80.0), (298.0, 80.0), color=(0, 0, 0), width=1.0)
        page.draw_line((278.0, 180.0), (298.0, 180.0), color=(0, 0, 0), width=1.0)
        page.insert_text((287.0, 147.0), "2400", fontsize=9.0, rotate=90)
    if vertical_pairs == "both":
        page.draw_line((60.0, 100.0), (60.0, 160.0), color=(0, 0, 0), width=1.0)
        page.draw_line((48.0, 100.0), (100.0, 100.0), color=(0, 0, 0), width=1.0)
        page.draw_line((48.0, 160.0), (100.0, 160.0), color=(0, 0, 0), width=1.0)
        page.insert_text((57.0, 137.0), "1440", fontsize=9.0, rotate=90)
    if vertical_pairs == "short_only":
        page.draw_line((290.0, 80.0), (290.0, 140.0), color=(0, 0, 0), width=1.0)
        page.draw_line((250.0, 80.0), (298.0, 80.0), color=(0, 0, 0), width=1.0)
        page.draw_line((278.0, 140.0), (298.0, 140.0), color=(0, 0, 0), width=1.0)
        page.insert_text((287.0, 117.0), "1440", fontsize=9.0, rotate=90)
    page.insert_text((150.0, 130.0), label, fontsize=10.0)
    return doc.tobytes()


def _chain(data: bytes, *, rings: bool):
    source = SourceVisibilityProducer(producer_method="layered-ring-wiring-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="layered-ring-wiring-doc", source_bytes=data,
        source_locator="memory://layered-ring-wiring.pdf", page_ids=("1",),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=("1",), evidence_page_ids=(),
    )
    walls = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening)
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids,
        **({"layered_doorway_room_rings": True} if rings else {}),
    )
    return source, published, wall_opening, rooms


def _area(source, rooms, *, selection: bool):
    return SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(
        **({"layered_ring_box_selection_shadow": True} if selection else {}),
    )


def test_default_composition_is_unchanged_by_an_explicit_false_and_ignores_the_layered_ink():
    data = layered_room_pdf()
    _s1, _p1, _w1, absent = _chain(data, rings=False)
    source = SourceVisibilityProducer(producer_method="layered-ring-wiring-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="layered-ring-wiring-doc", source_bytes=data,
        source_locator="memory://layered-ring-wiring.pdf", page_ids=("1",),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id, page_ids=("1",), evidence_page_ids=(),
    )
    walls = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening)
    explicit = compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids, layered_doorway_room_rings=False,
    )
    assert [r.polygon_pdf_pts for r in absent.rooms] == [r.polygon_pdf_pts for r in explicit.rooms]
    assert not any(LAYERED_RING_SCOPE_REASON in "".join(r.room_label_reason_codes) for r in absent.rooms)


def test_flag_must_be_an_explicit_boolean():
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,
                                     layered_doorway_room_rings=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim("unused.pdf", layered_doorway_room_rings="yes")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        SameViewRoomAreaProducer.publish(object(), layered_ring_box_selection_shadow=1)  # type: ignore[arg-type]


def test_ring_scope_replaces_the_page_room_scope_with_one_labelled_room_owned_by_strips_and_a_closure():
    _source, _published, _wall_opening, rooms = _chain(layered_room_pdf(), rings=True)
    assert len(rooms.rooms) == 1
    room = rooms.rooms[0]
    assert room.room_label == "BED 2" and room.geometry_complete is True
    xs = [p[0] for p in room.polygon_pdf_pts]
    ys = [p[1] for p in room.polygon_pdf_pts]
    assert (min(xs), min(ys), max(xs), max(ys)) == (100.0, 80.0, 250.0, 180.0)
    assert any(owner.startswith("layered_wall_strip:") for owner in room.bounding_wall_ids)
    # a doorway chord is a planarization barrier only: never a wall owner of any kind
    assert not any("closure" in owner for owner in room.bounding_wall_ids)
    assert room.canonical_bounding_wall_ids == ()
    binding = rooms.room_face_authority_binding_for(room)
    assert binding is not None
    scope = binding.authority.resolve_scope(SourceRoomFaceSelector(
        document_id=room.document_id, revision_id=room.revision_id, source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id, page_id=room.page_id, decision_scope_id=room.decision_scope_id,
    ))
    assert LAYERED_RING_SCOPE_REASON in scope.reason_codes and SOURCE_ROOM_FACE_UNIVERSE_PARTIAL in scope.reason_codes
    assert scope.face_universe_complete is False  # a ring scope never claims the face universe
    record = scope.records[0]
    assert ring_face_bounding_box(record) == (100.0, 80.0, 250.0, 180.0)
    assert not any("closure" in owner for owner, _edge in record.boundary_wall_edges)
    # the chord is exactly the polygon edge with no wall owner: the doorway between its two jambs
    owned = {edge for _owner, edge in record.boundary_wall_edges}
    points = record.polygon_pdf_pts
    polygon_edges = {tuple(sorted((points[i], points[(i + 1) % len(points)]))) for i in range(len(points))}
    assert polygon_edges - owned == {((250.0, 110.0), (250.0, 134.0))}


def test_two_figured_pairs_conflict_by_default_and_the_ring_selects_only_the_pair_equal_to_its_box():
    source, _published, _wall_opening, rooms = _chain(layered_room_pdf(vertical_pairs="both"), rings=True)
    default = _area(source, rooms, selection=False)
    assert default.status is EvidenceResolutionStatus.CONFLICT and default.records == ()
    assert "same_view_multiple_authenticated_dimension_pairs" in {c for _r, c in default.unresolved_first_failure_codes}
    selected = _area(source, rooms, selection=True)
    assert selected.status is EvidenceResolutionStatus.CORROBORATED and len(selected.records) == 1
    evidence = selected.records[0].area_evidence
    assert evidence.normalized_value == pytest.approx(3.6 * 2.4)
    assert (evidence.metadata["horizontal_value_mm"], evidence.metadata["vertical_value_mm"]) == (3600, 2400)


def test_a_ring_no_printed_figure_corroborates_is_never_a_room_face():
    data = layered_room_pdf(vertical_pairs="short_only")
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="d", source_bytes=data, source_locator="memory://x.pdf", page_ids=("1",))
    # the ring closes, but the only figured pair's box is smaller than the ring: abstain, no override
    assert layered_ring_scope_overrides(source, revision_id=published.revision.revision_id, page_ids=("1",)) == {}
    relaxed = layered_ring_scope_overrides(
        source, revision_id=published.revision.revision_id, page_ids=("1",), require_figured_box=False)
    assert len(relaxed) == 1  # without the corroboration requirement the ring itself would have been used


def test_same_view_still_rejects_a_pair_that_differs_from_a_ring_face(monkeypatch):
    original = scope_module.layered_ring_scope_overrides
    monkeypatch.setattr(
        scope_module, "layered_ring_scope_overrides",
        lambda *a, **k: original(*a, **{**k, "require_figured_box": False}))
    source, _published, _wall_opening, rooms = _chain(layered_room_pdf(vertical_pairs="short_only"), rings=True)
    # the single smaller pair is accepted when no ring is consulted: exactly the hazard
    assert _area(source, rooms, selection=False).records[0].area_evidence.normalized_value == pytest.approx(3.6 * 1.44)
    rejected = _area(source, rooms, selection=True)
    assert rejected.records == ()
    assert "same_view_figured_box_differs_from_layered_ring" in {c for _r, c in rejected.unresolved_first_failure_codes}


def _dim(dimension_id, orientation, a, b):
    return SimpleNamespace(dimension_id=dimension_id, orientation=orientation, endpoints_pt=(a, b))


def test_figured_box_pair_count_is_exact_equality_within_a_hard_tolerance():
    box_ = (100.0, 80.0, 250.0, 180.0)
    h = _dim("h1", "horizontal", (100.0, 70.0), (250.0, 70.0))
    v = _dim("v1", "vertical", (290.0, 80.0), (290.0, 180.0))
    assert figured_box_pair_count(box_, [h, v]) == 1
    assert figured_box_pair_count(box_, [h]) == 0 and figured_box_pair_count(box_, [v]) == 0
    assert figured_box_pair_count(box_, [h, v, _dim("v2", "vertical", (320.0, 80.3), (320.0, 179.8))]) == 2
    # the same dimension seen twice is one dimension
    assert figured_box_pair_count(box_, [h, h, v]) == 1
    assert figured_box_pair_count(box_, [_dim("h2", "horizontal", (100.0, 70.0), (250.7, 70.0)), v]) == 0
    assert figured_box_pair_count(box_, [_dim("h3", "horizontal", (100.0, 70.0), (250.4, 70.0)), v]) == 1


def test_parallel_prints_of_the_same_figured_span_are_one_pair_not_a_conflict():
    box_ = (100.0, 80.0, 250.0, 180.0)
    h1 = _dim("h1", "horizontal", (100.0, 70.0), (250.0, 70.0))
    h2 = _dim("h2", "horizontal", (100.0, 50.0), (250.0, 50.0))
    v = _dim("v1", "vertical", (290.0, 80.0), (290.0, 180.0))
    assert figured_box_pair_count(box_, [h1, h2, v]) == 1
    # disagreeing millimetres on those same ticks stay competing
    left = SimpleNamespace(dimension_id="a", orientation="horizontal",
                           endpoints_pt=((100.0, 70.0), (250.0, 70.0)), value_mm=3600.0)
    right = SimpleNamespace(dimension_id="b", orientation="horizontal",
                            endpoints_pt=((100.0, 50.0), (250.0, 50.0)), value_mm=3500.0)
    assert figured_box_pair_count(box_, [left, right, v]) == 2


def test_parallel_prints_still_corroborate_a_closed_ring_as_one_face():
    data = layered_room_pdf(vertical_pairs="full_only")
    sha = hashlib.sha256(data).hexdigest()
    ring_result = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    kwargs = dict(document_id="d", revision_id="r", source_sha256=sha, snapshot_id="s", page_id="1",
                  decision_scope_id="wall-source:page-1")
    dims = [
        _dim("h1", "horizontal", (100.0, 70.0), (250.0, 70.0)),
        _dim("h2", "horizontal", (100.0, 50.0), (250.0, 50.0)),
        _dim("v1", "vertical", (290.0, 80.0), (290.0, 180.0)),
    ]
    scope = layered_ring_room_face_scope(ring_result, **kwargs, corroborating_dimensions=dims)
    assert scope is not None and len(scope.records) == 1


def test_ring_corroboration_tolerance_matches_the_same_view_selection_tolerance():
    assert RING_FIGURED_BOX_TOLERANCE_PT == same_view_module._LAYERED_RING_BOX_TOLERANCE_PT


def test_uncorroborated_closed_ring_is_an_abstention_with_dimensions_and_a_record_without():
    data = layered_room_pdf()
    sha = hashlib.sha256(data).hexdigest()
    ring_result = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    kwargs = dict(document_id="d", revision_id="r", source_sha256=sha, snapshot_id="s", page_id="1",
                  decision_scope_id="wall-source:page-1")
    assert layered_ring_room_face_scope(ring_result, **kwargs, corroborating_dimensions=[]) is None
    assert len(layered_ring_room_face_scope(ring_result, **kwargs).records) == 1


def test_selection_never_touches_a_room_that_is_not_a_ring_face():
    source, _published, _wall_opening, rooms = _chain(layered_room_pdf(vertical_pairs="both"), rings=False)
    plain = _area(source, rooms, selection=False)
    with_option = _area(source, rooms, selection=True)
    assert plain == with_option


@pytest.mark.parametrize("kwargs", [
    {"swing": False},                       # a doorway gap with no door evidence stays open
    {"wall_layer": "Interior_Joinery"},     # not a wall layer
    {"wall_layer": "Finish_WallTiles"},     # a wall FINISH layer is not a wall
])
def test_without_source_evidence_the_option_changes_nothing(kwargs):
    data = layered_room_pdf(**kwargs)
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="d", source_bytes=data, source_locator="memory://x.pdf", page_ids=("1",))
    assert layered_ring_scope_overrides(source, revision_id=published.revision.revision_id, page_ids=("1",)) == {}
    _s, _p, _w, off = _chain(data, rings=False)
    _s2, _p2, _w2, on = _chain(data, rings=True)
    assert [r.polygon_pdf_pts for r in on.rooms] == [r.polygon_pdf_pts for r in off.rooms]


def test_override_must_be_producer_issued_untampered_and_replace_a_derived_scope():
    from dataclasses import replace

    from pb_source_room_face_authority import (
        SCOPE_OVERRIDE_SEAL,
        SourceRoomFaceScopeOverride,
        scope_override_digest,
    )

    data = layered_room_pdf()
    source, published, wall_opening, _rooms = _chain(data, rings=False)
    overrides = layered_ring_scope_overrides(source, revision_id=published.revision.revision_id, page_ids=("1",))
    (key, issued), = overrides.items()
    scope = issued.scope
    authority_of = wall_opening.physical_wall_candidate_authority
    authority = build_source_room_face_authority(authority_of, scope_overrides=overrides)
    selector = SourceRoomFaceSelector(
        document_id=key[0], revision_id=key[1], source_sha256=key[2], snapshot_id=key[3], page_id=key[4], decision_scope_id=key[5])
    assert authority.resolve_scope(selector) is scope
    assert build_source_room_face_authority(authority_of).resolve_scope(selector) != scope
    # a plain scope with matching lineage strings is not an issued override
    with pytest.raises(TypeError):
        build_source_room_face_authority(authority_of, scope_overrides={key: scope})  # type: ignore[dict-item]
    # an issued-looking object without the issuer seal cannot even be constructed
    with pytest.raises(TypeError):
        SourceRoomFaceScopeOverride(scope=scope, receipt_digest=scope_override_digest(scope))
    with pytest.raises(TypeError):
        SourceRoomFaceScopeOverride(scope=scope, receipt_digest=scope_override_digest(scope), _seal=object())
    # edited content no longer matches the issued digest
    tampered = replace(scope, records=(replace(scope.records[0], polygon_pdf_pts=((0.0, 0.0), (9.0, 0.0), (9.0, 9.0), (0.0, 9.0))),))
    with pytest.raises(ValueError):
        build_source_room_face_authority(authority_of, scope_overrides={key: replace(issued, scope=tampered)})
    # a digest-consistent scope for a lineage this authority never derived is refused (foreign document)
    foreign = replace(scope, document_id="some-other-document")
    foreign_issued = SourceRoomFaceScopeOverride(
        scope=foreign, receipt_digest=scope_override_digest(foreign), _seal=SCOPE_OVERRIDE_SEAL)
    foreign_key = (foreign.document_id, *key[1:])
    with pytest.raises(ValueError):
        build_source_room_face_authority(authority_of, scope_overrides={foreign_key: foreign_issued})
    # the key must equal the scope's own lineage
    with pytest.raises(ValueError):
        build_source_room_face_authority(authority_of, scope_overrides={(*key[:5], "wall-source:page-9"): issued})


def test_converter_is_deterministic_and_keeps_abstained_rings_as_abstentions():
    data = layered_room_pdf()
    sha = hashlib.sha256(data).hexdigest()
    ring_result = build_from_pdf_bytes(data, source_sha256=sha, page_index=0)
    kwargs = dict(document_id="d", revision_id="r", source_sha256=sha, snapshot_id="s", page_id="1", decision_scope_id="wall-source:page-1")
    first = layered_ring_room_face_scope(ring_result, **kwargs)
    second = layered_ring_room_face_scope(ring_result, **kwargs)
    assert first == second and len(first.records) == 1 and first.abstained_faces == ()
    owners = {owner for owner, _edge in first.records[0].boundary_wall_edges}
    assert owners == set(first.records[0].bounding_wall_ids) and len(owners) >= 2
    assert all(owner.startswith("layered_wall_") for owner in owners)
    no_ring = build_from_pdf_bytes(layered_room_pdf(swing=False), source_sha256=hashlib.sha256(layered_room_pdf(swing=False)).hexdigest(), page_index=0)
    assert layered_ring_room_face_scope(no_ring, **kwargs) is None


def test_whole_claim_with_the_option_yields_one_firm_floor_area_and_one_customer_row(tmp_path):
    path = tmp_path / "layered_room.pdf"
    path.write_bytes(layered_room_pdf(vertical_pairs="both"))
    off = collect_live_physical_net_wall_claim(path, pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,))
    assert off.room_area_quantity_evidence == () and publish_live_floor_area_quantities(off) == ()
    on = collect_live_physical_net_wall_claim(path, pages=(0,), topology_pages=(0,), surface_semantic_pages=(0,),
                                              layered_doorway_room_rings=True)
    assert len(on.room_area_quantity_evidence) == 1
    quantity = on.room_area_quantity_evidence[0]
    assert (quantity.status, quantity.unit, quantity.authority) == ("firm", "m2", "documented_dimension")
    assert quantity.value == pytest.approx(8.64) and not quantity.abstained
    floors = publish_live_floor_area_quantities(on)
    assert [(q.family, q.status) for q in floors] == [("floor_area", "firm")]
    rows = project_live_floor_area_customer_rows(on, workspace_id=1, project_id="layered-ring-wiring")
    assert len(rows) == 1


def _strip_rows(x0, y0, x1, y1):
    c = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    items = [("l", fitz.Point(*c[i]), fitz.Point(*c[(i + 1) % 4])) for i in range(4)]
    return [{"layer": "Enclosure_WallInternal", "fill": (0.0, 0.0, 0.0), "items": items}]


def test_a_region_left_open_by_an_unevidenced_wall_cut_is_an_abstention_and_never_a_record():
    rows = []
    # room A: closed box, no gaps
    for box_ in ((0, 0, 100, 4), (0, 96, 100, 100), (0, 4, 4, 96), (96, 4, 100, 96)):
        rows += _strip_rows(*box_)
    # region B: two boxes sharing a partition that is cut in two with no door evidence
    for box_ in ((200, 0, 400, 4), (200, 96, 400, 100), (200, 4, 204, 96), (396, 4, 400, 96)):
        rows += _strip_rows(*box_)
    rows += _strip_rows(298, 4, 302, 30) + _strip_rows(298, 60, 302, 96)
    ring_result = build_layered_wall_doorway_room_rings(rows, source_sha256="ab" * 32, page_index=0)
    statuses = sorted(r.status.value for r in ring_result.rings)
    assert statuses == ["abstained", "candidate"]
    scope = layered_ring_room_face_scope(
        ring_result, document_id="d", revision_id="r", source_sha256="ab" * 32,
        snapshot_id="s", page_id="1", decision_scope_id="wall-source:page-1")
    assert len(scope.records) == 1 and len(scope.abstained_faces) == 1
    assert scope.abstained_faces[0].reason == SOURCE_ROOM_FACE_BOUNDARY_UNRESOLVED
    assert {a.face_id for a in scope.abstained_faces}.isdisjoint({r.face_id for r in scope.records})
    assert ring_face_bounding_box(scope.records[0]) == (4.0, 4.0, 96.0, 96.0)


def test_a_face_that_is_not_its_rectangle_loses_the_documented_route_but_a_true_rectangle_keeps_it():
    # rectangle: no token, documented 3.6 x 2.4 area stands
    source, _p, _w, rooms = _chain(layered_room_pdf(vertical_pairs="both"), rings=True)
    room = rooms.rooms[0]
    scope = rooms.room_face_authority_binding_for(room).authority.resolve_scope(SourceRoomFaceSelector(
        document_id=room.document_id, revision_id=room.revision_id, source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id, page_id=room.page_id, decision_scope_id=room.decision_scope_id))
    assert not any(code.startswith(RING_NOT_A_RECTANGLE_PREFIX) for code in scope.reason_codes)
    assert _area(source, rooms, selection=True).records[0].area_evidence.normalized_value == pytest.approx(8.64)
    # the same room with a wall return inside it: width x depth is withdrawn; the face polygon is measured
    source, _p, _w, rooms = _chain(layered_room_pdf(vertical_pairs="both", stub=True), rings=True)
    room = rooms.rooms[0]
    scope = rooms.room_face_authority_binding_for(room).authority.resolve_scope(SourceRoomFaceSelector(
        document_id=room.document_id, revision_id=room.revision_id, source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id, page_id=room.page_id, decision_scope_id=room.decision_scope_id))
    assert f"{RING_NOT_A_RECTANGLE_PREFIX}{room.source_room_face_record_id}" in scope.reason_codes
    selected = _area(source, rooms, selection=True)
    evidence = selected.records[0].area_evidence
    face_m2 = Polygon(room.polygon_pdf_pts).area * 24.0 * 24.0 / 1_000_000.0
    assert evidence.normalized_value == pytest.approx(face_m2)
    assert evidence.normalized_value < 8.64
    assert evidence.metadata["face_polygon_area"] is True


@pytest.mark.parametrize("depth", [10.0, 1.0])
def test_a_shallow_wall_return_is_spatial_content_and_withdraws_the_documented_area(depth):
    # the return's area (2 x depth) is far below the perimeter-scaled allowance the first rectangle test used
    # (25 pt2 on this 150 x 100 room), yet it is real wall ink inside the room: the box is not the face
    source, _p, _w, rooms = _chain(layered_room_pdf(vertical_pairs="both", stub=True, stub_depth=depth), rings=True)
    room = rooms.rooms[0]
    scope = rooms.room_face_authority_binding_for(room).authority.resolve_scope(SourceRoomFaceSelector(
        document_id=room.document_id, revision_id=room.revision_id, source_sha256=room.source_sha256,
        snapshot_id=room.snapshot_id, page_id=room.page_id, decision_scope_id=room.decision_scope_id))
    assert f"{RING_NOT_A_RECTANGLE_PREFIX}{room.source_room_face_record_id}" in scope.reason_codes
    selected = _area(source, rooms, selection=True)
    evidence = selected.records[0].area_evidence
    face_m2 = Polygon(room.polygon_pdf_pts).area * 24.0 * 24.0 / 1_000_000.0
    assert evidence.normalized_value == pytest.approx(face_m2)
    assert evidence.normalized_value < 8.64
    assert evidence.metadata["face_polygon_area"] is True


def _notched(width, depth):
    return [(0.0, 0.0), (20.0, 0.0), (20.0, depth), (20.0 + width, depth), (20.0 + width, 0.0),
            (150.0, 0.0), (150.0, 100.0), (0.0, 100.0)]


def test_rectangle_predicate_is_spatial_not_an_area_deficit():
    fills = scope_module._fills_its_bounding_rectangle
    assert fills([(0.0, 0.0), (150.0, 0.0), (150.0, 100.0), (0.0, 100.0)])
    # extra collinear vertices (a split edge) change nothing, in either orientation
    assert fills([(0.0, 0.0), (75.0, 0.0), (150.0, 0.0), (150.0, 50.0), (150.0, 100.0), (0.0, 100.0)])
    assert fills([(0.0, 100.0), (0.0, 50.0), (0.0, 0.0), (150.0, 0.0), (150.0, 100.0)])
    # a return of any real width is content however small its area; one under twice the noise bound is noise
    assert not fills(_notched(2.0, 10.0)) and not fills(_notched(2.0, 1.0))
    assert not fills(_notched(0.2, 50.0)) and not fills(_notched(0.12, 50.0))
    assert fills(_notched(0.08, 50.0))
    # an L-shaped face and a degenerate polygon are not rectangles
    assert not fills([(0.0, 0.0), (150.0, 0.0), (150.0, 40.0), (60.0, 40.0), (60.0, 100.0), (0.0, 100.0)])
    assert not fills([(0.0, 0.0), (150.0, 100.0), (150.0, 0.0), (0.0, 100.0)])  # self-crossing
    # a spike that doubles back on itself covers the whole box but is not a valid face
    spiked = [(0.0, 0.0), (150.0, 0.0), (150.0, 100.0), (0.0, 100.0), (0.0, 50.0), (10.0, 50.0), (0.0, 50.0)]
    assert not Polygon(spiked).is_valid
    assert not fills(spiked)


def test_sliding_leaf_control_needs_the_ring_control_and_explicit_booleans(tmp_path):
    source = SourceVisibilityProducer(producer_method="t", producer_version="1")
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
                                     layered_sliding_leaf_closure=True)
    with pytest.raises(ValueError):
        compose_live_canonical_rooms(source_visibility_producer=source, wall_opening_composition=None,  # type: ignore[arg-type]
                                     layered_doorway_room_rings=True, layered_sliding_leaf_closure=1)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim("unused.pdf", layered_sliding_leaf_closure=True)
    with pytest.raises(ValueError):
        collect_live_physical_net_wall_claim("unused.pdf", layered_doorway_room_rings=True, layered_sliding_leaf_closure="yes")  # type: ignore[arg-type]


def _chain_with(data: bytes, *, sliding: bool):
    source = SourceVisibilityProducer(producer_method="layered-ring-wiring-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="layered-ring-wiring-doc", source_bytes=data,
        source_locator="memory://layered-ring-wiring.pdf", page_ids=("1",),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=published.revision.revision_id,
        page_ids=("1",), evidence_page_ids=(),
    )
    walls = compose_live_canonical_walls(source_visibility_producer=source, wall_opening_composition=wall_opening)
    rooms = compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
        canonical_wall_ids_by_candidate=walls.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=walls.unresolved_wall_candidate_ids,
        layered_doorway_room_rings=True,
        **({"layered_sliding_leaf_closure": True} if sliding else {}),
    )
    return source, rooms


def test_wardrobe_front_splits_the_alcove_frees_the_label_and_withdraws_the_documented_area():
    data = layered_room_pdf(vertical_pairs="both", robe=True)
    # without its own control the wardrobe opening stays open: the ring is not closed, nothing replaces the scope
    _source, closed_off = _chain_with(data, sliding=False)
    assert not any(LAYERED_RING_SCOPE_REASON in "".join(r.room_label_reason_codes) for r in closed_off.rooms)
    assert not any(r.bounding_wall_ids and r.bounding_wall_ids[0].startswith("layered_") for r in closed_off.rooms)
    source, rooms = _chain_with(data, sliding=True)
    assert len(rooms.rooms) == 1
    room = rooms.rooms[0]
    # the bedroom's own label, not the wardrobe word that used to sit inside the same ring
    assert room.room_label == "BED 2"
    xs = [p[0] for p in room.polygon_pdf_pts]
    ys = [p[1] for p in room.polygon_pdf_pts]
    assert (min(xs), min(ys), max(xs), max(ys)) == (100.0, 80.0, 250.0, 180.0)
    area = SameViewRoomAreaProducer.from_source(source=source, rooms=rooms).publish(layered_ring_box_selection_shadow=True)
    evidence = area.records[0].area_evidence
    face_m2 = Polygon(room.polygon_pdf_pts).area * 24.0 * 24.0 / 1_000_000.0
    assert evidence.normalized_value == pytest.approx(face_m2)
    assert evidence.normalized_value < 8.64
    assert evidence.metadata["face_polygon_area"] is True
