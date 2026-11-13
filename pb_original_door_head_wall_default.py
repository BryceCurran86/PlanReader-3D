"""Owner's wall-above-frame rule for original source schedule doors.

An explicit, default-off policy assessment. The source producer re-resolves
every row and optional RCP selector; no caller-supplied frame number, row,
height receipt or exception string is accepted. It never measures a wall.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_door_schedule_authority import (
    SourceDoorScheduleResult, SourceDoorScheduleWord,
    _producer_owned_native_words, inspect_published_door_schedule,
)
from pb_source_rcp_height_material_evidence import (
    SourceRcpHeightMaterialCandidate, collect_original_rcp_height_material_evidence,
)
from pb_source_visibility_authority import SourceVisibilityProducer

_EXCEPTION_PHRASES = (
    ("NO", "WALL", "ABOVE"),
    ("OPEN", "TO", "CEILING"),
    ("FULL", "HEIGHT"),
    ("OPEN", "TRANSOM"),
    ("GLAZED", "TRANSOM"),
    ("PARTITION", "STOPS", "BELOW", "CEILING"),
)
_DOOR_CODE = re.compile(r"D(?:0[1-9]|[1-9][0-9]*)")


@dataclass(frozen=True)
class OriginalDoorHeadWallDefault:
    record_id: str
    document_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    schedule_page_id: str
    door_code: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schedule_height_word_id: str | None
    schedule_leaf_height_literal: str | None
    ceiling_height_pair_id: str | None
    selected_ceiling_height_mm: int | None
    exception_source_ids: tuple[str, ...] = ()
    wall_above_frame_presumed: bool = False
    door_opening_remains_open_below_frame: bool = True
    # A schedule leaf, a selected RCP word, or an owner presumption cannot
    # supply the actual frame top or a measured wall height/area.
    frame_top_mm: None = None
    wall_above_frame_mm: None = None
    room_ceiling_binding_authenticated: bool = False
    physical_host_authenticated: bool = False
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    benchmark_credit: bool = False


def _exception_words(row, words: tuple[SourceDoorScheduleWord, ...]) -> tuple[str, ...] | None:
    """Only a trusted, door-specific native schedule row can supply a note."""
    owned = [w for w in words if w.observation_id in row.observation_ids]
    if not owned or len(owned) != len(row.observation_ids):
        return None
    if any(not w.trusted or w.block_no != row.native_block_no
           or w.page_id != row.source_page_id or w.partition_id != "page:" + row.source_page_id
           for w in owned):
        return None
    owned.sort(key=lambda w: (w.line_no, w.word_no, w.observation_id))
    tokens = [(token, w.observation_id) for w in owned
              for token in w.literal.upper().split()]
    if {text for text, _ in tokens if _DOOR_CODE.fullmatch(text)} != {row.code}:
        return None
    found = set()
    texts = tuple(text for text, _ in tokens)
    for phrase in _EXCEPTION_PHRASES:
        for start in range(len(texts) - len(phrase) + 1):
            if texts[start:start + len(phrase)] == phrase:
                found.update(obs for _, obs in tokens[start:start + len(phrase)])
    return tuple(sorted(found))


def _assess_source_row(
    *, document_id: str, schedule: SourceDoorScheduleResult, door_code: str,
    words: tuple[SourceDoorScheduleWord, ...],
    selected_pair: SourceRcpHeightMaterialCandidate | None = None,
    pair_requested: bool = False,
) -> OriginalDoorHeadWallDefault:
    """Private policy step; public entry always obtains all inputs from source."""
    rows = [r for r in schedule.rows if r.code == door_code]
    row = rows[0] if len(rows) == 1 else None
    literal = row.original_height_literal if row is not None else None
    trusted = (
        row is not None and schedule.title_source_trusted
        and door_code in schedule.all_original_source_codes
        and door_code not in schedule.unparsed_original_door_codes
        and row.status == "source_schedule_row_text_authenticated"
        and row.complete_native_row_text_trusted
        and row.source_dimension_column_roles_authenticated
        and row.original_height_word_id
        and type(literal) is str and literal.isascii() and literal.isdecimal()
        and int(literal) > 0
        and row.door_kind_candidate != "manufacturer_display_shelving"
    )
    status = EvidenceResolutionStatus.ABSTAINED
    reasons = ("original_door_schedule_source_untrusted_or_ambiguous",)
    presumed = False
    exceptions = ()
    pair_ok = (
        type(selected_pair) is SourceRcpHeightMaterialCandidate
        and selected_pair.document_id == document_id
        and selected_pair.source_sha256 == schedule.source_sha256
        and selected_pair.revision_id == schedule.revision_id
        and selected_pair.snapshot_id == schedule.snapshot_id
    )
    if trusted:
        # Complete row text is already re-proved by the original producer.
        exceptions = _exception_words(row, words)
        if exceptions is None:
            reasons = ("original_door_schedule_row_word_scope_unresolved",)
            exceptions = ()
        elif pair_requested and not pair_ok:
            reasons = ("original_door_rcp_selector_missing_or_foreign",)
        elif exceptions:
            status = EvidenceResolutionStatus.CANDIDATE
            reasons = ("original_door_head_source_exception_requires_physical_review",)
        elif pair_ok and int(literal) >= selected_pair.height_mm:
            # Even equality does not prove a full-height FRAME: the selector
            # is not yet independently bound to the physical door/room.
            reasons = ("original_door_leaf_and_selected_ceiling_require_physical_review",)
        else:
            status = EvidenceResolutionStatus.CANDIDATE
            presumed = True
            reasons = ("owner_wall_above_frame_presumption", "exact_frame_top_unresolved")
            if not pair_ok:
                reasons += ("door_ceiling_height_unresolved",)
    payload = dict(
        document_id=document_id, source_sha256=schedule.source_sha256,
        revision_id=schedule.revision_id, snapshot_id=schedule.snapshot_id,
        schedule_page_id=schedule.page_id, door_code=door_code,
        schedule_height_word_id=row.original_height_word_id if trusted else None,
        schedule_leaf_height_literal=literal if trusted else None,
        ceiling_height_pair_id=selected_pair.record_id if pair_ok else None,
        selected_ceiling_height_mm=selected_pair.height_mm if pair_ok else None,
        exception_source_ids=exceptions, wall_above_frame_presumed=presumed,
        status=status, reason_codes=reasons,
    )
    return OriginalDoorHeadWallDefault(
        record_id=stable_contract_id("original_door_head_policy", payload, digest_chars=32),
        **payload,
    )


def collect_original_door_head_wall_defaults(
    *, source: SourceVisibilityProducer, revision_id: str, schedule_page_id: str,
    ceiling_page_ids: tuple[str, ...] = (),
    ceiling_pair_ids_by_door: Mapping[str, str] | None = None,
    enabled: bool = False,
) -> tuple[OriginalDoorHeadWallDefault, ...]:
    """Apply one owner policy to the producer's complete door-code census.

    RCP IDs are selectors, never caller-owned evidence or proof of room
    correspondence. Unknown, unparsed and duplicate source rows remain explicit.
    Source notes outside the schedule still require physical exception review.
    """
    if type(enabled) is not bool:
        raise TypeError("original_door_head_enabled_requires_bool")
    if not enabled:
        return ()
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("original_door_head_requires_source_producer")
    if type(ceiling_page_ids) is not tuple:
        raise ValueError("original_door_head_rcp_pages_invalid")
    if any(type(p) is not str or not p.isascii() or not p.isdecimal()
           or int(p) < 1 or p != str(int(p)) for p in ceiling_page_ids):
        raise ValueError("original_door_head_rcp_pages_invalid")
    if len(set(ceiling_page_ids)) != len(ceiling_page_ids):
        raise ValueError("original_door_head_rcp_pages_invalid")
    if ceiling_pair_ids_by_door is not None and not isinstance(ceiling_pair_ids_by_door, Mapping):
        raise TypeError("original_door_head_rcp_selectors_invalid")
    selectors = dict(ceiling_pair_ids_by_door or {})
    if any(type(k) is not str or not k or type(v) is not str or not v
           for k, v in selectors.items()):
        raise ValueError("original_door_head_rcp_selectors_invalid")
    schedule = inspect_published_door_schedule(
        source, revision_id=revision_id, page_id=schedule_page_id,
    )
    published = source.published_snapshot_for_revision(revision_id)
    codes = set(schedule.all_original_source_codes) | {r.code for r in schedule.rows}
    if set(selectors) - codes:
        raise ValueError("original_door_head_unknown_schedule_code")
    words = _producer_owned_native_words(source, published, schedule_page_id)
    pairs = {}
    for page_id in ceiling_page_ids:
        result = collect_original_rcp_height_material_evidence(
            source=source, revision_id=revision_id, page_id=page_id,
        )
        for pair in result.candidate_records:
            if pair.record_id in pairs:
                raise ValueError("original_door_head_duplicate_rcp_source_receipt")
            pairs[pair.record_id] = pair
    return tuple(
        _assess_source_row(
            document_id=published.revision.document_id, schedule=schedule,
            door_code=code, words=words, selected_pair=pairs.get(selectors.get(code)),
            pair_requested=code in selectors,
        )
        for code in sorted(codes)
    )
