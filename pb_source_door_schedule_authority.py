"""Source-owned original PDF door SCHEDULE row evidence; no opening quantities.

Use the existing SourceVisibilityProducer's complete, immutable published
text-observation universe. Never take caller-curated text, untrusted PDF words,
a nearest plan label or a default opening count as source row authority.

An authenticated schedule row can establish the PRINTED door specification;
it cannot establish a physical opening, host, frame axes, metric units or count.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, replace
import math
import re

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


_DOOR_CODE = re.compile(r"^D(?:0[1-9]|[1-9][0-9]*)$")
_NUMERIC = re.compile(r"^[1-9][0-9]*$")
_MAX_ORIGINAL_WORDS = 25000


@dataclass(frozen=True)
class SourceDoorScheduleWord:
    observation_id: str
    page_id: str
    partition_id: str
    block_no: int
    line_no: int
    word_no: int
    literal: str
    trusted: bool
    bbox_pdf_pts: tuple[float,float,float,float] = (0.,0.,0.,0.)


@dataclass(frozen=True)
class SourceDoorScheduleRow:
    code: str
    source_page_id: str
    native_block_no: int
    observation_ids: tuple[str, ...]
    original_width_literal: str | None
    original_height_literal: str | None
    door_kind_candidate: str
    source_title_observation_ids: tuple[str, ...]
    complete_native_row_text_trusted: bool
    status: str
    first_unclosed_gate: str
    original_width_header_id: str | None = None
    original_height_header_id: str | None = None
    original_width_word_id: str | None = None
    original_height_word_id: str | None = None
    original_body_schedule_title_ids: tuple[str,...] = ()
    source_dimension_column_roles_authenticated: bool = False
    width_height_metric_units_authenticated: bool = False
    physical_host_or_frame_authenticated: bool = False
    default_opening_count: int | None = None
    new_customer_quantity_authority: bool = False


@dataclass(frozen=True)
class SourceDoorScheduleResult:
    source_sha256: str
    revision_id: str
    snapshot_id: str
    page_id: str
    rows: tuple[SourceDoorScheduleRow, ...]
    all_original_source_codes: tuple[str, ...]
    title_source_trusted: bool
    complete_source_word_universe: bool
    new_opening_counts: int = 0
    new_opening_areas_m2: int = 0


def _producer_owned_native_words(
    producer: SourceVisibilityProducer, published, page_id: str,
) -> tuple[SourceDoorScheduleWord, ...]:
    original_ids = getattr(published, "text_observation_ids", ()) or ()
    if (
        type(original_ids) not in (list, tuple)
        or len(set(original_ids)) != len(original_ids)
        or len(original_ids) > _MAX_ORIGINAL_WORDS
    ):
        raise ValueError("source_door_complete_observation_universe_unavailable")
    authority = producer.text_integrity_authority()
    rows = []
    addresses = set()
    for observation_id in original_ids:
        if type(observation_id) is not str or not observation_id:
            raise ValueError("malformed_source_door_parent_observation")
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        resolved = authority.resolve_text(selector)
        receipt = resolved.receipt
        if receipt is None:
            raise ValueError("missing_source_door_text_integrity_receipt")
        if (
            receipt.parent_observation_id != observation_id
            or receipt.document_id != published.revision.document_id
            or receipt.revision_id != published.revision.revision_id
            or receipt.source_sha256 != published.revision.source_sha256
            or type(receipt.page_id) is not str
            or type(receipt.source_partition_id) is not str
            or type(receipt.raw_text) is not str
            or any(type(v) is not int or v < 0 for v in
                   (receipt.block_no, receipt.line_no, receipt.word_no))
        ):
            raise ValueError("foreign_or_incomplete_original_door_word")
        if receipt.page_id != page_id:
            continue
        if receipt.source_partition_id != "page:" + page_id:
            raise ValueError("original_door_word_partition_conflict")
        try:
            bbox=tuple(float(x) for x in receipt.geometry)
        except (TypeError, ValueError, OverflowError):
            raise ValueError("invalid_native_door_word_geometry") from None
        if (len(bbox)!=4 or any(not math.isfinite(x) for x in bbox)
                or bbox[0]>=bbox[2] or bbox[1]>=bbox[3]):
            raise ValueError("invalid_native_door_word_geometry")
        address=(receipt.block_no,receipt.line_no,receipt.word_no)
        if address in addresses:
            raise ValueError("duplicate_native_door_word_address")
        addresses.add(address)
        verified = (
            resolved.status is EvidenceResolutionStatus.CORROBORATED
            and resolved.trusted_text is not None
        )
        rows.append(SourceDoorScheduleWord(
            observation_id=observation_id,
            page_id=page_id,
            partition_id=receipt.source_partition_id,
            block_no=receipt.block_no,
            line_no=receipt.line_no,
            word_no=receipt.word_no,
            literal=str(resolved.trusted_text) if verified else receipt.raw_text,
            trusted=verified,
            bbox_pdf_pts=bbox,
        ))
    return tuple(sorted(rows,key=lambda w:(
        w.block_no,w.line_no,w.word_no,w.observation_id)))


def _native_door_kind(words: tuple[str, ...]) -> str:
    values=set(words)
    if {"AUTOMATED","SLIDING"}<=values: return "automated_sliding"
    if {"DISPLAY","SHELVING","DOOR"}<=values: return "manufacturer_display_shelving"
    if {"SLIDING","DOOR","COOLROOM"}<=values: return "coolroom_access_sliding"
    if {"PARTITION","SYSTEM","SWING"}<=values: return "partition_system_swing"
    if {"SOLID","CORE","SWING"}<=values: return "solid_core_swing"
    if {"ALUMINIUM","GLASS","DOOR"}<=values: return "glazed_access_candidate"
    if {"COOLROOM","CONTRACTOR"}<=values: return "coolroom_contractor_candidate"
    return "original_door_kind_unverified"


def _original_source_row_candidates(
    words: tuple[SourceDoorScheduleWord, ...],
) -> tuple[SourceDoorScheduleRow, ...]:
    grouped=defaultdict(list)
    for word in words:
        grouped[word.block_no].append(word)
    titles=[
        tuple(row) for row in grouped.values()
        if tuple(w.literal for w in row)==("DOOR","SCHEDULE")
    ]
    title_unique=len(titles)==1
    title_trusted=title_unique and all(w.trusted for w in titles[0])
    title_ids=tuple(w.observation_id for w in titles[0]) if title_unique else ()
    candidates=[]
    for block,source_words in sorted(grouped.items()):
        strings=tuple(w.literal for w in source_words)
        if not strings or not _DOOR_CODE.fullmatch(strings[0]):
            continue
        if "DOOR" not in strings and "SWING" not in strings:
            continue
        if sum(_DOOR_CODE.fullmatch(x) is not None for x in strings)!=1:
            continue
        start=strings.index("SWING")+1 if "SWING" in strings else 1
        numeric=[x for x in strings[start:] if _NUMERIC.fullmatch(x)]
        sizes=numeric[:2] if len(numeric)>=2 else []
        words_trusted=all(word.trusted for word in source_words)
        authenticated=bool(title_trusted and words_trusted)
        candidates.append(SourceDoorScheduleRow(
            code=strings[0],
            source_page_id=source_words[0].page_id,
            native_block_no=block,
            observation_ids=tuple(w.observation_id for w in source_words),
            original_width_literal=sizes[0] if sizes else None,
            original_height_literal=sizes[1] if sizes else None,
            door_kind_candidate=_native_door_kind(strings),
            source_title_observation_ids=title_ids,
            complete_native_row_text_trusted=words_trusted,
            status="source_schedule_row_text_authenticated" if authenticated
                   else "source_schedule_row_text_unverified",
            first_unclosed_gate=(
                "original_schedule_title_or_row_word_trust"
                if not authenticated else
                "source_dimension_units_and_unique_physical_opening_host"
            ),
        ))
    counts=defaultdict(int)
    for r in candidates: counts[r.code]+=1
    return tuple(
        SourceDoorScheduleRow(
            **{
                **r.__dict__,
                "status":"source_schedule_row_duplicate_code_conflict",
                "first_unclosed_gate":"duplicate_original_source_door_rows",
            }
        ) if counts[r.code]>1 else r
        for r in candidates
    )



def _original_door_schedule_column_proof(
    words: tuple[SourceDoorScheduleWord, ...],
    rows: tuple[SourceDoorScheduleRow, ...],
) -> tuple[tuple[SourceDoorScheduleRow, ...], bool]:
    """Distinguish original table title from repeated drawing title.

    An exact printed WIDTH/HEIGHT/THICKNESS native header block plus a
    distinct No./ROOM NAME/TYPE header column prove the real schedule
    table's source coordinate frame. The table's caption must be uniquely
    BEFORE the headers in the same original native axis as the rows.
    Actual numeric column ink must overlap its own header projection, not
    a different column or a nearer label. No plan host, metric unit, count
    or door size quantity is inferred.
    """
    by_block=defaultdict(list)
    for w in words:
        by_block[w.block_no].append(w)
    headers=[
        tuple(block) for block in by_block.values()
        if all(sum(w.literal==code for w in block)==1
               for code in ("WIDTH","HEIGHT","THICKNESS"))
    ]
    first_columns=[
        tuple(block) for block in by_block.values()
        if all(sum(w.literal==code for w in block)==1
               for code in ("No.","ROOM","NAME","TYPE"))
    ]
    captions=[
        tuple(block) for block in by_block.values()
        if tuple(w.literal for w in block)==("DOOR","SCHEDULE")
    ]
    if len(headers)!=1 or len(first_columns)!=1 or not rows:
        return rows,False
    header=headers[0]
    first=first_columns[0]
    if not all(w.trusted for w in header+first):
        # Header identity can remain a source candidate but not source-
        # authenticated row authority when original PDF text is untrusted.
        headers_trusted=False
    else:
        headers_trusted=True
    width=next(w for w in header if w.literal=="WIDTH")
    height=next(w for w in header if w.literal=="HEIGHT")
    header_x=min(w.bbox_pdf_pts[0] for w in header)
    head_right=max(w.bbox_pdf_pts[2] for w in header)
    first_x=min(w.bbox_pdf_pts[0] for w in first)
    first_right=max(w.bbox_pdf_pts[2] for w in first)
    # Both source-native header groups must occupy the SAME original
    # table-header x band; no nearest-caption or expected sheet position.
    same_header_band = (
        max(header_x,first_x) < min(head_right,first_right)
    )
    candidates=[
        title for title in captions
        if max(w.bbox_pdf_pts[2] for w in title)
           < min(header_x,first_x)
    ]
    if len(candidates)!=1 or not same_header_band:
        return rows,False
    caption=candidates[0]
    title_ids=tuple(w.observation_id for w in caption)
    table_trusted=(
        headers_trusted and all(w.trusted for w in caption)
    )
    new=[]
    for row in rows:
        members=by_block.get(row.native_block_no,())
        if not members:
            new.append(row)
            continue
        row_x=min(w.bbox_pdf_pts[0] for w in members)
        row_in_table=row_x>max(head_right,first_right)
        if not row_in_table:
            new.append(replace(row,
                status="source_schedule_row_table_scope_conflict",
                first_unclosed_gate="original_source_table_column_scope",
            ))
            continue
        matched={}
        for key,literal,column in (
            ("width",row.original_width_literal,width),
            ("height",row.original_height_literal,height),
        ):
            if literal is None:
                continue
            # Column source words must have exact original literal,
            # same original native table block, downstream x, and a
            # strictly positive projection onto their own HEADER band.
            rivals=[
                word for word in members
                if word.literal==literal
                and word.bbox_pdf_pts[0]>column.bbox_pdf_pts[2]
                and min(word.bbox_pdf_pts[3],column.bbox_pdf_pts[3])
                    > max(word.bbox_pdf_pts[1],column.bbox_pdf_pts[1])
            ]
            if len(rivals)==1:
                matched[key]=rivals[0]
        both_printed=(row.original_width_literal is not None and
                      row.original_height_literal is not None)
        geometry_verified=(both_printed and
                           "width" in matched and "height" in matched and
                           matched["width"].observation_id!=matched["height"].observation_id)
        accepted_row=table_trusted and row.complete_native_row_text_trusted
        first_gate=(
            "original_schedule_title_or_row_word_trust"
            if not accepted_row else
            "source_numeric_columns_unresolved"
            if both_printed and not geometry_verified else
            "source_dimensions_not_printed_or_unique_physical_host"
            if not both_printed else
            "source_dimension_units_and_unique_physical_opening_host"
        )
        new.append(replace(
            row,
            original_body_schedule_title_ids=title_ids,
            source_title_observation_ids=title_ids,
            original_width_header_id=width.observation_id,
            original_height_header_id=height.observation_id,
            original_width_word_id=(
                matched["width"].observation_id if "width" in matched else None
            ),
            original_height_word_id=(
                matched["height"].observation_id if "height" in matched else None
            ),
            source_dimension_column_roles_authenticated=bool(
                table_trusted and row.complete_native_row_text_trusted
                and geometry_verified
            ),
            status=(
                "source_schedule_row_text_authenticated" if accepted_row
                else "source_schedule_row_text_unverified"
            ) if row.status!="source_schedule_row_duplicate_code_conflict"
            else row.status,
            first_unclosed_gate=(
                row.first_unclosed_gate if row.status==
                "source_schedule_row_duplicate_code_conflict"
                else first_gate
            ),
        ))
    return tuple(new),table_trusted

def inspect_published_door_schedule(
    producer: SourceVisibilityProducer, *,
    revision_id: str, page_id: str,
) -> SourceDoorScheduleResult:
    if type(producer) is not SourceVisibilityProducer:
        raise TypeError("door_source_requires_existing_visibility_producer")
    if (type(revision_id) is not str or not revision_id
            or type(page_id) is not str or not page_id.isdecimal()
            or int(page_id)<1):
        raise ValueError("exact_door_source_revision_and_page_required")
    published=producer.published_snapshot_for_revision(revision_id)
    if published is None:
        raise ValueError("source_door_revision_not_producer_owned")
    if int(page_id) not in {int(x) for x in published.coverage.decoded_pages}:
        raise ValueError("source_door_page_not_in_published_source_coverage")
    words=_producer_owned_native_words(producer,published,page_id)
    rows,title_ok=_original_door_schedule_column_proof(
        words,_original_source_row_candidates(words),
    )
    return SourceDoorScheduleResult(
        source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        rows=rows,
        all_original_source_codes=tuple(sorted({r.code for r in rows})),
        title_source_trusted=title_ok,
        complete_source_word_universe=True,
    )
