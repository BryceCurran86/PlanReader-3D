"""Typed source-layer evidence for physical wall candidates (SHADOW ONLY).

The wall authority already records, for every candidate, which source layers its primitives sit in (``pb_physical_wall_source_metadata_shadow``),
and documents that this is descriptive provenance and neither support nor opposition. This module is the first typed reading of that
provenance. It changes no verdict, filters nothing, is imported by no live path, and grants no authority: it only says, per candidate, what the
source itself attests about the candidate's layer, and what that would imply for a pair.

Atoms (from the producer-owned metadata table, never from geometry, a project, a file name or an expected value):

* ``explicit_wall_layer``  - every source primitive sits in ONE agreed layer whose name says wall (the repository's literal, case-insensitive
  substring convention), unless the name also says finish, tile, lining, cladding or paint (a wall FINISH is not a wall).
* ``other_single_layer``   - every source primitive sits in ONE agreed layer that is not wall-named.
* ``mixed_layers``         - the primitives span layers.
* ``no_layer``             - layer provenance is missing, partial, or the lineage is not fully matched. Never a guess.

Opposition is page-relative and conservative: ``other_single_layer`` becomes opposing evidence ONLY on a page that itself names an explicit wall
layer. A page with no wall-named layer (a CAD export without layers, a scan) produces no opposition, so those documents behave exactly as today.
Mixed and missing provenance is never opposed. Nothing is deleted: an opposed candidate stays in every record.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from pb_physical_wall_source_metadata_shadow import (
    SOURCE_METADATA_DESCRIBED,
    PhysicalWallSourceMetadataScopeTable,
)

WALL_LAYER_EVIDENCE_SCHEMA_VERSION = "1.0.0"

ATOM_EXPLICIT_WALL_LAYER = "explicit_wall_layer"
ATOM_OTHER_SINGLE_LAYER = "other_single_layer"
ATOM_MIXED_LAYERS = "mixed_layers"
ATOM_NO_LAYER = "no_layer"

RELATION_SAME_WALL_LAYER = "same_explicit_wall_layer"
RELATION_DIFFERENT_WALL_LAYERS = "different_explicit_wall_layers"
RELATION_WALL_VERSUS_OTHER_LAYER = "wall_versus_other_layer"
RELATION_NOT_ATTESTED = "not_attested"

_AGREED = "agreed"
_FINISH_TOKENS = frozenset({"finish", "finishes", "tile", "tiles", "tiling", "lining", "cladding", "paint"})


def is_explicit_wall_layer_name(name: str) -> bool:
    lowered = name.lower()
    if "wall" not in lowered:
        return False
    return not (set(re.findall(r"[a-z0-9]+", lowered)) & _FINISH_TOKENS)


@dataclass(frozen=True)
class WallLayerAtom:
    wall_candidate_id: str
    kind: str
    layer_value: str = ""


@dataclass(frozen=True)
class WallLayerEvidence:
    atoms: Mapping[str, WallLayerAtom]
    explicit_wall_layer_values: tuple[str, ...]
    page_uses_explicit_wall_layers: bool
    opposing_candidate_ids: tuple[str, ...]
    unavailable_reason: Optional[str] = None
    shadow_only: bool = True
    live_effect: bool = False
    grants_authority: bool = False
    schema_version: str = WALL_LAYER_EVIDENCE_SCHEMA_VERSION

    def counts(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for atom in self.atoms.values():
            result[atom.kind] = result.get(atom.kind, 0) + 1
        return dict(sorted(result.items()))


def _atom(descriptor) -> WallLayerAtom:
    wall_id = str(descriptor.wall_candidate_id)
    layers = tuple(str(value) for value in descriptor.layer_values)
    if descriptor.layer_status == "conflict" or len(layers) > 1:
        return WallLayerAtom(wall_id, ATOM_MIXED_LAYERS)
    complete = (
        descriptor.layer_status == _AGREED
        and len(layers) == 1
        and layers[0] != ""
        and int(descriptor.source_record_count) > 0
        and int(descriptor.layer_present_source_record_count) == int(descriptor.source_record_count)
        and not tuple(descriptor.missing_source_primitive_ids)
    )
    if not complete:
        return WallLayerAtom(wall_id, ATOM_NO_LAYER)
    kind = ATOM_EXPLICIT_WALL_LAYER if is_explicit_wall_layer_name(layers[0]) else ATOM_OTHER_SINGLE_LAYER
    return WallLayerAtom(wall_id, kind, layers[0])


def build_wall_layer_evidence(table: PhysicalWallSourceMetadataScopeTable) -> WallLayerEvidence:
    """Type the layer provenance of every candidate in one exact wall authority scope (read-only)."""
    if type(table) is not PhysicalWallSourceMetadataScopeTable:
        raise TypeError("table must be PhysicalWallSourceMetadataScopeTable")
    if table.status != SOURCE_METADATA_DESCRIBED:
        return WallLayerEvidence(
            atoms=MappingProxyType({}), explicit_wall_layer_values=(), page_uses_explicit_wall_layers=False,
            opposing_candidate_ids=(), unavailable_reason=str(table.reason_code or "source_metadata_not_described"))
    atoms: dict[str, WallLayerAtom] = {}
    for descriptor in table.descriptors:
        atom = _atom(descriptor)
        if atom.wall_candidate_id in atoms:
            raise ValueError(f"duplicate wall candidate {atom.wall_candidate_id}")
        atoms[atom.wall_candidate_id] = atom
    ordered = {wall_id: atoms[wall_id] for wall_id in sorted(atoms)}
    wall_values = tuple(sorted({a.layer_value for a in ordered.values() if a.kind == ATOM_EXPLICIT_WALL_LAYER}))
    uses_wall_layers = bool(wall_values)
    opposing = tuple(
        wall_id for wall_id, atom in ordered.items()
        if uses_wall_layers and atom.kind == ATOM_OTHER_SINGLE_LAYER
    )
    return WallLayerEvidence(
        atoms=MappingProxyType(ordered), explicit_wall_layer_values=wall_values,
        page_uses_explicit_wall_layers=uses_wall_layers, opposing_candidate_ids=opposing)


def pair_layer_relation(evidence: WallLayerEvidence, left_id: str, right_id: str) -> str:
    """What the source layers say about a pair. Symmetric. Descriptive: it decides nothing."""
    if type(evidence) is not WallLayerEvidence:
        raise TypeError("evidence must be WallLayerEvidence")
    left, right = evidence.atoms.get(str(left_id)), evidence.atoms.get(str(right_id))
    if left is None or right is None or left.wall_candidate_id == right.wall_candidate_id:
        return RELATION_NOT_ATTESTED
    opposing = set(evidence.opposing_candidate_ids)
    if left.kind == ATOM_EXPLICIT_WALL_LAYER and right.kind == ATOM_EXPLICIT_WALL_LAYER:
        return RELATION_SAME_WALL_LAYER if left.layer_value == right.layer_value else RELATION_DIFFERENT_WALL_LAYERS
    walls = [a for a in (left, right) if a.kind == ATOM_EXPLICIT_WALL_LAYER]
    others = [a for a in (left, right) if a.wall_candidate_id in opposing]
    if len(walls) == 1 and len(others) == 1:
        return RELATION_WALL_VERSUS_OTHER_LAYER
    return RELATION_NOT_ATTESTED


__all__ = [
    "ATOM_EXPLICIT_WALL_LAYER", "ATOM_MIXED_LAYERS", "ATOM_NO_LAYER", "ATOM_OTHER_SINGLE_LAYER",
    "RELATION_DIFFERENT_WALL_LAYERS", "RELATION_NOT_ATTESTED", "RELATION_SAME_WALL_LAYER", "RELATION_WALL_VERSUS_OTHER_LAYER",
    "WALL_LAYER_EVIDENCE_SCHEMA_VERSION", "WallLayerAtom", "WallLayerEvidence",
    "build_wall_layer_evidence", "is_explicit_wall_layer_name", "pair_layer_relation",
]
