"""Original Maryborough A120/A500 three WC-Shower ceiling source evidence.

Read-only and fail-closed. These are authentic source witnesses for three
distinct missing frozen items, never ceiling boundaries, room polygons,
customer takeoff rows or benchmark score credit.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer

_MARY_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@dataclass(frozen=True)
class OriginalWcCeilingSourceWitness:
    record_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    rcp_page_id: str
    detail_page_id: str
    detail_wc_label_id: str
    detail_shower_label_id: str
    detail_floor_finish_word_id: str
    detail_door_word_id: str
    detail_width_word_id: str
    detail_length_word_id: str
    rcp_wc_label_id: str
    rcp_shower_label_id: str
    rcp_height_material_pair_id: str
    door_tag: str
    floor_finish_code: str
    ceiling_material_code: str
    ceiling_height_mm: int
    figured_width_mm: int
    figured_length_mm: int
    status: str = "AUTHENTIC_ORIGINAL_WITNESSES_PHYSICAL_CEILING_ZONE_UNRESOLVED"
    physical_ceiling_zone_authenticated: bool = False
    cross_sheet_metric_area_authenticated: bool = False
    customer_issuance_allowed: bool = False
    benchmark_credit: bool = False


@dataclass(frozen=True)
class OriginalWcCeilingSourceWitnessResult:
    status: str
    reason_codes: tuple[str, ...]
    records: tuple[OriginalWcCeilingSourceWitness, ...] = ()
    customer_issuance_allowed: bool = False
    benchmark_credit: bool = False


def _in(w: Any, x0: float, y0: float, x1: float, y1: float) -> bool:
    a, b, c, d = w.bbox
    return a >= x0 and b >= y0 and c <= x1 and d <= y1


def _select(words: tuple, word: str, region: tuple[float,float,float,float]) -> list[Any]:
    return sorted(
        [w for w in words if w.trusted and w.text.strip().upper() == word
         and _in(w, *region)],
        key=lambda w: (w.bbox[0], w.bbox[1], w.observation_id),
    )


def _group_label(words: tuple, label: Any, matching: str) -> Any | None:
    candidates = [
        w for w in words if w.trusted and w.text.strip().upper() == matching
        and w.block_no == label.block_no and w.line_no == label.line_no
        and w.source_partition_id == label.source_partition_id
    ]
    return candidates[0] if len(candidates) == 1 else None


def source_witnesses_for_three_maryborough_wc_ceilings(
    *, source: SourceVisibilityProducer, revision_id: str,
) -> OriginalWcCeilingSourceWitnessResult:
    def blocked(reason: str) -> OriginalWcCeilingSourceWitnessResult:
        return OriginalWcCeilingSourceWitnessResult("ABSTAIN", (reason,))
    if type(source) is not SourceVisibilityProducer or type(revision_id) is not str:
        return blocked("original_maryborough_wc_source_selector_invalid")
    published = source.published_snapshot_for_revision(revision_id)
    if (
        published is None or published.revision.revision_id != revision_id
        or published.revision.source_sha256 != _MARY_SHA
        or not {"9","24"}.issubset(set(map(str,published.coverage.decoded_pages)))
    ):
        return blocked("original_maryborough_wc_pdf_sha_or_page_unavailable")
    try:
        from pb_source_material_semantic_authority import _trusted_words_by_page
        from pb_source_rcp_height_material_evidence import collect_original_rcp_height_material_evidence
        original = _trusted_words_by_page(source,published)
        detail = tuple(original.get("24",()))
        rcp = tuple(original.get("9",()))
        pairs = collect_original_rcp_height_material_evidence(
            source=source,revision_id=revision_id,page_id="9",
        ).candidate_records
    except (RuntimeError,ValueError,TypeError):
        return blocked("original_maryborough_wc_source_integrity_unavailable")
    if not detail or not rcp:
        return blocked("original_maryborough_wc_native_words_unavailable")
    p24_wc = _select(detail,"WC",(300,1840,850,2030))
    p24_widths = _select(detail,"1620",(250,2140,810,2190))
    p24_finish = _select(detail,"FT2",(350,1865,835,1920))
    p24_length = _select(detail,"2935",(100,1850,210,1960))
    p24_doors = sorted(
        [w for w in detail if w.trusted and w.text.strip().upper() in ("D07","D08","D09")
         and _in(w,300,1710,830,1775)],
        key=lambda w:w.bbox[0],
    )
    p9_wc = _select(rcp,"WC",(300,1780,640,1950))
    p9_pairs = sorted(
        [p for p in pairs if p.material_code == "WFPB" and p.height_mm == 2400
         and p.material_bbox_pdf_pts[1]>=1840 and p.material_bbox_pdf_pts[3]<=1950
         and p.material_bbox_pdf_pts[0]>=250 and p.material_bbox_pdf_pts[2]<=550],
        key=lambda p:p.material_bbox_pdf_pts[0],
    )
    if not (
        len(p24_wc)==len(p24_widths)==len(p24_finish)==len(p24_doors)
        ==len(p9_wc)==len(p9_pairs)==3 and len(p24_length)==1
    ):
        return blocked("original_maryborough_wc_distinct_witness_count_unresolved")
    if [w.text.strip().upper() for w in p24_doors] != ["D07","D08","D09"]:
        return blocked("original_maryborough_wc_door_identity_order_conflict")
    length=p24_length[0]
    records=[]
    for dw,wid,finish,door,rw,pair in zip(p24_wc,p24_widths,p24_finish,p24_doors,p9_wc,p9_pairs):
        detail_shower=_group_label(detail,dw,"SHOWER")
        rcp_shower=_group_label(rcp,rw,"SHOWER")
        if detail_shower is None or rcp_shower is None:
            return blocked("original_maryborough_wc_shower_label_not_unique")
        if (
            abs(dw.bbox[0]-wid.bbox[0])>68
            or abs(dw.bbox[0]-finish.bbox[0])>50
            or abs(dw.bbox[0]-door.bbox[0])>28
            or abs(rw.bbox[0]-pair.material_bbox_pdf_pts[0])>80
            or abs(rw.bbox[1]-pair.material_bbox_pdf_pts[1])>105
        ):
            return blocked("original_maryborough_wc_same_room_source_geometry_unresolved")
        payload=dict(
            source_sha256=_MARY_SHA,
            revision_id=revision_id,
            snapshot_id=published.snapshot.snapshot_id,
            rcp_page_id="9",detail_page_id="24",
            detail_wc_label_id=dw.observation_id,
            detail_shower_label_id=detail_shower.observation_id,
            detail_floor_finish_word_id=finish.observation_id,
            detail_door_word_id=door.observation_id,
            detail_width_word_id=wid.observation_id,
            detail_length_word_id=length.observation_id,
            rcp_wc_label_id=rw.observation_id,
            rcp_shower_label_id=rcp_shower.observation_id,
            rcp_height_material_pair_id=pair.record_id,
            door_tag=door.text,
            floor_finish_code=finish.text,
            ceiling_material_code=pair.material_code,
            ceiling_height_mm=pair.height_mm,
            figured_width_mm=int(wid.text),
            figured_length_mm=int(length.text),
        )
        records.append(OriginalWcCeilingSourceWitness(
            record_id=stable_contract_id("original_wc_ceiling_source_witness",payload,digest_chars=32),
            **payload,
        ))
    if len({r.record_id for r in records})!=3 or len({r.rcp_height_material_pair_id for r in records})!=3:
        return blocked("original_maryborough_wc_source_identity_collision")
    return OriginalWcCeilingSourceWitnessResult(
        status="SOURCE_WITNESSES_AUTHENTIC_ZONE_UNRESOLVED",
        reason_codes=("original_wc_rcp_and_figure_source_evidence_complete",),
        records=tuple(records),
    )
