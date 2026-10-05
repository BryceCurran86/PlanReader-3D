"""Source-owned structural definitions and explicit links to physical members.

Specification text describes a member type, never a physical instance. This
module leaves quantity publication to StructuralMemberProducer. A definition
can be attached only through a separately authenticated, member-specific link.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Sequence

from pb_migration_contracts import stable_contract_id
from pb_structural_member_authority import (
    StructuralMemberDefinition,
    StructuralMemberObservation,
    StructuralMemberSelector,
)

_SECTION = re.compile(
    r"\b(circular\s+hollow\s+sections?|rectangular\s+hollow\s+sections?|"
    r"square\s+hollow\s+sections?|universal\s+beams?|universal\s+columns?|"
    r"parallel\s+flange\s+channels?|welded\s+beams?|"
    r"stone\s+masonry|block\s+masonry|masonry|"
    r"CHS|RHS|SHS|UB|UC|PFC|WB)\b", re.I
)
_ROLE = re.compile(
    r"\b(pillars?|columns?|posts?|piers?|stanchions?|beams?|rafters?|"
    r"lintels?|purlins?|girts?|braces?|bracing)\b",
    re.I,
)
_SIZE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mm\s*(?:dia(?:meter)?\s*)?)?x\s*"
    r"\d+(?:\.\d+)?\s*mm\s*(?:thick)?\b", re.I
)
_ROLLED_SECTION = re.compile(
    r"\b(?:"
    r"\d{2,4}\s*(?:(?:UB|UC|WB)\s*\d+(?:\.\d+)?|PFC(?:\s*\d+(?:\.\d+)?)?)|"
    r"(?:C|Z)\d{2,4}(?:\d{2,3})?"
    r")\b",
    re.I,
)
_CANONICAL_SECTION = {
    "chs": "circular hollow section",
    "rhs": "rectangular hollow section",
    "shs": "square hollow section",
    "ub": "universal beam",
    "uc": "universal column",
    "pfc": "parallel flange channel",
    "wb": "welded beam",
}


@dataclass(frozen=True)
class SourceStructuralTextBlock:
    page_id: str
    view_id: str
    block_id: str
    reading_order: int
    bbox: tuple[float, float, float, float]
    text: str
    scope_id: str = ""


@dataclass(frozen=True)
class ParsedStructuralDefinition:
    selector: StructuralMemberSelector
    definition: StructuralMemberDefinition
    member_role: str
    scope_id: str
    source_block_ids: tuple[str, ...]


@dataclass(frozen=True)
class AuthenticatedStructuralDefinitionLink:
    """A source mark/leader explicitly connecting a definition and instance.

    The producer of this record must have independently authenticated the
    connection; a common count, size, building name, or nearby text is not a
    link. The full selector prevents reuse after any source lineage changes.
    """

    selector: StructuralMemberSelector
    definition_id: str
    observation_id: str
    source_primitive_id: str
    scope_id: str
    member_role: str
    source_evidence_ids: tuple[str, ...]
    link_kind: str


@dataclass(frozen=True)
class StructuralDefinitionBinding:
    observations: tuple[StructuralMemberObservation, ...]
    definitions: tuple[StructuralMemberDefinition, ...]
    bound_observation_ids: tuple[str, ...]
    unresolved_observation_ids: tuple[str, ...]


def _section_name(text: str) -> str | None:
    match = _SECTION.search(text)
    if match is not None:
        name = " ".join(match.group(0).lower().split())
        if name.endswith(" sections"):
            name = name[:-1]
        return _CANONICAL_SECTION.get(name, name)

    rolled = _ROLLED_SECTION.search(text)
    if rolled is None:
        return None
    token = re.sub(r"\s+", "", rolled.group(0)).upper()
    for abbreviation, name in (
        ("PFC", "parallel flange channel"),
        ("UB", "universal beam"),
        ("UC", "universal column"),
        ("WB", "welded beam"),
    ):
        if abbreviation in token:
            return name
    if token.startswith("C"):
        return "cold formed c section"
    if token.startswith("Z"):
        return "cold formed z section"
    return None


def _member_role(text: str) -> str | None:
    match = _ROLE.search(text)
    if match is None:
        return None
    name = match.group(0).lower()
    if name.startswith("stanchion"):
        return "stanchion"
    if name == "bracing":
        return "brace"
    return name.rstrip("s")


def _compatible_kind(selector_kind: str, role: str) -> bool:
    kind = selector_kind.strip().lower()
    return kind == "structural_support" or kind == role


def _adjacent(material: SourceStructuralTextBlock, member: SourceStructuralTextBlock) -> bool:
    if (
        material.page_id != member.page_id
        or material.view_id != member.view_id
        or material.scope_id != member.scope_id
        or member.reading_order != material.reading_order + 1
    ):
        return False
    ax0, _, ax1, ay1 = material.bbox
    bx0, by0, bx1, _ = member.bbox
    overlap = min(ax1, bx1) - max(ax0, bx0)
    return (
        overlap > 0
        and overlap >= 0.5 * min(ax1 - ax0, bx1 - bx0)
        and 0 <= by0 - ay1 <= 25
    )


def parse_structural_member_definitions(
    *,
    selector: StructuralMemberSelector,
    blocks: Sequence[SourceStructuralTextBlock],
) -> tuple[ParsedStructuralDefinition, ...]:
    """Parse a same-block clause or consecutive, spatially adjacent fragments.

    BOQ quantities, rates, and totals are deliberately absent from the output.
    The selector and source block IDs make definitions stable within a source
    revision while keeping another revision/snapshot isolated.
    """
    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")
    ordered = sorted(
        blocks,
        key=lambda b: (b.page_id, b.view_id, b.scope_id, b.reading_order, b.block_id),
    )
    parsed: list[ParsedStructuralDefinition] = []
    for index, block in enumerate(ordered):
        section = _section_name(block.text)
        if section is None or not block.text.strip() or not block.block_id.strip():
            continue
        member = block
        role = _member_role(block.text)
        if role is None and index + 1 < len(ordered):
            following = ordered[index + 1]
            if _adjacent(block, following) and _section_name(following.text) is None:
                role = _member_role(following.text)
                member = following
        if role is None or not _compatible_kind(selector.member_kind, role):
            continue
        combined_text = f"{block.text} {member.text}"
        size = _SIZE.search(combined_text)
        rolled = _ROLLED_SECTION.search(combined_text)
        size_text = " ".join(size.group(0).lower().split()) if size else ""
        rolled_text = (
            re.sub(r"\s+", "", rolled.group(0)).lower()
            if rolled is not None
            else ""
        )
        section_spec = "; ".join(
            part for part in (section, rolled_text, size_text, role) if part
        )
        block_ids = tuple(dict.fromkeys((block.block_id, member.block_id)))
        source_ids = tuple(sorted({
            f"sha256:{selector.source_sha256}:page:{block.page_id}:block:{source_id}"
            for source_id in block_ids
        }))
        definition_id = stable_contract_id(
            "structural_definition_v1",
            {
                "selector": selector.__dict__,
                "page_id": block.page_id,
                "view_id": block.view_id,
                "scope_id": block.scope_id,
                "source_block_ids": block_ids,
                "section_spec": section_spec,
            },
            digest_chars=32,
        )
        parsed.append(ParsedStructuralDefinition(
            selector=selector,
            definition=StructuralMemberDefinition(
                definition_id=definition_id,
                member_kind=selector.member_kind,
                section_spec=section_spec,
                source_evidence_ids=source_ids,
                page_id=block.page_id,
                view_id=block.view_id,
            ),
            member_role=role,
            scope_id=block.scope_id,
            source_block_ids=block_ids,
        ))
    return tuple(sorted(parsed, key=lambda row: row.definition.definition_id))


def bind_structural_member_definitions(
    *,
    selector: StructuralMemberSelector,
    definitions: Sequence[ParsedStructuralDefinition],
    observations: Sequence[StructuralMemberObservation],
    links: Sequence[AuthenticatedStructuralDefinitionLink],
) -> StructuralDefinitionBinding:
    """Attach uniquely proven links to uniquely identified input observations.

    Duplicate definition or observation IDs are invalid; never add, remove,
    or merge members to repair an ambiguous input identity.
    """
    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")
    current = tuple(row for row in definitions if row.selector == selector)
    by_id = {row.definition.definition_id: row for row in current}
    if len(by_id) != len(current):
        raise ValueError("duplicate structural definition id")
    by_observation_id = {row.observation_id: row for row in observations}
    if len(by_observation_id) != len(observations):
        raise ValueError("duplicate structural observation id")
    accepted: dict[str, set[str]] = {}
    for link in links:
        parsed = by_id.get(link.definition_id)
        observation = by_observation_id.get(link.observation_id)
        if (
            parsed is None or observation is None or link.selector != selector
            or not parsed.scope_id or parsed.scope_id != link.scope_id
            or parsed.member_role != link.member_role
            or observation.member_kind.strip().lower() != selector.member_kind.strip().lower()
            or link.source_primitive_id not in observation.source_primitive_ids
            or link.link_kind not in {"explicit_member_mark", "source_leader"}
            or not link.source_evidence_ids
        ):
            continue
        accepted.setdefault(observation.observation_id, set()).add(link.definition_id)

    bound = []
    unresolved = []
    output = []
    for observation in observations:
        candidates = accepted.get(observation.observation_id, set())
        if len(candidates) == 1 and observation.definition_id in (None, *candidates):
            output.append(replace(observation, definition_id=next(iter(candidates))))
            bound.append(observation.observation_id)
        else:
            # A conflicting old claim or multiple candidate definitions must
            # not gain a type by first-match ordering. Physical quantity can
            # still be resolved independently without any attached definition.
            output.append(replace(observation, definition_id=None))
            unresolved.append(observation.observation_id)
    return StructuralDefinitionBinding(
        observations=tuple(output),
        definitions=tuple(sorted((row.definition for row in current), key=lambda d: d.definition_id)),
        bound_observation_ids=tuple(sorted(bound)),
        unresolved_observation_ids=tuple(sorted(unresolved)),
    )
