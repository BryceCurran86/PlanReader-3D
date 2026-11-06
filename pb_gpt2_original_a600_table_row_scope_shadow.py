"""Source-owned architectural door TABLE row versus detail-code shadow.

A repeated Dxx word in another ORIGINAL drawing detail is not a duplicate
schedule row. Conversely two valid table rows with one printed code must
remain ambiguous. Whole-word source evidence is consumed from the already
published SourceVisibilityProducer; caller-curated boxes cannot produce a
positive source-owning receipt. No physical opening, count, units, m2,
customer output, or frozen benchmark authority is issued here.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
import re

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord,
    _DOOR_CODE,
    _DOOR_LIKE_TOKEN,
    _original_source_row_candidates,
    _producer_owned_native_words,
)
from pb_source_visibility_authority import SourceVisibilityProducer



@dataclass(frozen=True)
class SourceDoorTableCodeScopeShadow:
    code: str
    original_table_native_blocks: tuple[int, ...]
    original_other_native_blocks: tuple[int, ...]
    original_code_observation_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    first_unclosed_gate: str
    source_table_row_candidate_only: bool
    original_physical_door_identity_granted: bool = False
    source_dimension_units_granted: bool = False
    original_opening_count_granted: bool = False
    customer_projection_allowed: bool = False
    firm_quantity_issued: bool = False


@dataclass(frozen=True)
class OriginalDoorTableScopeShadow:
    source_sha256: str
    revision_id: str
    snapshot_id: str
    page_id: str
    source_title_observation_ids: tuple[str, ...]
    source_header_observation_ids: tuple[str, ...]
    source_table_geometry_candidate_only: bool
    all_original_code_native_blocks: tuple[int, ...]
    decisions: tuple[SourceDoorTableCodeScopeShadow, ...]
    shadow_only: bool = True
    physical_opening_issued: bool = False
    source_metric_opening_area_issued: bool = False
    commercial_projection_allowed: bool = False


def _bounded_source_words(words: tuple[SourceDoorScheduleWord, ...]) -> dict[int, tuple[SourceDoorScheduleWord, ...]]:
    if type(words) is not tuple or len(words)>25000:
        raise ValueError('complete original door source word universe required')
    blocks=defaultdict(list)
    addresses=set()
    observation_ids=set()
    page=None
    for word in words:
        if type(word) is not SourceDoorScheduleWord:
            raise ValueError('source observation must be a typed native door word')
        if not word.observation_id or word.observation_id in observation_ids:
            raise ValueError('duplicate original observation identifier')
        address=(word.page_id,word.block_no,word.line_no,word.word_no)
        if address in addresses:
            raise ValueError('duplicate original native word address')
        if (type(word.page_id) is not str or not word.page_id
                or word.partition_id!='page:'+word.page_id
                or any(type(v) is not int or v<0 for v in address[1:])
                or type(word.literal) is not str
                or type(word.bbox_pdf_pts) is not tuple
                or len(word.bbox_pdf_pts)!=4
                or any(type(v) not in (int,float) or not math.isfinite(v)
                       for v in word.bbox_pdf_pts)
                or word.bbox_pdf_pts[0]>=word.bbox_pdf_pts[2]
                or word.bbox_pdf_pts[1]>=word.bbox_pdf_pts[3]):
            raise ValueError('malformed or foreign native door word')
        if page is None:
            page=word.page_id
        elif page!=word.page_id:
            raise ValueError('mixed original source pages')
        observation_ids.add(word.observation_id)
        addresses.add(address)
        blocks[word.block_no].append(word)
    return {block:tuple(sorted(members,key=lambda w:(w.line_no,w.word_no)))
            for block,members in sorted(blocks.items())}


def _find_title_and_headers(blocks):
    def group_with_exact_fields(fields):
        return [members for members in blocks.values()
                if all(sum(w.literal==name for w in members)==1 for name in fields)]
    primary=group_with_exact_fields(('No.','ROOM','NAME','TYPE'))
    numerical=group_with_exact_fields(('WIDTH','HEIGHT','THICKNESS'))
    if len(primary)!=1 or len(numerical)!=1:
        return None
    first,numbers=primary[0],numerical[0]
    first_header=tuple(w for w in first if w.literal in ('No.','ROOM','NAME','TYPE'))
    numerical_header=tuple(w for w in numbers if w.literal in ('WIDTH','HEIGHT','THICKNESS'))
    if not all(w.trusted for w in (*first_header,*numerical_header)):
        return None
    first_left=min(w.bbox_pdf_pts[0] for w in first)
    first_right=max(w.bbox_pdf_pts[2] for w in first)
    num_left=min(w.bbox_pdf_pts[0] for w in numbers)
    num_right=max(w.bbox_pdf_pts[2] for w in numbers)
    if max(first_left,num_left)>=min(first_right,num_right):
        return None
    no=next(w for w in first_header if w.literal=='No.')
    width=next(w for w in numerical_header if w.literal=='WIDTH')
    height=next(w for w in numerical_header if w.literal=='HEIGHT')
    # The source has two separately printed column roles, not one number
    # that can occupy both height and width.
    if max(width.bbox_pdf_pts[1],height.bbox_pdf_pts[1])<min(
            width.bbox_pdf_pts[3],height.bbox_pdf_pts[3]):
        return None
    titles=[members for members in blocks.values()
            if tuple(w.literal for w in members)==('DOOR','SCHEDULE')
            and max(w.bbox_pdf_pts[2] for w in members)<min(first_left,num_left)]
    # A second ORIGINAL printed caption stays a rival even if its native
    # glyph/clip evidence is untrusted. Never count only the trusted subset.
    if len(titles)!=1 or not all(w.trusted for w in titles[0]):
        return None
    return (titles[0],(*first_header,*numerical_header),
            no,max(first_right,num_right))


def classify_original_door_table_row_scope_shadow(
    words: tuple[SourceDoorScheduleWord,...],
    *, source_sha256: str, revision_id: str, snapshot_id: str,
    page_id: str,
) -> OriginalDoorTableScopeShadow:
    """Pure, nonpublishing original-source row census for negative comparison."""
    if (type(source_sha256) is not str or not re.fullmatch(r'[0-9a-f]{64}',source_sha256)
            or any(type(v) is not str or not v for v in (revision_id,snapshot_id,page_id))
            or not page_id.isascii() or not page_id.isdecimal()
            or int(page_id)<1 or page_id!=str(int(page_id))):
        raise ValueError('exact source revision / page identity required')
    blocks=_bounded_source_words(words)
    if any(w.page_id != page_id for members in blocks.values() for w in members):
        raise ValueError('source words from foreign page')
    first_code_words={block:members[0] for block,members in blocks.items()
                      if members and _DOOR_LIKE_TOKEN.fullmatch(members[0].literal)
                      and members[0].line_no==0 and members[0].word_no==0}
    scopes=_find_title_and_headers(blocks)
    # Retain every native D-digit word, not just the first word in a block.
    # A NOTE followed by D99 inside the independently authenticated table
    # must block the complete schedule census. Foreign drawing details remain
    # observations, not additional schedule rows or physical openings.
    all_code_mentions=defaultdict(list)
    for block,members in blocks.items():
        for word in members:
            if _DOOR_LIKE_TOKEN.fullmatch(word.literal):
                all_code_mentions[word.literal].append(word)
    original_ordered_words=tuple(w for members in blocks.values() for w in members)
    parsed={(row.code,row.native_block_no):row
            for row in _original_source_row_candidates(original_ordered_words)}
    decisions=[]
    for code in sorted(all_code_mentions):
        table=[]
        outside=[]
        for word in all_code_mentions[code]:
            block=word.block_no
            # The existing foreign-detail block census intentionally counts
            # only block-leading codes; secondary foreign words are still
            # retained in original_code_observation_ids and cannot grant rows.
            block_leading=first_code_words.get(block) is word
            if scopes is None:
                if block_leading:
                    outside.append(block)
                continue
            _,_,no,header_right=scopes
            left,top,right,bottom=word.bbox_pdf_pts
            in_source_table=(left>header_right and
                min(bottom,no.bbox_pdf_pts[3])>max(top,no.bbox_pdf_pts[1]))
            if in_source_table:
                table.append(block)
            elif block_leading:
                outside.append(block)
        # Multiple D-like words in one block are separately audited below
        # by the schedule consumer, not two independently printed rows.
        table=sorted(set(table))
        outside=sorted(set(outside))
        if scopes is None:
            reason='original_schedule_header_or_caption_unproven'
        elif not table:
            reason='no_source_table_row_for_code'
        elif not _DOOR_CODE.fullmatch(code):
            reason='noncanonical_door_code_inside_printed_table'
        elif len(table)>1:
            reason='duplicate_original_schedule_table_rows'
        elif (code,table[0]) not in parsed:
            reason='unparsed_original_schedule_table_row'
        elif not first_code_words[table[0]].trusted:
            reason='original_schedule_row_code_glyph_untrusted'
        elif not parsed[(code,table[0])].complete_native_row_text_trusted:
            # The original row parser already records exact per-word glyph
            # trust. A source-visible code cannot launder an untrusted room,
            # type, thickness or numeric cell into an eligible table row.
            reason='original_schedule_row_semantic_words_untrusted'
        else:
            reason='original_source_row_scope_only_requires_physical_opening_and_dimensions'
        eligible=reason.startswith('original_source_row_scope_only')
        decisions.append(SourceDoorTableCodeScopeShadow(
            code=code,
            original_table_native_blocks=tuple(table),
            original_other_native_blocks=tuple(outside),
            original_code_observation_ids=tuple(
                w.observation_id for w in sorted(all_code_mentions[code],
                    key=lambda w:(w.block_no,w.line_no,w.word_no,w.observation_id))),
            status=EvidenceResolutionStatus.CANDIDATE if eligible
                else EvidenceResolutionStatus.ABSTAINED,
            first_unclosed_gate=reason,
            source_table_row_candidate_only=eligible,
        ))
    return OriginalDoorTableScopeShadow(
        source_sha256=source_sha256,revision_id=revision_id,
        snapshot_id=snapshot_id,page_id=page_id,
        source_title_observation_ids=tuple(w.observation_id for w in scopes[0]) if scopes else (),
        source_header_observation_ids=tuple(w.observation_id for w in scopes[1]) if scopes else (),
        source_table_geometry_candidate_only=scopes is not None,
        all_original_code_native_blocks=tuple(sorted(set(
            w.block_no for mentions in all_code_mentions.values() for w in mentions))),
        decisions=tuple(decisions),
    )


def audit_published_original_door_table_row_scope_shadow(
    producer: SourceVisibilityProducer, *, revision_id: str, page_id: str,
) -> OriginalDoorTableScopeShadow:
    """Only published, typed original source receipts can enter this adapter."""
    if type(producer) is not SourceVisibilityProducer:
        raise TypeError('original owner SourceVisibilityProducer required')
    if type(revision_id) is not str or not revision_id:
        raise ValueError('published source revision required')
    published=producer.published_snapshot_for_revision(revision_id)
    if published is None or published.revision.revision_id!=revision_id:
        raise ValueError('source revision is not published by this producer')
    if (type(page_id) is not str or not page_id.isascii()
            or not page_id.isdecimal() or int(page_id)<1
            or page_id!=str(int(page_id))):
        raise ValueError('canonical published source page required')
    if int(page_id) not in {int(x) for x in published.coverage.decoded_pages}:
        raise ValueError('source page outside published coverage')
    words=_producer_owned_native_words(producer,published,page_id)
    return classify_original_door_table_row_scope_shadow(
        words,source_sha256=published.revision.source_sha256,
        revision_id=published.revision.revision_id,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
    )
