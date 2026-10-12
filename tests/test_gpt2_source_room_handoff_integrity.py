"""Adversarial first-authenticated owner tests: no named room/area inference."""
from copy import deepcopy
from types import SimpleNamespace as Obj

import pytest

from tools.diag_gpt2_source_room_handoff_integrity import (
    report_source_room_handoff,
)

SHA = "a" * 64


def fixture():
    room = Obj(
        source_sha256=SHA, room_label="FOOD PREP",
        document_id="real-document", revision_id="source-revision",
        snapshot_id="original-snapshot", decision_scope_id="wall-source:viewport:7:v",
        page_id="7", viewport_id="v", physical_room_id="original-physical-1",
        canonical_room_id="canonical-room-1", source_room_face_record_id="face-receipt-1",
        room_label_binding_record_id="label-source-1",
        room_label_evidence_ids=("native-observation-1",),
        polygon_pdf_pts=((0.,0.),(2.,0.),(2.,1.),(0.,1.)),
        area_page_pts2=2., geometry_complete=True,
    )
    floor = Obj(
        source_sha256=SHA, room_entity_id=room.canonical_room_id,
        document_id=room.document_id, snapshot_id=room.snapshot_id,
        page_id=room.page_id, viewport_id=room.viewport_id,
        source_room_face_record_id=room.source_room_face_record_id,
        canonical_floor_id="canonical-floor-1",
        polygon_pdf_pts=room.polygon_pdf_pts, geometry_complete=True,
        metric_geometry_complete=True, metric_area_m2=1.5,
        metric_area_quantity_id="quantity-area-1",
        physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=True,
    )
    q = Obj(
        quantity_id="quantity-area-1", status="FIRM", family="ROOM_AREA",
        input_entity_ids=("original-source-face-id-1",),
        semantic_key="room_area:original-source-face-id-1",
        evidence_ids=("face-receipt-1","original-dimension-receipt"),
        metadata={"source_sha256":SHA,"revision_id":room.revision_id,
                  "viewport_id":room.viewport_id},
        unit="m2", value=1.5, abstained=False,
    )
    return Obj(canonical_rooms=(room,), canonical_floors=(floor,),
               room_area_quantity_evidence=(q,),floor_finish_quantity_evidence=(),
               ceiling_lining_quantity_evidence=())


def one(claim):
    return report_source_room_handoff(claim,original_source_sha=SHA,targets=("FOOD PREP",))["room_handoff_first_gates"][0]


def test_complete_unique_source_chain_is_only_a_handoff_and_not_finish():
    result=one(fixture())
    assert result["first_unproved_authority"]=="SOURCE_ROOM_AREA_READY_FOR_GPT1_GPT3_REVIEW"
    assert result["source_proven_area_m2"]==1.5
    assert result["original_source_face_receipt_id"]=="face-receipt-1"
    assert result["original_label_binding_record_id"]=="label-source-1"
    assert result["original_label_evidence_ids"]==["native-observation-1"]
    assert result["documented_area_quantity_id"]=="quantity-area-1"
    assert result["documented_area_source_evidence_ids"]==[
        "face-receipt-1","original-dimension-receipt"]
    assert result["canonical_floor_id"]=="canonical-floor-1"
    assert result["floor_finish_publication_allowed"] is False
    assert result["ceiling_lining_publication_allowed"] is False
    assert result["metric_area_inferred_from_page_points"] is False


