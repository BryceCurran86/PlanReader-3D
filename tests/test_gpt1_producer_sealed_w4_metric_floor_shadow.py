"""Only producer-sealed original W4 source room faces may reach figured m²."""
from dataclasses import replace
import fitz

from pb_live_canonical_floor_surface import compose_live_canonical_floor_surfaces
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_wall_composition import compose_live_canonical_walls
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_producer_sealed_w4_metric_floor_shadow import (
    bind_producer_sealed_w4_metric_floor_shadow,
)


def _actual_synthetic_producer():
    doc=fitz.open()
    try:
        p=doc.new_page(width=300,height=200)
        for a,b in (
            ((50,50),(250,50)),((250,50),(250,150)),
            ((250,150),(50,150)),((50,150),(50,50)),
            ((150,50),(150,150)),
        ):
            p.draw_line(a,b,color=(0,0,0),width=1)
        original=doc.tobytes()
    finally:
        doc.close()
    producer=SourceVisibilityProducer(
        producer_method="gpt1-source-owned-w4-shadow-test",
        producer_version="1.0",
    )
    published=producer.ingest_native_pdf_bytes(
        document_id="gpt1-source-owned-w4-shadow-test",
        source_bytes=original,
        source_locator="memory://gpt1-original-source-synthetic.pdf",
    )
    wall=compose_live_wall_opening_authority(
        source_visibility_producer=producer,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    wall_core=compose_live_canonical_walls(
        source_visibility_producer=producer,
        wall_opening_composition=wall,
    )
    rooms=compose_live_canonical_rooms(
        source_visibility_producer=producer,
        wall_opening_composition=wall,
        canonical_wall_ids_by_candidate=wall_core.candidate_to_canonical_wall_id,
        unresolved_wall_candidate_ids=wall_core.unresolved_wall_candidate_ids,
    )
    floors=compose_live_canonical_floor_surfaces(rooms)
    assert rooms.status is Status.CORROBORATED
    assert len(rooms.rooms)==2
    assert len(floors.floors)==2
    return rooms,floors


def _metric_candidate(room):
    # Synthetic stand-in for the independent figured dimension producer:
    # a CANDIDATE not FIRM. Only this test fixture supplies metric coordinates.
    original=room.polygon_pdf_pts
    metric=tuple((10*float(x),10*float(y)) for x,y in original)
    return FiguredPolygonMetricShadow(
        status=Status.CANDIDATE,
        reason_codes=("synthetic_figured_dimensions_candidate",),
        candidate_area_m2=room.area_page_pts2/10000.,
        metric_vertices_mm=metric,
        source_figure_ids=("test-figured-height","test-figured-width"),
        closure_inferred_side_ids=(),
        source_sha256=room.source_sha256,
        revision_id=room.revision_id,
        page_id=room.page_id,
        physical_room_id=room.physical_room_id,
        diagnostic_only=True,
        source_side_ids=tuple(f"side-{i}" for i in range(len(original))),
        source_segment_ids=tuple(f"source-wall-{i}" for i in range(len(original))),
        source_vertices_pdf_pts=tuple(original),
    )


def _run(rooms=None,floors=None,metric=None):
    actual_rooms,actual_floors=_actual_synthetic_producer()
    if rooms is None: rooms=actual_rooms
    if floors is None: floors=actual_floors
    chosen=actual_rooms.rooms[0]
    if metric is None: metric=_metric_candidate(chosen)
    return bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,metric,
        physical_room_id=chosen.physical_room_id,
    )


def test_only_existing_producer_sealed_w4_face_can_authenticate_metric_room_candidate():
    rooms,floors=_actual_synthetic_producer()
    chosen=rooms.rooms[0]
    out=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,_metric_candidate(chosen),
        physical_room_id=chosen.physical_room_id,
    )
    assert out.status is Status.CANDIDATE
    assert out.physical_room_id==chosen.physical_room_id
    assert out.source_room_face_record_id==chosen.source_room_face_record_id
    assert out.original_source_face_boundary_wall_ids
    assert out.original_published_boundary_subedges
    assert out.canonical_floor_id
    assert out.independent_candidate_metric_area_m2 is not None
    assert out.diagnostic_only
    assert not hasattr(out,"quantity_id")


def test_manual_canonical_room_copy_cannot_borrow_sealed_source_face():
    rooms,floors=_actual_synthetic_producer()
    unsealed=replace(rooms,_room_face_authority_bindings=())
    first=rooms.rooms[0]
    out=bind_producer_sealed_w4_metric_floor_shadow(
        unsealed,floors,_metric_candidate(first),
        physical_room_id=first.physical_room_id,
    )
    assert out.status is Status.ABSTAINED
    assert out.reason_codes==("original_w4_producer_sealed_room_face_authority_missing",)
    assert out.independent_candidate_metric_area_m2 is None


def test_w4_original_polygon_competitor_cannot_be_overwritten_by_metric_ring():
    rooms,floors=_actual_synthetic_producer()
    room=rooms.rooms[0]
    metric=_metric_candidate(room)
    shifted=tuple((x+10,y) for x,y in metric.source_vertices_pdf_pts)
    result=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,replace(metric,source_vertices_pdf_pts=shifted),
        physical_room_id=room.physical_room_id,
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("original_w4_source_room_face_geometry_conflict",)


def test_one_original_w4_face_cannot_fund_two_canonical_floors():
    rooms,floors=_actual_synthetic_producer()
    room=rooms.rooms[0]
    copied=replace(floors,floors=(*floors.floors,floors.floors[0]))
    out=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,copied,_metric_candidate(room),
        physical_room_id=room.physical_room_id,
    )
    assert out.status is Status.ABSTAINED
    assert out.reason_codes==("original_w4_canonical_floor_not_unique",)


def test_wrong_original_revision_does_not_alias_proven_room_face():
    rooms,floors=_actual_synthetic_producer()
    room=rooms.rooms[0]
    metric=replace(_metric_candidate(room),revision_id="foreign-revision")
    out=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,metric,physical_room_id=room.physical_room_id,
    )
    assert out.status is Status.ABSTAINED
    assert out.reason_codes==("original_w4_source_room_face_lineage_conflict",)


def test_revised_metric_value_cannot_borrow_original_producer_wall_authority():
    rooms,floors=_actual_synthetic_producer()
    room=rooms.rooms[0]
    altered=replace(_metric_candidate(room),candidate_area_m2=999.)
    out=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,altered,physical_room_id=room.physical_room_id,
    )
    assert out.status is Status.ABSTAINED
    assert out.reason_codes==("original_w4_independent_metric_ring_area_conflict",)


def test_missing_independent_figured_dimensional_witnesses_do_not_acquire_m2():
    rooms,floors=_actual_synthetic_producer()
    room=rooms.rooms[0]
    spoof=replace(_metric_candidate(room),source_figure_ids=("only-one",))
    out=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,spoof,physical_room_id=room.physical_room_id,
    )
    assert out.status is Status.ABSTAINED
    assert out.independent_candidate_metric_area_m2 is None
