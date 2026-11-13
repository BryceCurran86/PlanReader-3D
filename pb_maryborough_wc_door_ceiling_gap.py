"""Original Maryborough WC/Shower schedule → RCP ceiling-height correspondence.

This is ORIGINAL PlanReader source evidence for the D07/D08/D09 opening
height, not a wall-head assertion and NOT commercial quantity authority.
The original PDF SHA, native text integrity, original source text block
membership, and canonical source revision are all mandatory.
"""
from __future__ import annotations

from dataclasses import dataclass

from pb_migration_contracts import stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_maryborough_wc_ceiling_source_witness import (
    source_witnesses_for_three_maryborough_wc_ceilings,
)


@dataclass(frozen=True)
class OriginalWcDoorCeilingGap:
    record_id: str
    door_tag: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    door_schedule_page_id: str
    physical_ceiling_source_witness_id: str
    schedule_door_tag_observation_id: str
    schedule_room_label_observation_ids: tuple[str, ...]
    schedule_swing_observation_ids: tuple[str, ...]
    schedule_leaf_width_observation_id: str
    schedule_leaf_height_observation_id: str
    door_leaf_width_mm: int
    door_leaf_height_mm: int
    ceiling_height_mm: int
    leaf_height_to_ceiling_difference_mm: int
    status: str = "SOURCE_DOOR_HEIGHT_BELOW_CEILING_HEADER_NOT_AUTHENTICATED"
    source_ceil_wall_header_authenticated: bool = False
    physical_ceiling_perimeter_authenticated: bool = False
    customer_quantity_allowed: bool = False
    benchmark_credit: bool = False


@dataclass(frozen=True)
class OriginalWcDoorCeilingGapResult:
    status: str
    reason_codes: tuple[str, ...]
    records: tuple[OriginalWcDoorCeilingGap, ...] = ()
    customer_quantity_allowed: bool = False
    benchmark_credit: bool = False


def _exact_group(rows: tuple, *, block_no: int, line_no: int, expected: tuple[str,...]):
    hits = [
        x for x in rows
        if x.trusted and x.block_no == block_no and x.line_no == line_no
    ]
    hits.sort(key=lambda x:x.word_no)
    return hits if tuple(x.text.strip().upper() for x in hits) == expected else None


def authenticate_original_maryborough_wc_door_ceiling_gaps(
    *, source: SourceVisibilityProducer, revision_id: str,
) -> OriginalWcDoorCeilingGapResult:
    def blocked(reason: str) -> OriginalWcDoorCeilingGapResult:
        return OriginalWcDoorCeilingGapResult("ABSTAIN",(reason,))
    if type(source) is not SourceVisibilityProducer or type(revision_id) is not str:
        return blocked("original_wc_door_schedule_selector_invalid")
    original = source_witnesses_for_three_maryborough_wc_ceilings(
        source=source,revision_id=revision_id,
    )
    if original.status != "SOURCE_WITNESSES_AUTHENTIC_ZONE_UNRESOLVED" or len(original.records)!=3:
        return blocked("original_wc_door_scheduled_ceiling_source_unavailable")
    published=source.published_snapshot_for_revision(revision_id)
    if published is None or published.revision.revision_id!=revision_id:
        return blocked("original_wc_door_schedule_revision_unavailable")
    if "28" not in set(map(str,published.coverage.decoded_pages)):
        return blocked("original_wc_door_schedule_page_unavailable")
    try:
        from pb_source_material_semantic_authority import _trusted_words_by_page
        rows=tuple(_trusted_words_by_page(source,published).get("28",()))
    except (TypeError,ValueError,RuntimeError):
        return blocked("original_wc_door_schedule_native_text_untrusted")
    if not rows:return blocked("original_wc_door_schedule_native_text_untrusted")
    output=[]
    used_blocks=set()
    for ceiling in original.records:
        matches=[w for w in rows if w.trusted and w.text.strip().upper()==ceiling.door_tag
                 and w.line_no==0 and w.word_no==0]
        if len(matches)!=1:
            return blocked("original_wc_door_schedule_tag_not_unique")
        tag=matches[0]
        if tag.block_no in used_blocks:
            return blocked("original_wc_door_schedule_block_reused")
        used_blocks.add(tag.block_no)
        room=_exact_group(rows,block_no=tag.block_no,line_no=1,
                          expected=("WC","&","SHOWER","SINGLE","SWING"))
        width=_exact_group(rows,block_no=tag.block_no,line_no=2,expected=("920",))
        height=_exact_group(rows,block_no=tag.block_no,line_no=3,expected=("2040",))
        if room is None or width is None or height is None:
            return blocked("original_wc_door_schedule_row_details_untrusted")
        door_height=int(height[0].text)
        ceiling_height=ceiling.ceiling_height_mm
        if door_height<=0 or door_height>=ceiling_height:
            return blocked("original_wc_door_too_high_for_ceiling_header_candidate")
        payload=dict(
            door_tag=ceiling.door_tag,
            source_sha256=ceiling.source_sha256,
            revision_id=revision_id,
            snapshot_id=published.snapshot.snapshot_id,
            door_schedule_page_id="28",
            physical_ceiling_source_witness_id=ceiling.record_id,
            schedule_door_tag_observation_id=tag.observation_id,
            schedule_room_label_observation_ids=tuple(w.observation_id for w in room[:3]),
            schedule_swing_observation_ids=tuple(w.observation_id for w in room[3:]),
            schedule_leaf_width_observation_id=width[0].observation_id,
            schedule_leaf_height_observation_id=height[0].observation_id,
            door_leaf_width_mm=int(width[0].text),
            door_leaf_height_mm=door_height,
            ceiling_height_mm=ceiling_height,
            leaf_height_to_ceiling_difference_mm=ceiling_height-door_height,
        )
        output.append(OriginalWcDoorCeilingGap(
            record_id=stable_contract_id("original_wc_door_ceiling_gap_source",payload,digest_chars=32),
            **payload,
        ))
    if len({x.door_tag for x in output})!=3 or len({x.record_id for x in output})!=3:
        return blocked("original_wc_door_schedule_identity_collision")
    return OriginalWcDoorCeilingGapResult(
        "SOURCE_SCHEDULED_DOOR_HEIGHT_BELOW_RCP_HEADER_UNPROVEN",
        ("original_d07_d09_door_schedule_source_correspondence_complete",),
        records=tuple(output),
    )
