"""One-face W4 gross lining candidate consumes issued documented wall heights."""
from dataclasses import replace
import math

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus as Status, QuantityEvidence
from pb_wall_height_authority import WALL_HEIGHT_FORMULA_VERSION
from pb_gpt1_producer_sealed_w4_metric_floor_shadow import (
    bind_producer_sealed_w4_metric_floor_shadow,
)
from pb_gpt1_source_sealed_w4_gross_wall_lining_shadow import (
    measure_source_sealed_w4_wall_gross_lining_shadow,
)
from test_gpt1_producer_sealed_w4_metric_floor_shadow import (
    _actual_synthetic_producer,_metric_candidate,
)


def source_room_with_metric_walls():
    rooms,floors=_actual_synthetic_producer()
    room=rooms.rooms[0]
    produced=bind_producer_sealed_w4_metric_floor_shadow(
        rooms,floors,_metric_candidate(room),
        physical_room_id=room.physical_room_id,
    )
    assert produced.status is Status.CANDIDATE
    return produced


def documented_wall_heights(source,meters=3.0):
    return tuple(QuantityEvidence(
        quantity_id=f"height-issuer-{wall}",
        family="wall_height",semantic_key=f"wall_height:{wall}",
        value=meters,unit="m",input_entity_ids=(wall,),
        formula="authoritative_explicit_wall_height",
        formula_version=WALL_HEIGHT_FORMULA_VERSION,
        evidence_ids=(f"original-height-source-{wall}",),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,confidence=1.,abstained=False,
        metadata={
            "source_sha256":source.source_sha256,
            "revision_id":source.revision_id,
            "target_entity_id":wall,
            "page_id":source.page_id,
            "viewport_id":"original-source-plan-viewport",
            "evidence_snapshot_id":"signed-evidence-snapshot",
            "evidence_kind":"wall_height_dimension",
        },
    ) for wall,_ in source.candidate_wall_length_m_by_w4_id)


def test_documented_per_wall_heights_yield_one_face_gross_area_only():
    source=source_room_with_metric_walls()
    heights=documented_wall_heights(source)
    result=measure_source_sealed_w4_wall_gross_lining_shadow(source,heights)
    assert result.status is Status.CANDIDATE
    assert set(w for w,_ in result.per_w4_wall_gross_area_m2)==set(
        source.original_source_face_boundary_wall_ids)
    assert math.isclose(result.total_single_face_gross_area_m2,12.,abs_tol=1e-9)
    assert all(value>0 for _,value in result.per_w4_wall_gross_area_m2)
    assert result.original_wall_height_quantity_ids
    assert result.diagnostic_only and not hasattr(result,"quantity_id")


def test_wall_height_missing_never_creates_default_room_height():
    source=source_room_with_metric_walls()
    full=documented_wall_heights(source)
    result=measure_source_sealed_w4_wall_gross_lining_shadow(source,full[:-1])
    assert result.status is Status.ABSTAINED
    assert result.total_single_face_gross_area_m2 is None
    assert result.reason_codes==("original_w4_wall_height_universe_incomplete",)


def test_reusing_one_wall_height_record_for_two_w4_walls_is_not_valid():
    source=source_room_with_metric_walls()
    full=documented_wall_heights(source)
    result=measure_source_sealed_w4_wall_gross_lining_shadow(
        source,(*full,full[0])
    )
    assert result.status is Status.ABSTAINED
    assert result.reason_codes==("original_w4_wall_height_duplicate_identity",)


def test_only_existing_explicit_documented_wall_height_semantics_are_accepted():
    source=source_room_with_metric_walls()
    originals=documented_wall_heights(source)
    for changed in (
        replace(originals[0],value=0.),
        replace(originals[0],status=AuthorityStatus.PROVISIONAL.value),
        replace(originals[0],family="room_height"),
        replace(originals[0],formula="datum_pair_not_proven"),
        replace(originals[0],metadata={
            **originals[0].metadata,"source_sha256":"f"*64,
        }),
        replace(originals[0],metadata={
            **originals[0].metadata,"evidence_kind":"room_height_dimension",
        }),
    ):
        out=measure_source_sealed_w4_wall_gross_lining_shadow(
            source,(changed,*originals[1:])
        )
        assert out.status is Status.ABSTAINED
        assert out.per_w4_wall_gross_area_m2 == ()


def test_distinct_original_height_values_produce_distinct_wall_face_areas():
    source=source_room_with_metric_walls()
    heights=list(documented_wall_heights(source))
    heights[0]=replace(heights[0],value=4.)
    out=measure_source_sealed_w4_wall_gross_lining_shadow(source,tuple(heights))
    assert out.status is Status.CANDIDATE
    lengths=dict(source.candidate_wall_length_m_by_w4_id)
    expected=math.fsum(
        (4. if i==0 else 3.)*lengths[height.input_entity_ids[0]]
        for i,height in enumerate(heights)
    )
    assert math.isclose(out.total_single_face_gross_area_m2,expected,abs_tol=1e-9)