@pytest.mark.parametrize("damage,first_gate",[
    ("no_room","SOURCE_PHYSICAL_FACE_UNAVAILABLE"),
    ("second_face","ROOM_LABEL_MULTIPLE_SOURCE_FACES"),
    ("foreign_room_sha","SOURCE_ROOM_FACE_IDENTITY_CONFLICT"),
    ("missing_viewport","SOURCE_ROOM_FACE_IDENTITY_CONFLICT"),
    ("missing_room_id","SOURCE_ROOM_FACE_IDENTITY_CONFLICT"),
    ("competing_face_receipt","ROOM_LABEL_MULTIPLE_SOURCE_FACES"),
    ("empty_label_receipt","ORIGINAL_ROOM_LABEL_RECEIPT_AMBIGUOUS"),
    ("duplicated_native_word","ORIGINAL_ROOM_LABEL_RECEIPT_AMBIGUOUS"),
    ("nan_polygon","SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE"),
    ("unclosed_polygon","SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE"),
    ("no_floor","CANONICAL_FLOOR_OWNER_UNAVAILABLE"),
    ("duplicated_floor","CANONICAL_FLOOR_OWNER_UNAVAILABLE"),
    ("foreign_floor_sha","FLOOR_ORIGINAL_PHYSICAL_FACE_LINEAGE_CONFLICT"),
    ("different_source_face","FLOOR_ORIGINAL_PHYSICAL_FACE_LINEAGE_CONFLICT"),
    ("different_floor_polygon","FLOOR_ORIGINAL_PHYSICAL_FACE_LINEAGE_CONFLICT"),
    ("missing_metric","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("abstained_quantity","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("unscaled_area","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("duplicate_quantity_id","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("quantity_input_missing_floor","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("nonfinite_quantity","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("quantity_foreign_sha","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("quantity_foreign_viewport","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("quantity_wrong_face_receipt","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("quantity_semantic_owner_mismatch","FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"),
    ("wrong_floor_quantity","COMMERCIAL_FLOOR_AREA_AUTHORITY_UNAVAILABLE"),
    ("untrusted_floor_measurement","COMMERCIAL_FLOOR_AREA_AUTHORITY_UNAVAILABLE"),
    ("unpublished_commercial","COMMERCIAL_FLOOR_AREA_AUTHORITY_UNAVAILABLE"),
])
def test_eight_authority_stages_fail_closed(damage,first_gate):
    c=fixture()
    r=c.canonical_rooms[0]
    f=c.canonical_floors[0]
    q=c.room_area_quantity_evidence[0]
    if damage=="no_room":c.canonical_rooms=()
    elif damage=="second_face":
        c.canonical_rooms=(r,deepcopy(r))
    elif damage=="foreign_room_sha":r.source_sha256="b"*64
    elif damage=="missing_viewport":r.viewport_id=None
    elif damage=="missing_room_id":r.physical_room_id=None
    elif damage=="competing_face_receipt":
        c.canonical_rooms=(r,deepcopy(r));c.canonical_rooms[1].source_room_face_record_id="other-face"
    elif damage=="empty_label_receipt":r.room_label_binding_record_id=None
    elif damage=="duplicated_native_word":r.room_label_evidence_ids=("observation-1","observation-1")
    elif damage=="nan_polygon":r.polygon_pdf_pts=((0.,0.),(1.,float("nan")),(2.,2.))
    elif damage=="unclosed_polygon":r.geometry_complete=False
    elif damage=="no_floor":c.canonical_floors=()
    elif damage=="duplicated_floor":c.canonical_floors=(f,deepcopy(f))
    elif damage=="foreign_floor_sha":f.source_sha256="b"*64
    elif damage=="different_source_face":f.source_room_face_record_id="foreign-face-receipt"
    elif damage=="different_floor_polygon":f.polygon_pdf_pts=((0.,0.),(1.,0.),(1.,1.))
    elif damage=="missing_metric":c.room_area_quantity_evidence=()
    elif damage=="abstained_quantity":q.abstained=True;q.value=None
    elif damage=="unscaled_area":q.status="candidate"
    elif damage=="duplicate_quantity_id":c.room_area_quantity_evidence=(q,deepcopy(q))
    elif damage=="quantity_input_missing_floor":q.input_entity_ids=("unrelated-object",)
    elif damage=="nonfinite_quantity":q.value=float("nan")
    elif damage=="quantity_foreign_sha":q.metadata["source_sha256"]="b"*64
    elif damage=="quantity_foreign_viewport":q.metadata["viewport_id"]="other"
    elif damage=="quantity_wrong_face_receipt":q.evidence_ids=("wrong-face","original-dimension-receipt")
    elif damage=="quantity_semantic_owner_mismatch":q.semantic_key="room_area:foreign-face"
    elif damage=="wrong_floor_quantity":f.metric_area_quantity_id="another-quantity"
    elif damage=="untrusted_floor_measurement":f.metric_geometry_complete=False
    elif damage=="unpublished_commercial":f.commercial_quantity_authority=False
    out=one(c)
    assert out["first_unproved_authority"]==first_gate
    assert out["floor_finish_publication_allowed"] is False
    assert out["benchmark_accuracy"] is None


def test_missing_targets_are_not_materialised_from_names():
    c=fixture()
    result=report_source_room_handoff(c,original_source_sha=SHA)
    assert len(result["room_handoff_first_gates"])==15
    for name in ("DRY STORE","POS COUNTER","FOOD SERVICE","WASH UP",
                 "TRUCK DRIVER LOUNGE","M-AMB","F-AMB","FREEZER"):
        row=next(r for r in result["room_handoff_first_gates"]
                 if r["source_room_label"]==name)
        assert row["first_unproved_authority"]=="SOURCE_PHYSICAL_FACE_UNAVAILABLE"
        assert row["source_proven_area_m2"] is None
        assert row["original_label_binding_record_id"] is None
        assert row["original_label_evidence_ids"]==[]
        assert row["documented_area_source_evidence_ids"]==[]
    assert result["dry_store_must_abstain_without_new_proof"]
    assert result["diagnostic_only"]
    assert result["benchmark_accuracy"] is None


@pytest.mark.parametrize("bad",[
    "bad-sha","", "a"*63, "z"*64, "A"*64,
])
def test_original_pdf_sha_must_be_real_lower_hex(bad):
    with pytest.raises(ValueError):
        report_source_room_handoff(fixture(),original_source_sha=bad)


def test_duplicate_target_names_do_not_publish_multiple_rows():
    with pytest.raises(ValueError):
        report_source_room_handoff(fixture(),original_source_sha=SHA,
                                   targets=("food prep"," FOOD  PREP "))


def test_original_word_and_metric_evidence_only_appear_after_source_gates():
    c=fixture()
    c.canonical_rooms[0].room_label_binding_record_id=""
    row=one(c)
    assert row["original_label_binding_record_id"] is None
    assert row["original_label_evidence_ids"]==[]
    assert row["documented_area_source_evidence_ids"]==[]
    assert row["documented_area_quantity_id"] is None
    c=fixture()
    c.room_area_quantity_evidence[0].metadata["source_sha256"]="b"*64
    row=one(c)
    assert row["original_label_binding_record_id"]=="label-source-1"
    assert row["original_label_evidence_ids"]==["native-observation-1"]
    assert row["documented_area_quantity_id"] is None
    assert row["documented_area_source_evidence_ids"]==[]


@pytest.mark.parametrize("ring", [
    ((0.0, 0.0), (2.0, 2.0), (0.0, 2.0), (2.0, 0.0)),
    ((0.0, 0.0), (2.0, 0.0), (1.0, 0.0), (0.0, 0.0)),
])
def test_original_source_self_intersecting_or_collapsed_face_cannot_handoff_area(ring):
    """A claimed positive area must not launder invalid source geometry."""
    source = fixture()
    physical = source.canonical_rooms[0]
    physical.polygon_pdf_pts = ring
    # Keep a plausible forged area and an allegedly complete original face.
    physical.area_page_pts2 = 2.0
    physical.geometry_complete = True
    # Match the supposed floor polygon so ancestry mismatch cannot hide
    # the original physical face's first failed authority.
    source.canonical_floors[0].polygon_pdf_pts = ring
    row = one(source)
    assert row["first_unproved_authority"] == (
        "SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE"
    )
    assert row["source_proven_area_m2"] is None
    assert row["documented_area_quantity_id"] is None
    assert row["floor_finish_publication_allowed"] is False
    assert row["ceiling_lining_publication_allowed"] is False


def test_valid_original_open_vertex_ring_retains_existing_source_metric_handoff():
    """A legitimate source ring need not repeat its initial closing vertex."""
    source = fixture()
    row = one(source)
    assert row["first_unproved_authority"] == (
        "SOURCE_ROOM_AREA_READY_FOR_GPT1_GPT3_REVIEW"
    )
    assert row["source_proven_area_m2"] == 1.5
    assert row["metric_area_inferred_from_page_points"] is False


def test_source_polygon_geos_exception_abstains_before_metric_claim(monkeypatch):
    """A GEOS failure cannot turn a suspect native ring into a measured floor."""
    import shapely.geometry
    from shapely.errors import GEOSException

    def invalid_native_ring(*_args, **_kwargs):
        raise GEOSException("original source polygon topology unavailable")

    monkeypatch.setattr(shapely.geometry, "Polygon", invalid_native_ring)
    result = one(fixture())
    assert result["first_unproved_authority"] == (
        "SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE"
    )
    assert result["documented_area_quantity_id"] is None
    assert result["floor_finish_publication_allowed"] is False
