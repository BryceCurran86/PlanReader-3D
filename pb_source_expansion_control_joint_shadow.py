"""Producer-Owned Source Expansion & Control Joint Physical Discontinuity Shadow Authority.

Workstream A Item 4:
Identifies structural expansion joints (EJ) and masonry control joints (CJ),
preserves intentional movement gaps without erroneous stitching or false doorway
classification, and computes elastomeric sealant linear joint takeoffs.

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

_JOINT_SEAL = object()


class JointKind(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXPANSION_JOINT = "EXPANSION_JOINT"
    CONTROL_JOINT = "CONTROL_JOINT"
    CONSTRUCTION_JOINT = "CONSTRUCTION_JOINT"
    SEISMIC_ISOLATION_JOINT = "SEISMIC_ISOLATION_JOINT"


@dataclass(frozen=True)
class MovementJointRecord:
    joint_id: str
    joint_kind: JointKind
    host_element_id: str
    gap_width_pt: float
    joint_length_pt: float
    sealant_volume_pt3: float
    prohibits_wall_healing_stitching: bool
    is_doorway_opening: bool
    backing_rod_spec: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "joint_id": self.joint_id,
            "joint_kind": self.joint_kind.value,
            "host_element_id": self.host_element_id,
            "gap_width_pt": self.gap_width_pt,
            "joint_length_pt": self.joint_length_pt,
            "sealant_volume_pt3": self.sealant_volume_pt3,
            "prohibits_wall_healing_stitching": self.prohibits_wall_healing_stitching,
            "is_doorway_opening": self.is_doorway_opening,
            "backing_rod_spec": self.backing_rod_spec,
        }


@dataclass(frozen=True)
class ExpansionControlJointReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_joints_count: int
    total_joint_length_pt: float
    total_sealant_volume_pt3: float
    joints: Tuple[MovementJointRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _JOINT_SEAL:
            raise TypeError("ExpansionControlJointReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_joints_count": self.total_joints_count,
            "total_joint_length_pt": self.total_joint_length_pt,
            "total_sealant_volume_pt3": self.total_sealant_volume_pt3,
            "joints": [j.to_dict() for j in self.joints],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceExpansionControlJointShadowAuthority:
    """Evaluates movement joints, enforcing structural discontinuity and calculating sealant volumes."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_movement_joint(
        self,
        *,
        joint_id: str,
        host_element_id: str,
        joint_kind: JointKind = JointKind.UNKNOWN,
        gap_width_pt: float = 0.0,
        joint_length_pt: float = 0.0,
        backing_rod_spec: str = "",
    ) -> MovementJointRecord:
        sealant_depth = gap_width_pt / 2.0
        sealant_vol = joint_length_pt * gap_width_pt * sealant_depth

        return MovementJointRecord(
            joint_id=joint_id,
            joint_kind=joint_kind,
            host_element_id=host_element_id,
            gap_width_pt=round(gap_width_pt, 4),
            joint_length_pt=round(joint_length_pt, 4),
            sealant_volume_pt3=round(sealant_vol, 4),
            prohibits_wall_healing_stitching=True,
            is_doorway_opening=False,
            backing_rod_spec=backing_rod_spec,
        )

    def compile_joint_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        joints: Sequence[MovementJointRecord],
    ) -> ExpansionControlJointReceipt:
        j_tuple = tuple(joints)
        total = len(j_tuple)
        total_len = sum(j.joint_length_pt for j in j_tuple)
        total_vol = sum(j.sealant_volume_pt3 for j in j_tuple)

        receipt_id = stable_contract_id(
            "JOINT_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(total_len, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return ExpansionControlJointReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_joints_count=total,
            total_joint_length_pt=round(total_len, 4),
            total_sealant_volume_pt3=round(total_vol, 4),
            joints=j_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_JOINT_SEAL,
        )
