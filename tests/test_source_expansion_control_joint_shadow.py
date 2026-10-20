import math
import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_expansion_control_joint_shadow import (
    SourceExpansionControlJointShadowAuthority,
    ExpansionControlJointReceipt,
    JointKind,
    SCHEMA_VERSION,
)


def test_masonry_control_joint():
    authority = SourceExpansionControlJointShadowAuthority()

    j = authority.compute_movement_joint(
        joint_id="CJ_01",
        host_element_id="WALL_EXT_01",
        joint_kind=JointKind.CONTROL_JOINT,
        gap_width_pt=0.28,
        joint_length_pt=80.0,
    )

    assert j.joint_id == "CJ_01"
    assert j.joint_kind == JointKind.CONTROL_JOINT
    assert j.prohibits_wall_healing_stitching is True
    assert j.is_doorway_opening is False
    assert j.gap_width_pt == 0.28
    assert j.joint_length_pt == 80.0
    # Depth = half-gap only; no 6 mm minimum. vol = 80 * 0.28 * 0.14 = 3.136
    assert math.isclose(j.sealant_volume_pt3, 3.136, abs_tol=1e-3)


def test_structural_expansion_joint():
    authority = SourceExpansionControlJointShadowAuthority()

    j = authority.compute_movement_joint(
        joint_id="EJ_01",
        host_element_id="SLAB_01",
        joint_kind=JointKind.EXPANSION_JOINT,
        gap_width_pt=2.0,
        joint_length_pt=100.0,
    )

    assert j.joint_kind == JointKind.EXPANSION_JOINT
    # Depth = 2.0 / 2 = 1.0 -> vol = 100 * 2.0 * 1.0 = 200.0
    assert j.sealant_volume_pt3 == 200.0


def test_omitted_joint_geometry_does_not_invent_typical_gap():
    authority = SourceExpansionControlJointShadowAuthority()

    j = authority.compute_movement_joint(
        joint_id="J_UNKNOWN",
        host_element_id="W_UNKNOWN",
    )

    assert j.gap_width_pt == 0.0
    assert j.joint_length_pt == 0.0
    assert j.sealant_volume_pt3 == 0.0
    assert j.backing_rod_spec == ""


def test_compile_joint_receipt():
    authority = SourceExpansionControlJointShadowAuthority()

    j1 = authority.compute_movement_joint(
        joint_id="J1",
        host_element_id="W1",
        gap_width_pt=1.0,
        joint_length_pt=50.0,
    )

    receipt = authority.compile_joint_receipt(
        document_id="DOC_JOINTS",
        revision_id="REV_1",
        source_sha256="11335577" * 8,
        joints=[j1],
    )

    assert isinstance(receipt, ExpansionControlJointReceipt)
    assert receipt.total_joints_count == 1
    assert receipt.total_joint_length_pt == 50.0
    assert receipt.status == EvidenceResolutionStatus.CANDIDATE
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_JOINTS"
    assert len(d["joints"]) == 1


def test_empty_receipt_abstained():
    authority = SourceExpansionControlJointShadowAuthority()

    receipt = authority.compile_joint_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        joints=[],
    )

    assert receipt.total_joints_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        ExpansionControlJointReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_joints_count=0,
            total_joint_length_pt=0.0,
            total_sealant_volume_pt3=0.0,
            joints=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
