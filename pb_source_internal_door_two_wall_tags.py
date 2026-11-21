"""Review-only adapter: source-native internal door marks -> the owner's TWO traced wall section tags.

Owner rule (hub 7056071002 / 7056082708, AGENTS.md): every detected opening is tagged with the TWO traced wall
sections that terminate at it, never one elected host. ``pb_opening_two_wall_contact_tags`` owns that vocabulary and its
matching rule; ``pb_source_door_wall_end_sections`` turns native wall-end paths into that contract's inputs for any
drawing convention. This module is the front end for the strict internal door inventory: every hinged swing and
cavity-slider mark it reports, with its two native wall-end host paths and its jamb returns.

Each mark's jamb returns anchor the contact; the two host paths are the wall ends. The mark's own evidence is read
from the native rows it names, never re-detected. A mark that is not hosted, or whose wall ends fail any named gate in
the core, stays UNRESOLVED with that reason, and every mark in the inventory appears exactly once in the output.

A tag is topology only. It does not authenticate a physical wall, a host, a frame, a kind, a width, a height or any
quantity (all flags are False by construction) and adds no geometric measurement authority: a gap between two wall
ends is never a width. Hosting by the inventory still needs a recognised internal-wall layer name, so a drawing without
one yields no mark and therefore no tag here (the limit is made visible, not hidden).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import stable_contract_id
from pb_opening_two_wall_contact_tags import (
    TwoWallOpeningTag,
    tag_opening_to_two_wall_sections,
)
from pb_source_door_wall_end_sections import (  # noqa: F401  (re-exported gate names)
    GATE_ANCHOR_MISSING,
    GATE_ANCHORS_DISAGREE,
    GATE_END_EDGE_MISSING,
    GATE_ENDS_NOT_OPPOSED,
    GATE_NOT_COLLINEAR,
    GATE_OPENING_PATHS_MISSING,
    GATE_ROW_UNREADABLE,
    Blocked,
    WallEndReceipt,
    build_contract_inputs,
    row_rect,
    scope_ok,
)
from pb_source_internal_door_completeness_shadow import (
    SourceInternalDoorMark,
    inspect_source_internal_door_completeness,
)

INTERNAL_DOOR_TWO_WALL_TAGS_SCHEMA_VERSION = "1.0.0"
INTERNAL_DOOR_TWO_WALL_TAGS_STATUS = "INTERNAL_DOOR_TWO_WALL_TAGS_REVIEW_ONLY"
INTERNAL_DOOR_TWO_WALL_TAGS_ABSTAINED = "ABSTAINED"

SYMBOL_HINGED_SWING = "hinged_swing"
SYMBOL_CAVITY_SLIDER = "cavity_slider"

TAG_TAGGED = "TWO_WALL_SECTIONS_TAGGED"
TAG_UNRESOLVED = "UNRESOLVED"

REASON_SCOPE_INVALID = "scope_invalid"
GATE_MARK_NOT_HOSTED = "mark_has_no_two_native_host_paths"

# The next authority a topology tag cannot supply by itself.
NEXT_AUTHORITY = "physical_host_frame_kind_and_metric_authority_required"

_AUTHORITY_FLAGS = (
    "physical_wall_authenticated", "physical_host_authorized", "physical_opening_authenticated",
    "kind_authorized", "measurement_authorized", "customer_quantity_authorized",
    "frozen_benchmark_scored",
)


@dataclass(frozen=True)
class InternalDoorTwoWallEntry:
    entry_id: str
    symbol_kind: str
    mark_status: str
    mark_native_path_ids: tuple[int, ...]
    host_native_path_ids: tuple[int, ...]
    tag_status: str
    reason: str
    wall_section_ids: tuple[str, ...]
    contact_geometry: str
    candidate_sections_first: tuple[str, ...]
    candidate_sections_second: tuple[str, ...]
    next_authority: str = NEXT_AUTHORITY
    physical_wall_authenticated: bool = False
    physical_host_authorized: bool = False
    physical_opening_authenticated: bool = False
    kind_authorized: bool = False
    measurement_authorized: bool = False
    customer_quantity_authorized: bool = False
    frozen_benchmark_scored: bool = False

    def __post_init__(self) -> None:
        for name in _AUTHORITY_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError("internal_door_two_wall_entry_cannot_carry_authority")

    @property
    def tagged(self) -> bool:
        return self.tag_status == TAG_TAGGED

    def to_dict(self) -> dict[str, object]:
        return {
            "entry_id": self.entry_id,
            "symbol_kind": self.symbol_kind,
            "mark_status": self.mark_status,
            "mark_native_path_ids": list(self.mark_native_path_ids),
            "host_native_path_ids": list(self.host_native_path_ids),
            "tag_status": self.tag_status,
            "reason": self.reason,
            "wall_section_ids": list(self.wall_section_ids),
            "contact_geometry": self.contact_geometry,
            "candidate_sections_first": list(self.candidate_sections_first),
            "candidate_sections_second": list(self.candidate_sections_second),
            "next_authority": self.next_authority,
            **{name: False for name in _AUTHORITY_FLAGS},
        }


@dataclass(frozen=True)
class InternalDoorTwoWallReview:
    status: str
    reason_codes: tuple[str, ...]
    scope: tuple[str, ...]
    page_index: int
    entries: tuple[InternalDoorTwoWallEntry, ...]
    physical_wall_authenticated: bool = False
    physical_host_authorized: bool = False
    physical_opening_authenticated: bool = False
    kind_authorized: bool = False
    measurement_authorized: bool = False
    customer_quantity_authorized: bool = False
    frozen_benchmark_scored: bool = False
    schema_version: str = INTERNAL_DOOR_TWO_WALL_TAGS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in _AUTHORITY_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError("internal_door_two_wall_review_cannot_carry_authority")

    def to_public_summary(self) -> dict[str, object]:
        """Counts only; no path ids, coordinates or drawing content."""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "marks": len(self.entries),
            "tagged": sum(e.tagged for e in self.entries),
            "unresolved": sum(not e.tagged for e in self.entries),
            "by_symbol_kind": dict(sorted(Counter(e.symbol_kind for e in self.entries).items())),
            "by_reason": dict(sorted(Counter(e.reason for e in self.entries).items())),
            "by_contact_geometry": dict(
                sorted(Counter(e.contact_geometry for e in self.entries).items())
            ),
            **{name: False for name in _AUTHORITY_FLAGS},
        }


def _symbol_kind(mark: SourceInternalDoorMark) -> str:
    return SYMBOL_CAVITY_SLIDER if mark.kind == "native_cavity_slider_callout" else SYMBOL_HINGED_SWING


def _receipt(
    drawings: Sequence[Any], mark: SourceInternalDoorMark, *, scope: tuple[str, ...], opening_id: str,
) -> WallEndReceipt | Blocked:
    hosts = tuple(mark.host_wall_native_path_ids)
    if (
        mark.status != "HOSTED_TOPOLOGY_ONLY" or len(hosts) != 2 or hosts[0] == hosts[1]
        or any(type(h) is not int or h < 0 or h >= len(drawings) for h in hosts)
    ):
        return Blocked(GATE_MARK_NOT_HOSTED)
    anchors = tuple(
        rect for rect in (
            row_rect(drawings[j]) for j in mark.jamb_native_path_ids
            if type(j) is int and 0 <= j < len(drawings)
        ) if rect is not None
    )
    opening_paths = tuple(sorted({
        int(p) for p in mark.native_path_ids if type(p) is int and p not in hosts and p >= 0
    }))
    return WallEndReceipt(opening_id, scope, opening_paths, (hosts[0],), (hosts[1],), anchors)


def tag_marks_to_two_wall_sections(
    drawings: Sequence[Any],
    marks: Sequence[SourceInternalDoorMark],
    *,
    page_index: int,
    scope: tuple[str, ...],
) -> InternalDoorTwoWallReview:
    """Tag each inventory mark with its two traced wall sections through the owner contract, or say why not."""
    if not scope_ok(scope):
        return InternalDoorTwoWallReview(
            INTERNAL_DOOR_TWO_WALL_TAGS_ABSTAINED, (REASON_SCOPE_INVALID,), (), page_index, (),
        )
    entries: list[InternalDoorTwoWallEntry] = []
    for mark in marks:
        entry_id = stable_contract_id(
            "internal_door_two_wall",
            {
                "scope": list(scope), "page_index": page_index, "kind": mark.kind,
                "native_path_ids": sorted(int(p) for p in mark.native_path_ids),
                "host_native_path_ids": sorted(int(p) for p in mark.host_wall_native_path_ids),
            },
        )
        receipt = _receipt(drawings, mark, scope=scope, opening_id=entry_id)
        built = build_contract_inputs(drawings, receipt) if isinstance(receipt, WallEndReceipt) else receipt
        if isinstance(built, Blocked):
            tag: TwoWallOpeningTag = TwoWallOpeningTag(entry_id, TAG_UNRESOLVED, built.reason)
        else:
            contacts, sections = built
            tag = tag_opening_to_two_wall_sections(contacts, sections)
        entries.append(InternalDoorTwoWallEntry(
            entry_id=entry_id,
            symbol_kind=_symbol_kind(mark),
            mark_status=mark.status,
            mark_native_path_ids=tuple(int(p) for p in mark.native_path_ids),
            host_native_path_ids=tuple(int(p) for p in mark.host_wall_native_path_ids),
            tag_status=tag.status,
            reason=tag.reason,
            wall_section_ids=tuple(tag.wall_section_ids),
            contact_geometry=tag.contact_geometry,
            candidate_sections_first=tuple(tag.candidate_sections_first),
            candidate_sections_second=tuple(tag.candidate_sections_second),
        ))
    entries.sort(key=lambda e: (e.symbol_kind, e.mark_native_path_ids, e.entry_id))
    return InternalDoorTwoWallReview(
        INTERNAL_DOOR_TWO_WALL_TAGS_STATUS, (), scope, page_index, tuple(entries),
    )


def tag_internal_door_marks(
    drawings: Sequence[Any],
    source_words: Sequence[Any] = (),
    *,
    page_index: int,
    scope: tuple[str, ...],
) -> InternalDoorTwoWallReview:
    """Run the strict internal door inventory, then tag every mark it reports."""
    inventory = inspect_source_internal_door_completeness(
        drawings, source_words, page_index=page_index,
    )
    return tag_marks_to_two_wall_sections(
        drawings, inventory.marks, page_index=page_index, scope=scope,
    )
