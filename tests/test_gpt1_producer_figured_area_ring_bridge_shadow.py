"""Source-issuer receipts bind real canonical floors to independent metric rings."""
from dataclasses import replace
from pb_migration_contracts import EvidenceResolutionStatus as Status, EvidenceAtom, stable_contract_id
from pb_same_view_room_area_authority import (
    SameViewRoomAreaRecord,SameViewRoomAreaResult,_RECORD_SEAL
)
from pb_live_canonical_floor_surface import (
    LiveCanonicalFloorSurfaceObject,LiveCanonicalFloorSurfaceComposition,
)
from pb_gpt1_figured_chain_metric_shadow import (
    FiguredPhysicalSide,measure_figured_room_edge_chain_shadow,
)
from pb_gpt1_producer_figured_area_ring_bridge_shadow import (
    bind_producer_figured_area_to_original_room_ring_shadow
)

SHA="a"*64


def original_ring():
    points=((0,0),(10,0),(10,5),(0,5))
    sides=tuple(FiguredPhysicalSide(
        f"side-{i}",points[i],points[(i+1)%4],(f"original-wall-{i}",),
        {0:5000,1:2000}.get(i),
        {0:"original-figured-h",1:"original-figured-v"}.get(i),
        (f"figure-native-{i}-a",f"figure-native-{i}-b") if i<2 else (),
    ) for i in range(4))
    return measure_figured_room_edge_chain_shadow(
        sides,source_sha256=SHA,revision_id="rev",page_id="7",
        physical_room_id="physical-room-one",
    )


def original_producer_area():
    evidence=EvidenceAtom(
        evidence_id="original-area-receipt",
        document_id="document",page_id="7",
        viewport_id="original-main",
        kind="explicit_room_area",
        method="authenticated_same_view_figured_dimensions",
        normalized_value=10.,unit="m2",status=Status.CORROBORATED,
        metadata={
            "source_dimension_box_pdf_pts":(0,0,10,5),
            "source_dimension_page_id":"7",
            "source_sha256":SHA,
            "room_revision_id":"rev",
            "figured_dimension_ids":("original-figured-h","original-figured-v"),
        }
    )
    record=SameViewRoomAreaRecord(
        physical_room_id="physical-room-one",
        source_room_face_record_id="original-room-face-one",
        room_label="Original room",
        source_dimension_page_id="7",
        source_label_observation_ids=("label-1",),
        source_label_receipt_ids=("label-proof-1",),
        horizontal_dimension_id="original-figured-h",
        vertical_dimension_id="original-figured-v",
        area_evidence=evidence,_seal=_RECORD_SEAL,
    )
    return SameViewRoomAreaResult(Status.CORROBORATED,("source",),(record,),())


def original_canonical_floor():
    floor_id=stable_contract_id(
        "physical_room_floor_surface",
        {"document_id":"document","physical_room_id":"physical-room-one",
         "surface_role":"floor"},
        digest_chars=32,
    )
    obj=LiveCanonicalFloorSurfaceObject(
        canonical_floor_id=floor_id,physical_floor_surface_id=floor_id,
        room_entity_id="canonical-room",document_id="document",
        revision_id="rev",source_sha256=SHA,snapshot_id="snapshot",
        page_id="7",viewport_id="original-main",
        polygon_pdf_pts=((0,0),(10,0),(10,5),(0,5)),
        area_page_pts2=50.,bounding_wall_ids=(),canonical_bounding_wall_ids=(),
        source_room_face_record_id="original-room-face-one",
        evidence_ids=("original-area-receipt",),geometry_complete=True,
        metric_geometry_complete=False,metric_area_m2=10.,
        metric_area_quantity_id="original-existing-signed-area-id",
        metric_area_authority="documented_dimension",
        finish_descriptor=None,structural_slab_id=None,
        physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=False,
    )
    return LiveCanonicalFloorSurfaceComposition(
        Status.CORROBORATED,("original",),(obj,),(7,),
    )


def bind(**overrides):
    params=dict(
        physical_ring=original_ring(),
        same_view=original_producer_area(),cross_view=None,
        canonical_floors=original_canonical_floor(),
        original_room_face_id="original-room-face-one",
    )
    params.update(overrides)
    return bind_producer_figured_area_to_original_room_ring_shadow(**params)


def test_exact_existing_area_issuer_matches_source_owned_metric_ring():
    result=bind()
    assert result.status is Status.CANDIDATE
    assert result.original_room_area_m2==10.
    assert result.independently_calculated_polygon_m2==10.
    assert result.original_figured_area_evidence_id=="original-area-receipt"
    assert result.original_figure_ids==(
        "original-figured-h","original-figured-v"
    )
    assert result.diagnostic_only
    assert not hasattr(result,"quantity_id")


def test_same_original_face_reused_by_two_area_records_quarantines_both():
    source=original_producer_area()
    rival=replace(source.records[0],horizontal_dimension_id="another-figure")
    result=bind(same_view=replace(source,records=source.records+(rival,)))
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("source_producer_figured_room_owner_conflict",)


def test_polygon_candidate_must_match_unchanged_issued_metric_area():
    ring=replace(original_ring(),candidate_area_m2=11.)
    result=bind(physical_ring=ring)
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("source_producer_figured_polygon_area_disagreement",)


def test_source_figure_id_identity_cannot_come_from_rekeyed_numeric_label():
    original=original_producer_area()
    unowned=replace(original.records[0].area_evidence,
                    metadata={**original.records[0].area_evidence.metadata,
                              "figured_dimension_ids":("fake-h","fake-v")})
    tampered=replace(original.records[0],area_evidence=unowned)
    result=bind(same_view=replace(original,records=(tampered,)))
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("source_producer_figured_polygon_physical_scope_conflict",)


def test_source_room_face_is_not_selected_by_matched_label_or_equal_area():
    assert bind(original_room_face_id="another-source-face").status is Status.ABSTAINED


def test_stale_pdf_issuer_cannot_rebind_prior_figure_to_new_revision():
    floor=original_canonical_floor()
    old=replace(floor.floors[0],revision_id="previous")
    result=bind(canonical_floors=replace(floor,floors=(old,)))
    assert result.status is Status.ABSTAINED
