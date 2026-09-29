"""
pb_physical_wall_body_evidence_shadow.py

SHADOW-ONLY AUTHORITY
=====================

This module introduces a non-consuming, non-authoritative,
fail-closed evidence compiler for *positive physical wall-body proof*.

It MUST NOT:
    - modify physical opening existence
    - modify wall equivalence
    - modify host binding
    - modify net-wall or gross-wall geometry
    - modify finish or QuantityEvidence
    - modify benchmark outputs
    - modify JobHub publication
    - modify any live authority

It MUST:
    - consume existing primitive provenance from Stage A
    - consume existing structural segment candidates
    - consume existing detect_wall_pairs() geometry
    - produce immutable PhysicalWallBodyEvidence records
    - remain fully SHADOW-ONLY until an explicit promotion step is designed

This module provides:
    - candidate wall-band generation (shadow)
    - positive wall-body evidence gates
    - negative evidence filters
    - topology continuity checks
    - thickness-family inference (shadow)
    - segmentation-support hooks (optional, non-authoritative)
    - stable PhysicalWallBodyEvidence records

No opening existence, host binding, or wall identity may depend on this module.

No consumer may treat this module as authoritative.

---------------------------------------------------------------------------
Record Definition
---------------------------------------------------------------------------
"""

from __future__ import annotations

from dataclasses import dataclass

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class PhysicalWallBodyEvidence:
    record_id: str

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str | None
    view_scope_id: str | None

    physical_wall_body_id: str | None

    candidate_face_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]

    wall_band_geometry: tuple[tuple[float, float], ...] | None

    thickness_family_id: str | None
    topology_evidence_ids: tuple[str, ...]
    negative_evidence_ids: tuple[str, ...]

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]


def compile_physical_wall_body_evidence_shadow(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    viewport_id: str | None,
    view_scope_id: str | None,
    structural_segments: list,
    wall_pair_candidates: list,
    segmentation_mask: object | None,
) -> list[PhysicalWallBodyEvidence]:
    """
    SHADOW-ONLY compiler.

    Input:
        - structural_segments: Stage A structural segment candidates
        - wall_pair_candidates: output of detect_wall_pairs()
        - segmentation_mask: optional raster wall mask (non-authoritative)

    Output:
        - list of PhysicalWallBodyEvidence records

    Behaviour:
        - fail-closed
        - no fallback heuristics
        - no nearest-line pairing
        - no confidence winner
        - no benchmark-specific rules
        - no opening-dependent evidence
        - no wall-identity modification
        - no consumption by live authorities

    This function MUST NOT raise if evidence is insufficient.
    It MUST return ABSTAINED records with appropriate reason_codes.
    """
    raise NotImplementedError("SHADOW-ONLY scaffold")
