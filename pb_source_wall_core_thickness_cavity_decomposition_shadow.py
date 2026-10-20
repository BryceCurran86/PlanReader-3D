"""Producer-Owned Source Wall Core Thickness & Multi-Leaf Cavity Wall Decomposition Shadow Authority.

Workstream A Items 2, 4 & 5:
Decomposes multi-leaf composite wall assemblies (cavity brick/block, brick veneer,
double stud) into inner structural loadbearing leaf, air/insulation cavity zone,
and outer veneer/cladding leaf. Determines exact structural core thickness and
prevents cavity gaps from being falsely classified as rooms.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_CAVITY_SEAL = object()


class WallLeafRole(str, Enum):
    STRUCTURAL_INNER_CORE = "STRUCTURAL_INNER_CORE"
    INSULATED_OR_AIR_CAVITY = "INSULATED_OR_AIR_CAVITY"
    ARCHITECTURAL_OUTER_VENEER = "ARCHITECTURAL_OUTER_VENEER"


class WallAssemblyType(str, Enum):
    SOLID_MONOLITHIC = "SOLID_MONOLITHIC"
    CAVITY_BRICK = "CAVITY_BRICK"
    BRICK_VENEER = "BRICK_VENEER"
    DOUBLE_STUD_ACOUSTIC = "DOUBLE_STUD_ACOUSTIC"


@dataclass(frozen=True)
class WallLeafRecord:
    leaf_id: str
    role: WallLeafRole
    thickness_pt: float
    is_loadbearing: bool
    material: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "leaf_id": self.leaf_id,
            "role": self.role.value,
            "thickness_pt": self.thickness_pt,
            "is_loadbearing": self.is_loadbearing,
            "material": self.material,
        }


@dataclass(frozen=True)
class CompositeWallAssemblyRecord:
    assembly_id: str
    assembly_type: WallAssemblyType
    overall_thickness_pt: float
    structural_core_thickness_pt: float
    cavity_width_pt: float
    leaves: Tuple[WallLeafRecord, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "assembly_id": self.assembly_id,
            "assembly_type": self.assembly_type.value,
            "overall_thickness_pt": self.overall_thickness_pt,
            "structural_core_thickness_pt": self.structural_core_thickness_pt,
            "cavity_width_pt": self.cavity_width_pt,
            "leaves": [l.to_dict() for l in self.leaves],
        }


@dataclass(frozen=True)
class CompositeWallDecompositionReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_assemblies_count: int
    cavity_assemblies_count: int
    assemblies: Tuple[CompositeWallAssemblyRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _CAVITY_SEAL:
            raise TypeError("CompositeWallDecompositionReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_assemblies_count": self.total_assemblies_count,
            "cavity_assemblies_count": self.cavity_assemblies_count,
            "assemblies": [a.to_dict() for a in self.assemblies],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceWallCoreCavityDecompositionShadowAuthority:
    """Decomposes multi-leaf composite walls and measures core structural thickness."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def decompose_cavity_brick(
        self,
        *,
        inner_leaf_thickness_pt: float = 0.0,
        cavity_width_pt: float = 0.0,
        outer_leaf_thickness_pt: float = 0.0,
        inner_material: str = "COMMON_BRICK",
        outer_material: str = "FACE_BRICK",
        assembly_name: str = "CAVITY_BRICK_DEFAULT",
    ) -> CompositeWallAssemblyRecord:
        inner_id = stable_contract_id("LEAF_INNER", (assembly_name, inner_leaf_thickness_pt, inner_material))
        inner_leaf = WallLeafRecord(
            leaf_id=inner_id,
            role=WallLeafRole.STRUCTURAL_INNER_CORE,
            thickness_pt=inner_leaf_thickness_pt,
            is_loadbearing=True,
            material=inner_material,
        )

        cavity_id = stable_contract_id("LEAF_CAV", (assembly_name, cavity_width_pt))
        cavity_leaf = WallLeafRecord(
            leaf_id=cavity_id,
            role=WallLeafRole.INSULATED_OR_AIR_CAVITY,
            thickness_pt=cavity_width_pt,
            is_loadbearing=False,
            material="AIR_OR_INSULATION",
        )

        outer_id = stable_contract_id("LEAF_OUTER", (assembly_name, outer_leaf_thickness_pt, outer_material))
        outer_leaf = WallLeafRecord(
            leaf_id=outer_id,
            role=WallLeafRole.ARCHITECTURAL_OUTER_VENEER,
            thickness_pt=outer_leaf_thickness_pt,
            is_loadbearing=False,
            material=outer_material,
        )

        overall = inner_leaf_thickness_pt + cavity_width_pt + outer_leaf_thickness_pt
        assy_id = stable_contract_id("ASSY_CAVITY_BRICK", (assembly_name, overall))

        return CompositeWallAssemblyRecord(
            assembly_id=assy_id,
            assembly_type=WallAssemblyType.CAVITY_BRICK,
            overall_thickness_pt=overall,
            structural_core_thickness_pt=inner_leaf_thickness_pt,
            cavity_width_pt=cavity_width_pt,
            leaves=(inner_leaf, cavity_leaf, outer_leaf),
        )

    def decompose_brick_veneer(
        self,
        *,
        stud_core_thickness_pt: float = 0.0,
        cavity_width_pt: float = 0.0,
        brick_veneer_thickness_pt: float = 0.0,
        stud_material: str = "TIMBER_OR_LIGHT_GAUGE_STEEL_STUD",
        veneer_material: str = "FACE_BRICK",
        assembly_name: str = "BRICK_VENEER_DEFAULT",
    ) -> CompositeWallAssemblyRecord:
        core_id = stable_contract_id("LEAF_STUD", (assembly_name, stud_core_thickness_pt, stud_material))
        core_leaf = WallLeafRecord(
            leaf_id=core_id,
            role=WallLeafRole.STRUCTURAL_INNER_CORE,
            thickness_pt=stud_core_thickness_pt,
            is_loadbearing=True,
            material=stud_material,
        )

        cavity_id = stable_contract_id("LEAF_CAV_VENEER", (assembly_name, cavity_width_pt))
        cavity_leaf = WallLeafRecord(
            leaf_id=cavity_id,
            role=WallLeafRole.INSULATED_OR_AIR_CAVITY,
            thickness_pt=cavity_width_pt,
            is_loadbearing=False,
            material="AIR_CAVITY_WITH_WALL_TIES",
        )

        veneer_id = stable_contract_id("LEAF_VENEER", (assembly_name, brick_veneer_thickness_pt, veneer_material))
        veneer_leaf = WallLeafRecord(
            leaf_id=veneer_id,
            role=WallLeafRole.ARCHITECTURAL_OUTER_VENEER,
            thickness_pt=brick_veneer_thickness_pt,
            is_loadbearing=False,
            material=veneer_material,
        )

        overall = stud_core_thickness_pt + cavity_width_pt + brick_veneer_thickness_pt
        assy_id = stable_contract_id("ASSY_BRICK_VENEER", (assembly_name, overall))

        return CompositeWallAssemblyRecord(
            assembly_id=assy_id,
            assembly_type=WallAssemblyType.BRICK_VENEER,
            overall_thickness_pt=overall,
            structural_core_thickness_pt=stud_core_thickness_pt,
            cavity_width_pt=cavity_width_pt,
            leaves=(core_leaf, cavity_leaf, veneer_leaf),
        )

    def decompose_solid_monolithic(
        self,
        *,
        thickness_pt: float,
        material: str = "PRECAST_CONCRETE",
        assembly_name: str = "MONOLITHIC_DEFAULT",
    ) -> CompositeWallAssemblyRecord:
        leaf_id = stable_contract_id("LEAF_MONO", (assembly_name, thickness_pt, material))
        leaf = WallLeafRecord(
            leaf_id=leaf_id,
            role=WallLeafRole.STRUCTURAL_INNER_CORE,
            thickness_pt=thickness_pt,
            is_loadbearing=True,
            material=material,
        )

        assy_id = stable_contract_id("ASSY_MONOLITHIC", (assembly_name, thickness_pt))

        return CompositeWallAssemblyRecord(
            assembly_id=assy_id,
            assembly_type=WallAssemblyType.SOLID_MONOLITHIC,
            overall_thickness_pt=thickness_pt,
            structural_core_thickness_pt=thickness_pt,
            cavity_width_pt=0.0,
            leaves=(leaf,),
        )

    def compile_decomposition_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        assemblies: Sequence[CompositeWallAssemblyRecord],
    ) -> CompositeWallDecompositionReceipt:
        assy_tuple = tuple(assemblies)
        total = len(assy_tuple)
        cavity_count = sum(1 for a in assy_tuple if a.cavity_width_pt > 0.0)

        receipt_id = stable_contract_id(
            "WALL_DECOMPOSITION_RECEIPT",
            (document_id, revision_id, source_sha256, total, cavity_count),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return CompositeWallDecompositionReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_assemblies_count=total,
            cavity_assemblies_count=cavity_count,
            assemblies=assy_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_CAVITY_SEAL,
        )
